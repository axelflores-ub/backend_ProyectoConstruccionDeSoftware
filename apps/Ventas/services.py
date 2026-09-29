# Lógica de negocio del módulo Ventas (fuera de views y serializers).
from decimal import Decimal

from django.db import transaction

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
def anular_orden_venta(*, orden_venta, motivo, detalle=None):
    """Registra la anulación y mueve la orden al estado 'Anulada'."""
    anulacion = Anulacion.objects.create(orden_venta=orden_venta, motivo=motivo, detalle=detalle)
    estado_anulada, _ = EstadoOrdenVenta.objects.get_or_create(nombre="Anulada")
    orden_venta.estado = estado_anulada
    orden_venta.save(update_fields=["estado"])
    return anulacion


@transaction.atomic
def registrar_nota_credito(*, orden_venta, monto, saldo_a_favor, detalles, usuario):
    """Crea la nota de crédito, repone stock de lo devuelto a 'stock disponible'
    (con un movimiento de inventario DEVOLUCION) y mueve la orden a 'Devolución parcial'."""
    nota_credito = NotaCredito.objects.create(
        orden_venta=orden_venta, monto=monto, saldo_a_favor=saldo_a_favor
    )

    for item in detalles:
        DetalleNotaCredito.objects.create(nota_credito=nota_credito, **item)
        if item["destino"] == DetalleNotaCredito.Destino.STOCK_DISPONIBLE:
            producto = Producto.objects.select_for_update().get(pk=item["producto"].id)
            producto.stock_actual += item["cantidad_devuelta"]
            producto.save(update_fields=["stock_actual"])
            _registrar_movimiento(
                producto=producto,
                usuario=usuario,
                tipo=MovimientoInventario.Tipo.DEVOLUCION,
                cantidad=item["cantidad_devuelta"],
                observacion=f"Devolución - nota de crédito #{nota_credito.pk}",
            )

    estado_devolucion, _ = EstadoOrdenVenta.objects.get_or_create(nombre="Devolución parcial")
    orden_venta.estado = estado_devolucion
    orden_venta.save(update_fields=["estado"])
    return nota_credito
