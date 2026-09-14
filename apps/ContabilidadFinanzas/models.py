from django.db import models


class Periodo(models.Model):
    anio = models.PositiveIntegerField(verbose_name="año")
    mes = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "periodo"
        verbose_name = "período"
        verbose_name_plural = "períodos"
        ordering = ["-anio", "-mes"]
        constraints = [
            models.UniqueConstraint(fields=["anio", "mes"], name="uq_periodo_anio_mes"),
        ]

    def __str__(self):
        return f"{self.mes:02d}/{self.anio}"


class CierreMensual(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = "ABIERTO", "Abierto"
        CERRADO = "CERRADO", "Cerrado"

    periodo = models.ForeignKey(
        Periodo, on_delete=models.PROTECT, related_name="cierres_mensuales"
    )
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.ABIERTO
    )

    class Meta:
        db_table = "cierre_mensual"
        verbose_name = "cierre mensual"
        verbose_name_plural = "cierres mensuales"
        ordering = ["-periodo__anio", "-periodo__mes"]

    def __str__(self):
        return f"Cierre {self.periodo} ({self.estado})"


class Diario(models.Model):
    cierre_mensual = models.ForeignKey(
        CierreMensual, on_delete=models.PROTECT, related_name="diarios"
    )
    fecha = models.DateTimeField()
    descripcion = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "diario"
        verbose_name = "diario"
        verbose_name_plural = "diarios"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Diario #{self.pk}"


class FacturaCabecera(models.Model):
    class Tipo(models.TextChoices):
        VENTA = "VENTA", "Venta"
        COMPRA = "COMPRA", "Compra"

    # Sin FK real todavía: Ventas y CompraYProveedores no tienen sus modelos.
    # Cuando existan OrdenVenta/OrdenCompra, reemplazar por ForeignKey("ventas.OrdenVenta", ...)
    # y ForeignKey("compra_y_proveedores.OrdenCompra", ...) con la migración correspondiente.
    orden_venta_id = models.PositiveIntegerField(null=True, blank=True)
    orden_compra_id = models.PositiveIntegerField(null=True, blank=True)
    diario = models.ForeignKey(
        Diario,
        on_delete=models.PROTECT,
        related_name="facturas",
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    numero = models.CharField(max_length=50)
    fecha = models.DateTimeField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    impuestos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "factura_cabecera"
        verbose_name = "factura"
        verbose_name_plural = "facturas"
        ordering = ["-fecha"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "numero"], name="uq_factura_tipo_numero"),
        ]

    def __str__(self):
        return f"Factura {self.tipo} {self.numero}"

    def recalcular_totales(self):
        self.subtotal = sum(
            (detalle.subtotal for detalle in self.detalles.all()), start=0
        )
        self.total = self.subtotal + self.impuestos
        return self.total


class FacturaDetalle(models.Model):
    factura = models.ForeignKey(
        FacturaCabecera, on_delete=models.CASCADE, related_name="detalles"
    )
    # Sin FK real todavía: SCM no tiene su modelo Producto.
    # Reemplazar por ForeignKey("scm.Producto", ...) cuando exista, con su migración.
    producto_id = models.PositiveIntegerField()
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "factura_detalle"
        verbose_name = "detalle de factura"
        verbose_name_plural = "detalles de factura"
        ordering = ["id"]

    def __str__(self):
        return f"Detalle #{self.pk} de factura {self.factura_id}"

    def recalcular_subtotal(self):
        self.subtotal = self.cantidad * self.precio_unitario
        return self.subtotal
