from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from .models import Periodo
from .serializers import PeriodoSerializer


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
