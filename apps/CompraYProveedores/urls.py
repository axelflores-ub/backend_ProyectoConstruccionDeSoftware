# Rutas del módulo. Registrá tus ViewSets en un router y exponé `urlpatterns`.
#
# from rest_framework.routers import DefaultRouter
# router = DefaultRouter()
# router.register("recurso", RecursoViewSet, basename="recurso")
# urlpatterns = router.urls

"""Router del módulo. Prefijo /api/compras/ en config/urls.py."""

from rest_framework.routers import DefaultRouter

from .views import (
    EstadoOrdenCompraViewSet,
    OrdenCompraDetalleViewSet,
    OrdenCompraViewSet,
    ProveedorViewSet,
)

router = DefaultRouter()
router.register("proveedores", ProveedorViewSet, basename="proveedor")
router.register(
    "estados-orden-compra",
    EstadoOrdenCompraViewSet,
    basename="estado-orden-compra",
)
router.register("ordenes-compra", OrdenCompraViewSet, basename="orden-compra")
router.register(
    "ordenes-compra-detalle",
    OrdenCompraDetalleViewSet,
    basename="orden-compra-detalle",
)

urlpatterns = router.urls