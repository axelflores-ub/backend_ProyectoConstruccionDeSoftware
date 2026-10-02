from django.db import migrations, models


def copiar_producto_al_vinculo(apps, schema_editor):
    """Pasa el producto_id 1 a 1 al vínculo muchos a muchos, si el producto existe."""
    Proveedor = apps.get_model("compra_y_proveedores", "Proveedor")
    Producto = apps.get_model("scm", "Producto")
    Vinculo = apps.get_model("compra_y_proveedores", "Proveedor_productos")
    existentes = set(Producto.objects.values_list("pk", flat=True))
    vinculos = [
        Vinculo(proveedor_id=proveedor.pk, producto_id=proveedor.producto_id)
        for proveedor in Proveedor.objects.all()
        if proveedor.producto_id in existentes
    ]
    Vinculo.objects.bulk_create(vinculos)


class Migration(migrations.Migration):
    dependencies = [
        ("compra_y_proveedores", "0004_cuit_canonico"),
        ("scm", "0001_modelos_iniciales"),
    ]

    operations = [
        migrations.AddField(
            model_name="proveedor",
            name="productos",
            field=models.ManyToManyField(blank=True, related_name="proveedores", to="scm.producto"),
        ),
        migrations.RunPython(copiar_producto_al_vinculo, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="proveedor",
            name="producto_id",
        ),
    ]
