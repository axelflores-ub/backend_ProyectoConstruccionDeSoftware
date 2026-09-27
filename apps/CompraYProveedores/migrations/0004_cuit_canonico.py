from django.db import migrations

from apps.CompraYProveedores.cuit import cuit_canonico


def canonizar_cuits(apps, schema_editor):
    Proveedor = apps.get_model("compra_y_proveedores", "Proveedor")
    grupos = {}
    invalidos = []
    for proveedor in Proveedor.objects.all():
        canonico = cuit_canonico(proveedor.cuit)
        if canonico is None:
            invalidos.append(proveedor.pk)
            continue
        grupos.setdefault(canonico, []).append(proveedor)

    if invalidos:
        ids = ", ".join(str(pk) for pk in invalidos)
        raise RuntimeError(f"CUIT que no tiene 11 dígitos en proveedor_id: {ids}")

    choques = {
        canonico: [proveedor.pk for proveedor in filas]
        for canonico, filas in grupos.items()
        if len(filas) > 1
    }
    if choques:
        detalle = "; ".join(
            f"{canonico} en proveedor_id {ids}" for canonico, ids in choques.items()
        )
        raise RuntimeError(
            "Hay proveedores con el mismo CUIT y distinta escritura. "
            f"Borrá el duplicado y volvé a migrar: {detalle}"
        )

    for canonico, filas in grupos.items():
        proveedor = filas[0]
        if proveedor.cuit != canonico:
            proveedor.cuit = canonico
            proveedor.save(update_fields=["cuit"])


class Migration(migrations.Migration):
    dependencies = [
        ("compra_y_proveedores", "0003_estados_orden_compra_iniciales"),
    ]

    operations = [
        migrations.RunPython(canonizar_cuits, migrations.RunPython.noop),
    ]
