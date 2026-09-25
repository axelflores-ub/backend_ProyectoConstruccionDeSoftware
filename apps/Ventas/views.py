# Vistas del módulo (DRF): ViewSets / APIViews con la lógica de cada endpoint.
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


from .models import Cliente, EstadoOrdenVenta, OrdenVenta, OrdenVentaDetalle, Producto
from .serializers import (
    ClienteSerializer,
    EstadoOrdenVentaSerializer,
    OrdenVentaDetalleSerializer,
    OrdenVentaSerializer,
    OrdenVentaUpdateSerializer,
    ProductoSerializer,
)


class ClienteListView(APIView):
    """
    GET /api/clientes/  -> Lista todos los clientes.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        clientes = Cliente.objects.all()
        serializer = ClienteSerializer(clientes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClienteDetailView(APIView):
    """
    GET    /api/clientes/<id_cliente>/  -> Obtiene un cliente por id_cliente.
    PUT    /api/clientes/<id_cliente>/  -> Actualiza un cliente por id_cliente.
    DELETE /api/clientes/<id_cliente>/  -> Baja lógica: setea estado = 'OF'.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, id_cliente):
        return get_object_or_404(Cliente, id_cliente=id_cliente)

    def get(self, request, id_cliente):
        cliente = self.get_object(id_cliente)
        serializer = ClienteSerializer(cliente)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, id_cliente):
        cliente = self.get_object(id_cliente)
        serializer = ClienteSerializer(cliente, data=request.data,
partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id_cliente):
        cliente = self.get_object(id_cliente)
        cliente.estado = Cliente.ESTADO_BAJA  # 'OF'
        cliente.save(update_fields=['estado'])
        serializer = ClienteSerializer(cliente)
        return Response(
            {
                'mensaje': f'Cliente {id_cliente} dado de baja correctamente (estado = OF).',
                'cliente': serializer.data,
            },
            status=status.HTTP_200_OK,
        )



class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all().order_by("nombre")
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ["get", "post", "put", "head", "options"]


class EstadoOrdenVentaViewSet(viewsets.ModelViewSet):
    """Catálogo de estados (Pendiente, Confirmada, Completada, etc.)."""

    queryset = EstadoOrdenVenta.objects.all().order_by("nombre")
    serializer_class = EstadoOrdenVentaSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ["get", "post", "put", "head", "options"]


class OrdenVentaViewSet(viewsets.ModelViewSet):
    """Registrar (POST), modificar cliente/forma de pago/estado (PUT)
    y listar/consultar (GET) órdenes de venta."""

    queryset = OrdenVenta.objects.select_related(
        "cliente", "estado", "usuario"
    ).prefetch_related("detalles")
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ["get", "post", "put", "head", "options"]

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return OrdenVentaUpdateSerializer
        return OrdenVentaSerializer


class OrdenVentaDetalleViewSet(viewsets.ModelViewSet):
    """Consulta del detalle. Es de SOLO LECTURA: el detalle se crea
    automáticamente junto con la orden de venta (ver OrdenVentaSerializer.create).

    No se habilita POST/PUT acá porque el serializer no completa
    'precio_unitario' (causaba un 500 IntegrityError) ni actualiza el
    stock del producto o el total de la orden, dejando los datos
    inconsistentes."""

    queryset = OrdenVentaDetalle.objects.select_related("orden_venta", "producto")
    serializer_class = OrdenVentaDetalleSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ["get", "head", "options"]
