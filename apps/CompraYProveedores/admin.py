# Admin del módulo: registrá acá los modelos que quieras administrar desde /admin/.

"""Admin para inspección local. En Python 3.14 + Django 5.1 las pantallas
de agregar/listar pueden fallar; la API no se ve afectada."""

from django.contrib import admin

from .models import EstadoOrdenCompra, OrdenCompra, OrdenCompraDetalle, Proveedor


class OrdenCompraDetalleInline(admin.TabularInline):
    """Renglones debajo de la cabecera."""

    model = OrdenCompraDetalle
    extra = 0


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "telefono", "email")
    search_fields = ("nombre", "email", "telefono")


@admin.register(EstadoOrdenCompra)
class EstadoOrdenCompraAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre")
    search_fields = ("nombre",)


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ("id", "proveedor", "estado", "fecha", "total")
    list_filter = ("estado", "fecha")
    inlines = [OrdenCompraDetalleInline]


@admin.register(OrdenCompraDetalle)
class OrdenCompraDetalleAdmin(admin.ModelAdmin):
    list_display = ("id", "orden_compra", "producto_id", "cantidad", "precio_unitario")