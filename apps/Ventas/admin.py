# Admin del módulo: registrá acá los modelos que quieras administrar desde /admin/.
from django.contrib import admin

from .models import Cliente, EstadoOrdenVenta, OrdenVenta, OrdenVentaDetalle, Producto


class OrdenVentaDetalleInline(admin.TabularInline):
    model = OrdenVentaDetalle
    extra = 0
    readonly_fields = ["precio_unitario"]


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
 list_display = ('id_cliente', 'nombre', 'telefono', 'email', 'direccion', 'estado')
 list_filter = ('estado',)
 search_fields = ('nombre', 'email', 'telefono')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ["id", "nombre", "precio", "stock"]
    search_fields = ["nombre"]


@admin.register(EstadoOrdenVenta)
class EstadoOrdenVentaAdmin(admin.ModelAdmin):
    list_display = ["id", "nombre", "descripcion"]
    search_fields = ["nombre"]


@admin.register(OrdenVenta)
class OrdenVentaAdmin(admin.ModelAdmin):
    list_display = ["id", "cliente", "estado", "forma_pago", "fecha", "total"]
    list_filter = ["estado", "forma_pago"]
    search_fields = ["cliente__nombre", "cliente__documento"]
    inlines = [OrdenVentaDetalleInline]
