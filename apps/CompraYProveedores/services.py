"""La factura de compra se lee y la orden se marca Contabilizado desde acá.

No modifica ContabilidadFinanzas: usa el modelo que ese módulo ya tiene.
"""

from apps.ContabilidadFinanzas.models import FacturaCabecera

from .models import ESTADO_CONTABILIZADO, EstadoOrdenCompra


def tiene_factura_compra(orden_id):
    return FacturaCabecera.objects.filter(
        tipo=FacturaCabecera.Tipo.COMPRA,
        orden_compra_id=orden_id,
    ).exists()


def marcar_orden_contabilizada(orden):
    """La factura de compra ya existe: la orden vuelve de finanzas como Contabilizado."""
    orden.estado = EstadoOrdenCompra.objects.get(nombre=ESTADO_CONTABILIZADO)
    orden.save(update_fields=["estado"])
