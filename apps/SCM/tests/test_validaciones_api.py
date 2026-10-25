import pytest

from apps.SCM.models import MovimientoInventario, Producto

pytestmark = pytest.mark.django_db

URL_PRODUCTOS = "/api/scm/productos/"
URL_MOVIMIENTOS = "/api/scm/movimientos-inventario/"


def datos_producto(**extra):
    datos = {"codigo": "LAD-001", "nombre": "Ladrillo", "precio": "150.00"}
    datos.update(extra)
    return datos


# --- Movimientos ------------------------------------------------------------


@pytest.mark.parametrize("tipo", ["ENTRADA", "SALIDA", "AJUSTE", "DEVOLUCION"])
def test_movimiento_con_cantidad_cero_da_400(api_client, producto, tipo):
    response = api_client.post(
        URL_MOVIMIENTOS,
        {"producto": producto.id, "tipo": tipo, "cantidad": 0},
        format="json",
    )
    assert response.status_code == 400
    assert "cantidad" in response.data
    producto.refresh_from_db()
    assert producto.stock_actual == 20
    assert MovimientoInventario.objects.count() == 0


def test_movimiento_con_producto_inexistente_da_400(api_client):
    response = api_client.post(
        URL_MOVIMIENTOS,
        {"producto": 99999, "tipo": "ENTRADA", "cantidad": 1},
        format="json",
    )
    assert response.status_code == 400
    assert "producto" in response.data
    assert MovimientoInventario.objects.count() == 0


def test_movimiento_sin_producto_da_400(api_client):
    response = api_client.post(URL_MOVIMIENTOS, {"tipo": "ENTRADA", "cantidad": 1}, format="json")
    assert response.status_code == 400
    assert "producto" in response.data


def test_movimiento_con_tipo_invalido_da_400(api_client, producto):
    response = api_client.post(
        URL_MOVIMIENTOS,
        {"producto": producto.id, "tipo": "INVENTADO", "cantidad": 1},
        format="json",
    )
    assert response.status_code == 400
    assert "tipo" in response.data
    producto.refresh_from_db()
    assert producto.stock_actual == 20


def test_ajuste_negativo_que_deja_stock_negativo_da_400(api_client, producto):
    response = api_client.post(
        URL_MOVIMIENTOS,
        {"producto": producto.id, "tipo": "AJUSTE", "cantidad": -21},
        format="json",
    )
    assert response.status_code == 400
    producto.refresh_from_db()
    assert producto.stock_actual == 20
    assert MovimientoInventario.objects.count() == 0


def test_devolucion_por_api_suma_stock(api_client, producto):
    response = api_client.post(
        URL_MOVIMIENTOS,
        {"producto": producto.id, "tipo": "DEVOLUCION", "cantidad": 4},
        format="json",
    )
    assert response.status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 24


# --- Productos --------------------------------------------------------------


def test_stock_actual_enviado_al_crear_producto_se_ignora(api_client):
    response = api_client.post(URL_PRODUCTOS, datos_producto(stock_actual=500), format="json")
    assert response.status_code == 201
    assert response.data["stock_actual"] == 0
    assert Producto.objects.get(codigo="LAD-001").stock_actual == 0


@pytest.mark.parametrize("metodo", ["put", "patch"])
def test_stock_actual_enviado_al_editar_producto_se_ignora(api_client, producto, metodo):
    datos = datos_producto(codigo=producto.codigo, stock_actual=500)
    response = getattr(api_client, metodo)(f"{URL_PRODUCTOS}{producto.id}/", datos, format="json")
    assert response.status_code == 200
    producto.refresh_from_db()
    assert producto.stock_actual == 20


def test_stock_minimo_negativo_da_400(api_client):
    response = api_client.post(URL_PRODUCTOS, datos_producto(stock_minimo=-1), format="json")
    assert response.status_code == 400
    assert "stock_minimo" in response.data


@pytest.mark.parametrize("precio", ["0", "0.00", "-5.00"])
def test_precio_cero_o_negativo_da_400(api_client, precio):
    response = api_client.post(URL_PRODUCTOS, datos_producto(precio=precio), format="json")
    assert response.status_code == 400
    assert "precio" in response.data


def test_codigo_duplicado_da_400(api_client, producto):
    response = api_client.post(URL_PRODUCTOS, datos_producto(codigo=producto.codigo), format="json")
    assert response.status_code == 400
    assert "codigo" in response.data
    assert Producto.objects.filter(codigo=producto.codigo).count() == 1


def test_producto_sin_campos_obligatorios_da_400(api_client):
    response = api_client.post(URL_PRODUCTOS, {}, format="json")
    assert response.status_code == 400
    assert {"codigo", "nombre", "precio"} <= set(response.data)
