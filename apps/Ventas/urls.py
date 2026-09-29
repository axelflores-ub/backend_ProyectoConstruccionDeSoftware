from rest_framework.routers import DefaultRouter

from .views import (
    AnulacionViewSet,
    ClienteViewSet,
    DetalleNotaCreditoViewSet,
    EstadoOrdenVentaViewSet,
    NotaCreditoViewSet,
    OrdenVentaDetalleViewSet,
    OrdenVentaViewSet,
)

router = DefaultRouter()

router.register("clientes", ClienteViewSet, basename="cliente")
router.register("estados-orden-venta", EstadoOrdenVentaViewSet, basename="estadoordenventa")
router.register("ordenes-venta", OrdenVentaViewSet, basename="ordenventa")
router.register("ordenes-venta-detalle", OrdenVentaDetalleViewSet, basename="ordenventadetalle")
router.register("anulaciones", AnulacionViewSet, basename="anulacion")
router.register("notas-credito", NotaCreditoViewSet, basename="notacredito")
router.register("notas-credito-detalle", DetalleNotaCreditoViewSet, basename="detallenotacredito")

urlpatterns = router.urls
