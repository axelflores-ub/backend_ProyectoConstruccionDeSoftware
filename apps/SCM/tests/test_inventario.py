import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.CompraYProveedores.models import (
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
)
from apps.SCM.models import MovimientoInventario, Producto, Rubro

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    usuario = get_user_model().objects.create_user(username="tester", password="x")
    client = APIClient()
    client.force_authenticate(user=usuario)
    return client


@pytest.fixture
def rubro():
    return Rubro.objects.create(nombre="Cemento", descripcion="Bolsas y a granel")


@pytest.fixture
def producto(rubro):
    return Producto.objects.create(
        codigo="CEM-001",
        nombre="Cemento Portland 50kg",
        precio="12000.00",
        rubro=rubro,
        stock_actual=20,
        stock_minimo=5,
    )


def mover(client, producto, tipo, cantidad):
    return client.post(
        "/api/scm/movimientos-inventario/",
        {"producto": producto.id, "tipo": tipo, "cantidad": cantidad},
        format="json",
    )


# --- Productos ---------------------------------------------------------------


def test_sin_token_da_401():
    assert APIClient().get("/api/scm/productos/").status_code == 401


def test_crear_producto_empieza_con_stock_cero(api_client, rubro):
    response = api_client.post(
        "/api/scm/productos/",
        {
            "codigo": "CEM-002",
            "nombre": "Cemento 25kg",
            "precio": "7000.00",
            "rubro": rubro.id,
            "stock_minimo": 10,
            "stock_actual": 999,  # se ignora: solo cambia con movimientos
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["stock_actual"] == 0
    assert response.data["stock_minimo"] == 10
    assert response.data["rubro_nombre"] == "Cemento"


def test_crear_producto_precio_invalido(api_client, rubro):
    response = api_client.post(
        "/api/scm/productos/",
        {"codigo": "X", "nombre": "X", "precio": "0", "rubro": rubro.id},
        format="json",
    )
    assert response.status_code == 400
    assert "precio" in response.data


def test_bajo_stock_lista_solo_productos_en_el_minimo_o_debajo(api_client, producto, rubro):
    Producto.objects.create(
        codigo="ARE-001", nombre="Arena", precio="1", rubro=rubro, stock_actual=5, stock_minimo=5
    )
    response = api_client.get("/api/scm/productos/?bajo_stock=true")
    assert response.status_code == 200
    codigos = [p["codigo"] for p in response.data["results"]]
    assert codigos == ["ARE-001"]  # CEM-001 tiene 20 > 5


# --- Movimientos de inventario -----------------------------------------------


def test_entrada_suma_stock(api_client, producto):
    assert mover(api_client, producto, "ENTRADA", 10).status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 30


def test_salida_resta_stock(api_client, producto):
    assert mover(api_client, producto, "SALIDA", 15).status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 5


def test_salida_sin_stock_suficiente_devuelve_error(api_client, producto):
    response = mover(api_client, producto, "SALIDA", 999)
    assert response.status_code == 400
    producto.refresh_from_db()
    assert producto.stock_actual == 20
    assert MovimientoInventario.objects.count() == 0


def test_ajuste_admite_cantidad_negativa(api_client, producto):
    assert mover(api_client, producto, "AJUSTE", -3).status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 17


def test_entrada_con_cantidad_negativa_se_rechaza(api_client, producto):
    assert mover(api_client, producto, "ENTRADA", -3).status_code == 400


def test_historial_filtra_por_producto_y_tipo(api_client, producto, rubro):
    otro = Producto.objects.create(
        codigo="ARE-001", nombre="Arena", precio="1", rubro=rubro, stock_actual=10
    )
    mover(api_client, producto, "ENTRADA", 5)
    mover(api_client, producto, "SALIDA", 2)
    mover(api_client, otro, "ENTRADA", 1)

    response = api_client.get(
        f"/api/scm/movimientos-inventario/?producto={producto.id}&tipo=entrada"
    )
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["cantidad"] == 5


def test_movimientos_no_se_editan_ni_borran(api_client, producto):
    mov_id = mover(api_client, producto, "ENTRADA", 1).data["id"]
    url = f"/api/scm/movimientos-inventario/{mov_id}/"
    assert api_client.patch(url, {"cantidad": 9}, format="json").status_code == 405
    assert api_client.delete(url).status_code == 405


# --- Compras -> SCM: orden Recibida suma stock ----------------------------------


@pytest.fixture
def orden_pendiente(producto):
    proveedor = Proveedor.objects.create(
        nombre="Prov", cuit="20111222333", producto_id=producto.id
    )
    orden = OrdenCompra.objects.create(
        proveedor=proveedor,
        estado=EstadoOrdenCompra.objects.get(nombre="Pendiente"),
        fecha="2026-09-20T10:00:00-03:00",
        total="120000.00",
    )
    OrdenCompraDetalle.objects.create(
        orden_compra=orden, producto_id=producto.id, cantidad=10, precio_unitario="12000.00"
    )
    return orden


def cambiar_estado(client, orden, nombre):
    estado = EstadoOrdenCompra.objects.get(nombre=nombre)
    return client.patch(
        f"/api/compras/ordenes-compra/{orden.pk}/",
        {"estado": estado.pk},
        format="json",
    )


def test_estados_de_orden_de_compra_vienen_cargados():
    nombres = set(EstadoOrdenCompra.objects.values_list("nombre", flat=True))
    assert {"Pendiente", "Aprobada", "Rechazada", "Recibida"} <= nombres


def test_marcar_recibida_suma_stock_y_deja_movimiento(api_client, producto, orden_pendiente):
    assert cambiar_estado(api_client, orden_pendiente, "Aprobada").status_code == 200
    producto.refresh_from_db()
    assert producto.stock_actual == 20  # aprobar no toca el stock

    assert cambiar_estado(api_client, orden_pendiente, "Recibida").status_code == 200
    producto.refresh_from_db()
    assert producto.stock_actual == 30

    movimiento = MovimientoInventario.objects.get(producto=producto)
    assert movimiento.tipo == "ENTRADA"
    assert movimiento.cantidad == 10
    assert str(orden_pendiente.pk) in movimiento.observacion


def test_orden_recibida_no_puede_cambiar_de_estado(api_client, producto, orden_pendiente):
    cambiar_estado(api_client, orden_pendiente, "Recibida")
    response = cambiar_estado(api_client, orden_pendiente, "Pendiente")
    assert response.status_code == 400

    orden_pendiente.refresh_from_db()
    assert orden_pendiente.estado.nombre == "Recibida"
    producto.refresh_from_db()
    assert producto.stock_actual == 30


def test_recibida_con_producto_inexistente_no_cambia_nada(api_client, producto, orden_pendiente):
    OrdenCompraDetalle.objects.create(
        orden_compra=orden_pendiente, producto_id=99999, cantidad=1, precio_unitario="1.00"
    )
    response = cambiar_estado(api_client, orden_pendiente, "Recibida")
    assert response.status_code == 400

    orden_pendiente.refresh_from_db()
    assert orden_pendiente.estado.nombre == "Pendiente"
    producto.refresh_from_db()
    assert producto.stock_actual == 20
    assert MovimientoInventario.objects.count() == 0
