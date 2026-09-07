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
    """Serializador para el modelo Proveedor.
    
    Convierte instancias de Proveedor entre objetos Python y JSON.
    Incluye todos los campos del modelo para lectura y escritura.
    """
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
        ]


class EstadoOrdenCompraSerializer(serializers.ModelSerializer):
    """Serializador para el modelo EstadoOrdenCompra.
    
    Convierte instancias de EstadoOrdenCompra entre objetos Python y JSON.
    Expone el ID y nombre del estado.
    """
    class Meta:
        model = EstadoOrdenCompra
        fields = ["estadoordencompra_id", "nombre"]


class OrdenCompraDetalleSerializer(serializers.ModelSerializer):
    """Serializador para el modelo OrdenCompraDetalle.
    
    Convierte instancias de OrdenCompraDetalle entre objetos Python y JSON.
    Incluye todos los campos del modelo: ID, referencia a orden, producto, cantidad y precio.
    """
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
    """Serializador para el modelo OrdenCompra.
    
    Convierte instancias de OrdenCompra entre objetos Python y JSON.
    Incluye los detalles (renglones) anidados en modo lectura (solo lectura, no editables).
    Expone todos los campos: ID, proveedor, estado, fecha, total y detalles anidados.
    """
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