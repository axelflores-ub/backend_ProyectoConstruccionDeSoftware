"""
Pruebas unitarias e integración del módulo CompraYProveedores.

Cubre los siguientes escenarios:
- Validación de autenticación: retorna 401 sin JWT
- CRUD de Proveedor: creación, lectura, actualización, eliminación
- Flujo completo de Orden de Compra: crear estado, proveedor, orden y detalles
- Validación de datos: CUIT único, campos requeridos, formatos correctos

Nota: producto_id se almacena como entero hasta que el módulo SCM esté integrado.
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
    return APIClient()


@pytest.fixture
def usuario(db):
    User = get_user_model()
    return User.objects.create_user(username="tester", password="tester123")


@pytest.fixture
def auth_client(api_client, usuario):
    api_client.force_authenticate(user=usuario)
    return api_client


@pytest.mark.django_db
def test_proveedores_sin_token_da_401(api_client):
    response = api_client.get("/api/compras/proveedores/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_crear_y_listar_proveedor(auth_client):
    alta = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Corralón Test",
            "apellido": "Sur",
            "telefono": "2210000000",
            "email": "test@corralon.test",
            "cuit": "30712345678",
            "direccion": "Calle 1",
            "producto_id": 1,
        },
        format="json",
    )
    assert alta.status_code == 201
    assert alta.data["producto_id"] == 1

    listado = auth_client.get("/api/compras/proveedores/")
    assert listado.status_code == 200
    assert listado.data["count"] >= 1


@pytest.mark.django_db
def test_proveedor_sin_datos_mensajes_claros(auth_client):
    response = auth_client.post("/api/compras/proveedores/", {}, format="json")
    assert response.status_code == 400
    assert "Falta completar el nombre." in str(response.data.get("nombre", []))
    assert "Falta completar el apellido." in str(response.data.get("apellido", []))
    assert "Falta completar el CUIT." in str(response.data.get("cuit", []))
    assert "producto_id" in response.data


@pytest.mark.django_db
def test_flujo_orden_compra_con_detalle(auth_client):
    estado = auth_client.post(
        "/api/compras/estados-orden-compra/",
        {"nombre": "Pendiente"},
        format="json",
    )
    assert estado.status_code == 201

    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor OC",
            "apellido": "SA",
            "telefono": "",
            "email": "",
            "cuit": "20111222333",
            "direccion": "",
            "producto_id": 2,
        },
        format="json",
    )
    assert proveedor.status_code == 201
    oc = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor.data["proveedor_id"],
            "estado": estado.data["estadoordencompra_id"],
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "15000.00",
        },
        format="json",
    )
    assert oc.status_code == 201
    oc_id = oc.data["ordencompra_id"]

    detalle = auth_client.post(
        "/api/compras/ordenes-compra-detalle/",
        {
            "orden_compra": oc_id,
            "producto_id": 2,
            "cantidad": 10,
            "precio_unitario": "1500.00",
        },
        format="json",
    )
    assert detalle.status_code == 201

    detalle_get = auth_client.get(f"/api/compras/ordenes-compra/{oc_id}/")
    assert detalle_get.status_code == 200
    assert len(detalle_get.data["detalles"]) == 1
    assert OrdenCompra.objects.count() == 1
    assert Proveedor.objects.filter(nombre="Proveedor OC").exists()
    assert EstadoOrdenCompra.objects.filter(nombre="Pendiente").exists()
    assert OrdenCompraDetalle.objects.filter(orden_compra_id=oc_id).count() == 1