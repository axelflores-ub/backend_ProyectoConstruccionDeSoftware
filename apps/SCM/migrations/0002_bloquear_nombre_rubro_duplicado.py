from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("SCM", "0001_modelos_iniciales"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rubro",
            name="nombre",
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
