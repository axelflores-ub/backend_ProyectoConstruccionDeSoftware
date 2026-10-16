# Lógica de negocio del módulo Ventas (fuera de views y serializers).
import re
from decimal import ROUND_HALF_UP, Decimal

from apps.SCM.models import MovimientoInventario, Producto
from django.db import transaction
from django.db.models import Sum
from rest_framework import status

from .models import (
    Anulacion,
    Cliente,
    DetalleNotaCredito,
    EstadoOrdenVenta,
    NotaCredito,
    OrdenVenta,
    OrdenVentaDetalle,
)


class ErrorDeNegocio(Exception):
    """Regla de negocio incumplida. Cada subclase fija el código HTTP que corresponde.
    views.manejador_de_errores lo convierte en la respuesta de error estándar."""

    status_code = status.HTTP_400_BAD_REQUEST
    codigo = "error_de_negocio"

    def __init__(self, mensaje, *, codigo=None, campo=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        if codigo:
            self.codigo = codigo
        self.campo = campo


class SolicitudInvalida(ErrorDeNegocio):
    """400: el pedido en sí es incorrecto (datos que nunca podrían ser válidos)."""

    status_code = status.HTTP_400_BAD_REQUEST
    codigo = "solicitud_invalida"


class NoEncontrado(ErrorDeNegocio):
    """404: lo que se busca no existe."""

    status_code = status.HTTP_404_NOT_FOUND
    codigo = "no_encontrado"


class Conflicto(ErrorDeNegocio):
    """409: el pedido es válido pero choca con el estado actual de los datos."""

    status_code = status.HTTP_409_CONFLICT
    codigo = "conflicto"


ESTADOS_DEVOLVIBLES = (EstadoOrdenVenta.PENDIENTE, EstadoOrdenVenta.DEVOLUCION_PARCIAL)


def normalizar_cuit(valor):
    """Deja solo los dígitos: '20-12345678-9' y '20123456789' son el mismo CUIT."""
    return re.sub(r"\D", "", str(valor or ""))


def _estado(nombre):
    estado, _ = EstadoOrdenVenta.objects.get_or_create(nombre=nombre)
    return estado


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


def acumular_cantidades(items, campo="cantidad"):
    """Suma las cantidades por producto (un producto puede repetirse en varios ítems)."""
    acumulado = {}
    for item in items:
        producto_id = item["producto"].id
        acumulado[producto_id] = acumulado.get(producto_id, 0) + item[campo]
    return acumulado


def obtener_cliente_activo_por_cuit(cuit):
    """Busca al cliente por CUIT. 404 si no existe, 409 si está dado de baja."""
    cliente = Cliente.objects.filter(cuit=cuit).first()
    if cliente is None:
        raise NoEncontrado(
            "No existe un cliente con ese CUIT. Primero hay que darlo de alta en ABM de clientes.",
            codigo="cliente_no_encontrado",
        )
    if cliente.estado != Cliente.ESTADO_ACTIVO:
        raise Conflicto(
            "El cliente está dado de baja y no puede tener nuevas órdenes de venta.",
            codigo="cliente_de_baja",
        )
    return cliente


def _estado_invalido(accion, orden):
    return Conflicto(
        f"No se puede {accion} una orden en estado '{orden.estado.nombre}'.",
        codigo="estado_de_orden_invalido",
    )


@transaction.atomic
def registrar_orden_venta(*, cuit, datos, detalles, usuario=None):
    """Genera la orden de venta: obtiene el cliente por CUIT, crea el detalle, calcula el
    total, descuenta stock y registra un movimiento de inventario SALIDA por producto.

    select_for_update bloquea las filas de producto hasta el fin de la transacción,
    evitando que dos órdenes concurrentes descuenten el mismo stock.
    """
    cliente = obtener_cliente_activo_por_cuit(cuit)
    cantidad_por_producto = acumular_cantidades(detalles)

    productos = {
        p.id: p
        for p in Producto.objects.select_for_update().filter(id__in=cantidad_por_producto.keys())
    }
    for producto_id, cantidad_total in cantidad_por_producto.items():
        producto = productos[producto_id]
        if producto.stock_actual < cantidad_total:
            raise Conflicto(
                f"Stock insuficiente para '{producto.nombre}' "
                f"(disponible: {producto.stock_actual}).",
                codigo="stock_insuficiente",
            )

    # Toda orden nueva arranca en el estado "Pendiente".
    orden = OrdenVenta.objects.create(
        cliente=cliente, usuario=usuario, estado=_estado(EstadoOrdenVenta.PENDIENTE), **datos
    )

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
def anular_orden_venta(*, orden_venta, motivo, detalle=""):
    """Registra la anulación y mueve la orden al estado 'Anulada'.
    Solo se puede anular una orden en estado 'Pendiente'."""
    orden = OrdenVenta.objects.select_for_update().get(pk=orden_venta.pk)
    if orden.estado.nombre == EstadoOrdenVenta.ANULADA:
        raise Conflicto("Esta orden ya fue anulada.", codigo="orden_ya_anulada")
    if orden.estado.nombre != EstadoOrdenVenta.PENDIENTE:
        raise _estado_invalido("anular", orden)

    anulacion = Anulacion.objects.create(orden_venta=orden, motivo=motivo, detalle=detalle or "")
    orden.estado = _estado(EstadoOrdenVenta.ANULADA)
    orden.save(update_fields=["estado"])
    return anulacion


@transaction.atomic
def registrar_nota_credito(*, orden_venta, saldo_a_favor, detalles, usuario):
    """Registra una devolución sobre una orden.

    Valida (400) que los productos pertenezcan a la orden y que no se devuelva más de lo
    vendido; valida (409) que la orden admita devoluciones y que no se supere lo que aún
    queda por devolver. El monto lo calcula el servidor con el precio realmente cobrado
    (descuento incluido). Repone stock de lo devuelto a 'stock disponible' (con un
    movimiento DEVOLUCION) y deja la orden en 'Devolución parcial' o 'Devolución total'.
    """
    orden = OrdenVenta.objects.select_for_update().get(pk=orden_venta.pk)
    if orden.estado.nombre not in ESTADOS_DEVOLVIBLES:
        raise _estado_invalido("devolver", orden)

    vendido = {}
    for detalle in orden.detalles.all():
        datos = vendido.setdefault(detalle.producto_id, {"cantidad": 0, "importe": Decimal("0")})
        datos["cantidad"] += detalle.cantidad
        datos["importe"] += detalle.subtotal

    devuelto = {
        fila["producto_id"]: fila["total"]
        for fila in DetalleNotaCredito.objects.filter(nota_credito__orden_venta=orden)
        .values("producto_id")
        .annotate(total=Sum("cantidad_devuelta"))
        .order_by()
    }

    pedido = acumular_cantidades(detalles, "cantidad_devuelta")
    nombres = {item["producto"].id: item["producto"].nombre for item in detalles}

    monto = Decimal("0")
    for producto_id, cantidad in pedido.items():
        nombre = nombres[producto_id]
        if producto_id not in vendido:
            raise SolicitudInvalida(
                f"El producto '{nombre}' no pertenece a la orden #{orden.pk}.",
                codigo="producto_fuera_de_la_orden",
                campo="detalles",
            )
        cantidad_vendida = vendido[producto_id]["cantidad"]
        if cantidad > cantidad_vendida:
            raise SolicitudInvalida(
                f"No se pueden devolver {cantidad} unidades de '{nombre}': "
                f"la orden incluye {cantidad_vendida}.",
                codigo="cantidad_supera_lo_vendido",
                campo="detalles",
            )
        ya_devuelto = devuelto.get(producto_id, 0)
        pendiente = cantidad_vendida - ya_devuelto
        if cantidad > pendiente:
            raise Conflicto(
                f"No se pueden devolver {cantidad} unidades de '{nombre}': ya se devolvieron "
                f"{ya_devuelto} de {cantidad_vendida} y quedan {pendiente} por devolver.",
                codigo="devolucion_excedida",
            )
        monto += vendido[producto_id]["importe"] * cantidad / cantidad_vendida
    monto = monto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    nota_credito = NotaCredito.objects.create(
        orden_venta=orden, monto=monto, saldo_a_favor=saldo_a_favor
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

    devolucion_completa = all(
        devuelto.get(producto_id, 0) + pedido.get(producto_id, 0) >= datos["cantidad"]
        for producto_id, datos in vendido.items()
    )
    orden.estado = _estado(
        EstadoOrdenVenta.DEVOLUCION_TOTAL
        if devolucion_completa
        else EstadoOrdenVenta.DEVOLUCION_PARCIAL
    )
    orden.save(update_fields=["estado"])
    return nota_credito
