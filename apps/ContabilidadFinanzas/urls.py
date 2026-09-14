from rest_framework.routers import DefaultRouter

from .views import PeriodoViewSet

router = DefaultRouter()
router.register("periodos", PeriodoViewSet, basename="periodo")

urlpatterns = router.urls
