"""
Pruebas unitarias e integración del módulo CompraYProveedores.

Cubre los siguientes escenarios:
- Validación de autenticación: retorna 401 sin JWT
- CRUD de Proveedor: creación, lectura, actualización, eliminación
- Flujo completo de Orden de Compra: crear estado, proveedor, orden y detalles
- Validación de datos: CUIT único, campos requeridos, formatos correctos

Nota: el renglón guarda producto_id como entero. El proveedor se vincula
a uno o más productos de SCM, con el precio de compra en cada vínculo.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import Resolver404, resolve
from django.utils import timezone
from rest_framework.test import APIClient

from apps.CompraYProveedores.models import (
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
    ProveedorProducto,
)
from apps.SCM.models import Producto


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


def _producto(codigo):
    return Producto.objects.create(
        codigo=codigo,
        nombre=f"Producto {codigo}",
        precio="10.00",
    )


def _catalogo(producto_id, precio="10.00"):
    ids = producto_id if isinstance(producto_id, list) else [producto_id]
    return [{"producto_id": pk, "precio_compra": precio} for pk in ids]


def _por_producto(productos):
    return sorted(productos, key=lambda item: item["producto_id"])


@pytest.mark.django_db
def test_proveedores_sin_token_da_401(api_client):
    response = api_client.get("/api/compras/proveedores/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_crear_y_listar_proveedor(auth_client):
    producto = _producto("PRV-001")
    alta = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Corralón Test",
            "apellido": "Sur",
            "telefono": "2210000000",
            "email": "test@corralon.test",
            "cuit": "30712345678",
            "direccion": "Calle 1",
            "productos": _catalogo(producto.pk),
        },
        format="json",
    )
    assert alta.status_code == 201
    assert alta.data["productos"] == _catalogo(producto.pk)

    listado = auth_client.get("/api/compras/proveedores/")
    assert listado.status_code == 200
    assert listado.data["count"] >= 1


@pytest.mark.django_db
def test_cuit_con_y_sin_guiones_es_el_mismo_proveedor(auth_client):
    producto = _producto("CUIT-001")
    alta = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Madera Norte",
            "apellido": "SA",
            "cuit": "20442152099",
            "productos": _catalogo(producto.pk),
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
            "productos": _catalogo(producto.pk),
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


@pytest.mark.django_db
def test_un_proveedor_puede_tener_varios_productos_y_compartirlos(auth_client):
    tabla = _producto("MM-TABLA")
    clavo = _producto("MM-CLAVO")
    primero = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Corralón Norte",
            "apellido": "SA",
            "cuit": "30111000111",
            "productos": [
                {"producto_id": tabla.pk, "precio_compra": "1500.00"},
                {"producto_id": clavo.pk, "precio_compra": "25.50"},
            ],
        },
        format="json",
    )
    assert primero.status_code == 201
    assert primero.data["productos"] == _por_producto(
        [
            {"producto_id": tabla.pk, "precio_compra": "1500.00"},
            {"producto_id": clavo.pk, "precio_compra": "25.50"},
        ]
    )

    segundo = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Corralón Sur",
            "apellido": "SA",
            "cuit": "30111000222",
            "productos": _catalogo(tabla.pk, "900.00"),
        },
        format="json",
    )
    assert segundo.status_code == 201
    assert segundo.data["productos"] == _catalogo(tabla.pk, "900.00")


@pytest.mark.django_db
def test_el_precio_de_compra_sale_en_el_listado_y_en_el_detalle(auth_client):
    tabla = _producto("PRE-TABLA")
    clavo = _producto("PRE-CLAVO")
    esperado = _por_producto(
        [
            {"producto_id": tabla.pk, "precio_compra": "1500.00"},
            {"producto_id": clavo.pk, "precio_compra": "25.50"},
        ]
    )
    alta = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Corralón Precio",
            "apellido": "SA",
            "cuit": "30111000333",
            "productos": esperado,
        },
        format="json",
    )
    assert alta.status_code == 201, alta.data
    proveedor_id = alta.data["proveedor_id"]
    assert alta.data["productos"] == esperado

    detalle = auth_client.get(f"/api/compras/proveedores/{proveedor_id}/")
    assert detalle.status_code == 200
    assert detalle.data["productos"] == esperado

    listado = auth_client.get("/api/compras/proveedores/")
    assert listado.status_code == 200
    guardado = next(
        item for item in listado.data["results"] if item["proveedor_id"] == proveedor_id
    )
    assert guardado["productos"] == esperado

    mismo_nombre = auth_client.patch(
        f"/api/compras/proveedores/{proveedor_id}/",
        {"nombre": "Corralón Precio Actualizado"},
        format="json",
    )
    assert mismo_nombre.status_code == 200
    assert mismo_nombre.data["productos"] == esperado

    actualizado = _por_producto(
        [
            {"producto_id": tabla.pk, "precio_compra": "1600.00"},
            {"producto_id": clavo.pk, "precio_compra": "25.50"},
        ]
    )
    cambio = auth_client.patch(
        f"/api/compras/proveedores/{proveedor_id}/",
        {"productos": actualizado},
        format="json",
    )
    assert cambio.status_code == 200, cambio.data
    assert cambio.data["productos"] == actualizado
    assert (
        auth_client.get(f"/api/compras/proveedores/{proveedor_id}/").data["productos"]
        == actualizado
    )


@pytest.mark.django_db
def test_el_precio_de_compra_se_valida(auth_client):
    producto = _producto("PRE-VAL")
    base = {"nombre": "Valida Precio", "apellido": "SA", "cuit": "30111000444"}

    sin_precio = auth_client.post(
        "/api/compras/proveedores/",
        {**base, "productos": [{"producto_id": producto.pk}]},
        format="json",
    )
    assert sin_precio.status_code == 400
    assert "Falta el precio de compra." in str(sin_precio.data)

    formato_viejo = auth_client.post(
        "/api/compras/proveedores/",
        {**base, "productos": [producto.pk]},
        format="json",
    )
    assert formato_viejo.status_code == 400
    assert "El formato de productos no es válido." in str(formato_viejo.data)

    negativo = auth_client.post(
        "/api/compras/proveedores/",
        {**base, "productos": _catalogo(producto.pk, "-1.00")},
        format="json",
    )
    assert negativo.status_code == 400
    assert "El precio de compra no puede ser negativo." in str(negativo.data)

    inexistente = auth_client.post(
        "/api/compras/proveedores/",
        {**base, "productos": [{"producto_id": 999999, "precio_compra": "1.00"}]},
        format="json",
    )
    assert inexistente.status_code == 400
    assert "El producto 999999 no existe." in str(inexistente.data)

    repetido = auth_client.post(
        "/api/compras/proveedores/",
        {
            **base,
            "productos": _catalogo(producto.pk, "10.00") + _catalogo(producto.pk, "12.00"),
        },
        format="json",
    )
    assert repetido.status_code == 400
    assert f"El producto {producto.pk} está repetido." in str(repetido.data)
    assert Proveedor.objects.filter(nombre="Valida Precio").count() == 0


@pytest.mark.django_db
def test_un_vinculo_sin_precio_se_lee_en_null(auth_client):
    producto = _producto("PRE-NULL")
    proveedor = Proveedor.objects.create(nombre="Viejo", apellido="SA", cuit="30999000111")
    ProveedorProducto.objects.create(proveedor=proveedor, producto=producto, precio_compra=None)

    detalle = auth_client.get(f"/api/compras/proveedores/{proveedor.pk}/")
    assert detalle.status_code == 200
    assert detalle.data["productos"] == [{"producto_id": producto.pk, "precio_compra": None}]


def _id_estado(client, nombre):
    respuesta = client.get("/api/compras/estados-orden-compra/")
    assert respuesta.status_code == 200
    for estado in respuesta.data["results"]:
        if estado["nombre"] == nombre:
            return estado["estadoordencompra_id"]
    raise AssertionError(f"No está el estado {nombre}")


@pytest.mark.django_db
def test_alta_de_orden_trae_renglones_y_queda_pendiente(auth_client):
    producto = _producto("OC-ALTA")
    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor OC",
            "apellido": "SA",
            "cuit": "27111222334",
            "productos": _catalogo(producto.pk),
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
            "detalles": [
                {"producto_id": producto.pk, "cantidad": 10, "precio_unitario": "1500.00"}
            ],
        },
        format="json",
    )
    assert alta.status_code == 201

    detalle = auth_client.get(f"/api/compras/ordenes-compra/{alta.data['ordencompra_id']}/")
    assert detalle.status_code == 200
    assert detalle.data["estado"] == _id_estado(auth_client, "Pendiente")
    assert len(detalle.data["detalles"]) == 1
    renglon = detalle.data["detalles"][0]
    assert renglon["producto_id"] == producto.pk
    assert renglon["cantidad"] == 10
    assert renglon["precio_unitario"] == "1500.00"
    assert isinstance(renglon["ordencompradetalle_id"], int)
    assert "orden_compra" not in renglon


@pytest.mark.django_db
def test_alta_de_orden_no_acepta_otro_estado_que_pendiente(auth_client):
    producto = _producto("OC-ESTADO")
    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor Estado",
            "apellido": "SA",
            "cuit": "30111222335",
            "productos": _catalogo(producto.pk),
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
            "detalles": [{"producto_id": producto.pk, "cantidad": 1, "precio_unitario": "100.00"}],
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
            "productos": _catalogo(producto_id),
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
                    "producto_id": producto_id,
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
    producto = _producto("OC-RECHAZO")
    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor Rechazo",
            "apellido": "SA",
            "cuit": "24111222337",
            "productos": _catalogo(producto.pk),
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
            "detalles": [{"producto_id": producto.pk, "cantidad": 1, "precio_unitario": "800.00"}],
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
    producto = _producto("OC-TOTAL")
    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor Total",
            "apellido": "SA",
            "cuit": "25111222338",
            "productos": _catalogo(producto.pk),
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
            "detalles": [{"producto_id": producto.pk, "cantidad": 1, "precio_unitario": "800.00"}],
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
    producto = _producto("OC-VUELTA")
    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor Vuelta",
            "apellido": "SA",
            "cuit": "26111222339",
            "productos": _catalogo(producto.pk),
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
            "detalles": [{"producto_id": producto.pk, "cantidad": 1, "precio_unitario": "800.00"}],
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
    producto = _producto("OC-FLUJO")

    proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor OC",
            "apellido": "SA",
            "telefono": "",
            "email": "",
            "cuit": "20111222333",
            "direccion": "",
            "productos": _catalogo(producto.pk),
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
            "detalles": [
                {"producto_id": producto.pk, "cantidad": 10, "precio_unitario": "1500.00"}
            ],
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
                    "producto_id": producto_id,
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
@pytest.mark.parametrize("nombre_estado", ["Aprobada", "Recibida"])
def test_no_se_puede_eliminar_orden_aprobada_o_recibida(auth_client, nombre_estado):
    proveedor = Proveedor.objects.create(
        nombre="Proveedor Delete",
        apellido="SA",
        cuit="20111222333",
    )
    estado = EstadoOrdenCompra.objects.get(nombre=nombre_estado)
    orden = OrdenCompra.objects.create(
        proveedor=proveedor,
        estado=estado,
        fecha=timezone.now(),
        total="100.00",
    )

    respuesta = auth_client.delete(f"/api/compras/ordenes-compra/{orden.pk}/")

    assert respuesta.status_code == 400
    assert "No se puede eliminar una orden aprobada o recibida." in str(respuesta.data)
    assert OrdenCompra.objects.filter(pk=orden.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("nombre_estado", ["Pendiente", "Rechazada"])
def test_se_puede_eliminar_orden_pendiente_o_rechazada(auth_client, nombre_estado):
    proveedor = Proveedor.objects.create(
        nombre="Proveedor Delete",
        apellido="SA",
        cuit="20111222333",
    )
    estado = EstadoOrdenCompra.objects.get(nombre=nombre_estado)
    orden = OrdenCompra.objects.create(
        proveedor=proveedor,
        estado=estado,
        fecha=timezone.now(),
        total="100.00",
    )

    respuesta = auth_client.delete(f"/api/compras/ordenes-compra/{orden.pk}/")

    assert respuesta.status_code == 204
    assert not OrdenCompra.objects.filter(pk=orden.pk).exists()


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
            "productos": _catalogo(producto_id),
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
            "productos": _catalogo(producto_id),
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


def _proveedor(client, cuit, producto_id):
    respuesta = client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Proveedor Renglones",
            "apellido": "SA",
            "cuit": cuit,
            "productos": _catalogo(producto_id),
        },
        format="json",
    )
    assert respuesta.status_code == 201, respuesta.data
    return respuesta.data["proveedor_id"]


@pytest.mark.django_db
@pytest.mark.parametrize("detalles", [None, []])
def test_la_orden_exige_al_menos_un_renglon(auth_client, detalles):
    producto = _producto(f"REN-{detalles is None}")
    proveedor_id = _proveedor(auth_client, "27111000119", producto.pk)
    payload = {
        "proveedor": proveedor_id,
        "fecha": "2026-09-04T10:00:00-03:00",
        "total": "100.00",
    }
    if detalles is not None:
        payload["detalles"] = detalles

    alta = auth_client.post("/api/compras/ordenes-compra/", payload, format="json")

    assert alta.status_code == 400
    assert "La orden debe tener al menos un renglón." in str(alta.data.get("detalles", []))
    assert OrdenCompra.objects.count() == 0


@pytest.mark.django_db
def test_el_total_tiene_que_coincidir_con_los_renglones(auth_client):
    producto = _producto("TOT-MAL")
    proveedor_id = _proveedor(auth_client, "27111000227", producto.pk)
    alta = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor_id,
            "fecha": "2026-09-04T10:00:00-03:00",
            "total": "999.00",
            "detalles": [
                {"producto_id": producto.pk, "cantidad": 2, "precio_unitario": "100.00"},
            ],
        },
        format="json",
    )
    assert alta.status_code == 400
    assert "El total no coincide con la suma de cantidad por precio unitario." in str(
        alta.data.get("total", [])
    )


@pytest.mark.django_db
def test_sin_total_lo_calcula_con_la_suma_de_los_renglones(auth_client):
    producto = _producto("TOT-CALC")
    otro = _producto("TOT-CALC-2")
    proveedor_id = _proveedor(auth_client, "27111000335", [producto.pk, otro.pk])
    alta = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor_id,
            "fecha": "2026-09-04T10:00:00-03:00",
            "detalles": [
                {"producto_id": producto.pk, "cantidad": 2, "precio_unitario": "10.00"},
                {"producto_id": otro.pk, "cantidad": 1, "precio_unitario": "5.50"},
            ],
        },
        format="json",
    )
    assert alta.status_code == 201, alta.data
    assert alta.data["total"] == "25.50"
    assert len(alta.data["detalles"]) == 2


@pytest.mark.django_db
def test_al_reemplazar_renglones_recalcula_el_total(auth_client):
    producto = _producto("TOT-UPD")
    proveedor_id = _proveedor(auth_client, "27111000443", producto.pk)
    oc_id = _orden(auth_client, proveedor_id, "200.00", producto.pk, 2, "100.00")

    cambio = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {
            "detalles": [
                {"producto_id": producto.pk, "cantidad": 3, "precio_unitario": "50.00"},
            ]
        },
        format="json",
    )
    assert cambio.status_code == 200, cambio.data
    assert cambio.data["total"] == "150.00"

    vacio = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"detalles": []},
        format="json",
    )
    assert vacio.status_code == 400
    assert "La orden debe tener al menos un renglón." in str(vacio.data.get("detalles", []))
    assert _estado(auth_client, oc_id)["total"] == "150.00"


@pytest.mark.django_db
def test_un_total_distinto_en_una_orden_pendiente_se_rechaza(auth_client):
    producto = _producto("TOT-PEN")
    proveedor_id = _proveedor(auth_client, "27111000551", producto.pk)
    oc_id = _orden(auth_client, proveedor_id, "200.00", producto.pk, 2, "100.00")

    cambio = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"total": "10.00"},
        format="json",
    )
    assert cambio.status_code == 400
    assert _estado(auth_client, oc_id)["total"] == "200.00"


@pytest.mark.django_db
def test_la_orden_rechaza_un_producto_que_el_proveedor_no_tiene(auth_client):
    propio = _producto("CAT-OK")
    ajeno = _producto("CAT-NO")
    proveedor_id = _proveedor(auth_client, "27111000660", propio.pk)
    alta = auth_client.post(
        "/api/compras/ordenes-compra/",
        {
            "proveedor": proveedor_id,
            "fecha": "2026-09-04T10:00:00-03:00",
            "detalles": [
                {"producto_id": ajeno.pk, "cantidad": 1, "precio_unitario": "10.00"},
            ],
        },
        format="json",
    )
    assert alta.status_code == 400
    assert f"El producto {ajeno.pk} no está asociado al proveedor." in str(
        alta.data.get("detalles", [])
    )
    assert OrdenCompra.objects.count() == 0


@pytest.mark.django_db
def test_al_cambiar_el_proveedor_los_renglones_tienen_que_ser_de_su_catalogo(auth_client):
    producto = _producto("CAT-PROV")
    otro = _producto("CAT-OTRO")
    proveedor_id = _proveedor(auth_client, "27111000778", producto.pk)
    otro_proveedor = auth_client.post(
        "/api/compras/proveedores/",
        {
            "nombre": "Otro proveedor",
            "apellido": "SA",
            "cuit": "27111000886",
            "productos": _catalogo(otro.pk),
        },
        format="json",
    )
    assert otro_proveedor.status_code == 201
    oc_id = _orden(auth_client, proveedor_id, "10.00", producto.pk, 1, "10.00")

    cambio = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {"proveedor": otro_proveedor.data["proveedor_id"]},
        format="json",
    )
    assert cambio.status_code == 400
    assert f"El producto {producto.pk} no está asociado al proveedor." in str(
        cambio.data.get("detalles", [])
    )
    assert _estado(auth_client, oc_id)["proveedor"] == proveedor_id


@pytest.mark.django_db
def test_se_puede_cargar_otro_producto_del_mismo_proveedor(auth_client):
    primero = _producto("CAT-1")
    segundo = _producto("CAT-2")
    proveedor_id = _proveedor(auth_client, "27111000994", [primero.pk, segundo.pk])
    oc_id = _orden(auth_client, proveedor_id, "10.00", primero.pk, 1, "10.00")

    cambio = auth_client.patch(
        f"/api/compras/ordenes-compra/{oc_id}/",
        {
            "detalles": [
                {"producto_id": segundo.pk, "cantidad": 2, "precio_unitario": "10.00"},
            ]
        },
        format="json",
    )
    assert cambio.status_code == 200, cambio.data
    assert cambio.data["detalles"][0]["producto_id"] == segundo.pk
    assert cambio.data["total"] == "20.00"
