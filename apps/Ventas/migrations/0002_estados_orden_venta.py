"""Carga los estados fijos de la orden de venta (el catálogo es de solo lectura en la API)."""

from django.db import migrations

ESTADOS = [
    ("Pendiente", "Orden generada, sin anulaciones ni devoluciones."),
    ("Anulada", "Orden anulada."),
    ("Devolución parcial", "Se devolvió una parte de lo vendido."),
    ("Devolución total", "Se devolvió todo lo vendido."),
]


def cargar_estados(apps, schema_editor):
    EstadoOrdenVenta = apps.get_model("ventas", "EstadoOrdenVenta")
    for nombre, descripcion in ESTADOS:
        EstadoOrdenVenta.objects.get_or_create(nombre=nombre, defaults={"descripcion": descripcion})


class Migration(migrations.Migration):
    dependencies = [("ventas", "0001_initial")]

    operations = [migrations.RunPython(cargar_estados, migrations.RunPython.noop)]
