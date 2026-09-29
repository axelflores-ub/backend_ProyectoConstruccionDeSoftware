"""Lógica de negocio del módulo SCM que no encaja en un solo modelo."""

from django.db import transaction
from rest_framework import serializers

from apps.SCM.models import MovimientoInventario, Producto

SUMAN_STOCK = {MovimientoInventario.Tipo.ENTRADA, MovimientoInventario.Tipo.DEVOLUCION}
RESTAN_STOCK = {MovimientoInventario.Tipo.SALIDA}


def _delta_stock(tipo: str, cantidad: int) -> int:
    if tipo == MovimientoInventario.Tipo.AJUSTE:
        return cantidad
    if tipo in SUMAN_STOCK:
        return abs(cantidad)
    if tipo in RESTAN_STOCK:
        return -abs(cantidad)
    raise ValueError(f"Tipo de movimiento desconocido: {tipo}")


@transaction.atomic
def registrar_movimiento(
    *, producto: Producto, tipo: str, cantidad: int, usuario, observacion: str = ""
) -> MovimientoInventario:
    """Aplica un movimiento de inventario y actualiza producto.stock_actual.

    Rechaza el movimiento si dejaría el stock en negativo.
    """
    producto = Producto.objects.select_for_update().get(pk=producto.pk)

    nuevo_stock = producto.stock_actual + _delta_stock(tipo, cantidad)
    if nuevo_stock < 0:
        raise serializers.ValidationError({"cantidad": "Stock insuficiente para este movimiento."})

    producto.stock_actual = nuevo_stock
    producto.save(update_fields=["stock_actual"])

    return MovimientoInventario.objects.create(
        producto=producto,
        usuario=usuario,
        tipo=tipo,
        cantidad=cantidad,
        observacion=observacion,
    )


@transaction.atomic
def registrar_recepcion_orden_compra(orden, usuario) -> list[MovimientoInventario]:
    """Suma al stock lo recibido: una ENTRADA por cada renglón de la orden.

    Lo llama Compras cuando una orden pasa al estado "Recibida".
    """
    movimientos = []
    for detalle in orden.detalles.all():
        try:
            producto = Producto.objects.get(pk=detalle.producto_id)
        except Producto.DoesNotExist:
            raise serializers.ValidationError(
                {"detalles": f"El producto {detalle.producto_id} no existe en SCM."}
            ) from None
        movimientos.append(
            registrar_movimiento(
                producto=producto,
                tipo=MovimientoInventario.Tipo.ENTRADA,
                cantidad=detalle.cantidad,
                usuario=usuario,
                observacion=f"Recepción de orden de compra #{orden.pk}",
            )
        )
    return movimientos
