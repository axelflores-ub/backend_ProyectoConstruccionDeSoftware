from django.db import migrations

ESTADOS = ["Pendiente", "Aprobada", "Rechazada", "Recibida"]


def cargar_estados(apps, schema_editor):
    EstadoOrdenCompra = apps.get_model("compra_y_proveedores", "EstadoOrdenCompra")
    for nombre in ESTADOS:
        EstadoOrdenCompra.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):
    dependencies = [
        ("compra_y_proveedores", "0002_proveedor_producto_id"),
    ]

    operations = [
        # No se borran en reversa: pueden tener órdenes asociadas.
        migrations.RunPython(cargar_estados, migrations.RunPython.noop),
    ]
