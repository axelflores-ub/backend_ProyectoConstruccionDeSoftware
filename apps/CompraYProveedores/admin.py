"""
Configuración del administrador de Django para el módulo CompraYProveedores.

Registra los modelos (Proveedor, EstadoOrdenCompra, OrdenCompra, OrdenCompraDetalle)
en el panel de administración (/admin/) de Django, permitiendo la inspección y gestión
local de datos a través de una interfaz web.
"""

from django.contrib import admin

from .models import (
    ESTADO_PENDIENTE,
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
    ProveedorProducto,
)


class ProveedorProductoInline(admin.TabularInline):
    """Precio de compra de cada producto. activo=0 es la baja: la fila no se borra."""

    model = ProveedorProducto
    extra = 0
    can_delete = False
    fields = ("producto", "precio_compra", "activo")


class OrdenCompraDetalleInline(admin.TabularInline):
    """Inline de renglones de la orden de compra.

    Cuando la orden está en estado Pendiente, los renglones son editables y se
    pueden agregar o eliminar. En cualquier otro estado (Aprobada, Rechazada,
    Recibida, Devuelto, Contabilizado) el inline pasa a modo lectura: no se
    permite agregar, eliminar ni modificar ningún campo.
    """

    model = OrdenCompraDetalle
    extra = 0
    # Campos que se muestran (también aplica en modo lectura).
    fields = ("producto_id", "cantidad", "precio_unitario")

    def get_readonly_fields(self, request, obj=None):
        """Devuelve todos los campos como solo lectura si la orden no es Pendiente."""
        if obj is not None and obj.estado.nombre != ESTADO_PENDIENTE:
            return self.fields
        return super().get_readonly_fields(request, obj)

    def has_add_permission(self, request, obj=None):
        """Impide agregar renglones a órdenes fuera de Pendiente."""
        if obj is not None and obj.estado.nombre != ESTADO_PENDIENTE:
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Impide eliminar renglones de órdenes fuera de Pendiente."""
        if obj is not None and obj.estado.nombre != ESTADO_PENDIENTE:
            return False
        return super().has_delete_permission(request, obj)


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
    inlines = [ProveedorProductoInline]


@admin.register(EstadoOrdenCompra)
class EstadoOrdenCompraAdmin(admin.ModelAdmin):
    """Catálogo de estados de orden de compra. Solo lectura: lo mantienen las migraciones.

    Los estados se cargan mediante las migraciones 0003 y 0008 (Devuelto y
    Contabilizado) y no deben modificarse manualmente desde el admin.

    Atributos:
        list_display: Campos mostrados en la lista de estados.
        search_fields: Campos en los que se puede buscar.
    """

    list_display = ("estadoordencompra_id", "nombre")
    search_fields = ("nombre",)

    def has_add_permission(self, request):
        """El catálogo de estados lo mantienen las migraciones, no el admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Impide editar estados desde el admin."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Impide borrar estados desde el admin."""
        return False


# Campos de cabecera de la orden que se congelan fuera del estado Pendiente.
_CAMPOS_CABECERA = ("proveedor", "estado", "fecha", "total")


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    """Interfaz de administración para Órdenes de Compra.

    Fuera del estado Pendiente la orden es de solo lectura: estado, total,
    proveedor y fecha no se pueden modificar, y los renglones del inline
    tampoco (ver OrdenCompraDetalleInline).

    Atributos:
        list_display: Campos mostrados en la lista de órdenes.
        list_filter: Filtros disponibles en la barra lateral (estado, fecha).
        inlines: Tabla inline de renglones.
    """

    list_display = ("ordencompra_id", "proveedor", "estado", "fecha", "total")
    list_filter = ("estado", "fecha")
    inlines = [OrdenCompraDetalleInline]

    def get_readonly_fields(self, request, obj=None):
        """Devuelve estado/total/proveedor/fecha como solo lectura fuera de Pendiente.

        En una orden nueva (obj=None) o en estado Pendiente todos los campos
        son editables. En cualquier otro estado la cabecera queda congelada.
        """
        if obj is not None and obj.estado.nombre != ESTADO_PENDIENTE:
            return _CAMPOS_CABECERA
        return super().get_readonly_fields(request, obj)


@admin.register(OrdenCompraDetalle)
class OrdenCompraDetalleAdmin(admin.ModelAdmin):
    """Interfaz de administración para Detalles de Órdenes de Compra.

    Permite ver renglones individuales. La edición directa de un renglón
    queda bloqueada si su orden no está en estado Pendiente.

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
    # Campos del renglón (se usan en get_readonly_fields).
    _CAMPOS_DETALLE = ("orden_compra", "producto_id", "cantidad", "precio_unitario")

    def get_readonly_fields(self, request, obj=None):
        """Congela todos los campos si la orden asociada no está en Pendiente."""
        if obj is not None and obj.orden_compra.estado.nombre != ESTADO_PENDIENTE:
            return self._CAMPOS_DETALLE
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Impide borrar renglones de órdenes fuera de Pendiente."""
        if obj is not None and obj.orden_compra.estado.nombre != ESTADO_PENDIENTE:
            return False
        return super().has_delete_permission(request, obj)