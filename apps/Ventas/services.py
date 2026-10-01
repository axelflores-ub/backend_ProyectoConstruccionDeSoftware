# Lógica de negocio del módulo Ventas (fuera de views y serializers).
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.SCM.models import MovimientoInventario, Producto

from .models import (
    Anulacion,
    DetalleNotaCredito,
    EstadoOrdenVenta,
    NotaCredito,
    OrdenVenta,
    OrdenVentaDetalle,
)


class StockInsuficienteError(Exception):
    """Se intentó vender más unidades de las disponibles de un producto."""

    def __init__(self, producto):
        self.producto = producto
        super().__init__(
            f"Stock insuficiente para '{producto.nombre}' (disponible: {producto.stock_actual})."
        )


class OperacionInvalidaError(Exception):
    """La devolución o anulación no cumple las reglas de negocio."""


def _registrar_movimiento(*, producto, usuario, tipo, cantidad, observacion):
    """Deja constancia en el historial de inventario de SCM (cantidad siempre positiva;
    el sentido lo da el tipo: SALIDA descuenta, DEVOLUCION repone)."""
    if usuario is None:
        raise ValueError("Se necesita un usuario autenticado para registrar el movimiento.")
    return MovimientoInventario.objects.create(
        producto=producto,
        usuario=usuario,
        tipo=tipo,
        cantidad=cantidad,
        observacion=observacion,
    )


def acumular_cantidades(items):
    """Suma las cantidades por producto (un producto puede repetirse en varios ítems)."""
    acumulado = {}
    for item in items:
        producto_id = item["producto"].id
        acumulado[producto_id] = acumulado.get(producto_id, 0) + item["cantidad"]
    return acumulado


def _vendido_por_producto(orden_venta):
    filas = (
        OrdenVentaDetalle.objects.filter(orden_venta=orden_venta)
        .values("producto_id")
        .annotate(total=Sum("cantidad"))
    )
    return {f["producto_id"]: f["total"] for f in filas}


def _devuelto_por_producto(orden_venta):
    """Unidades devueltas en todas las notas de crédito de la orden (cualquier destino)."""
    filas = (
        DetalleNotaCredito.objects.filter(nota_credito__orden_venta=orden_venta)
        .values("producto_id")
        .annotate(total=Sum("cantidad_devuelta"))
    )
    return {f["producto_id"]: f["total"] for f in filas}


def _orden_bloqueada(orden_venta):
    """Bloquea la orden hasta el fin de la transacción: serializa notas de crédito
    y anulaciones concurrentes sobre la misma orden."""
    return OrdenVenta.objects.select_for_update().get(pk=orden_venta.pk)


def _validar_orden_no_anulada(orden_venta):
    if Anulacion.objects.filter(orden_venta=orden_venta).exists():
        raise OperacionInvalidaError("La orden ya fue anulada.")


def _validar_devoluciones(orden_venta, detalles):
    """La cantidad a devolver no puede superar lo vendido menos lo ya devuelto."""
    vendido = _vendido_por_producto(orden_venta)
    devuelto = _devuelto_por_producto(orden_venta)
    nombres = {item["producto"].id: item["producto"].nombre for item in detalles}
    pedido = {}
    for item in detalles:
        pid = item["producto"].id
        pedido[pid] = pedido.get(pid, 0) + item["cantidad_devuelta"]

    for pid, cantidad in pedido.items():
        if pid not in vendido:
            raise OperacionInvalidaError(f"El producto '{nombres[pid]}' no pertenece a la orden.")
        ya_devuelto = devuelto.get(pid, 0)
        disponible = vendido[pid] - ya_devuelto
        if cantidad > disponible:
            raise OperacionInvalidaError(
                f"No se pueden devolver {cantidad} unidades de '{nombres[pid]}': "
                f"vendidas {vendido[pid]}, ya devueltas {ya_devuelto}, "
                f"disponibles para devolver {disponible}."
            )


def _reponer_stock(*, producto, cantidad, usuario, observacion):
    """Suma stock y deja el movimiento DEVOLUCION. El producto debe venir ya bloqueado
    (select_for_update)."""
    producto.stock_actual += cantidad
    producto.save(update_fields=["stock_actual"])
    return _registrar_movimiento(
        producto=producto,
        usuario=usuario,
        tipo=MovimientoInventario.Tipo.DEVOLUCION,
        cantidad=cantidad,
        observacion=observacion,
    )


@transaction.atomic
def registrar_orden_venta(*, datos, detalles, usuario=None):
    """Crea la orden con su detalle, calcula el total, descuenta stock y registra un
    movimiento de inventario SALIDA por producto.

    select_for_update bloquea las filas de producto hasta el fin de la transacción,
    evitando que dos órdenes concurrentes descuenten el mismo stock.
    """
    cantidad_por_producto = acumular_cantidades(detalles)

    productos = {
        p.id: p
        for p in Producto.objects.select_for_update().filter(id__in=cantidad_por_producto.keys())
    }
    for producto_id, cantidad_total in cantidad_por_producto.items():
        if productos[producto_id].stock_actual < cantidad_total:
            raise StockInsuficienteError(productos[producto_id])

    # Toda orden nueva arranca en el estado "Pendiente" (se crea si no existe).
    estado_inicial, _ = EstadoOrdenVenta.objects.get_or_create(nombre="Pendiente")
    orden = OrdenVenta.objects.create(usuario=usuario, estado=estado_inicial, **datos)

    total = Decimal("0")
    for item in detalles:
        producto = productos[item["producto"].id]
        cantidad = item["cantidad"]
        descuento = item.get("descuento") or Decimal("0")
        OrdenVentaDetalle.objects.create(
            orden_venta=orden,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=producto.precio,
            descuento=descuento,
        )
        total += (producto.precio * cantidad) - descuento

    for producto_id, cantidad_total in cantidad_por_producto.items():
        producto = productos[producto_id]
        producto.stock_actual -= cantidad_total
        producto.save(update_fields=["stock_actual"])
        _registrar_movimiento(
            producto=producto,
            usuario=usuario,
            tipo=MovimientoInventario.Tipo.SALIDA,
            cantidad=cantidad_total,
            observacion=f"Venta - orden #{orden.pk}",
        )

    orden.total = total
    orden.save(update_fields=["total"])
    return orden


@transaction.atomic
def anular_orden_venta(*, orden_venta, motivo, detalle=None, usuario):
    """Registra la anulación, repone el stock pendiente de devolver (vendido menos lo ya
    devuelto en notas de crédito) con movimientos DEVOLUCION y pasa la orden a 'Anulada'."""
    orden_venta = _orden_bloqueada(orden_venta)
    _validar_orden_no_anulada(orden_venta)

    vendido = _vendido_por_producto(orden_venta)
    devuelto = _devuelto_por_producto(orden_venta)
    a_reponer = {}
    for pid, cantidad in vendido.items():
        pendiente = cantidad - devuelto.get(pid, 0)
        if pendiente > 0:
            a_reponer[pid] = pendiente

    # order_by("id") para bloquear siempre en el mismo orden y evitar deadlocks
    productos = Producto.objects.select_for_update().filter(id__in=a_reponer).order_by("id")
    for producto in productos:
        _reponer_stock(
            producto=producto,
            cantidad=a_reponer[producto.id],
            usuario=usuario,
            observacion=f"Anulación - orden #{orden_venta.pk}",
        )

    anulacion = Anulacion.objects.create(orden_venta=orden_venta, motivo=motivo, detalle=detalle)
    estado_anulada, _ = EstadoOrdenVenta.objects.get_or_create(nombre="Anulada")
    orden_venta.estado = estado_anulada
    orden_venta.save(update_fields=["estado"])
    return anulacion


@transaction.atomic
def registrar_nota_credito(*, orden_venta, monto, saldo_a_favor, detalles, usuario):
    """Valida que no se devuelva más de lo vendido (contando devoluciones previas), crea la
    nota de crédito, repone stock de lo devuelto a 'stock disponible' (movimiento
    DEVOLUCION) y mueve la orden a 'Devolución parcial'."""
    orden_venta = _orden_bloqueada(orden_venta)
    _validar_orden_no_anulada(orden_venta)
    _validar_devoluciones(orden_venta, detalles)

    nota_credito = NotaCredito.objects.create(
        orden_venta=orden_venta, monto=monto, saldo_a_favor=saldo_a_favor
    )

    for item in detalles:
        DetalleNotaCredito.objects.create(nota_credito=nota_credito, **item)
        if item["destino"] == DetalleNotaCredito.Destino.STOCK_DISPONIBLE:
            producto = Producto.objects.select_for_update().get(pk=item["producto"].id)
            _reponer_stock(
                producto=producto,
                cantidad=item["cantidad_devuelta"],
                usuario=usuario,
                observacion=f"Devolución - nota de crédito #{nota_credito.pk}",
            )

    estado_devolucion, _ = EstadoOrdenVenta.objects.get_or_create(nombre="Devolución parcial")
    orden_venta.estado = estado_devolucion
    orden_venta.save(update_fields=["estado"])
    return nota_credito
