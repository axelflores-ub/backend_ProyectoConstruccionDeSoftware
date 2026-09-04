"""
Pruebas del módulo CompraYProveedores.

Cubre el contrato del README:
- 401 sin JWT
- CRUD de proveedor
- alta de estado + OC + detalle (producto_id numérico hasta que exista SCM)
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.CompraYProveedores.models import (
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
)


@pytest.fixture
def api_client():
    """Cliente HTTP de DRF (requests JSON)."""
    return APIClient()


@pytest.fixture
def usuario(db):
    """Usuario de prueba para autenticar los endpoints protegidos."""
    User = get_user_model()
    return User.objects.create_user(username="tester", password="tester123")


@pytest.fixture
def auth_client(api_client, usuario):
    """Cliente ya autenticado (equivalente a mandar el Bearer)."""
    api_client.force_authenticate(user=usuario)
    return api_client


@pytest.mark.django_db
def test_proveedores_sin_token_da_401(api_client):
    """Sin JWT el listado tiene que rechazar. Confirma IsAuthenticated."""
    response = api_client.get("/api/compras/proveedores/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_crear_y_listar_proveedor(auth_client):
    """POST crea un proveedor y GET lo devuelve paginado."""
    alta = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Corralón Test",
            "telefono": "2210000000",
            "email": "test@corralon.test",
            "direccion": "Calle 1",
        },
        format="json",
    )
    assert alta.status_code == 201
    assert alta.data["nombre"] == "Corralón Test"

    listado = auth_client.get("/api/compras/proveedores/")
    assert listado.status_code == 200
    assert listado.data["count"] == 1
    assert listado.data["results"][0]["nombre"] == "Corralón Test"


@pytest.mark.django_db
def test_flujo_orden_compra_con_detalle(auth_client):
    """
    Flujo mínimo de negocio:
    estado -> proveedor -> cabecera OC -> renglón con producto_id.
    """
    estado = auth_client.post(
        "/api/compras/estados-orden-compra/",
        {"nombre": "Pendiente"},
        format="json",
    )
    assert estado.status_code == 201

    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {"nombre": "Proveedor OC", "telefono": "", "email": "", "direccion": ""},
        format="json",
    )
    assert proveedor.status_code == 201

    orden = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor.data["id"],
            "estado": estado.data["id"],
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "15000.00",
        },
        format="json",
    )
    assert orden.status_code == 201
    assert orden.data["detalles"] == []

    detalle = auth_client.post(
        "/api/compras/ordenes-compra-detalle/",
        {
            "orden_compra": orden.data["id"],
            "producto_id": 1,
            "cantidad": 10,
            "precio_unitario": "1500.00",
        },
        format="json",
    )
    assert detalle.status_code == 201
    assert detalle.data["producto_id"] == 1
    assert detalle.data["cantidad"] == 10

    detalle_get = auth_client.get(f"/api/compras/ordenes-compra/{orden.data['id']}/")
    assert detalle_get.status_code == 200
    assert len(detalle_get.data["detalles"]) == 1
    assert OrdenCompraDetalle.objects.filter(orden_compra_id=orden.data["id"]).count() == 1
    assert OrdenCompra.objects.count() == 1
    assert Proveedor.objects.filter(nombre="Proveedor OC").exists()
    assert EstadoOrdenCompra.objects.filter(nombre="Pendiente").exists()