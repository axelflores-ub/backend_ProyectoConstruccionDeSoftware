# Modelos (tablas) del módulo. Definí acá tus clases que heredan de models.Model.
from django.conf import settings
from django.db import models


class Cliente(models.Model):
    """
    Modelo que representa la tabla 'clientes'.
    La baja lógica se maneja actualizando el campo 'estado' a 'OF'.
    """
 
    ESTADO_ACTIVO = 'AC'
    ESTADO_BAJA = 'OF'
 
    id_cliente = models.AutoField(primary_key=True, db_column='id_cliente')
    nombre = models.CharField(max_length=150, db_column='nombre')
    telefono = models.CharField(max_length=50, db_column='telefono', blank=True, null=True)
    email = models.CharField(max_length=100, db_column='email', blank=True, null=True)
    direccion = models.CharField(max_length=200, db_column='direccion', blank=True, null=True)
    estado = models.CharField(max_length=2, db_column='estado', default=ESTADO_ACTIVO)
 
    class Meta:
        db_table = 'clientes'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['id_cliente']
 
    def __str__(self):
        return f'{self.id_cliente} - {self.nombre}'



class Producto(models.Model):
    """Nota: se asume acá como referencia simple para poder registrar el detalle
    de la orden de venta. Si en tu proyecto el catálogo de productos vive en otro
    módulo (p. ej. Inventario), reemplazá esta FK por la de ese módulo."""

    nombre = models.CharField(max_length=150)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self):
        return f"{self.nombre} (stock: {self.stock})"


class EstadoOrdenVenta(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Estado de orden de venta"
        verbose_name_plural = "Estados de orden de venta"

    def __str__(self):
        return self.nombre


class OrdenVenta(models.Model):
    class FormaPago(models.TextChoices):
        EFECTIVO = "EFECTIVO", "Efectivo"
        TARJETA = "TARJETA", "Tarjeta"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"

    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="ordenes_venta"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ordenes_venta_registradas",
        null=True,
        blank=True,
    )
    estado = models.ForeignKey(
        EstadoOrdenVenta, on_delete=models.PROTECT, related_name="ordenes_venta"
    )
    forma_pago = models.CharField(max_length=20, choices=FormaPago.choices)
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Orden de venta"
        verbose_name_plural = "Ordenes de venta"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Orden #{self.pk} - {self.cliente} - {self.estado}"

    def calcular_total(self):
        total = sum(d.subtotal for d in self.detalles.all())
        self.total = total
        return total


class OrdenVentaDetalle(models.Model):
    orden_venta = models.ForeignKey(
        OrdenVenta, on_delete=models.CASCADE, related_name="detalles"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="detalles_orden_venta"
    )
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Detalle de orden de venta"
        verbose_name_plural = "Detalles de orden de venta"

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario