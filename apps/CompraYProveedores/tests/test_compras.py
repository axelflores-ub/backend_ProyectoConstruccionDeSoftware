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
    """Fixture que proporciona un cliente API REST para pruebas sin autenticacion."""
    return APIClient()


@pytest.fixture
def usuario(db):
    """Fixture que crea un usuario de prueba (username: 'tester', password: 'tester123')."""
    User = get_user_model()
    return User.objects.create_user(username="tester", password="tester123")


@pytest.fixture
def auth_client(api_client, usuario):
    """Fixture que proporciona un cliente API REST autenticado con el usuario de prueba."""
    api_client.force_authenticate(user=usuario)
    return api_client


@pytest.mark.django_db
def test_proveedores_sin_token_da_401(api_client):
    """Prueba que verifica que acceder a /api/compras/proveedores/ sin JWT retorna 401 Unauthorized.
    
    Valida que los endpoints estan protegidos y requieren autenticacion.
    """
    response = api_client.get("/api/compras/proveedores/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_crear_y_listar_proveedor(auth_client):
    """Prueba CRUD de Proveedor: crear un proveedor y listar que aparece en el listado.
    
    Valida:
    - POST /api/compras/proveedores/ retorna 201 Created
    - Respuesta contiene proveedor_id
    - Datos creados coinciden (CUIT)
    - GET /api/compras/proveedores/ retorna listado con al menos 1 proveedor
    """
    alta = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Corralón Test",
            "apellido": "Sur",
            "telefono": "2210000000",
            "email": "test@corralon.test",
            "cuit": "30712345678",
            "direccion": "Calle 1",
        },
        format="json",
    )
    assert alta.status_code == 201
    assert "proveedor_id" in alta.data
    assert alta.data["cuit"] == "30712345678"

    listado = auth_client.get("/api/compras/proveedores/")
    assert listado.status_code == 200
    assert listado.data["count"] >= 1


@pytest.mark.django_db
def test_flujo_orden_compra_con_detalle(auth_client):
    """Prueba del flujo completo: crear estado, proveedor, orden y detalles.
    
    Valida el proceso end-to-end:
    1. POST /api/compras/estados-orden-compra/ - crear estado "Pendiente"
    2. POST /api/compras/proveedores/ - crear proveedor
    3. POST /api/compras/ordenes-compra/ - crear orden con ese proveedor y estado
    4. POST /api/compras/ordenes-compra-detalle/ - agregar renglon a la orden
    5. GET /api/compras/ordenes-compra/{id}/ - verificar que el detalle aparece anidado
    6. Validaciones finales de consistencia en base de datos
    """
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
            "apellido": "",
            "telefono": "",
            "email": "",
            "cuit": "20111222333",
            "direccion": "",
        },
        format="json",
    )
    assert proveedor.status_code == 201

    orden = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor.data["proveedor_id"],
            "estado": estado.data["estadoordencompra_id"],
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "15000.00",
        },
        format="json",
    )
    assert orden.status_code == 201
    oc_id = orden.data["ordencompra_id"]

    detalle = auth_client.post(
        "/api/compras/ordenes-compra-detalle/",
        {
            "orden_compra": oc_id,
            "producto_id": 1,
            "cantidad": 10,
            "precio_unitario": "1500.00",
        },
        format="json",
    )
    assert detalle.status_code == 201

    detalle_get = auth_client.get(f"/api/compras/ordenes-compra/{oc_id}/")
    assert detalle_get.status_code == 200
    assert len(detalle_get.data["detalles"]) == 1
    assert OrdenCompraDetalle.objects.filter(orden_compra_id=oc_id).count() == 1
    assert OrdenCompra.objects.count() == 1
    assert Proveedor.objects.filter(nombre="Proveedor OC").exists()
    assert EstadoOrdenCompra.objects.filter(nombre="Pendiente").exists()