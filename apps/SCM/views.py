from django.db.models import F
from rest_framework import mixins, viewsets

from apps.SCM.models import MovimientoInventario, Producto, Rubro
from apps.SCM.serializers import (
    MovimientoInventarioSerializer,
    ProductoSerializer,
    RubroSerializer,
)


class RubroViewSet(viewsets.ModelViewSet):
    queryset = Rubro.objects.all()
    serializer_class = RubroSerializer
    search_fields = ["nombre"]
    ordering_fields = ["nombre"]


class ProductoViewSet(viewsets.ModelViewSet):
    """Catálogo + stock actual.

    `?bajo_stock=true` lista los productos con stock_actual <= stock_minimo,
    que son los candidatos a una orden de reposición.
    """

    queryset = Producto.objects.select_related("rubro").all()
    serializer_class = ProductoSerializer
    search_fields = ["codigo", "nombre"]
    ordering_fields = ["nombre", "precio", "stock_actual"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("bajo_stock", "").lower() in {"true", "1"}:
            queryset = queryset.filter(stock_actual__lte=F("stock_minimo"))
        return queryset


class MovimientoInventarioViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Solo alta y consulta: el historial de movimientos no se edita ni se borra.

    Filtros: `?producto=<id>` y `?tipo=ENTRADA|SALIDA|AJUSTE|DEVOLUCION`.
    """

    queryset = MovimientoInventario.objects.select_related("producto", "usuario").all()
    serializer_class = MovimientoInventarioSerializer
    search_fields = ["producto__codigo", "producto__nombre"]
    ordering_fields = ["fecha"]

    def get_queryset(self):
        queryset = super().get_queryset()
        producto_id = self.request.query_params.get("producto")
        if producto_id:
            queryset = queryset.filter(producto_id=producto_id)
        tipo = self.request.query_params.get("tipo")
        if tipo:
            queryset = queryset.filter(tipo=tipo.upper())
        return queryset
