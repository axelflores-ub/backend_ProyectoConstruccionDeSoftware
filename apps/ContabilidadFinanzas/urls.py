from rest_framework.routers import DefaultRouter

from .views import (
    CierreMensualViewSet,
    DiarioViewSet,
    FacturaCabeceraViewSet,
    FacturaDetalleViewSet,
    PeriodoViewSet,
)

router = DefaultRouter()
router.register("periodos", PeriodoViewSet, basename="periodo")
router.register("cierres-mensuales", CierreMensualViewSet, basename="cierre-mensual")
router.register("diarios", DiarioViewSet, basename="diario")
router.register("facturas", FacturaCabeceraViewSet, basename="factura")
router.register("facturas-detalle", FacturaDetalleViewSet, basename="factura-detalle")

urlpatterns = router.urls
