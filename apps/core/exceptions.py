"""Manejo global de excepciones de DRF."""

from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _nombre_modelo(context):
    """Nombre legible del recurso que se intentó borrar (ej. "rubro")."""
    view = context.get("view")
    queryset = getattr(view, "queryset", None)
    if queryset is None:
        return "registro"
    return str(queryset.model._meta.verbose_name).lower()


def custom_exception_handler(exc, context):
    """Convierte ProtectedError (FK con on_delete=PROTECT) en un 409 con mensaje claro.

    Sin esto, borrar un registro con dependientes devuelve 500. El resto de
    las excepciones sigue el manejo estándar de DRF.
    """
    if isinstance(exc, ProtectedError):
        dependientes = sorted(
            {str(obj._meta.verbose_name_plural).lower() for obj in exc.protected_objects}
        )
        detalle = (
            f"No se puede eliminar el {_nombre_modelo(context)} "
            f"porque tiene registros asociados: {', '.join(dependientes)}."
        )
        return Response({"detail": detalle}, status=status.HTTP_409_CONFLICT)
    return exception_handler(exc, context)
