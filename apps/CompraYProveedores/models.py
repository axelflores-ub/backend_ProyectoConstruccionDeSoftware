"""
Modelos de datos para el módulo CompraYProveedores.

Define las estructuras de datos (tablas de base de datos) para gestionar:
- Proveedores: información de los proveedores de la empresa
- Estados de Orden de Compra: catálogo de posibles estados
- Órdenes de Compra: cabeceras de las órdenes
- Detalles de Orden de Compra: renglones/líneas de cada orden
"""

from django.db import models


class Proveedor(models.Model):
    """Modelo de Proveedor.
    
    Representa un proveedor de la empresa con su informacion de contacto.
    
    Atributos:
        proveedor_id: Identificador unico del proveedor (clave primaria).
        nombre: Nombre o razon social del proveedor (requerido).
        apellido: Apellido o complemento del nombre (opcional).
        email: Correo electronico de contacto (opcional).
        telefono: Numero de telefono (opcional).
        cuit: CUIT/NIT del proveedor (unico y requerido).
        direccion: Direccion fisica (opcional).
    """

    proveedor_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    apellido = models.CharField(max_length=150, blank=True)
    email = models.EmailField(max_length=150, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    cuit = models.CharField(max_length=13, unique=True)
    direccion = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "proveedor"
        ordering = ["nombre", "apellido"]
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

    def __str__(self):
        """Retorna la representacion en string del proveedor (nombre y apellido)."""
        extra = f" {self.apellido}" if self.apellido else ""
        return f"{self.nombre}{extra}"


class EstadoOrdenCompra(models.Model):
    """Catalogo de estados posibles para una Orden de Compra.
    
    Define los estados que puede tener una orden (ej: Pendiente, Confirmada, Rechazada, etc.).
    
    Atributos:
        estadoordencompra_id: Identificador unico del estado (clave primaria).
        nombre: Nombre del estado (unico y requerido).
    """

    estadoordencompra_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "estado_orden_compra"
        ordering = ["estadoordencompra_id"]
        verbose_name = "Estado de orden de compra"
        verbose_name_plural = "Estados de orden de compra"

    def __str__(self):
        """Retorna el nombre del estado."""
        return self.nombre


class OrdenCompra(models.Model):
    """Cabecera de una Orden de Compra.
    
    Representa una orden de compra completa con sus datos generales.
    Los renglones especificos se almacenan en OrdenCompraDetalle.
    
    Atributos:
        ordencompra_id: Identificador unico de la orden (clave primaria).
        proveedor: Referencia al Proveedor (clave foranea, no eliminable).
        estado: Referencia al EstadoOrdenCompra (clave foranea, no eliminable).
        fecha: Fecha y hora de la orden (requerida).
        total: Monto total de la orden en moneda (requerida).
    """

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
        """Retorna una representacion legible de la orden (ID y proveedor)."""
        return f"OC #{self.pk} - {self.proveedor}"


class OrdenCompraDetalle(models.Model):
    """Detalle/Renglon de una Orden de Compra.
    
    Representa cada linea de la orden con informacion del producto, cantidad y precio.
    Atributos:
        ordencompradetalle_id: Identificador unico del renglon (clave primaria).
        orden_compra: Referencia a la OrdenCompra padre (clave foranea, eliminacion en cascada).
        producto_id: Identificador del producto (almacenado como entero hasta que exista modelo Producto de SCM).
        cantidad: Cantidad de unidades del producto en este renglon (requerida).
        precio_unitario: Precio por unidad del producto (requerido).
    """

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
        """Retorna una representacion legible del detalle (OC y producto)."""
        return f"OC #{self.orden_compra_id} - producto {self.producto_id}"