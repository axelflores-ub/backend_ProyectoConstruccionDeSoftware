"""
Rutas (URLs) del módulo CompraYProveedores.

Registra todos los ViewSets en un router de DRF y expone los patrones de URL.
Este router se incluye en config/urls.py con el prefijo /api/compras/,
generando automáticamente los endpoints REST para todas las operaciones CRUD.
"""

from rest_framework.routers import DefaultRouter

from .views import (
    EstadoOrdenCompraViewSet,
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

# Catálogo de estados (solo lectura)
# GET    /api/compras/estados-orden-compra/           - lista de estados
# GET    /api/compras/estados-orden-compra/{id}/      - detalle de estado
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
# POST   /api/compras/ordenes-compra/{id}/enviar-a-finanzas/ - factura de compra
router.register("ordenes-compra", OrdenCompraViewSet, basename="orden-compra")

urlpatterns = router.urls
