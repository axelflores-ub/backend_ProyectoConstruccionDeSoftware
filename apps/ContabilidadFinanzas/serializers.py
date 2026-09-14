from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from .models import CierreMensual, Diario, FacturaCabecera, FacturaDetalle, Periodo


class PeriodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Periodo
        fields = ["id", "anio", "mes"]
        validators = [
            UniqueTogetherValidator(
                queryset=Periodo.objects.all(),
                fields=["anio", "mes"],
                message="Ya existe un período para ese año y mes.",
            )
        ]

    def validate_mes(self, value):
        if not 1 <= value <= 12:
            raise serializers.ValidationError("El mes debe estar entre 1 y 12.")
        return value


class CierreMensualSerializer(serializers.ModelSerializer):
    class Meta:
        model = CierreMensual
        fields = ["id", "periodo", "fecha_cierre", "estado"]
        read_only_fields = ["fecha_cierre"]

    def validate(self, attrs):
        estado = attrs.get("estado", getattr(self.instance, "estado", None))
        if estado == CierreMensual.Estado.CERRADO and not attrs.get("fecha_cierre"):
            attrs["fecha_cierre"] = timezone.now()
        return attrs


class DiarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diario
        fields = ["id", "cierre_mensual", "fecha", "descripcion"]

    def validate_cierre_mensual(self, value):
        if value.estado == CierreMensual.Estado.CERRADO:
            raise serializers.ValidationError(
                "No se pueden registrar asientos en un cierre mensual ya cerrado."
            )
        return value


class FacturaDetalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacturaDetalle
        fields = ["id", "producto_id", "cantidad", "precio_unitario", "subtotal"]
        read_only_fields = ["subtotal"]

    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a cero.")
        return value


class FacturaCabeceraSerializer(serializers.ModelSerializer):
    detalles = FacturaDetalleSerializer(many=True)

    class Meta:
        model = FacturaCabecera
        fields = [
            "id",
            "orden_venta_id",
            "orden_compra_id",
            "diario",
            "tipo",
            "numero",
            "fecha",
            "impuestos",
            "subtotal",
            "total",
            "detalles",
        ]
        read_only_fields = ["subtotal", "total"]

    def validate(self, attrs):
        tipo = attrs.get("tipo", getattr(self.instance, "tipo", None))
        orden_venta_id = attrs.get(
            "orden_venta_id", getattr(self.instance, "orden_venta_id", None)
        )
        orden_compra_id = attrs.get(
            "orden_compra_id", getattr(self.instance, "orden_compra_id", None)
        )
        if tipo == FacturaCabecera.Tipo.VENTA and not orden_venta_id:
            raise serializers.ValidationError(
                {"orden_venta_id": "Requerido para facturas de tipo VENTA."}
            )
        if tipo == FacturaCabecera.Tipo.COMPRA and not orden_compra_id:
            raise serializers.ValidationError(
                {"orden_compra_id": "Requerido para facturas de tipo COMPRA."}
            )
        detalles = attrs.get("detalles")
        if detalles is not None and len(detalles) == 0:
            raise serializers.ValidationError(
                {"detalles": "La factura debe tener al menos un detalle."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        detalles_data = validated_data.pop("detalles")
        factura = FacturaCabecera.objects.create(**validated_data)
        self._guardar_detalles(factura, detalles_data)
        factura.recalcular_totales()
        factura.save(update_fields=["subtotal", "total"])
        return factura

    @transaction.atomic
    def update(self, instance, validated_data):
        detalles_data = validated_data.pop("detalles", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if detalles_data is not None:
            instance.detalles.all().delete()
            self._guardar_detalles(instance, detalles_data)
        instance.recalcular_totales()
        instance.save()
        return instance

    @staticmethod
    def _guardar_detalles(factura, detalles_data):
        for detalle_data in detalles_data:
            detalle = FacturaDetalle(factura=factura, **detalle_data)
            detalle.recalcular_subtotal()
            detalle.save()
