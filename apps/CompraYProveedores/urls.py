"""
Rutas (URLs) del módulo CompraYProveedores.

Registra todos los ViewSets en un router de DRF y expone los patrones de URL.
Este router se incluye en config/urls.py con el prefijo /api/compras/,
generando automáticamente los endpoints REST para todas las operaciones CRUD.
"""

from rest_framework.routers import DefaultRouter

from .views import (
    EstadoOrdenCompraViewSet,
    OrdenCompraDetalleViewSet,
    OrdenCompraViewSet,
    ProveedorViewSet,
)

router = DefaultRouter()

# CRUD de Proveedores
# GET    /api/compras/proveedores/           - lista de proveedores
# POST   /api/compras/proveedores/           - crear proveedor
# GET    /api/compras/proveedores/{id}/      - detalle de proveedor
# PUT    /api/compras/proveedores/{id}/      - actualizar proveedor
# DELETE /api/compras/proveedores/{id}/      - eliminar proveedor
router.register("proveedores", ProveedorViewSet, basename="proveedor")

# CRUD de Estados de Orden de Compra (catalogo)
# GET    /api/compras/estados-orden-compra/           - lista de estados
# POST   /api/compras/estados-orden-compra/           - crear estado
# GET    /api/compras/estados-orden-compra/{id}/      - detalle de estado
# PUT    /api/compras/estados-orden-compra/{id}/      - actualizar estado
# DELETE /api/compras/estados-orden-compra/{id}/      - eliminar estado
router.register(
    "estados-orden-compra",
    EstadoOrdenCompraViewSet,
    basename="estado-orden-compra",
)

# CRUD de Ordenes de Compra (cabeceras)
# GET    /api/compras/ordenes-compra/           - lista de ordenes
# POST   /api/compras/ordenes-compra/           - crear orden
# GET    /api/compras/ordenes-compra/{id}/      - detalle de orden (con detalles anidados)
# PUT    /api/compras/ordenes-compra/{id}/      - actualizar orden
# DELETE /api/compras/ordenes-compra/{id}/      - eliminar orden
router.register("ordenes-compra", OrdenCompraViewSet, basename="orden-compra")

# CRUD de Detalles de Orden de Compra (renglones)
# GET    /api/compras/ordenes-compra-detalle/           - lista de detalles
# POST   /api/compras/ordenes-compra-detalle/           - crear detalle
# GET    /api/compras/ordenes-compra-detalle/{id}/      - detalle especifico
# PUT    /api/compras/ordenes-compra-detalle/{id}/      - actualizar detalle
# DELETE /api/compras/ordenes-compra-detalle/{id}/      - eliminar detalle
router.register(
    "ordenes-compra-detalle",
    OrdenCompraDetalleViewSet,
    basename="orden-compra-detalle",
)

urlpatterns = router.urls