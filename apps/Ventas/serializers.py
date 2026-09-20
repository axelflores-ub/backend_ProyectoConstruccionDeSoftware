# Serializers del módulo (DRF): traducen JSON <-> objetos y validan.
from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import Cliente, EstadoOrdenVenta, OrdenVenta, OrdenVentaDetalle, Producto


class ClienteSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo Cliente.
    id_cliente se expone como solo lectura ya que es autogenerado.
    """
 
    class Meta:
        model = Cliente
        fields = ['id_cliente', 'nombre', 'telefono', 'email', 'direccion', 'estado']
        read_only_fields = ['id_cliente']

class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = ["id", "nombre", "precio", "stock"]


class EstadoOrdenVentaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoOrdenVenta
        fields = ["id", "nombre", "descripcion"]


class OrdenVentaDetalleInputSerializer(serializers.Serializer):
    """Ítems que llegan al registrar la orden de venta."""

    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())
    cantidad = serializers.IntegerField(min_value=1)


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
            "subtotal",
        ]
        read_only_fields = ["precio_unitario"]


class OrdenVentaSerializer(serializers.ModelSerializer):
    """Alta de la orden de venta: valida stock, calcula el total y descuenta stock."""

    detalles = OrdenVentaDetalleInputSerializer(many=True, write_only=True)
    items = OrdenVentaDetalleSerializer(source="detalles", many=True, read_only=True)
    estado_nombre = serializers.CharField(source="estado.nombre", read_only=True)

    class Meta:
        model = OrdenVenta
        fields = [
            "id",
            "cliente",
            "forma_pago",
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
        detalles = attrs.get("detalles", [])
        acumulado = {}
        for item in detalles:
            producto = item["producto"]
            acumulado[producto.id] = acumulado.get(producto.id, 0) + item["cantidad"]
        for producto_id, cantidad in acumulado.items():
            producto = Producto.objects.get(pk=producto_id)
            if producto.stock < cantidad:
                raise serializers.ValidationError(
                    {
                        "detalles": (
                            f"Stock insuficiente para '{producto.nombre}' "
                            f"(disponible: {producto.stock})."
                        )
                    }
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        detalles_data = validated_data.pop("detalles")
        request = self.context.get("request")
        usuario = getattr(request, "user", None)
        usuario = usuario if getattr(usuario, "is_authenticated", False) else None

        # Toda orden nueva arranca en el estado "Pendiente" (se crea si no existe).
        estado_inicial, _ = EstadoOrdenVenta.objects.get_or_create(nombre="Pendiente")

        orden = OrdenVenta.objects.create(
            usuario=usuario, estado=estado_inicial, **validated_data
        )

        total = Decimal("0")
        for item in detalles_data:
            producto = item["producto"]
            cantidad = item["cantidad"]
            OrdenVentaDetalle.objects.create(
                orden_venta=orden,
                producto=producto,
                cantidad=cantidad,
                precio_unitario=producto.precio,
            )
            total += producto.precio * cantidad
            producto.stock -= cantidad
            producto.save(update_fields=["stock"])

        orden.total = total
        orden.save(update_fields=["total"])
        return orden


class OrdenVentaUpdateSerializer(serializers.ModelSerializer):
    """Modificación de una orden ya registrada: cliente, forma de pago y estado.
    El detalle de ítems no se reenvía acá; se administra desde OrdenVentaDetalle."""

    class Meta:
        model = OrdenVenta
        fields = ["id", "cliente", "forma_pago", "estado", "fecha", "total"]
        read_only_fields = ["fecha", "total"]
