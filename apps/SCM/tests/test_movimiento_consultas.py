import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.SCM import services
from apps.SCM.models import MovimientoInventario, Producto

pytestmark = pytest.mark.django_db

URL = "/api/scm/movimientos-inventario/"


@pytest.fixture
def otro_producto(rubro):
    return Producto.objects.create(
        codigo="ARE-001", nombre="Arena fina", precio="1", rubro=rubro, stock_actual=50
    )


@pytest.fixture
def historial(producto, otro_producto):
    usuario = get_user_model().objects.create_user(username="historial", password="x")
    for p, tipo, cantidad in [
        (producto, "ENTRADA", 5),
        (producto, "SALIDA", 2),
        (producto, "AJUSTE", -1),
        (otro_producto, "ENTRADA", 7),
        (otro_producto, "DEVOLUCION", 3),
    ]:
        services.registrar_movimiento(producto=p, tipo=tipo, cantidad=cantidad, usuario=usuario)


def tipos(response):
    return [m["tipo"] for m in response.data["results"]]


# --- Filtros ----------------------------------------------------------------


@pytest.mark.parametrize("filtro", ["entrada", "ENTRADA", "Entrada"])
def test_filtro_tipo_no_distingue_mayusculas(api_client, historial, filtro):
    response = api_client.get(f"{URL}?tipo={filtro}")

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert set(tipos(response)) == {"ENTRADA"}


def test_filtro_tipo_inexistente_devuelve_vacio(api_client, historial):
    response = api_client.get(f"{URL}?tipo=inventado")

    assert response.status_code == 200
    assert response.data["count"] == 0


def test_filtro_por_producto_sin_movimientos_devuelve_vacio(api_client, historial, rubro):
    sin_mov = Producto.objects.create(codigo="X-1", nombre="X", precio="1", rubro=rubro)

    assert api_client.get(f"{URL}?producto={sin_mov.id}").data["count"] == 0


def test_filtro_por_producto_devuelve_solo_los_suyos(api_client, historial, producto):
    response = api_client.get(f"{URL}?producto={producto.id}")

    assert response.data["count"] == 3
    assert {m["producto"] for m in response.data["results"]} == {producto.id}


def test_filtros_producto_y_tipo_combinados(api_client, historial, otro_producto):
    response = api_client.get(f"{URL}?producto={otro_producto.id}&tipo=devolucion")

    assert response.data["count"] == 1
    assert response.data["results"][0]["cantidad"] == 3


# --- Búsqueda, orden y detalle ----------------------------------------------


def test_buscar_por_codigo_y_por_nombre_del_producto(api_client, historial):
    assert api_client.get(f"{URL}?search=ARE-001").data["count"] == 2
    assert api_client.get(f"{URL}?search=cemento").data["count"] == 3
    assert api_client.get(f"{URL}?search=noexiste").data["count"] == 0


def test_historial_viene_del_mas_reciente_al_mas_antiguo(api_client, historial):
    ids = [m["id"] for m in api_client.get(URL).data["results"]]

    assert ids == sorted(ids, reverse=True)


def test_ordering_por_fecha_ascendente(api_client, historial):
    ids = [m["id"] for m in api_client.get(f"{URL}?ordering=fecha").data["results"]]

    assert ids == sorted(ids)


def test_detalle_de_movimiento(api_client, historial, producto):
    movimiento = MovimientoInventario.objects.filter(producto=producto, tipo="SALIDA").get()

    response = api_client.get(f"{URL}{movimiento.id}/")

    assert response.status_code == 200
    assert response.data["producto"] == producto.id
    assert response.data["producto_codigo"] == "CEM-001"
    assert response.data["tipo"] == "SALIDA"
    assert response.data["cantidad"] == 2


def test_detalle_de_movimiento_inexistente_da_404(api_client):
    assert api_client.get(f"{URL}99999/").status_code == 404


# --- Seguridad --------------------------------------------------------------


def test_movimientos_sin_token_da_401_en_listado_y_alta(producto):
    client = APIClient()

    assert client.get(URL).status_code == 401
    alta = client.post(
        URL, {"producto": producto.id, "tipo": "ENTRADA", "cantidad": 1}, format="json"
    )
    assert alta.status_code == 401
    producto.refresh_from_db()
    assert producto.stock_actual == 20


def test_movimiento_sin_token_da_401_en_detalle(historial):
    movimiento = MovimientoInventario.objects.first()

    assert APIClient().get(f"{URL}{movimiento.id}/").status_code == 401


def test_el_usuario_del_movimiento_sale_del_token_y_no_del_body(api_client, producto):
    ajeno = get_user_model().objects.create_user(username="ajeno", password="x")

    response = api_client.post(
        URL,
        {"producto": producto.id, "tipo": "ENTRADA", "cantidad": 1, "usuario": ajeno.id},
        format="json",
    )

    assert response.status_code == 201
    movimiento = MovimientoInventario.objects.get(pk=response.data["id"])
    assert movimiento.usuario.username == "tester"
    assert movimiento.usuario != ajeno
