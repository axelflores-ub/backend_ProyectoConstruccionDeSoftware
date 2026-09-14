"""
Serializadores para el módulo CompraYProveedores.

Utiliza Django REST Framework (DRF) para convertir entre objetos Python
y representaciones JSON, así como para validar datos en las peticiones API.
Cada serializer corresponde a un modelo del módulo.
"""
from rest_framework import serializers

from .models import (
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
)


class ProveedorSerializer(serializers.ModelSerializer):
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
        cuit = value.strip().replace("-", "")
        if not cuit.isdigit() or len(cuit) != 11:
            raise serializers.ValidationError(
                "El CUIT debe tener 11 dígitos (podés usar guiones)."
            )
        return value.strip()

    def validate_producto_id(self, value):
        if value is None:
            raise serializers.ValidationError(
                "Falta indicar el producto (producto_id)."
            )
        if value < 1:
            raise serializers.ValidationError("producto_id tiene que ser mayor a 0.")
        return value


class EstadoOrdenCompraSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoOrdenCompra
        fields = ["estadoordencompra_id", "nombre"]


class OrdenCompraDetalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrdenCompraDetalle
        fields = [
            "ordencompradetalle_id",
            "orden_compra",
            "producto_id",
            "cantidad",
            "precio_unitario",
        ]


class OrdenCompraSerializer(serializers.ModelSerializer):
    detalles = OrdenCompraDetalleSerializer(many=True, read_only=True)

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