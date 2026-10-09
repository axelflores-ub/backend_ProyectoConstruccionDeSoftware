# La tabla proveedor_productos ya existe: la creó el M2M automático de 0005.
# Acá solo se agrega la columna. El modelo intermedio se declara en el estado
# de Django para no borrar ni volver a crear la tabla ni su índice único.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compra_y_proveedores", "0005_proveedor_productos"),
        ("scm", "0001_modelos_iniciales"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE proveedor_productos "
                        "ADD COLUMN precio_compra numeric(12, 2) NULL;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE proveedor_productos DROP COLUMN precio_compra;"
                    ),
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name="ProveedorProducto",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "precio_compra",
                            models.DecimalField(decimal_places=2, max_digits=12, null=True),
                        ),
                        (
                            "producto",
                            models.ForeignKey(
                                db_column="producto_id",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="vinculos_proveedor",
                                to="scm.producto",
                            ),
                        ),
                        (
                            "proveedor",
                            models.ForeignKey(
                                db_column="proveedor_id",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="vinculos",
                                to="compra_y_proveedores.proveedor",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Producto del proveedor",
                        "verbose_name_plural": "Productos del proveedor",
                        "db_table": "proveedor_productos",
                        "ordering": ["producto_id"],
                    },
                ),
                migrations.AlterField(
                    model_name="proveedor",
                    name="productos",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="proveedores",
                        through="compra_y_proveedores.ProveedorProducto",
                        to="scm.producto",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="proveedorproducto",
                    constraint=models.UniqueConstraint(
                        fields=("proveedor", "producto"),
                        name="proveedor_productos_proveedor_id_producto_id_022f31af_uniq",
                    ),
                ),
            ],
        ),
    ]
