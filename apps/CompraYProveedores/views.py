"""
Vistas (endpoints) del módulo CompraYProveedores.

Define los ViewSets de Django REST Framework que implementan la lógica CRUD
de cada entidad (Proveedor, EstadoOrdenCompra, OrdenCompra).
Todos los endpoints requieren autenticación JWT (IsAuthenticated).
"""

from django.db import transaction
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.SCM.services import registrar_recepcion_orden_compra

from .models import (
    ESTADO_APROBADA,
    ESTADO_RECIBIDA,
    EstadoOrdenCompra,
    OrdenCompra,
    Proveedor,
)
from .serializers import (
    EstadoOrdenCompraSerializer,
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

    queryset = Proveedor.objects.prefetch_related("vinculos")
    serializer_class = ProveedorSerializer
    search_fields = ["nombre", "email", "telefono"]
    ordering_fields = ["id", "nombre"]


class EstadoOrdenCompraViewSet(viewsets.ReadOnlyModelViewSet):
    """Catálogo fijo de estados. Solo lectura: Pendiente, Aprobada, Rechazada, Recibida."""

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

    queryset = OrdenCompra.objects.select_related("proveedor", "estado").prefetch_related(
        "detalles"
    )
    serializer_class = OrdenCompraSerializer
    ordering_fields = ["id", "fecha", "total"]

    def perform_destroy(self, instance):
        """No permite eliminar órdenes aprobadas o recibidas."""
        if instance.estado.nombre in {ESTADO_APROBADA, ESTADO_RECIBIDA}:
            raise ValidationError(
                {"detail": "No se puede eliminar una orden aprobada o recibida."}
            )
        instance.delete()

    def perform_update(self, serializer):
        """Al pasar la orden a "Recibida" se suma lo recibido al stock de SCM.

        Todo va en una transacción con SELECT FOR UPDATE sobre la OrdenCompra
        para serializar requests concurrentes. El estado anterior se relee desde
        la DB después del bloqueo (estado_en_db), de modo que si dos requests
        llegan simultáneamente sólo uno ejecuta la recepción y el segundo
        detecta que la orden ya es "Recibida" antes de intentar volver a hacerlo.

        Si algún producto no existe en SCM la orden no cambia de estado.
        Una orden Recibida ya no puede cambiar de estado (evita doble stock).
        """
        with transaction.atomic():
            # Bloquea la fila para serializar requests concurrentes que
            # intenten cambiar el estado de la misma orden al mismo tiempo.
            orden_bloqueada = (
                OrdenCompra.objects.select_related("estado")
                .select_for_update()
                .get(pk=serializer.instance.pk)
            )
            # Releemos el estado desde la DB (puede diferir del que leyó
            # el serializer antes de entrar a la transacción).
            estado_en_db = orden_bloqueada.estado.nombre

            # Sincronizamos la instancia del serializer con la fila bloqueada
            # para que serializer.save() trabaje sobre datos frescos.
            serializer.instance = orden_bloqueada

            orden = serializer.save()
            estado_nuevo = orden.estado.nombre

            if estado_en_db == ESTADO_RECIBIDA and estado_nuevo != ESTADO_RECIBIDA:
                raise ValidationError({"estado": "Una orden recibida no puede cambiar de estado."})
            if estado_nuevo == ESTADO_RECIBIDA and estado_en_db != ESTADO_RECIBIDA:
                registrar_recepcion_orden_compra(orden, self.request.user)
