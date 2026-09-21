from rest_framework import serializers

from apps.SCM import services
from apps.SCM.models import MovimientoInventario, Producto, Rubro


class RubroSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rubro
        fields = ["id", "nombre", "descripcion"]


class ProductoSerializer(serializers.ModelSerializer):
    rubro_nombre = serializers.CharField(source="rubro.nombre", read_only=True)
    necesita_reposicion = serializers.BooleanField(read_only=True)

    class Meta:
        model = Producto
        fields = [
            "id",
            "codigo",
            "nombre",
            "descripcion",
            "precio",
            "rubro",
            "rubro_nombre",
            "stock_actual",
            "stock_minimo",
            "necesita_reposicion",
        ]
        # El stock solo cambia a través de movimientos de inventario.
        read_only_fields = ["stock_actual"]

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a cero.")
        return value

    def validate_stock_minimo(self, value):
        if value < 0:
            raise serializers.ValidationError("El stock mínimo no puede ser negativo.")
        return value


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    producto_codigo = serializers.CharField(source="producto.codigo", read_only=True)

    class Meta:
        model = MovimientoInventario
        fields = [
            "id",
            "producto",
            "producto_codigo",
            "usuario",
            "tipo",
            "cantidad",
            "fecha",
            "observacion",
        ]
        read_only_fields = ["usuario", "fecha"]

    def validate_cantidad(self, value):
        if value == 0:
            raise serializers.ValidationError("La cantidad no puede ser cero.")
        return value

    def validate(self, attrs):
        tipo = attrs.get("tipo")
        cantidad = attrs.get("cantidad")
        if (
            tipo != MovimientoInventario.Tipo.AJUSTE
            and cantidad is not None
            and cantidad < 0
        ):
            raise serializers.ValidationError(
                {"cantidad": "Solo los ajustes admiten cantidad negativa."}
            )
        return attrs

    def create(self, validated_data):
        return services.registrar_movimiento(
            producto=validated_data["producto"],
            tipo=validated_data["tipo"],
            cantidad=validated_data["cantidad"],
            usuario=self.context["request"].user,
            observacion=validated_data.get("observacion", ""),
        )
