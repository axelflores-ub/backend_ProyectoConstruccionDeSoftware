"""
Vistas (endpoints) del módulo CompraYProveedores.

Define los ViewSets de Django REST Framework que implementan la lógica CRUD
de cada entidad (Proveedor, EstadoOrdenCompra, OrdenCompra).
Todos los endpoints requieren autenticación JWT (IsAuthenticated).
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.SCM.services import registrar_recepcion_orden_compra

from .models import (
    ESTADO_CONTABILIZADO,
    ESTADO_RECIBIDA,
    ESTADOS_FACTURABLES,
    ESTADOS_NO_ELIMINABLES,
    EstadoOrdenCompra,
    OrdenCompra,
    Proveedor,
)
from .serializers import (
    TRANSICIONES_ORDEN,
    EstadoOrdenCompraSerializer,
    OrdenCompraSerializer,
    ProveedorSerializer,
)
from .services import marcar_orden_contabilizada, tiene_factura_compra


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
    """Catálogo fijo. Solo lectura: Pendiente, Aprobada, Rechazada, Recibida, Devuelto, Contabilizado."""

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
        """No permite eliminar una orden que ya salió de Pendiente o Rechazada."""
        if instance.estado.nombre in ESTADOS_NO_ELIMINABLES:
            raise ValidationError(
                {
                    "detail": (
                        "No se puede eliminar una orden aprobada, recibida, "
                        "devuelta o contabilizada."
                    )
                }
            )
        instance.delete()

    def perform_update(self, serializer):
        """Aplica el cambio de estado y el efecto de stock que le corresponde.

        Todo va en una transacción con SELECT FOR UPDATE sobre la OrdenCompra.
        El estado se relee después del bloqueo: si dos requests llegan juntos,
        el segundo ve el estado que dejó el primero y no vuelve a sumar o
        restar stock.

        Recibida suma una ENTRADA: el camión se aceptó. Devuelto no toca el
        stock: el camión se rechazó y no hubo carga. Contabilizado no toca
        el stock y solo se permite desde Recibida si ya hay factura.
        """
        with transaction.atomic():
            orden_bloqueada = OrdenCompra.objects.select_for_update(of=("self",)).get(
                pk=serializer.instance.pk
            )
            serializer.instance = orden_bloqueada
            estado_en_db = orden_bloqueada.estado.nombre
            estado_pedido = serializer.validated_data.get("estado", orden_bloqueada.estado)
            estado_nuevo = estado_pedido.nombre

            if estado_nuevo != estado_en_db and estado_nuevo not in TRANSICIONES_ORDEN.get(
                estado_en_db, set()
            ):
                raise ValidationError({"estado": "Ese cambio de estado no está permitido."})
            if (
                estado_nuevo == ESTADO_CONTABILIZADO
                and estado_en_db != ESTADO_CONTABILIZADO
                and not tiene_factura_compra(orden_bloqueada.pk)
            ):
                raise ValidationError({"estado": "La orden todavía no tiene factura de compra."})

            orden = serializer.save()

            if estado_nuevo == ESTADO_RECIBIDA and estado_en_db != ESTADO_RECIBIDA:
                registrar_recepcion_orden_compra(orden, self.request.user)

    @action(detail=True, methods=["post"], url_path="enviar-a-finanzas")
    def enviar_a_finanzas(self, request, pk=None):
        """Arma la factura de compra con los renglones de la orden y la contabiliza.

        Solo una orden Recibida. Devuelto es el camión rechazado y termina ahí.
        Al emitir la factura la orden pasa a Contabilizado.
        """
        from apps.ContabilidadFinanzas.serializers import FacturaCabeceraSerializer

        self.get_object()
        numero = str(request.data.get("numero", "")).strip()
        if not numero:
            raise ValidationError({"numero": "Falta el número de factura."})

        with transaction.atomic():
            orden = OrdenCompra.objects.select_for_update(of=("self",)).get(pk=pk)
            if tiene_factura_compra(orden.pk):
                raise ValidationError(
                    {"estado": "Esa orden ya tiene una factura de compra."}
                )
            if orden.estado.nombre not in ESTADOS_FACTURABLES:
                raise ValidationError(
                    {"estado": "Solo se puede pasar a finanzas una orden recibida."}
                )
            payload = {
                "tipo": "COMPRA",
                "orden_compra_id": orden.pk,
                "numero": numero,
                "fecha": request.data.get("fecha") or timezone.now(),
                "impuestos": request.data.get("impuestos", "0.00"),
                "detalles": [
                    {
                        "producto_id": detalle.producto_id,
                        "cantidad": detalle.cantidad,
                        "precio_unitario": str(detalle.precio_unitario),
                    }
                    for detalle in orden.detalles.all()
                ],
            }
            factura_serializer = FacturaCabeceraSerializer(data=payload)
            factura_serializer.is_valid(raise_exception=True)
            factura = factura_serializer.save()
            marcar_orden_contabilizada(orden)
            orden.refresh_from_db()

        return Response(
            {
                "orden": OrdenCompraSerializer(orden).data,
                "factura": FacturaCabeceraSerializer(factura).data,
            },
            status=status.HTTP_201_CREATED,
        )
