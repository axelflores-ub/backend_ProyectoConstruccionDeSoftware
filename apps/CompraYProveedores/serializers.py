"""
Serializadores para el módulo CompraYProveedores.

Utiliza Django REST Framework (DRF) para convertir entre objetos Python
y representaciones JSON, así como para validar datos en las peticiones API.
Cada serializer corresponde a un modelo del módulo.
"""

from decimal import Decimal

from django.core.validators import MaxLengthValidator
from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Replace
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.SCM.models import Producto

from .cuit import cuit_canonico
from .models import (
    ESTADO_APROBADA,
    ESTADO_CONTABILIZADO,
    ESTADO_DEVUELTO,
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
from .services import tiene_factura_compra

MENSAJE_CUIT_DIGITOS = "El CUIT tiene que tener 11 dígitos. Podés escribirlo con o sin guiones."

TRANSICIONES_ORDEN = {
    ESTADO_PENDIENTE: {ESTADO_APROBADA, ESTADO_RECHAZADA},
    ESTADO_APROBADA: {ESTADO_RECIBIDA, ESTADO_DEVUELTO},
    ESTADO_RECHAZADA: set(),
    ESTADO_RECIBIDA: {ESTADO_CONTABILIZADO},
    ESTADO_DEVUELTO: set(),
    ESTADO_CONTABILIZADO: set(),
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
            "null": "Falta indicar el producto.",
            "invalid": "El formato de productos no es válido.",
            "min_value": "El formato de productos no es válido.",
            "max_string_length": "El formato de productos no es válido.",
        },
    )
    precio_compra = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        error_messages={
            "required": "Falta el precio de compra.",
            "null": "Falta el precio de compra.",
            "invalid": "El precio de compra no es válido.",
            "max_digits": "El precio de compra no puede tener más de {max_digits} dígitos.",
            "max_decimal_places": (
                "El precio de compra no puede tener más de {max_decimal_places} decimales."
            ),
            "max_whole_digits": (
                "El precio de compra no puede tener más de {max_whole_digits} dígitos enteros."
            ),
            "max_string_length": "El precio de compra no es válido.",
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
        error_messages={
            "required": "Falta indicar el producto.",
            "null": "Falta indicar el producto.",
        }
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La unicidad y los 11 dígitos los resuelve validate_cuit.
        # Sin el tope de 13 caracteres, un CUIT largo llega al aviso amistoso
        # en vez de cortarse antes por el tamaño de la columna.
        self.fields["cuit"].validators = [
            validator
            for validator in self.fields["cuit"].validators
            if not isinstance(validator, UniqueValidator | MaxLengthValidator)
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
                    "null": "Falta completar el nombre.",
                    "invalid": "El nombre no es válido.",
                    "max_length": "El nombre no puede tener más de {max_length} caracteres.",
                },
            },
            "apellido": {
                "required": True,
                "allow_blank": False,
                "error_messages": {
                    "blank": "Falta completar el apellido.",
                    "required": "Falta completar el apellido.",
                    "null": "Falta completar el apellido.",
                    "invalid": "El apellido no es válido.",
                    "max_length": "El apellido no puede tener más de {max_length} caracteres.",
                },
            },
            "cuit": {
                "required": True,
                "allow_blank": False,
                "error_messages": {
                    "blank": "Falta completar el CUIT.",
                    "required": "Falta completar el CUIT.",
                    "null": "Falta completar el CUIT.",
                    "invalid": MENSAJE_CUIT_DIGITOS,
                    "unique": "Ya existe un proveedor con ese CUIT.",
                    "max_length": MENSAJE_CUIT_DIGITOS,
                },
            },
            "email": {
                "error_messages": {
                    "invalid": "El email no tiene un formato válido.",
                    "null": "El email no tiene un formato válido.",
                    "max_length": "El email no puede tener más de {max_length} caracteres.",
                },
            },
            "telefono": {
                "error_messages": {
                    "invalid": "El teléfono no es válido.",
                    "null": "El teléfono no es válido.",
                    "max_length": "El teléfono no puede tener más de {max_length} caracteres.",
                },
            },
            "direccion": {
                "error_messages": {
                    "invalid": "La dirección no es válida.",
                    "null": "La dirección no es válida.",
                    "max_length": "La dirección no puede tener más de {max_length} caracteres.",
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
            raise serializers.ValidationError(MENSAJE_CUIT_DIGITOS)
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
    default_error_messages = {
        "invalid": "Cada renglón tiene que ser un objeto, no un {datatype}.",
    }

    class Meta:
        model = OrdenCompraDetalle
        fields = [
            "ordencompradetalle_id",
            "producto_id",
            "cantidad",
            "precio_unitario",
        ]
        extra_kwargs = {
            "ordencompradetalle_id": {"read_only": True},
            "producto_id": {
                "error_messages": {
                    "required": "Falta indicar el producto.",
                    "null": "Falta indicar el producto.",
                    "invalid": "El producto no es válido.",
                    "min_value": "El producto no puede ser menor que {min_value}.",
                    "max_value": "El producto no puede ser mayor que {max_value}.",
                    "max_string_length": "El producto no es válido.",
                },
            },
            "cantidad": {
                "error_messages": {
                    "required": "Falta completar la cantidad.",
                    "null": "Falta completar la cantidad.",
                    "invalid": "La cantidad tiene que ser un número entero.",
                    "min_value": "La cantidad no puede ser menor que {min_value}.",
                    "max_value": "La cantidad no puede ser mayor que {max_value}.",
                    "max_string_length": "La cantidad tiene que ser un número entero.",
                },
            },
            "precio_unitario": {
                "error_messages": {
                    "required": "Falta completar el precio unitario.",
                    "null": "Falta completar el precio unitario.",
                    "invalid": "El precio unitario no es válido.",
                    "max_string_length": "El precio unitario no es válido.",
                    "max_digits": "El precio unitario no puede tener más de {max_digits} dígitos.",
                    "max_decimal_places": (
                        "El precio unitario no puede tener más de "
                        "{max_decimal_places} decimales."
                    ),
                    "max_whole_digits": (
                        "El precio unitario no puede tener más de "
                        "{max_whole_digits} dígitos enteros."
                    ),
                },
            },
        }

    def validate_precio_unitario(self, value):
        if value < 0:
            raise serializers.ValidationError("El precio unitario no puede ser negativo.")
        return value


class OrdenCompraSerializer(serializers.ModelSerializer):
    detalles = RenglonOrdenCompraSerializer(
        many=True,
        required=False,
        error_messages={
            "null": "La orden debe tener al menos un renglón.",
            "not_a_list": "Los renglones tienen que ser una lista, no un {input_type}.",
            "empty": "La orden debe tener al menos un renglón.",
        },
    )

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
            "proveedor": {
                "error_messages": {
                    "required": "Falta indicar el proveedor.",
                    "null": "Falta indicar el proveedor.",
                    "does_not_exist": "El proveedor {pk_value} no existe.",
                    "incorrect_type": "El proveedor tiene que ser un id, no un {data_type}.",
                },
            },
            "estado": {
                "required": False,
                "error_messages": {
                    "null": "El estado no es válido.",
                    "does_not_exist": "El estado {pk_value} no existe.",
                    "incorrect_type": "El estado tiene que ser un id, no un {data_type}.",
                },
            },
            "fecha": {
                "error_messages": {
                    "required": "Falta completar la fecha.",
                    "null": "Falta completar la fecha.",
                    "invalid": "La fecha no es válida. Usá un formato como {format}.",
                    "date": "La fecha no es válida.",
                    "make_aware": "La fecha no es válida para la zona {timezone}.",
                    "overflow": "La fecha no es válida.",
                },
            },
            "total": {
                "required": False,
                "error_messages": {
                    "invalid": "El total no es válido.",
                    "null": "El total no es válido.",
                    "max_digits": "El total no puede tener más de {max_digits} dígitos.",
                    "max_decimal_places": (
                        "El total no puede tener más de {max_decimal_places} decimales."
                    ),
                    "max_whole_digits": (
                        "El total no puede tener más de {max_whole_digits} dígitos enteros."
                    ),
                    "max_string_length": "El total no es válido.",
                },
            },
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
            if (
                nuevo == ESTADO_CONTABILIZADO
                and actual != ESTADO_CONTABILIZADO
                and not tiene_factura_compra(self.instance.pk)
            ):
                raise serializers.ValidationError(
                    {"estado": "La orden todavía no tiene factura de compra."}
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
