# Vistas del módulo (DRF): ViewSets con la lógica de cada endpoint.
# Permisos: se usa el default global de settings.py (IsAuthenticated -> requiere JWT).
from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import (
    Anulacion,
    Cliente,
    DetalleNotaCredito,
    EstadoOrdenVenta,
    NotaCredito,
    OrdenVenta,
    OrdenVentaDetalle,
)
from .serializers import (
    AnulacionSerializer,
    ClienteSerializer,
    DetalleNotaCreditoSerializer,
    EstadoOrdenVentaSerializer,
    NotaCreditoSerializer,
    OrdenVentaDetalleSerializer,
    OrdenVentaSerializer,
    OrdenVentaUpdateSerializer,
)


class ClienteViewSet(viewsets.ModelViewSet):
    """
    GET    /api/ventas/clientes/                -> Lista clientes (paginado).
    POST   /api/ventas/clientes/                -> Crea un cliente (siempre activo, 'AC').
    GET    /api/ventas/clientes/<id_cliente>/   -> Obtiene un cliente.
    PUT    /api/ventas/clientes/<id_cliente>/   -> Actualiza un cliente.
    DELETE /api/ventas/clientes/<id_cliente>/   -> Baja lógica: setea estado = 'OF'.
    """

    queryset = Cliente.objects.all()  # sin relaciones: no hay nada que precargar
    serializer_class = ClienteSerializer
    lookup_field = "id_cliente"
    lookup_value_regex = r"\d+"
    search_fields = ["nombre", "email", "telefono", "cuil"]
    ordering_fields = ["id_cliente", "nombre", "estado"]

    def perform_create(self, serializer):
        # Un cliente nuevo siempre se crea activo, sin importar lo que venga en el body.
        serializer.save(estado=Cliente.ESTADO_ACTIVO)

    def destroy(self, request, *args, **kwargs):
        cliente = self.get_object()
        cliente.estado = Cliente.ESTADO_BAJA  # 'OF'
        cliente.save(update_fields=["estado"])
        return Response(
            {
                "mensaje": (
                    f"Cliente {cliente.id_cliente} dado de baja correctamente (estado = OF)."
                ),
                "cliente": ClienteSerializer(cliente).data,
            },
            status=status.HTTP_200_OK,
        )


class EstadoOrdenVentaViewSet(viewsets.ModelViewSet):
    """Catálogo de estados (Pendiente, Confirmada, Completada, etc.)."""

    queryset = EstadoOrdenVenta.objects.all().order_by("nombre")  # sin relaciones
    serializer_class = EstadoOrdenVentaSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    search_fields = ["nombre"]
    ordering_fields = ["nombre"]


class OrdenVentaViewSet(viewsets.ModelViewSet):
    """Registrar (POST), modificar cliente/forma de pago/estado (PUT/PATCH)
    y listar/consultar (GET) órdenes de venta."""

    queryset = OrdenVenta.objects.select_related("cliente", "estado", "usuario").prefetch_related(
        "detalles__producto"
    )
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    search_fields = ["cliente__nombre", "cliente__cuil", "numero_comprobante"]
    ordering_fields = ["id", "fecha", "total"]

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return OrdenVentaUpdateSerializer
        return OrdenVentaSerializer


class OrdenVentaDetalleViewSet(viewsets.ModelViewSet):
    """Consulta del detalle. Es de SOLO LECTURA: el detalle se crea
    automáticamente junto con la orden de venta (ver services.registrar_orden_venta).

    No se habilita POST/PUT acá porque el serializer no completa
    'precio_unitario' ni actualiza el stock del producto o el total de la orden,
    dejando los datos inconsistentes."""

    queryset = OrdenVentaDetalle.objects.select_related("orden_venta", "producto")
    serializer_class = OrdenVentaDetalleSerializer
    http_method_names = ["get", "head", "options"]
    search_fields = ["producto__nombre", "orden_venta__numero_comprobante"]
    ordering_fields = ["id", "cantidad"]


class AnulacionViewSet(viewsets.ModelViewSet):
    """Anular una orden de venta (Devoluciones -> botón 'Anular').
    Solo lectura + alta: una anulación, una vez creada, no se edita ni se
    borra (es un registro de auditoría)."""

    queryset = Anulacion.objects.select_related("orden_venta")
    serializer_class = AnulacionSerializer
    http_method_names = ["get", "post", "head", "options"]
    search_fields = ["motivo", "orden_venta__numero_comprobante"]
    ordering_fields = ["id", "fecha"]


class NotaCreditoViewSet(viewsets.ModelViewSet):
    """Alta de una nota de crédito (devolución parcial/total). Repone stock
    para los ítems marcados como 'stock disponible' y mueve la orden a
    'Devolución parcial'. No se edita ni se borra una vez creada."""

    queryset = NotaCredito.objects.select_related("orden_venta").prefetch_related(
        "detalles__producto"
    )
    serializer_class = NotaCreditoSerializer
    http_method_names = ["get", "post", "head", "options"]
    search_fields = ["orden_venta__numero_comprobante"]
    ordering_fields = ["id", "fecha", "monto"]


class DetalleNotaCreditoViewSet(viewsets.ModelViewSet):
    """Consulta del detalle de notas de crédito. Solo lectura: el detalle
    se crea automáticamente junto con la nota de crédito."""

    queryset = DetalleNotaCredito.objects.select_related("nota_credito", "producto")
    serializer_class = DetalleNotaCreditoSerializer
    http_method_names = ["get", "head", "options"]
    search_fields = ["producto__nombre"]
    ordering_fields = ["id", "cantidad_devuelta"]
