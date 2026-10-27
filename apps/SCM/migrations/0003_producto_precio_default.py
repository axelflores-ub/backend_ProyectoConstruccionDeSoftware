# El precio de compra pasó a proveedor_productos y el alta de producto ya no
# envía precio: se le da un default para que deje de ser obligatorio.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scm", "0002_bloquear_nombre_rubro_duplicado"),
    ]

    operations = [
        migrations.AlterField(
            model_name="producto",
            name="precio",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
