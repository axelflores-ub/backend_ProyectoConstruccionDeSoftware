"""Modelos del módulo SCM (Inventario y movimientos).

Tablas según docs/DER.dbml: rubro, producto y movimiento_inventario.
El stock vive en producto.stock_actual (un solo depósito).
"""

from django.conf import settings
from django.db import models


class Rubro(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "rubro"
        ordering = ["nombre"]
        verbose_name = "Rubro"
        verbose_name_plural = "Rubros"

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=255, blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    rubro = models.ForeignKey(
        Rubro,
        on_delete=models.PROTECT,
        related_name="productos",
        null=True,
        blank=True,
    )
    stock_actual = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=0)

    class Meta:
        db_table = "producto"
        ordering = ["nombre"]
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    @property
    def necesita_reposicion(self):
        return self.stock_actual <= self.stock_minimo


class MovimientoInventario(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        SALIDA = "SALIDA", "Salida"
        AJUSTE = "AJUSTE", "Ajuste"
        DEVOLUCION = "DEVOLUCION", "Devolución"

    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="movimientos"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimientos_inventario",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    cantidad = models.IntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    observacion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "movimiento_inventario"
        ordering = ["-fecha", "-id"]
        verbose_name = "Movimiento de inventario"
        verbose_name_plural = "Movimientos de inventario"

    def __str__(self):
        return f"{self.get_tipo_display()} #{self.pk} - {self.producto.codigo}"
