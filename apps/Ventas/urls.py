from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ClienteDetailView,
    ClienteListView,
    EstadoOrdenVentaViewSet,
    OrdenVentaDetalleViewSet,
    OrdenVentaViewSet,
    ProductoViewSet,
)

router = DefaultRouter()

router.register(
    "productos",
    ProductoViewSet,
    basename="producto"
)

router.register(
    "estados-orden-venta",
    EstadoOrdenVentaViewSet,
    basename="estadoordenventa"
)

router.register(
    "ordenes-venta",
    OrdenVentaViewSet,
    basename="ordenventa"
)

router.register(
    "ordenes-venta-detalle",
    OrdenVentaDetalleViewSet,
    basename="ordenventadetalle"
)

urlpatterns = [
    path(
        "clientes/",
        ClienteListView.as_view(),
        name="cliente-list"
    ),
    path(
        "clientes/<int:id_cliente>/",
        ClienteDetailView.as_view(),
        name="cliente-detail"
    ),
]

urlpatterns += router.urls