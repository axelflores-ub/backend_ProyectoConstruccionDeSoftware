from rest_framework.routers import DefaultRouter

from .views import CierreMensualViewSet, PeriodoViewSet

router = DefaultRouter()
router.register("periodos", PeriodoViewSet, basename="periodo")
router.register("cierres-mensuales", CierreMensualViewSet, basename="cierre-mensual")

urlpatterns = router.urls
