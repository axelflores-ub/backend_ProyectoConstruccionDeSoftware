# Vistas del módulo (DRF): ViewSets / APIViews con la lógica de cada endpoint.

"""ViewSets. Requieren JWT (IsAuthenticated)."""

from rest_framework import viewsets

from .models import (
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
)
from .serializers import (
    EstadoOrdenCompraSerializer,
    OrdenCompraDetalleSerializer,
    OrdenCompraSerializer,
    ProveedorSerializer,
)


class ProveedorViewSet(viewsets.ModelViewSet):
    """CRUD de proveedores."""

    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    search_fields = ["nombre", "email", "telefono"]
    ordering_fields = ["id", "nombre"]


class EstadoOrdenCompraViewSet(viewsets.ModelViewSet):
    """CRUD del catálogo de estados de OC."""

    queryset = EstadoOrdenCompra.objects.all()
    serializer_class = EstadoOrdenCompraSerializer
    search_fields = ["nombre"]
    ordering_fields = ["id", "nombre"]


class OrdenCompraViewSet(viewsets.ModelViewSet):
    """CRUD de cabeceras de OC, con renglones anidados en lectura."""

    queryset = OrdenCompra.objects.select_related(
        "proveedor", "estado"
    ).prefetch_related("detalles")
    serializer_class = OrdenCompraSerializer
    ordering_fields = ["id", "fecha", "total"]


class OrdenCompraDetalleViewSet(viewsets.ModelViewSet):
    """CRUD de renglones. producto_id es el id que después será de SCM."""

    queryset = OrdenCompraDetalle.objects.select_related("orden_compra")
    serializer_class = OrdenCompraDetalleSerializer