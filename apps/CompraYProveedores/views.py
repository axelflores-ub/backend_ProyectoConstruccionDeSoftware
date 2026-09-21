"""
Vistas (endpoints) del módulo CompraYProveedores.

Define los ViewSets de Django REST Framework que implementan la lógica CRUD
de cada entidad (Proveedor, EstadoOrdenCompra, OrdenCompra, OrdenCompraDetalle).
Todos los endpoints requieren autenticación JWT (IsAuthenticated).
"""

from django.db import transaction
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.SCM.services import registrar_recepcion_orden_compra

from .models import (
    ESTADO_RECIBIDA,
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
)
from .serializers import (
    EstadoOrdenCompraSerializer,
    OrdenCompraDetalleSerializer,
    OrdenCompraSerializer,
    ProveedorSerializer,
)


class ProveedorViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD para Proveedores.
    
    Proporciona operaciones completas de lectura y escritura (Create, Read, Update, Delete)
    para proveedores. Incluye busqueda por nombre, email y telefono, y ordenamiento.
    
    Atributos:
        queryset: Todos los proveedores disponibles.
        serializer_class: ProveedorSerializer para conversión de datos.
        search_fields: Campos en los que se puede buscar.
        ordering_fields: Campos por los que se puede ordenar.
    """

    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    search_fields = ["nombre", "email", "telefono"]
    ordering_fields = ["id", "nombre"]


class EstadoOrdenCompraViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD para Estados de Orden de Compra.
    
    Proporciona operaciones CRUD para gestionar el catalogo de estados de ordenes.
    Permite crear nuevos estados, listarlos, buscarlos y modificarlos.
    
    Atributos:
        queryset: Todos los estados disponibles.
        serializer_class: EstadoOrdenCompraSerializer para conversión de datos.
        search_fields: Campos en los que se puede buscar.
        ordering_fields: Campos por los que se puede ordenar.
    """

    queryset = EstadoOrdenCompra.objects.all()
    serializer_class = EstadoOrdenCompraSerializer
    search_fields = ["nombre"]
    ordering_fields = ["id", "nombre"]


class OrdenCompraViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD para Ordenes de Compra.
    
    Proporciona operaciones CRUD para ordenes de compra con optimizaciones de base de datos.
    Utiliza select_related para traer datos de proveedor y estado en una sola consulta,
    y prefetch_related para los detalles de la orden. En lectura, anida los detalles.
    
    Atributos:
        queryset: Todas las ordenes con sus relaciones precargadas.
        serializer_class: OrdenCompraSerializer para conversión de datos.
        ordering_fields: Campos por los que se puede ordenar (id, fecha, total).
    """

    queryset = OrdenCompra.objects.select_related(
        "proveedor", "estado"
    ).prefetch_related("detalles")
    serializer_class = OrdenCompraSerializer
    ordering_fields = ["id", "fecha", "total"]

    def perform_update(self, serializer):
        """Al pasar la orden a "Recibida" se suma lo recibido al stock de SCM.

        Todo va en una transacción: si algún producto no existe en SCM, la orden
        no cambia de estado. Una orden Recibida ya no puede cambiar de estado
        (evita sumar el stock dos veces).
        """
        estado_anterior = serializer.instance.estado.nombre
        with transaction.atomic():
            orden = serializer.save()
            estado_nuevo = orden.estado.nombre
            if estado_anterior == ESTADO_RECIBIDA and estado_nuevo != ESTADO_RECIBIDA:
                raise ValidationError(
                    {"estado": "Una orden recibida no puede cambiar de estado."}
                )
            if estado_nuevo == ESTADO_RECIBIDA and estado_anterior != ESTADO_RECIBIDA:
                registrar_recepcion_orden_compra(orden, self.request.user)


class OrdenCompraDetalleViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD para Detalles/Renglones de Ordenes de Compra.
    
    Proporciona operaciones CRUD para gestionar los renglones individuales de las ordenes.
    Utiliza select_related para optimizar la consulta trayendo los datos de la orden.
    Nota: producto_id se almacena como numero entero hasta que el modulo SCM este integrado
          con un modelo Producto formal.
    
    Atributos:
        queryset: Todos los detalles con su orden de compra precargada.
        serializer_class: OrdenCompraDetalleSerializer para conversión de datos.
    """

    queryset = OrdenCompraDetalle.objects.select_related("orden_compra")
    serializer_class = OrdenCompraDetalleSerializer