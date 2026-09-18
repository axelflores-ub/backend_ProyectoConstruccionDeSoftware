from rest_framework import mixins
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import CierreMensual, Diario, FacturaCabecera, FacturaDetalle, Periodo
from .serializers import (
    CierreMensualSerializer,
    DiarioSerializer,
    FacturaCabeceraSerializer,
    FacturaDetalleConFacturaSerializer,
    PeriodoSerializer,
)


class ContabilidadViewSet(GenericViewSet):
    """Base de todos los endpoints del módulo: exige usuario autenticado (JWT o sesión)."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]


class PeriodoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    ContabilidadViewSet,
):
    queryset = Periodo.objects.all()
    serializer_class = PeriodoSerializer
    # Sin PATCH: el período se actualiza enviando anio y mes completos.
    http_method_names = ["get", "post", "put", "head", "options"]
    search_fields = ["anio", "mes"]
    ordering_fields = ["anio", "mes"]


class CierreMensualViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    ContabilidadViewSet,
):
    queryset = CierreMensual.objects.select_related("periodo")
    serializer_class = CierreMensualSerializer
    # Solo PUT: el cierre se modifica enviando el estado completo.
    http_method_names = ["get", "put", "head", "options"]
    search_fields = ["estado"]
    ordering_fields = ["periodo__anio", "periodo__mes", "estado", "fecha_cierre"]


class DiarioViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    ContabilidadViewSet,
):
    queryset = Diario.objects.select_related("cierre_mensual__periodo")
    serializer_class = DiarioSerializer
    search_fields = ["descripcion"]
    ordering_fields = ["fecha"]


class FacturaCabeceraViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    ContabilidadViewSet,
):
    queryset = FacturaCabecera.objects.prefetch_related("detalles")
    serializer_class = FacturaCabeceraSerializer
    # Sin PUT/PATCH/DELETE: una factura emitida no se modifica ni se borra.
    http_method_names = ["get", "post", "head", "options"]
    search_fields = ["numero", "tipo"]
    ordering_fields = ["fecha", "numero", "total"]


class FacturaDetalleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    ContabilidadViewSet,
):
    queryset = FacturaDetalle.objects.select_related("factura")
    serializer_class = FacturaDetalleConFacturaSerializer
    # Sin PUT/PATCH/DELETE: un detalle emitido no se modifica ni se borra.
    http_method_names = ["get", "post", "head", "options"]
    ordering_fields = ["id", "cantidad", "precio_unitario", "subtotal"]

    def get_queryset(self):
        queryset = super().get_queryset()
        # ?factura=<id> para traer solo las líneas de una factura.
        factura_id = self.request.query_params.get("factura", "")
        if factura_id.isdigit():
            queryset = queryset.filter(factura_id=factura_id)
        return queryset
