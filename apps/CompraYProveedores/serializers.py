"""
Serializadores para el módulo CompraYProveedores.

Utiliza Django REST Framework (DRF) para convertir entre objetos Python
y representaciones JSON, así como para validar datos en las peticiones API.
Cada serializer corresponde a un modelo del módulo.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Replace
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.SCM.models import Producto

from .cuit import cuit_canonico
from .models import (
    ESTADO_APROBADA,
    ESTADO_PENDIENTE,
    ESTADO_RECHAZADA,
    ESTADO_RECIBIDA,
    VINCULO_ACTIVO,
    VINCULO_INACTIVO,
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
    ProveedorProducto,
)

TRANSICIONES_ORDEN = {
    ESTADO_PENDIENTE: {ESTADO_APROBADA, ESTADO_RECHAZADA},
    ESTADO_APROBADA: {ESTADO_RECIBIDA, ESTADO_RECHAZADA},
    ESTADO_RECHAZADA: set(),
    ESTADO_RECIBIDA: set(),
}


def _importe(valor):
    return Decimal(valor).quantize(Decimal("0.01"))


def _suma_renglones(renglones):
    total = Decimal("0.00")
    for renglon in renglones:
        if isinstance(renglon, dict):
            cantidad = renglon["cantidad"]
            precio = renglon["precio_unitario"]
        else:
            cantidad = renglon.cantidad
            precio = renglon.precio_unitario
        total += Decimal(cantidad) * Decimal(precio)
    return _importe(total)


def _producto_id(renglon):
    if isinstance(renglon, dict):
        return renglon["producto_id"]
    return renglon.producto_id


def _validar_productos_del_proveedor(proveedor, renglones):
    """Cada renglón tiene que ser un producto vigente de ese proveedor."""
    permitidos = set(
        proveedor.vinculos.filter(activo=VINCULO_ACTIVO).values_list("producto_id", flat=True)
    )
    ajenos = []
    vistos = set()
    for renglon in renglones:
        producto_id = _producto_id(renglon)
        if producto_id not in permitidos and producto_id not in vistos:
            vistos.add(producto_id)
            ajenos.append(producto_id)
    if not ajenos:
        return
    if len(ajenos) == 1:
        mensaje = f"El producto {ajenos[0]} no está asociado al proveedor."
    else:
        lista = ", ".join(str(producto_id) for producto_id in ajenos)
        mensaje = f"Los productos {lista} no están asociados al proveedor."
    raise serializers.ValidationError({"detalles": mensaje})


class ProductoDelProveedorSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(
        min_value=1,
        error_messages={
            "required": "Falta indicar el producto.",
            "invalid": "El formato de productos no es válido.",
            "min_value": "El formato de productos no es válido.",
        },
    )
    precio_compra = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        error_messages={
            "required": "Falta el precio de compra.",
            "invalid": "El precio de compra no es válido.",
            "max_digits": "El precio de compra no es válido.",
            "max_decimal_places": "El precio de compra no es válido.",
            "max_whole_digits": "El precio de compra no es válido.",
        },
    )

    def validate_precio_compra(self, value):
        if value < 0:
            raise serializers.ValidationError("El precio de compra no puede ser negativo.")
        return value


class ProductosConPrecioField(serializers.Field):
    """Lista de {producto_id, precio_compra} leída desde proveedor_productos."""

    def to_representation(self, value):
        precio = serializers.DecimalField(max_digits=12, decimal_places=2)
        return [
            {
                "producto_id": vinculo.producto_id,
                "precio_compra": (
                    None
                    if vinculo.precio_compra is None
                    else precio.to_representation(vinculo.precio_compra)
                ),
            }
            for vinculo in value.instance.vinculos.all()
            if vinculo.activo == VINCULO_ACTIVO
        ]

    def to_internal_value(self, data):
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise serializers.ValidationError("El formato de productos no es válido.")
        if not data:
            raise serializers.ValidationError(
                "El proveedor debe tener al menos un producto asociado."
            )
        serializer = ProductoDelProveedorSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class ProveedorSerializer(serializers.ModelSerializer):
    productos = ProductosConPrecioField(
        error_messages={"required": "Falta indicar el producto."}
    )

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
            "productos",
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

    def validate_productos(self, productos):
        vistos = []
        repetidos = []
        for item in productos:
            producto_id = item["producto_id"]
            if producto_id in vistos:
                if producto_id not in repetidos:
                    repetidos.append(producto_id)
            else:
                vistos.append(producto_id)
        if repetidos:
            if len(repetidos) == 1:
                raise serializers.ValidationError(f"El producto {repetidos[0]} está repetido.")
            lista = ", ".join(str(producto_id) for producto_id in repetidos)
            raise serializers.ValidationError(f"Los productos {lista} están repetidos.")
        existentes = set(Producto.objects.filter(pk__in=vistos).values_list("pk", flat=True))
        faltantes = [producto_id for producto_id in vistos if producto_id not in existentes]
        if not faltantes:
            return productos
        if len(faltantes) == 1:
            raise serializers.ValidationError(f"El producto {faltantes[0]} no existe.")
        lista = ", ".join(str(producto_id) for producto_id in faltantes)
        raise serializers.ValidationError(f"Los productos {lista} no existen.")

    def _reemplazar_productos(self, proveedor, productos):
        """Sincroniza el catálogo. Sacar un producto pone activo=0; la fila queda."""
        nuevos = {item["producto_id"]: item["precio_compra"] for item in productos}
        existentes = {vinculo.producto_id: vinculo for vinculo in proveedor.vinculos.all()}
        altas = []
        cambios = []
        for producto_id, precio in nuevos.items():
            vinculo = existentes.get(producto_id)
            if vinculo is None:
                altas.append(
                    ProveedorProducto(
                        proveedor=proveedor,
                        producto_id=producto_id,
                        precio_compra=precio,
                        activo=VINCULO_ACTIVO,
                    )
                )
                continue
            if vinculo.precio_compra != precio or vinculo.activo != VINCULO_ACTIVO:
                vinculo.precio_compra = precio
                vinculo.activo = VINCULO_ACTIVO
                cambios.append(vinculo)
        for producto_id, vinculo in existentes.items():
            if producto_id not in nuevos and vinculo.activo != VINCULO_INACTIVO:
                vinculo.activo = VINCULO_INACTIVO
                cambios.append(vinculo)
        if altas:
            ProveedorProducto.objects.bulk_create(altas)
        if cambios:
            ProveedorProducto.objects.bulk_update(cambios, ["precio_compra", "activo"])

    def create(self, validated_data):
        productos = validated_data.pop("productos")
        with transaction.atomic():
            proveedor = Proveedor.objects.create(**validated_data)
            self._reemplazar_productos(proveedor, productos)
        return proveedor

    def update(self, instance, validated_data):
        productos = validated_data.pop("productos", None)
        with transaction.atomic():
            proveedor = super().update(instance, validated_data)
            if productos is not None:
                self._reemplazar_productos(proveedor, productos)
                cache = getattr(proveedor, "_prefetched_objects_cache", None)
                if cache is not None:
                    cache.pop("vinculos", None)
        return proveedor


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
        extra_kwargs = {
            "estado": {"required": False},
            "total": {"required": False},
        }

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

        mando_renglones = "detalles" in attrs
        mando_total = "total" in attrs
        mando_proveedor = "proveedor" in attrs
        if self.instance is None or mando_renglones or mando_total or mando_proveedor:
            if mando_renglones:
                renglones = attrs["detalles"]
            elif self.instance is not None:
                renglones = list(self.instance.detalles.all())
            else:
                renglones = []
            if not renglones:
                raise serializers.ValidationError(
                    {"detalles": "La orden debe tener al menos un renglón."}
                )
            proveedor = attrs.get("proveedor")
            if proveedor is None and self.instance is not None:
                proveedor = self.instance.proveedor
            _validar_productos_del_proveedor(proveedor, renglones)
            suma = _suma_renglones(renglones)
            if mando_total and _importe(attrs["total"]) != suma:
                raise serializers.ValidationError(
                    {"total": ("El total no coincide con la suma de cantidad por precio unitario.")}
                )
            if not mando_total:
                attrs["total"] = suma
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
