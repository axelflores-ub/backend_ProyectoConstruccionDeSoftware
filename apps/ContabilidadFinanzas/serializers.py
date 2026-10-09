from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from . import services
from .models import CierreMensual, Diario, FacturaCabecera, FacturaDetalle, Periodo

MENSAJE_IMPORTE_EXCEDIDO = "El importe supera el máximo permitido ($9.999.999.999,99)."


def _validar_cierre_abierto(cierre):
    """Convierte PeriodoCerradoError en ValidationError, para usar dentro de un serializer."""
    try:
        services.asegurar_cierre_abierto(cierre)
    except services.PeriodoCerradoError as exc:
        raise serializers.ValidationError(str(exc)) from exc


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

    def validate_anio(self, value):
        if not services.ANIO_MINIMO <= value <= services.ANIO_MAXIMO:
            raise serializers.ValidationError(
                f"El año debe estar entre {services.ANIO_MINIMO} y {services.ANIO_MAXIMO}."
            )
        return value

    def validate(self, attrs):
        # Un período con el cierre cerrado no se puede modificar.
        if self.instance and self.instance.cierres_mensuales.filter(
            estado=CierreMensual.Estado.CERRADO
        ).exists():
            raise serializers.ValidationError("El período ya está cerrado y no se puede modificar.")
        return attrs


class CierreMensualSerializer(serializers.ModelSerializer):
    class Meta:
        model = CierreMensual
        fields = ["id", "periodo", "fecha_cierre", "estado"]
        read_only_fields = ["periodo", "fecha_cierre"]
        extra_kwargs = {"estado": {"required": True}}

    def validate(self, attrs):
        if self.instance and self.instance.estado == CierreMensual.Estado.CERRADO:
            raise serializers.ValidationError("El período ya está cerrado y no se puede modificar.")
        if attrs["estado"] == CierreMensual.Estado.CERRADO:
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
    """Detalle anidado dentro de la factura: la factura la pone el serializer padre."""

    class Meta:
        model = FacturaDetalle
        fields = ["id", "producto_id", "cantidad", "precio_unitario", "subtotal"]
        read_only_fields = ["subtotal"]

    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a cero.")
        return value

    def validate_precio_unitario(self, value):
        if value < 0:
            raise serializers.ValidationError("El precio unitario no puede ser negativo.")
        return value


class FacturaDetalleConFacturaSerializer(FacturaDetalleSerializer):
    """Detalle como recurso propio: hay que indicar a qué factura pertenece."""

    class Meta(FacturaDetalleSerializer.Meta):
        fields = ["id", "factura", "producto_id", "cantidad", "precio_unitario", "subtotal"]

    def validate_factura(self, factura):
        # No se agregan renglones a una factura de un período cerrado.
        cierre = services.cierre_de_factura(factura)
        if cierre is not None:
            _validar_cierre_abierto(cierre)
        return factura

    def validate(self, attrs):
        # La nueva línea suma al subtotal de la factura: el resultado tiene que entrar en la base.
        factura = attrs["factura"]
        linea = attrs["cantidad"] * attrs["precio_unitario"]
        if factura.subtotal + linea + factura.impuestos > services.MAX_IMPORTE:
            raise serializers.ValidationError(MENSAJE_IMPORTE_EXCEDIDO)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        detalle = FacturaDetalle(**validated_data)
        detalle.recalcular_subtotal()
        detalle.save()
        # Al sumar una línea cambian los totales de la cabecera.
        factura = detalle.factura
        factura.recalcular_totales()
        factura.save(update_fields=["subtotal", "total"])
        return detalle


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

    def validate_diario(self, diario):
        # Si la factura indica su entrada de diario, esa entrada no puede ser de un cierre cerrado.
        if diario is not None:
            _validar_cierre_abierto(diario.cierre_mensual)
        return diario

    def validate_impuestos(self, value):
        if value < 0:
            raise serializers.ValidationError("Los impuestos no pueden ser negativos.")
        return value

    def validate_fecha(self, value):
        # El período de la factura se crea a partir de su fecha: el año tiene que ser válido.
        anio = timezone.localtime(value).year
        if not services.ANIO_MINIMO <= anio <= services.ANIO_MAXIMO:
            raise serializers.ValidationError(
                f"El año de la fecha debe estar entre {services.ANIO_MINIMO} y {services.ANIO_MAXIMO}."
            )
        return value

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
        if tipo == FacturaCabecera.Tipo.VENTA and orden_compra_id:
            raise serializers.ValidationError(
                {"orden_compra_id": "Una factura de venta no puede tener orden de compra."}
            )
        if tipo == FacturaCabecera.Tipo.COMPRA and orden_venta_id:
            raise serializers.ValidationError(
                {"orden_venta_id": "Una factura de compra no puede tener orden de venta."}
            )
        diario = attrs.get("diario")
        fecha = attrs.get("fecha")
        if diario is not None and fecha is not None:
            # La entrada de diario tiene que ser del mismo mes que la fecha de la factura:
            # si no, se podría facturar en un mes cerrado usando una entrada de un mes abierto.
            periodo = diario.cierre_mensual.periodo
            anio, mes = services.anio_y_mes(fecha)
            if (periodo.anio, periodo.mes) != (anio, mes):
                raise serializers.ValidationError(
                    {
                        "diario": (
                            f"La entrada de diario es del período {periodo}, pero la fecha "
                            f"de la factura corresponde a {mes:02d}/{anio}."
                        )
                    }
                )
        detalles = attrs.get("detalles")
        if detalles is not None and len(detalles) == 0:
            raise serializers.ValidationError(
                {"detalles": "La factura debe tener al menos un detalle."}
            )
        if detalles:
            # Subtotal y total se calculan al guardar: tienen que entrar en la base.
            subtotal = sum(
                (d["cantidad"] * d["precio_unitario"] for d in detalles), start=Decimal("0")
            )
            impuestos = attrs.get("impuestos", Decimal("0"))
            if subtotal + impuestos > services.MAX_IMPORTE:
                raise serializers.ValidationError({"detalles": MENSAJE_IMPORTE_EXCEDIDO})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        detalles_data = validated_data.pop("detalles")
        if validated_data.get("diario") is None:
            # Toda factura nueva genera su entrada en el libro diario.
            try:
                validated_data["diario"] = services.registrar_diario_de_factura(validated_data)
            except services.PeriodoCerradoError as exc:
                raise serializers.ValidationError({"fecha": str(exc)}) from exc
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
