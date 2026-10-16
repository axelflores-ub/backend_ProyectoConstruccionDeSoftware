# Vistas del módulo (DRF): ViewSets con la lógica de cada endpoint.
# Permisos: se usa el default global de settings.py (IsAuthenticated -> requiere JWT).
# Errores: todos los ViewSets usan el mismo formato de error (ver manejador_de_errores).
from rest_framework import exceptions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from . import services
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

CODIGOS_POR_ESTADO = {
    status.HTTP_400_BAD_REQUEST: "solicitud_invalida",
    status.HTTP_401_UNAUTHORIZED: "no_autenticado",
    status.HTTP_403_FORBIDDEN: "sin_permiso",
    status.HTTP_404_NOT_FOUND: "no_encontrado",
    status.HTTP_405_METHOD_NOT_ALLOWED: "metodo_no_permitido",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "formato_no_soportado",
}


def manejador_de_errores(exc, context):
    """Exception handler de DRF: mantiene los códigos HTTP y unifica el cuerpo de todo error:

        {"codigo": "stock_insuficiente", "mensaje": "Texto para mostrar.", "errores": {...}}

    `errores` solo aparece cuando hay detalle por campo (HTTP 400).
    """
    if isinstance(exc, services.ErrorDeNegocio):
        cuerpo = {"codigo": exc.codigo, "mensaje": exc.mensaje}
        if exc.campo:
            cuerpo["errores"] = {exc.campo: [exc.mensaje]}
        return Response(cuerpo, status=exc.status_code)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # error no controlado: que siga como 500

    if isinstance(exc, exceptions.ValidationError):
        errores = response.data
        if not isinstance(errores, dict):
            errores = {"non_field_errors": errores}
        response.data = {
            "codigo": "datos_invalidos",
            "mensaje": "Los datos enviados no son válidos.",
            "errores": errores,
        }
        return response

    detalle = response.data.get("detail", "") if isinstance(response.data, dict) else response.data
    if isinstance(exc, exceptions.AuthenticationFailed):
        codigo = "token_invalido"
    else:
        codigo = CODIGOS_POR_ESTADO.get(response.status_code, "error")
    response.data = {"codigo": codigo, "mensaje": str(detalle)}
    return response


class VentasViewSet(viewsets.ModelViewSet):
    """Base de los ViewSets de Ventas: errores con el formato estándar."""

    def get_exception_handler(self):
        return manejador_de_errores


class ClienteViewSet(VentasViewSet):
    """
    GET   /api/ventas/clientes/                -> Lista clientes (paginado).
    GET   /api/ventas/clientes/?cuil=<cuil>    -> Busca por CUIL exacto (acepta guiones).
    GET   /api/ventas/clientes/?search=<texto> -> Búsqueda libre (CUIL, nombre, email, teléfono).
    POST  /api/ventas/clientes/                -> Alta (siempre activo, 'AC').
    GET   /api/ventas/clientes/<id_cliente>/   -> Obtiene un cliente.
    PUT   /api/ventas/clientes/<id_cliente>/   -> Actualiza un cliente.
    PATCH /api/ventas/clientes/<id_cliente>/   -> Baja lógica: {"estado": "OF"} (reactivar: "AC").

    No existe DELETE: los clientes nunca se borran físicamente.
    """

    queryset = Cliente.objects.all()  # sin relaciones: no hay nada que precargar
    serializer_class = ClienteSerializer
    lookup_field = "id_cliente"
    lookup_value_regex = r"\d+"
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    search_fields = ["nombre", "email", "telefono", "cuil"]
    ordering_fields = ["id_cliente", "nombre", "estado"]

    def get_queryset(self):
        queryset = super().get_queryset()
        cuil = self.request.query_params.get("cuil") if self.action == "list" else None
        if cuil is not None:
            cuil = services.normalizar_cuil(cuil)
            if len(cuil) != 11:
                raise exceptions.ValidationError({"cuil": ["El CUIL debe tener 11 dígitos."]})
            queryset = queryset.filter(cuil=cuil)
        return queryset

    def perform_create(self, serializer):
        # Un cliente nuevo siempre se crea activo, sin importar lo que venga en el body.
        serializer.save(estado=Cliente.ESTADO_ACTIVO)


class EstadoOrdenVentaViewSet(VentasViewSet):
    """Catálogo de estados de la orden de venta (Pendiente, Anulada, Devolución parcial,
    Devolución total). Solo lectura: el estado cambia con las operaciones de la orden."""

    queryset = EstadoOrdenVenta.objects.all().order_by("nombre")  # sin relaciones
    serializer_class = EstadoOrdenVentaSerializer
    http_method_names = ["get", "head", "options"]
    search_fields = ["nombre"]
    ordering_fields = ["nombre"]


class OrdenVentaViewSet(VentasViewSet):
    """Generar una orden de venta (POST, el cliente se obtiene por CUIL), modificar forma
    de pago y comprobante mientras esté Pendiente (PUT/PATCH) y consultar (GET)."""

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


class OrdenVentaDetalleViewSet(VentasViewSet):
    """Consulta del detalle. Es de SOLO LECTURA: el detalle se crea automáticamente junto
    con la orden de venta (ver services.registrar_orden_venta)."""

    queryset = OrdenVentaDetalle.objects.select_related("orden_venta", "producto")
    serializer_class = OrdenVentaDetalleSerializer
    http_method_names = ["get", "head", "options"]
    search_fields = ["producto__nombre", "orden_venta__numero_comprobante"]
    ordering_fields = ["id", "cantidad"]


class AnulacionViewSet(VentasViewSet):
    """Anular una orden de venta Pendiente (Devoluciones -> botón 'Anular').
    Solo lectura + alta: una anulación, una vez creada, no se edita ni se borra
    (es un registro de auditoría)."""

    queryset = Anulacion.objects.select_related("orden_venta")
    serializer_class = AnulacionSerializer
    http_method_names = ["get", "post", "head", "options"]
    search_fields = ["motivo", "orden_venta__numero_comprobante"]
    ordering_fields = ["id", "fecha"]


class NotaCreditoViewSet(VentasViewSet):
    """Registrar una devolución. Valida lo devuelto contra lo vendido, calcula el monto,
    repone stock de los ítems a 'stock disponible' y deja la orden en 'Devolución parcial'
    o 'Devolución total'. No se edita ni se borra una vez creada."""

    queryset = NotaCredito.objects.select_related("orden_venta").prefetch_related(
        "detalles__producto"
    )
    serializer_class = NotaCreditoSerializer
    http_method_names = ["get", "post", "head", "options"]
    search_fields = ["orden_venta__numero_comprobante"]
    ordering_fields = ["id", "fecha", "monto"]


class DetalleNotaCreditoViewSet(VentasViewSet):
    """Consulta del detalle de notas de crédito. Solo lectura: el detalle se crea
    automáticamente junto con la nota de crédito."""

    queryset = DetalleNotaCredito.objects.select_related("nota_credito", "producto")
    serializer_class = DetalleNotaCreditoSerializer
    http_method_names = ["get", "head", "options"]
    search_fields = ["producto__nombre"]
    ordering_fields = ["id", "cantidad_devuelta"]
