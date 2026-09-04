# Modelos (tablas) del módulo. Definí acá tus clases que heredan de models.Model.

"""
Modelos del módulo CompraYProveedores.
Fuente de verdad: docs/DER.dbml
"""

from django.db import models


class Proveedor(models.Model):
    """Empresa o persona que nos vende materiales. Tabla DER: proveedor."""

    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(max_length=150, blank=True)
    direccion = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "proveedor"
        ordering = ["nombre"]
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

    def __str__(self):
        return self.nombre


class EstadoOrdenCompra(models.Model):
    """Catálogo de estados. Tabla DER: estado_orden_compra."""

    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "estado_orden_compra"
        ordering = ["id"]
        verbose_name = "Estado de orden de compra"
        verbose_name_plural = "Estados de orden de compra"

    def __str__(self):
        return self.nombre


class OrdenCompra(models.Model):
    """Cabecera de OC. Tabla DER: orden_compra."""

    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name="ordenes_compra",
    )
    estado = models.ForeignKey(
        EstadoOrdenCompra,
        on_delete=models.PROTECT,
        related_name="ordenes_compra",
    )
    fecha = models.DateTimeField()
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "orden_compra"
        ordering = ["-fecha"]
        verbose_name = "Orden de compra"
        verbose_name_plural = "Órdenes de compra"

    def __str__(self):
        return f"OC #{self.pk} - {self.proveedor}"


class OrdenCompraDetalle(models.Model):
    """
    Renglón de una OC. Tabla DER: orden_compra_detalle.

    producto_id es Integer (no FK) mientras SCM no publique Producto.
    La columna se llama igual que en el DER. Cuando exista scm.Producto:

        producto = models.ForeignKey(
            "scm.Producto",
            on_delete=models.PROTECT,
            related_name="detalles_orden_compra",
        )
    """

    orden_compra = models.ForeignKey(
        OrdenCompra,
        on_delete=models.CASCADE,
        related_name="detalles",
    )
    producto_id = models.PositiveIntegerField()
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "orden_compra_detalle"
        verbose_name = "Detalle de orden de compra"
        verbose_name_plural = "Detalles de orden de compra"

    def __str__(self):
        return f"OC #{self.orden_compra_id} - producto {self.producto_id}"