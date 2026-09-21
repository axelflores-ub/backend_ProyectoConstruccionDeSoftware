"""
Modelos de datos para el módulo CompraYProveedores.

Define las estructuras de datos (tablas de base de datos) para gestionar:
- Proveedores: información de los proveedores de la empresa
- Estados de Orden de Compra: catálogo de posibles estados
- Órdenes de Compra: cabeceras de las órdenes
- Detalles de Orden de Compra: renglones/líneas de cada orden
"""

from django.db import models

# Estados del catálogo estado_orden_compra (los carga la migración 0003).
ESTADO_PENDIENTE = "Pendiente"
ESTADO_APROBADA = "Aprobada"
ESTADO_RECHAZADA = "Rechazada"
ESTADO_RECIBIDA = "Recibida"
ESTADOS_ORDEN_COMPRA = [
    ESTADO_PENDIENTE,
    ESTADO_APROBADA,
    ESTADO_RECHAZADA,
    ESTADO_RECIBIDA,
]


class Proveedor(models.Model):
    proveedor_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    apellido = models.CharField(max_length=150, blank=True)
    email = models.EmailField(max_length=150, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    cuit = models.CharField(max_length=13, unique=True)
    direccion = models.CharField(max_length=200, blank=True)
    producto_id = models.PositiveIntegerField(
        unique=True,
        help_text="1 a 1 con Producto.",
    )

    class Meta:
        db_table = "proveedor"
        ordering = ["nombre", "apellido"]
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

    def __str__(self):
        extra = f" {self.apellido}" if self.apellido else ""
        return f"{self.nombre}{extra}"


class EstadoOrdenCompra(models.Model):
    estadoordencompra_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "estado_orden_compra"
        ordering = ["estadoordencompra_id"]
        verbose_name = "Estado de orden de compra"
        verbose_name_plural = "Estados de orden de compra"

    def __str__(self):
        return self.nombre


class OrdenCompra(models.Model):
    ordencompra_id = models.AutoField(primary_key=True)
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name="ordenes_compra",
        db_column="proveedor_id",
    )
    estado = models.ForeignKey(
        EstadoOrdenCompra,
        on_delete=models.PROTECT,
        related_name="ordenes_compra",
        db_column="estado_id",
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
    ordencompradetalle_id = models.AutoField(primary_key=True)
    orden_compra = models.ForeignKey(
        OrdenCompra,
        on_delete=models.CASCADE,
        related_name="detalles",
        db_column="ordencompra_id",
    )
    producto_id = models.PositiveIntegerField()
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="preciounitario",
    )

    class Meta:
        db_table = "orden_compra_detalle"
        verbose_name = "Detalle de orden de compra"
        verbose_name_plural = "Detalles de orden de compra"

    def __str__(self):
        return f"OC #{self.orden_compra_id} - producto {self.producto_id}"