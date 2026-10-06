from decimal import Decimal

from django.utils import timezone

from .models import CierreMensual, Diario, FacturaCabecera, Periodo

# Rango de años admitido para un período (el mismo que valida el front al crearlo).
ANIO_MINIMO = 2000
ANIO_MAXIMO = 2100

# Mayor importe que entra en un DecimalField(max_digits=12, decimal_places=2).
MAX_IMPORTE = Decimal("9999999999.99")


class PeriodoCerradoError(Exception):
    """El período ya está cerrado y no admite cambios."""


def asegurar_cierre_abierto(cierre):
    """Lanza PeriodoCerradoError si el cierre mensual ya está cerrado."""
    if cierre.estado == CierreMensual.Estado.CERRADO:
        raise PeriodoCerradoError(
            f"El período {cierre.periodo} ya está cerrado y no admite cambios."
        )


def cierre_de_factura(factura):
    """Cierre mensual de una factura existente, o None si todavía no hay uno.

    Si la factura tiene entrada de diario, es el cierre de esa entrada. Si no (facturas
    anteriores al libro diario automático), es el del período que corresponde a su fecha.
    """
    if factura.diario_id:
        return factura.diario.cierre_mensual

    fecha_local = timezone.localtime(factura.fecha)
    return (
        CierreMensual.objects.filter(
            periodo__anio=fecha_local.year, periodo__mes=fecha_local.month
        )
        .order_by("id")
        .first()
    )


def descripcion_de_factura(datos):
    es_venta = datos["tipo"] == FacturaCabecera.Tipo.VENTA
    etiqueta = "venta" if es_venta else "compra"
    orden_id = datos.get("orden_venta_id") if es_venta else datos.get("orden_compra_id")

    texto = f"Factura de {etiqueta} {datos['numero']}"
    if orden_id:
        texto += f" (orden de {etiqueta} #{orden_id})"
    return texto


def registrar_diario_de_factura(datos):
    """Crea la entrada del libro diario para una factura nueva y la devuelve.

    `datos` son los datos validados de la factura. La entrada va al cierre mensual del
    período que corresponde a la fecha de la factura (en hora local). Si ese período no
    existe se crea, junto con su cierre abierto. Debe llamarse dentro de una transacción.
    """
    fecha = datos["fecha"]
    fecha_local = timezone.localtime(fecha)

    periodo, _ = Periodo.objects.get_or_create(anio=fecha_local.year, mes=fecha_local.month)
    cierre = periodo.cierres_mensuales.order_by("id").first()
    if cierre is None:
        cierre = CierreMensual.objects.create(periodo=periodo)

    asegurar_cierre_abierto(cierre)

    return Diario.objects.create(
        cierre_mensual=cierre,
        fecha=fecha,
        descripcion=descripcion_de_factura(datos),
    )
