# Serializers del módulo (DRF): traducen JSON <-> objetos y validan.

"""Serializers: JSON <-> objetos Django."""

from rest_framework import serializers

from .models import (
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
)


class ProveedorSerializer(serializers.ModelSerializer):
    """Alta / edición / listado de proveedores."""

    class Meta:
        model = Proveedor
        fields = ["id", "nombre", "telefono", "email", "direccion"]


class EstadoOrdenCompraSerializer(serializers.ModelSerializer):
    """Catálogo de estados."""

    class Meta:
        model = EstadoOrdenCompra
        fields = ["id", "nombre"]


class OrdenCompraDetalleSerializer(serializers.ModelSerializer):
    """Un renglón: OC + producto_id + cantidad + precio."""

    class Meta:
        model = OrdenCompraDetalle
        fields = ["id", "orden_compra", "producto_id", "cantidad", "precio_unitario"]


class OrdenCompraSerializer(serializers.ModelSerializer):
    """Cabecera. `detalles` es de solo lectura (se crean por su propio endpoint)."""

    detalles = OrdenCompraDetalleSerializer(many=True, read_only=True)

    class Meta:
        model = OrdenCompra
        fields = ["id", "proveedor", "estado", "fecha", "total", "detalles"]