from django.contrib import admin

from .models import CierreMensual, Diario, FacturaCabecera, FacturaDetalle, Periodo


class FacturaDetalleInline(admin.TabularInline):
    model = FacturaDetalle
    extra = 1


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    list_display = ["id", "anio", "mes"]
    ordering = ["-anio", "-mes"]


@admin.register(CierreMensual)
class CierreMensualAdmin(admin.ModelAdmin):
    list_display = ["id", "periodo", "estado", "fecha_cierre"]
    list_filter = ["estado"]


@admin.register(Diario)
class DiarioAdmin(admin.ModelAdmin):
    list_display = ["id", "cierre_mensual", "fecha", "descripcion"]


@admin.register(FacturaCabecera)
class FacturaCabeceraAdmin(admin.ModelAdmin):
    list_display = ["id", "tipo", "numero", "fecha", "subtotal", "impuestos", "total"]
    list_filter = ["tipo"]
    inlines = [FacturaDetalleInline]
