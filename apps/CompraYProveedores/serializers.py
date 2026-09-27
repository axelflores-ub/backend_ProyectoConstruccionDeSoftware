"""
Serializadores para el módulo CompraYProveedores.

Utiliza Django REST Framework (DRF) para convertir entre objetos Python
y representaciones JSON, así como para validar datos en las peticiones API.
Cada serializer corresponde a un modelo del módulo.
"""

from django.db.models import Value
from django.db.models.functions import Replace
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .cuit import cuit_canonico
from .models import (
    ESTADO_APROBADA,
    ESTADO_PENDIENTE,
    ESTADO_RECHAZADA,
    ESTADO_RECIBIDA,
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
)

TRANSICIONES_ORDEN = {
    ESTADO_PENDIENTE: {ESTADO_APROBADA, ESTADO_RECHAZADA},
    ESTADO_APROBADA: {ESTADO_RECIBIDA, ESTADO_RECHAZADA},
    ESTADO_RECHAZADA: set(),
    ESTADO_RECIBIDA: set(),
}


class ProveedorSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La unicidad la resuelve validate_cuit comparando los 11 dígitos.
        self.fields["cuit"].validators = [
            validator
            for validator in self.fields["cuit"].validators
            if not isinstance(validator, UniqueValidator)
        ]

    class Meta:
        model = Proveedor
        fields = [
            "proveedor_id",
            "nombre",
            "apellido",
            "email",
            "telefono",
            "cuit",
            "direccion",
            "producto_id",
        ]
        extra_kwargs = {
            "nombre": {
                "required": True,
                "allow_blank": False,
                "error_messages": {
                    "blank": "Falta completar el nombre.",
                    "required": "Falta completar el nombre.",
                },
            },
            "apellido": {
                "required": True,
                "allow_blank": False,
                "error_messages": {
                    "blank": "Falta completar el apellido.",
                    "required": "Falta completar el apellido.",
                },
            },
            "cuit": {
                "required": True,
                "allow_blank": False,
                "error_messages": {
                    "blank": "Falta completar el CUIT.",
                    "required": "Falta completar el CUIT.",
                    "unique": "Ya existe un proveedor con ese CUIT.",
                    "max_length": "El CUIT no puede tener más de 13 caracteres.",
                },
            },
            "producto_id": {
                "required": True,
                "error_messages": {
                    "required": "Falta indicar el producto (producto_id).",
                    "invalid": "producto_id tiene que ser un número entero.",
                    "unique": "Ese producto ya está asignado a otro proveedor.",
                    "min_value": "producto_id tiene que ser mayor a 0.",
                },
            },
            "email": {
                "error_messages": {
                    "invalid": "El email no tiene un formato válido.",
                },
            },
        }

    def validate_nombre(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Falta completar el nombre.")
        return value.strip()

    def validate_apellido(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Falta completar el apellido.")
        return value.strip()

    def validate_cuit(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Falta completar el CUIT.")
        canonico = cuit_canonico(value)
        if canonico is None:
            raise serializers.ValidationError("El CUIT debe tener 11 dígitos (podés usar guiones).")
        digitos = canonico.replace("-", "")
        existentes = Proveedor.objects.annotate(
            digitos=Replace(
                Replace("cuit", Value("-"), Value("")),
                Value(" "),
                Value(""),
            )
        ).filter(digitos=digitos)
        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise serializers.ValidationError("Ya existe un proveedor con ese CUIT.")
        return canonico

    def validate_producto_id(self, value):
        if value is None:
            raise serializers.ValidationError("Falta indicar el producto (producto_id).")
        if value < 1:
            raise serializers.ValidationError("producto_id tiene que ser mayor a 0.")
        return value


class EstadoOrdenCompraSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoOrdenCompra
        fields = ["estadoordencompra_id", "nombre"]


class RenglonOrdenCompraSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrdenCompraDetalle
        fields = [
            "ordencompradetalle_id",
            "producto_id",
            "cantidad",
            "precio_unitario",
        ]
        extra_kwargs = {"ordencompradetalle_id": {"read_only": True}}


class OrdenCompraSerializer(serializers.ModelSerializer):
    detalles = RenglonOrdenCompraSerializer(many=True, required=False)

    class Meta:
        model = OrdenCompra
        fields = [
            "ordencompra_id",
            "proveedor",
            "estado",
            "fecha",
            "total",
            "detalles",
        ]
        extra_kwargs = {"estado": {"required": False}}

    def validate(self, attrs):
        if self.instance is None and "estado" in attrs:
            pendiente = EstadoOrdenCompra.objects.get(nombre=ESTADO_PENDIENTE)
            if attrs["estado"].pk != pendiente.pk:
                raise serializers.ValidationError(
                    {"estado": "La orden se da de alta en estado Pendiente."}
                )
        if self.instance is not None and "estado" in attrs:
            actual = self.instance.estado.nombre
            nuevo = attrs["estado"].nombre
            if nuevo != actual and nuevo not in TRANSICIONES_ORDEN.get(actual, set()):
                raise serializers.ValidationError(
                    {"estado": "Ese cambio de estado no está permitido."}
                )
        if self.instance is not None and self.instance.estado.nombre != ESTADO_PENDIENTE:
            bloqueados = {
                campo: "Solo se puede modificar una orden pendiente."
                for campo in ("proveedor", "fecha", "total", "detalles")
                if campo in attrs
            }
            if bloqueados:
                raise serializers.ValidationError(bloqueados)
        return attrs

    def create(self, validated_data):
        detalles_data = validated_data.pop("detalles", [])
        if "estado" not in validated_data:
            validated_data["estado"] = EstadoOrdenCompra.objects.get(nombre=ESTADO_PENDIENTE)
        orden = OrdenCompra.objects.create(**validated_data)
        for detalle in detalles_data:
            OrdenCompraDetalle.objects.create(orden_compra=orden, **detalle)
        return orden

    def update(self, instance, validated_data):
        detalles_data = validated_data.pop("detalles", None)
        orden = super().update(instance, validated_data)
        if detalles_data is not None:
            orden.detalles.all().delete()
            for detalle in detalles_data:
                OrdenCompraDetalle.objects.create(orden_compra=orden, **detalle)
        return orden
