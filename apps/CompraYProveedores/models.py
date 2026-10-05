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

# proveedor_productos.activo: 1 vigente, 0 dado de baja. La fila no se borra.
VINCULO_ACTIVO = 1
VINCULO_INACTIVO = 0


class ProveedorProducto(models.Model):
    """Vínculo proveedor–producto. El precio de compra es de esta relación."""

    proveedor = models.ForeignKey(
        "Proveedor",
        on_delete=models.CASCADE,
        db_column="proveedor_id",
        related_name="vinculos",
    )
    producto = models.ForeignKey(
        "scm.Producto",
        on_delete=models.CASCADE,
        db_column="producto_id",
        related_name="vinculos_proveedor",
    )
    precio_compra = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    activo = models.PositiveSmallIntegerField(
        default=VINCULO_ACTIVO,
        choices=[(VINCULO_ACTIVO, "Activo"), (VINCULO_INACTIVO, "De baja")],
    )

    class Meta:
        db_table = "proveedor_productos"
        ordering = ["producto_id"]
        verbose_name = "Producto del proveedor"
        verbose_name_plural = "Productos del proveedor"
        constraints = [
            models.UniqueConstraint(
                fields=["proveedor", "producto"],
                name="proveedor_productos_proveedor_id_producto_id_022f31af_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(activo__in=[VINCULO_ACTIVO, VINCULO_INACTIVO]),
                name="proveedor_productos_activo_es_0_o_1",
            ),
        ]

    def __str__(self):
        return f"Proveedor {self.proveedor_id} - producto {self.producto_id}"


class Proveedor(models.Model):
    proveedor_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    apellido = models.CharField(max_length=150, blank=True)
    email = models.EmailField(max_length=150, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    cuit = models.CharField(max_length=13, unique=True)
    direccion = models.CharField(max_length=200, blank=True)
    productos = models.ManyToManyField(
        "scm.Producto",
        through="ProveedorProducto",
        through_fields=("proveedor", "producto"),
        related_name="proveedores",
        blank=True,
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
