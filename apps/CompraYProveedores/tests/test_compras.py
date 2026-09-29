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
from django.urls import Resolver404, resolve
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
            "productos": [1],
        },
        format="json",
    )
    assert alta.status_code == 201
    assert 1 in alta.data["productos"]

    listado = auth_client.get("/api/compras/proveedores/")
    assert listado.status_code == 200
    assert listado.data["count"] >= 1


@pytest.mark.django_db
def test_cuit_con_y_sin_guiones_es_el_mismo_proveedor(auth_client):
    alta = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Madera Norte",
            "apellido": "SA",
            "cuit": "20442152099",
            "productos": [10],
        },
        format="json",
    )
    assert alta.status_code == 201
    proveedor_id = alta.data["proveedor_id"]

    repetido = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Madera Norte Bis",
            "apellido": "SRL",
            "cuit": "20-44215209-9",
            "productos": [11],
        },
        format="json",
    )
    assert repetido.status_code == 400
    assert "Ya existe un proveedor con ese CUIT." in str(repetido.data.get("cuit", []))

    detalle = auth_client.get(f"/api/compras/proveedores/{proveedor_id}/")
    assert detalle.status_code == 200
    assert detalle.data["cuit"] == "20-44215209-9"


@pytest.mark.django_db
def test_proveedor_sin_datos_mensajes_claros(auth_client):
    response = auth_client.post("/api/compras/proveedores/", {}, format="json")
    assert response.status_code == 400
    assert "Falta completar el nombre." in str(response.data.get("nombre", []))
    assert "Falta completar el apellido." in str(response.data.get("apellido", []))
    assert "Falta completar el CUIT." in str(response.data.get("cuit", []))
    assert "productos" in response.data


def _id_estado(client, nombre):
    respuesta = client.get("/api/compras/estados-orden-compra/")
    assert respuesta.status_code == 200
    for estado in respuesta.data["results"]:
        if estado["nombre"] == nombre:
            return estado["estadoordencompra_id"]
    raise AssertionError(f"No está el estado {nombre}")


@pytest.mark.django_db
def test_alta_de_orden_trae_renglones_y_queda_pendiente(auth_client):
    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor OC",
            "apellido": "SA",
            "cuit": "27111222334",
            "productos": [2],
        },
        format="json",
    )
    assert proveedor.status_code == 201

    alta = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor.data["proveedor_id"],
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "15000.00",
            "detalles": [{"productos": [2], "cantidad": 10, "precio_unitario": "1500.00"}],
        },
        format="json",
    )
    assert alta.status_code == 201

    detalle = auth_client.get(f"/api/compras/ordenes-compra/{alta.data['ordencompra_id']}/")
    assert detalle.status_code == 200
    assert detalle.data["estado"] == _id_estado(auth_client, "Pendiente")
    assert len(detalle.data["detalles"]) == 1
    renglon = detalle.data["detalles"][0]
    assert renglon["producto_id"] == 2
    assert renglon["cantidad"] == 10
    assert renglon["precio_unitario"] == "1500.00"
    assert isinstance(renglon["ordencompradetalle_id"], int)
    assert "orden_compra" not in renglon


@pytest.mark.django_db
def test_alta_de_orden_no_acepta_otro_estado_que_pendiente(auth_client):
    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor Estado",
            "apellido": "SA",
            "cuit": "30111222335",
            "productos": [3],
        },
        format="json",
    )
    assert proveedor.status_code == 201

    alta = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor.data["proveedor_id"],
            "estado": _id_estado(auth_client, "Recibida"),
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "100.00",
            "detalles": [{"productos": [3], "cantidad": 1, "precio_unitario": "100.00"}],
        },
        format="json",
    )
    assert alta.status_code == 400

    listado = auth_client.get("/api/compras/ordenes-compra/")
    assert listado.status_code == 200
    assert listado.data["count"] == 0


@pytest.mark.django_db
def test_orden_pendiente_no_pasa_directo_a_recibida(auth_client):
    rubro = auth_client.post(
        "/api/scm/rubros/",
        {"nombre": "Madera", "descripcion": "Tablas"},
        format="json",
    )
    assert rubro.status_code == 201
    producto = auth_client.post(
        "/api/scm/productos/",
        {
            "codigo": "MAD-001",
            "nombre": "Tabla de pino",
            "precio": "500.00",
            "rubro": rubro.data["id"],
            "stock_minimo": 0,
        },
        format="json",
    )
    assert producto.status_code == 201
    producto_id = producto.data["id"]

    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor Salto",
            "apellido": "SA",
            "cuit": "23111222336",
            "productos": [producto_id],
        },
        format="json",
    )
    assert proveedor.status_code == 201
    alta = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor.data["proveedor_id"],
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "500.00",
            "detalles": [
                {
                    "productos": [producto_id],
                    "cantidad": 1,
                    "precio_unitario": "500.00",
                }
            ],
        },
        format="json",
    )
    assert alta.status_code == 201
    oc_id = alta.data["ordencompra_id"]

    salto = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"estado": _id_estado(auth_client, "Recibida")},
        format="json",
    )
    assert salto.status_code == 400

    detalle = auth_client.get(f"/api/compras/ordenes-compra/{oc_id}/")
    assert detalle.status_code == 200
    assert detalle.data["estado"] == _id_estado(auth_client, "Pendiente")


@pytest.mark.django_db
def test_orden_rechazada_no_vuelve_a_aprobada(auth_client):
    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor Rechazo",
            "apellido": "SA",
            "cuit": "24111222337",
            "productos": [40],
        },
        format="json",
    )
    assert proveedor.status_code == 201
    alta = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor.data["proveedor_id"],
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "800.00",
        },
        format="json",
    )
    assert alta.status_code == 201
    oc_id = alta.data["ordencompra_id"]

    rechazo = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"estado": _id_estado(auth_client, "Rechazada")},
        format="json",
    )
    assert rechazo.status_code == 200

    vuelta = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"estado": _id_estado(auth_client, "Aprobada")},
        format="json",
    )
    assert vuelta.status_code == 400

    detalle = auth_client.get(f"/api/compras/ordenes-compra/{oc_id}/")
    assert detalle.status_code == 200
    assert detalle.data["estado"] == _id_estado(auth_client, "Rechazada")


@pytest.mark.django_db
def test_orden_aprobada_no_cambia_el_total(auth_client):
    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor Total",
            "apellido": "SA",
            "cuit": "25111222338",
            "productos": [41],
        },
        format="json",
    )
    assert proveedor.status_code == 201
    alta = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor.data["proveedor_id"],
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "800.00",
        },
        format="json",
    )
    assert alta.status_code == 201
    oc_id = alta.data["ordencompra_id"]

    aprobada = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"estado": _id_estado(auth_client, "Aprobada")},
        format="json",
    )
    assert aprobada.status_code == 200

    cambio = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"total": "999.00"},
        format="json",
    )
    assert cambio.status_code == 400

    detalle = auth_client.get(f"/api/compras/ordenes-compra/{oc_id}/")
    assert detalle.status_code == 200
    assert detalle.data["total"] == "800.00"


@pytest.mark.django_db
def test_orden_aprobada_no_vuelve_a_pendiente(auth_client):
    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor Vuelta",
            "apellido": "SA",
            "cuit": "26111222339",
            "productos": [42],
        },
        format="json",
    )
    assert proveedor.status_code == 201
    alta = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor.data["proveedor_id"],
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "800.00",
        },
        format="json",
    )
    assert alta.status_code == 201
    oc_id = alta.data["ordencompra_id"]
    assert (
        auth_client.patch(
            f"/api/compras/ordenes-compra/{oc_id}/",
            {"estado": _id_estado(auth_client, "Aprobada")},
            format="json",
        ).status_code
        == 200
    )

    vuelta = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"estado": _id_estado(auth_client, "Pendiente")},
        format="json",
    )
    assert vuelta.status_code == 400

    detalle = auth_client.get(f"/api/compras/ordenes-compra/{oc_id}/")
    assert detalle.data["estado"] == _id_estado(auth_client, "Aprobada")


@pytest.mark.django_db
def test_no_se_puede_crear_un_estado_de_orden(auth_client):
    respuesta = auth_client.post(
        "/api/compras/estados-orden-compra/",
        {"nombre": "Cancelada"},
        format="json",
    )
    assert respuesta.status_code == 405


@pytest.mark.django_db
def test_el_detalle_de_la_orden_no_tiene_endpoint_propio():
    # El cliente de tests no puede leer el 404 de una ruta inexistente: al
    # armar la página, Django revienta en Python 3.14. La ruta no resuelve.
    with pytest.raises(Resolver404):
        resolve("/api/compras/ordenes-compra-detalle/")


@pytest.mark.django_db
def test_flujo_orden_compra_con_detalle(auth_client):
    # "Pendiente" ya viene cargado por la migración 0003.
    estado = EstadoOrdenCompra.objects.get(nombre="Pendiente")

    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor OC",
            "apellido": "SA",
            "telefono": "",
            "email": "",
            "cuit": "20111222333",
            "direccion": "",
            "productos": [2],
        },
        format="json",
    )
    assert proveedor.status_code == 201
    oc = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor.data["proveedor_id"],
            "estado": estado.estadoordencompra_id,
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "15000.00",
            "detalles": [{"productos": [2], "cantidad": 10, "precio_unitario": "1500.00"}],
        },
        format="json",
    )
    assert oc.status_code == 201
    oc_id = oc.data["ordencompra_id"]

    detalle_get = auth_client.get(f"/api/compras/ordenes-compra/{oc_id}/")
    assert detalle_get.status_code == 200
    assert len(detalle_get.data["detalles"]) == 1
    assert OrdenCompra.objects.count() == 1
    assert Proveedor.objects.filter(nombre="Proveedor OC").exists()
    assert EstadoOrdenCompra.objects.filter(nombre="Pendiente").exists()
    assert OrdenCompraDetalle.objects.filter(orden_compra_id=oc_id).count() == 1


def _orden(client, proveedor_id, total, producto_id, cantidad, precio):
    respuesta = client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor_id,
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": total,
            "detalles": [
                {
                    "productos": [producto_id],
                    "cantidad": cantidad,
                    "precio_unitario": precio,
                }
            ],
        },
        format="json",
    )
    assert respuesta.status_code == 201, respuesta.data
    return respuesta.data["ordencompra_id"]


def _estado(client, oc_id):
    respuesta = client.get(f"/api/compras/ordenes-compra/{oc_id}/")
    assert respuesta.status_code == 200
    return respuesta.data


@pytest.mark.django_db
def test_recorrido_completo_del_modulo(auth_client):
    assert APIClient().get("/api/compras/proveedores/").status_code == 401

    catalogo = auth_client.get("/api/compras/estados-orden-compra/")
    assert catalogo.status_code == 200
    assert {estado["nombre"] for estado in catalogo.data["results"]} == {
        "Pendiente",
        "Aprobada",
        "Rechazada",
        "Recibida",
    }
    assert (
        auth_client.post(
            "/api/compras/estados-orden-compra/",
            {"nombre": "Cancelada"},
            format="json",
        ).status_code
        == 405
    )

    rubro = auth_client.post(
        "/api/scm/rubros/",
        {"nombre": "Recorrido", "descripcion": "Prueba del módulo"},
        format="json",
    )
    assert rubro.status_code == 201
    producto = auth_client.post(
        "/api/scm/productos/",
        {
            "codigo": "REC-001",
            "nombre": "Tabla de prueba",
            "precio": "100.00",
            "rubro": rubro.data["id"],
            "stock_minimo": 0,
        },
        format="json",
    )
    assert producto.status_code == 201
    producto_id = producto.data["id"]
    assert producto.data["stock_actual"] == 0

    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Maderas del Norte",
            "apellido": "SA",
            "cuit": "20442152099",
            "productos": [producto_id],
        },
        format="json",
    )
    assert proveedor.status_code == 201
    assert proveedor.data["cuit"] == "20-44215209-9"
    proveedor_id = proveedor.data["proveedor_id"]

    repetido = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Maderas del Norte Bis",
            "apellido": "SRL",
            "cuit": "20-44215209-9",
            "productos": [producto_id + 1],
        },
        format="json",
    )
    assert repetido.status_code == 400
    assert "Ya existe un proveedor con ese CUIT." in str(repetido.data["cuit"])

    oc_id = _orden(auth_client, proveedor_id, "400.00", producto_id, 4, "100.00")
    pendiente = _estado(auth_client, oc_id)
    assert pendiente["estado"] == _id_estado(auth_client, "Pendiente")
    assert pendiente["detalles"][0]["producto_id"] == producto_id
    assert pendiente["detalles"][0]["cantidad"] == 4
    assert pendiente["detalles"][0]["precio_unitario"] == "100.00"

    salto = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"estado": _id_estado(auth_client, "Recibida")},
        format="json",
    )
    assert salto.status_code == 400
    assert _estado(auth_client, oc_id)["estado"] == _id_estado(auth_client, "Pendiente")

    aprobada = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"estado": _id_estado(auth_client, "Aprobada")},
        format="json",
    )
    assert aprobada.status_code == 200
    assert _estado(auth_client, oc_id)["estado"] == _id_estado(auth_client, "Aprobada")
    stock = auth_client.get(f"/api/scm/productos/{producto_id}/")
    assert stock.data["stock_actual"] == 0

    cambio_total = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"total": "1.00"},
        format="json",
    )
    assert cambio_total.status_code == 400
    assert _estado(auth_client, oc_id)["total"] == "400.00"

    vuelve = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"estado": _id_estado(auth_client, "Pendiente")},
        format="json",
    )
    assert vuelve.status_code == 400
    assert _estado(auth_client, oc_id)["estado"] == _id_estado(auth_client, "Aprobada")

    recibida = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"estado": _id_estado(auth_client, "Recibida")},
        format="json",
    )
    assert recibida.status_code == 200
    assert _estado(auth_client, oc_id)["estado"] == _id_estado(auth_client, "Recibida")
    stock = auth_client.get(f"/api/scm/productos/{producto_id}/")
    assert stock.data["stock_actual"] == 4

    despues = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"estado": _id_estado(auth_client, "Aprobada")},
        format="json",
    )
    assert despues.status_code == 400
    assert _estado(auth_client, oc_id)["estado"] == _id_estado(auth_client, "Recibida")
    stock = auth_client.get(f"/api/scm/productos/{producto_id}/")
    assert stock.data["stock_actual"] == 4

    oc_rechazada = _orden(auth_client, proveedor_id, "200.00", producto_id, 2, "100.00")
    rechazo = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_rechazada}/",
        {"estado": _id_estado(auth_client, "Rechazada")},
        format="json",
    )
    assert rechazo.status_code == 200
    reabre = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_rechazada}/",
        {"estado": _id_estado(auth_client, "Aprobada")},
        format="json",
    )
    assert reabre.status_code == 400
    assert _estado(auth_client, oc_rechazada)["estado"] == _id_estado(auth_client, "Rechazada")
    stock = auth_client.get(f"/api/scm/productos/{producto_id}/")
    assert stock.data["stock_actual"] == 4

    with pytest.raises(Resolver404):
        resolve("/api/compras/ordenes-compra-detalle/")
