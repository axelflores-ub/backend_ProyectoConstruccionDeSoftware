# Admin del módulo: registrá acá los modelos que quieras administrar desde /admin/.
from django.contrib import admin

from .models import (
    Anulacion,
    Cliente,
    DetalleNotaCredito,
    EstadoOrdenVenta,
    NotaCredito,
    OrdenVenta,
    OrdenVentaDetalle,
    Producto,
)


class OrdenVentaDetalleInline(admin.TabularInline):
    model = OrdenVentaDetalle
    extra = 0
    readonly_fields = ["precio_unitario"]


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
 list_display = ('id_cliente', 'nombre', 'telefono', 'email', 'direccion', 'cuil', 'condicion_iva', 'estado')
 list_filter = ('estado', 'condicion_iva')
 search_fields = ('nombre', 'email', 'telefono', 'cuil')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ["id", "nombre", "precio", "stock"]
    search_fields = ["nombre"]


class DetalleNotaCreditoInline(admin.TabularInline):
    model = DetalleNotaCredito
    extra = 0


@admin.register(EstadoOrdenVenta)
class EstadoOrdenVentaAdmin(admin.ModelAdmin):
    list_display = ["id", "nombre", "descripcion"]
    search_fields = ["nombre"]


@admin.register(OrdenVenta)
class OrdenVentaAdmin(admin.ModelAdmin):
    list_display = ["id", "cliente", "estado", "forma_pago", "tipo_comprobante", "numero_comprobante", "fecha", "total"]
    list_filter = ["estado", "forma_pago", "tipo_comprobante"]
    search_fields = ["cliente__nombre", "cliente__documento", "numero_comprobante"]
    inlines = [OrdenVentaDetalleInline]


@admin.register(Anulacion)
class AnulacionAdmin(admin.ModelAdmin):
    list_display = ["id", "orden_venta", "motivo", "fecha"]
    search_fields = ["orden_venta__id", "motivo"]


@admin.register(NotaCredito)
class NotaCreditoAdmin(admin.ModelAdmin):
    list_display = ["id", "orden_venta", "monto", "saldo_a_favor", "fecha"]
    list_filter = ["saldo_a_favor"]
    inlines = [DetalleNotaCreditoInline]
