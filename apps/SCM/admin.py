from django.contrib import admin

from apps.SCM.models import MovimientoInventario, Producto, Rubro


@admin.register(Rubro)
class RubroAdmin(admin.ModelAdmin):
    list_display = ["id", "nombre"]
    search_fields = ["nombre"]


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ["id", "codigo", "nombre", "rubro", "stock_actual", "stock_minimo"]
    list_filter = ["rubro"]
    search_fields = ["codigo", "nombre"]


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ["id", "producto", "tipo", "cantidad", "usuario", "fecha"]
    list_filter = ["tipo"]
    search_fields = ["producto__codigo", "producto__nombre"]
