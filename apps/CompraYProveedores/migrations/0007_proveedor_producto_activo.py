from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compra_y_proveedores", "0006_precio_compra_en_proveedor_producto"),
    ]

    operations = [
        migrations.AddField(
            model_name="proveedorproducto",
            name="activo",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Activo"), (0, "De baja")],
                default=1,
            ),
        ),
        migrations.AddConstraint(
            model_name="proveedorproducto",
            constraint=models.CheckConstraint(
                condition=models.Q(activo__in=[1, 0]),
                name="proveedor_productos_activo_es_0_o_1",
            ),
        ),
    ]
