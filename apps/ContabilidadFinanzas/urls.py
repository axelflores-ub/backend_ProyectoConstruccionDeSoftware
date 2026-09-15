from rest_framework.routers import DefaultRouter

from .views import CierreMensualViewSet, DiarioViewSet, PeriodoViewSet

router = DefaultRouter()
router.register("periodos", PeriodoViewSet, basename="periodo")
router.register("cierres-mensuales", CierreMensualViewSet, basename="cierre-mensual")
router.register("diarios", DiarioViewSet, basename="diario")

urlpatterns = router.urls
