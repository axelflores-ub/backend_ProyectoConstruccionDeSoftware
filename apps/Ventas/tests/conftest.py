"""Fixtures compartidas de los tests del módulo Ventas."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.SCM.models import Producto
from apps.Ventas import services
from apps.Ventas.models import Cliente


@pytest.fixture
def usuario(django_user_model):
    """Usuario autenticado. Funciona con el auth.User de Django o con un Usuario propio
    cuyo login sea el email."""
    campo = django_user_model.USERNAME_FIELD
    login = "vendedor@corralon.test" if campo == "email" else "vendedor"
    return django_user_model.objects.create_user(**{campo: login}, password="clave-de-prueba")


@pytest.fixture
def api_client(usuario):
    """Cliente HTTP ya autenticado (equivale a mandar un JWT válido)."""
    client = APIClient()
    client.force_authenticate(user=usuario)
    return client


@pytest.fixture
def anon_client():
    """Cliente HTTP sin autenticar."""
    return APIClient()


@pytest.fixture
def cliente(db):
    return Cliente.objects.create(nombre="Juan Pérez", cuil="20123456789")


@pytest.fixture
def crear_producto(db):
    """Fábrica de productos de SCM (el código es único y obligatorio)."""

    def _crear(codigo="CEM-001", nombre="Cemento 50kg", precio="100.00", stock=10):
        return Producto.objects.create(
            codigo=codigo, nombre=nombre, precio=Decimal(precio), stock_actual=stock
        )

    return _crear


@pytest.fixture
def producto(crear_producto):
    return crear_producto()


@pytest.fixture
def orden(cliente, producto, usuario):
    """Orden ya registrada: 3 unidades de `producto` (stock 10 -> 7), total 300."""
    return services.registrar_orden_venta(
        datos={"cliente": cliente, "forma_pago": "EFECTIVO"},
        detalles=[{"producto": producto, "cantidad": 3}],
        usuario=usuario,
    )
