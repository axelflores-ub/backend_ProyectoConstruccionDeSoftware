from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import Periodo
from .serializers import PeriodoSerializer


class PeriodoViewSet(ReadOnlyModelViewSet):
    queryset = Periodo.objects.all()
    serializer_class = PeriodoSerializer
    search_fields = ["anio", "mes"]
    ordering_fields = ["anio", "mes"]
