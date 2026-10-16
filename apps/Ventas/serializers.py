# Serializers del módulo (DRF): traducen JSON <-> objetos y validan formato.
# Las reglas de negocio (stock, estados, devoluciones) viven en services.py.
from decimal import Decimal

from rest_framework import serializers

from . import services
from .models import (
    Anulacion,
    Cliente,
    DetalleNotaCredito,
    EstadoOrdenVenta,
    NotaCredito,
    OrdenVenta,
    OrdenVentaDetalle,
)


def _usuario_autenticado(request):
    """Devuelve el usuario de la request si está autenticado, o None."""
    usuario = getattr(request, "user", None)
    return usuario if getattr(usuario, "is_authenticated", False) else None


def _validar_comprobante_unico(valor, instancia=None):
    """Un número de comprobante vacío se guarda como NULL; repetido es un conflicto (409)."""
    if not valor:
        return None
    existentes = OrdenVenta.objects.filter(numero_comprobante=valor)
    if instancia is not None:
        existentes = existentes.exclude(pk=instancia.pk)
    if existentes.exists():
        raise services.Conflicto(
            "Ya existe una orden de venta con ese número de comprobante.",
            codigo="comprobante_duplicado",
        )
    return valor


class CuitField(serializers.CharField):
    """CUIT estandarizado: acepta '20-12345678-9' o '20123456789' y lo guarda sin guiones."""

    default_error_messages = {"cuit_invalido": "El CUIT debe tener 11 dígitos."}

    def to_internal_value(self, data):
        cuit = services.normalizar_cuit(super().to_internal_value(data))
        if len(cuit) != 11:
            self.fail("cuit_invalido")
        return cuit


class ClienteSerializer(serializers.ModelSerializer):
    """Serializer del cliente. id_cliente es solo lectura (autogenerado).
    La baja lógica se hace con PATCH {"estado": "OF"}."""

    cuit = CuitField()

    class Meta:
        model = Cliente
        fields = [
            "id_cliente",
            "nombre",
            "telefono",
            "email",
            "direccion",
            "cuit",
            "condicion_iva",
            "estado",
        ]
        read_only_fields = ["id_cliente"]

    def validate_cuit(self, cuit):
        existentes = Cliente.objects.filter(cuit=cuit)
        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise services.Conflicto("Ya existe un cliente con ese CUIT.", codigo="cuit_duplicado")
        return cuit


class EstadoOrdenVentaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoOrdenVenta
        fields = ["id", "nombre", "descripcion"]


class OrdenVentaDetalleItemSerializer(serializers.ModelSerializer):
    """Ítem de la orden: el cliente envía producto, cantidad y descuento; el precio
    unitario lo toma el servidor del producto."""

    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrdenVentaDetalle
        fields = [
            "id",
            "producto",
            "producto_nombre",
            "cantidad",
            "precio_unitario",
            "descuento",
            "subtotal",
        ]
        read_only_fields = ["precio_unitario"]
        extra_kwargs = {
            "cantidad": {"min_value": 1},
            "descuento": {"min_value": Decimal("0")},
        }


class OrdenVentaDetalleSerializer(serializers.ModelSerializer):
    """Consulta (solo lectura) de los detalles de órdenes."""

    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrdenVentaDetalle
        fields = [
            "id",
            "orden_venta",
            "producto",
            "producto_nombre",
            "cantidad",
            "precio_unitario",
            "descuento",
            "subtotal",
        ]
        read_only_fields = ["precio_unitario"]


class OrdenVentaSerializer(serializers.ModelSerializer):
    """Generar una orden de venta. El cliente NO se elige: se obtiene por `cuit`.
    La fecha la completa el servidor. Request y response usan `detalles`."""

    cuit = CuitField(write_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    cliente_cuit = serializers.CharField(source="cliente.cuit", read_only=True)
    estado_nombre = serializers.CharField(source="estado.nombre", read_only=True)
    detalles = OrdenVentaDetalleItemSerializer(many=True)

    class Meta:
        model = OrdenVenta
        fields = [
            "id",
            "cuit",
            "cliente",
            "cliente_nombre",
            "cliente_cuit",
            "forma_pago",
            "numero_comprobante",
            "tipo_comprobante",
            "estado",
            "estado_nombre",
            "fecha",
            "total",
            "detalles",
        ]
        read_only_fields = ["cliente", "estado", "fecha", "total"]
        extra_kwargs = {"numero_comprobante": {"validators": []}}

    def validate_numero_comprobante(self, valor):
        return _validar_comprobante_unico(valor)

    def validate_detalles(self, detalles):
        if not detalles:
            raise serializers.ValidationError("La orden debe tener al menos un producto.")
        return detalles

    def create(self, validated_data):
        detalles = validated_data.pop("detalles")
        cuit = validated_data.pop("cuit")
        return services.registrar_orden_venta(
            cuit=cuit,
            datos=validated_data,
            detalles=detalles,
            usuario=_usuario_autenticado(self.context.get("request")),
        )


class OrdenVentaUpdateSerializer(serializers.ModelSerializer):
    """Modificar forma de pago y datos del comprobante, solo mientras la orden esté
    'Pendiente'. El cliente, el estado, la fecha y el total no se editan."""

    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    estado_nombre = serializers.CharField(source="estado.nombre", read_only=True)

    class Meta:
        model = OrdenVenta
        fields = [
            "id",
            "cliente",
            "cliente_nombre",
            "forma_pago",
            "numero_comprobante",
            "tipo_comprobante",
            "estado",
            "estado_nombre",
            "fecha",
            "total",
        ]
        read_only_fields = ["cliente", "estado", "fecha", "total"]
        extra_kwargs = {"numero_comprobante": {"validators": []}}

    def validate_numero_comprobante(self, valor):
        return _validar_comprobante_unico(valor, self.instance)

    def validate(self, attrs):
        if self.instance.estado.nombre != EstadoOrdenVenta.PENDIENTE:
            raise services.Conflicto(
                f"Solo se puede modificar una orden en estado '{EstadoOrdenVenta.PENDIENTE}' "
                f"(estado actual: '{self.instance.estado.nombre}').",
                codigo="orden_no_modificable",
            )
        return attrs


class AnulacionSerializer(serializers.ModelSerializer):
    """Anula una orden de venta (botón 'Anular' en Devoluciones)."""

    class Meta:
        model = Anulacion
        fields = ["id", "orden_venta", "motivo", "detalle", "fecha"]
        read_only_fields = ["fecha"]
        # La regla "una orden se anula una sola vez" la valida services.anular_orden_venta
        # (409 con código propio); se desactiva el validador automático de OneToOne (400).
        extra_kwargs = {"orden_venta": {"validators": []}}

    def create(self, validated_data):
        return services.anular_orden_venta(
            orden_venta=validated_data["orden_venta"],
            motivo=validated_data["motivo"],
            detalle=validated_data.get("detalle", ""),
        )


class DetalleNotaCreditoItemSerializer(serializers.ModelSerializer):
    """Ítem devuelto: producto, cantidad devuelta y destino."""

    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = DetalleNotaCredito
        fields = ["id", "producto", "producto_nombre", "cantidad_devuelta", "destino"]
        extra_kwargs = {"cantidad_devuelta": {"min_value": 1}}


class DetalleNotaCreditoSerializer(serializers.ModelSerializer):
    """Consulta (solo lectura) de los detalles de notas de crédito."""

    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = DetalleNotaCredito
        fields = [
            "id",
            "nota_credito",
            "producto",
            "producto_nombre",
            "cantidad_devuelta",
            "destino",
        ]


class NotaCreditoSerializer(serializers.ModelSerializer):
    """Registrar una devolución. El monto lo calcula el servidor (es solo lectura)."""

    detalles = DetalleNotaCreditoItemSerializer(many=True)

    class Meta:
        model = NotaCredito
        fields = ["id", "orden_venta", "monto", "saldo_a_favor", "fecha", "detalles"]
        read_only_fields = ["monto", "fecha"]

    def validate_detalles(self, detalles):
        if not detalles:
            raise serializers.ValidationError("La nota de crédito debe tener al menos un producto.")
        return detalles

    def create(self, validated_data):
        return services.registrar_nota_credito(
            orden_venta=validated_data["orden_venta"],
            saldo_a_favor=validated_data.get("saldo_a_favor", False),
            detalles=validated_data["detalles"],
            usuario=_usuario_autenticado(self.context.get("request")),
        )
