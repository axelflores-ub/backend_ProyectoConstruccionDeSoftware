import pytest

from apps.SCM.models import MovimientoInventario, Producto

pytestmark = pytest.mark.django_db


def mover(client, producto, tipo, cantidad):
    return client.post(
        "/api/scm/movimientos-inventario/",
        {"producto": producto.id, "tipo": tipo, "cantidad": cantidad},
        format="json",
    )


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
