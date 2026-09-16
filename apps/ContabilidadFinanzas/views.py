from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from .models import CierreMensual, Diario, Periodo
from .serializers import CierreMensualSerializer, DiarioSerializer, PeriodoSerializer


class PeriodoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
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
    GenericViewSet,
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
    GenericViewSet,
):
    queryset = Diario.objects.select_related("cierre_mensual__periodo")
    serializer_class = DiarioSerializer
    search_fields = ["descripcion"]
    ordering_fields = ["fecha"]
