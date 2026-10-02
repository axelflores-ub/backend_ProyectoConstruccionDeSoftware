# Serializers del módulo (DRF): traducen JSON <-> objetos y validan.
# La lógica de negocio (stock, totales, estados) vive en services.py.
from decimal import Decimal

from rest_framework import serializers

from apps.SCM.models import Producto

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


class ClienteSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo Cliente.
    id_cliente se expone como solo lectura ya que es autogenerado.
    """

    class Meta:
        model = Cliente
        fields = [
            "id_cliente",
            "nombre",
            "telefono",
            "email",
            "direccion",
            "cuil",
            "condicion_iva",
            "estado",
        ]
        read_only_fields = ["id_cliente"]


class EstadoOrdenVentaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoOrdenVenta
        fields = ["id", "nombre", "descripcion"]


class OrdenVentaDetalleInputSerializer(serializers.Serializer):
    """Ítems que llegan al registrar la orden de venta."""

    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())
    cantidad = serializers.IntegerField(min_value=1)
    descuento = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default=Decimal("0"),
        min_value=Decimal("0"),
    )


class OrdenVentaDetalleSerializer(serializers.ModelSerializer):
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
    """Alta de la orden de venta. La lógica (stock, total, estado inicial) está en
    services.registrar_orden_venta."""

    detalles = OrdenVentaDetalleInputSerializer(many=True, write_only=True)
    items = OrdenVentaDetalleSerializer(source="detalles", many=True, read_only=True)
    estado_nombre = serializers.CharField(source="estado.nombre", read_only=True)

    class Meta:
        model = OrdenVenta
        fields = [
            "id",
            "cliente",
            "forma_pago",
            "numero_comprobante",
            "tipo_comprobante",
            "estado",
            "estado_nombre",
            "fecha",
            "total",
            "detalles",
            "items",
        ]
        read_only_fields = ["estado", "fecha", "total"]

    def validate_detalles(self, detalles):
        if not detalles:
            raise serializers.ValidationError("La orden debe tener al menos un producto.")
        return detalles

    def validate(self, attrs):
        # Chequeo "optimista" para devolver un error temprano y claro.
        # El chequeo que realmente vale (con lock) se repite en el service,
        # ya que entre validate() y create() el stock puede haber cambiado.
        acumulado = services.acumular_cantidades(attrs.get("detalles", []))
        for producto_id, cantidad in acumulado.items():
            producto = Producto.objects.get(pk=producto_id)
            if producto.stock_actual < cantidad:
                raise serializers.ValidationError(
                    {
                        "detalles": (
                            f"Stock insuficiente para '{producto.nombre}' "
                            f"(disponible: {producto.stock_actual})."
                        )
                    }
                )
        return attrs

    def create(self, validated_data):
        detalles = validated_data.pop("detalles")
        usuario = _usuario_autenticado(self.context.get("request"))
        try:
            return services.registrar_orden_venta(
                datos=validated_data, detalles=detalles, usuario=usuario
            )
        except services.StockInsuficienteError as exc:
            raise serializers.ValidationError({"detalles": str(exc)}) from exc


class OrdenVentaUpdateSerializer(serializers.ModelSerializer):
    """Modificación de una orden ya registrada: cliente, forma de pago y estado.
    El detalle de ítems no se reenvía acá; se administra desde OrdenVentaDetalle."""

    class Meta:
        model = OrdenVenta
        fields = [
            "id",
            "cliente",
            "forma_pago",
            "numero_comprobante",
            "tipo_comprobante",
            "estado",
            "fecha",
            "total",
        ]
        read_only_fields = ["fecha", "total"]


class AnulacionSerializer(serializers.ModelSerializer):
    """Anula una orden de venta (botón 'Anular' en Devoluciones).
    Al crearse, repone el stock pendiente y mueve la orden al estado 'Anulada'
    (ver services.anular_orden_venta)."""

    class Meta:
        model = Anulacion
        fields = ["id", "orden_venta", "motivo", "detalle", "fecha"]
        read_only_fields = ["fecha"]

    def validate_orden_venta(self, orden_venta):
        if hasattr(orden_venta, "anulacion"):
            raise serializers.ValidationError("Esta orden ya fue anulada.")
        return orden_venta

    def create(self, validated_data):
        try:
            return services.anular_orden_venta(
                orden_venta=validated_data["orden_venta"],
                motivo=validated_data["motivo"],
                detalle=validated_data.get("detalle"),
                usuario=_usuario_autenticado(self.context.get("request")),
            )
        except services.OperacionInvalidaError as exc:
            raise serializers.ValidationError({"orden_venta": str(exc)}) from exc


class DetalleNotaCreditoInputSerializer(serializers.Serializer):
    """Ítems que llegan al registrar una nota de crédito (qué se devuelve)."""

    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())
    cantidad_devuelta = serializers.IntegerField(min_value=1)
    destino = serializers.ChoiceField(choices=DetalleNotaCredito.Destino.choices)


class DetalleNotaCreditoSerializer(serializers.ModelSerializer):
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
    """Alta de una nota de crédito (devolución). La validación de cantidades, la reposición
    de stock y el cambio de estado a 'Devolución parcial' están en
    services.registrar_nota_credito."""

    detalles = DetalleNotaCreditoInputSerializer(many=True, write_only=True)
    items = DetalleNotaCreditoSerializer(source="detalles", many=True, read_only=True)

    class Meta:
        model = NotaCredito
        fields = ["id", "orden_venta", "monto", "saldo_a_favor", "fecha", "detalles", "items"]
        read_only_fields = ["fecha"]

    def validate_detalles(self, detalles):
        if not detalles:
            raise serializers.ValidationError("La nota de crédito debe tener al menos un producto.")
        return detalles

    def create(self, validated_data):
        detalles = validated_data.pop("detalles")
        try:
            return services.registrar_nota_credito(
                orden_venta=validated_data["orden_venta"],
                monto=validated_data["monto"],
                saldo_a_favor=validated_data.get("saldo_a_favor", False),
                detalles=detalles,
                usuario=_usuario_autenticado(self.context.get("request")),
            )
        except services.OperacionInvalidaError as exc:
            raise serializers.ValidationError({"detalles": str(exc)}) from exc
