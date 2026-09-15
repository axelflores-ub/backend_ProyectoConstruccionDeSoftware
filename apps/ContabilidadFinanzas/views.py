from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from .models import CierreMensual, Periodo
from .serializers import CierreMensualSerializer, PeriodoSerializer


class PeriodoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    queryset = Periodo.objects.all()
    serializer_class = PeriodoSerializer
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
