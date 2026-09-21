from rest_framework.routers import DefaultRouter

from apps.SCM.views import (
    MovimientoInventarioViewSet,
    ProductoViewSet,
    RubroViewSet,
)

router = DefaultRouter()
router.register("rubros", RubroViewSet, basename="rubro")
router.register("productos", ProductoViewSet, basename="producto")
router.register(
    "movimientos-inventario", MovimientoInventarioViewSet, basename="movimiento-inventario"
)

urlpatterns = router.urls
