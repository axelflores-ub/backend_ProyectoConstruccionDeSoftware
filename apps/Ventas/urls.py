from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AnulacionViewSet,
    ClienteDetailView,
    ClienteListView,
    DetalleNotaCreditoViewSet,
    EstadoOrdenVentaViewSet,
    NotaCreditoViewSet,
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

router.register(
    "anulaciones",
    AnulacionViewSet,
    basename="anulacion"
)

router.register(
    "notas-credito",
    NotaCreditoViewSet,
    basename="notacredito"
)

router.register(
    "notas-credito-detalle",
    DetalleNotaCreditoViewSet,
    basename="detallenotacredito"
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