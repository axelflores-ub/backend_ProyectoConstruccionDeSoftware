"""
Configuración del administrador de Django para el módulo CompraYProveedores.

Registra los modelos (Proveedor, EstadoOrdenCompra, OrdenCompra, OrdenCompraDetalle)
en el panel de administración (/admin/) de Django, permitiendo la inspección y gestión
local de datos a través de una interfaz web.
"""

from django.contrib import admin

from .models import EstadoOrdenCompra, OrdenCompra, OrdenCompraDetalle, Proveedor


class OrdenCompraDetalleInline(admin.TabularInline):
    """Inline para editar detalles de ordenes directamente desde OrdenCompraAdmin.
    
    Permite ver y editar los renglones de una orden de compra en forma de tabla
    dentro de la interfaz de administración de la orden.
    
    Atributos:
        model: Modelo OrdenCompraDetalle.
        extra: Numero de filas en blanco para agregar nuevos detalles (0 = ninguna fila vacia).
    """
    model = OrdenCompraDetalle
    extra = 0


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    """Interfaz de administración para Proveedores.
    
    Permite listar, buscar, crear, editar y eliminar proveedores desde el panel /admin/.
    
    Atributos:
        list_display: Campos mostrados en la lista de proveedores.
        search_fields: Campos en los que se puede buscar en el listado.
    """
    list_display = ("proveedor_id", "nombre", "apellido", "cuit", "telefono", "email")
    search_fields = ("nombre", "apellido", "cuit", "email", "telefono")


@admin.register(EstadoOrdenCompra)
class EstadoOrdenCompraAdmin(admin.ModelAdmin):
    """Interfaz de administración para Estados de Orden de Compra.
    
    Permite gestionar el catalogo de estados disponibles para las ordenes.
    
    Atributos:
        list_display: Campos mostrados en la lista de estados.
        search_fields: Campos en los que se puede buscar.
    """
    list_display = ("estadoordencompra_id", "nombre")
    search_fields = ("nombre",)


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    """Interfaz de administración para Ordenes de Compra.
    
    Permite gestionar ordenes de compra con sus detalles anidados.
    Incluye filtrado por estado y fecha, y permite editar los renglones en linea.
    
    Atributos:
        list_display: Campos mostrados en la lista de ordenes.
        list_filter: Filtros disponibles en la barra lateral (estado, fecha).
        inlines: Tablas inline para editar detalles directamente.
    """
    list_display = ("ordencompra_id", "proveedor", "estado", "fecha", "total")
    list_filter = ("estado", "fecha")
    inlines = [OrdenCompraDetalleInline]


@admin.register(OrdenCompraDetalle)
class OrdenCompraDetalleAdmin(admin.ModelAdmin):
    """Interfaz de administración para Detalles de Ordenes de Compra.
    
    Permite ver y editar los renglones individuales de las ordenes directamente
    desde el listado (sin necesidad de pasar por la orden).
    
    Atributos:
        list_display: Campos mostrados en la lista de detalles.
    """
    list_display = (
        "ordencompradetalle_id",
        "orden_compra",
        "producto_id",
        "cantidad",
        "precio_unitario",
    )