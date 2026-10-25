import pytest
from rest_framework.test import APIClient

from apps.SCM.models import Producto

pytestmark = pytest.mark.django_db

URL = "/api/scm/productos/"


def crear(rubro, codigo, nombre, precio="100.00", stock_actual=0, stock_minimo=0):
    return Producto.objects.create(
        codigo=codigo,
        nombre=nombre,
        precio=precio,
        rubro=rubro,
        stock_actual=stock_actual,
        stock_minimo=stock_minimo,
    )


def codigos(response):
    return [p["codigo"] for p in response.data["results"]]


# --- Edición y borrado ------------------------------------------------------


def test_put_reemplaza_el_producto(api_client, producto, rubro):
    response = api_client.put(
        f"{URL}{producto.id}/",
        {
            "codigo": "CEM-001",
            "nombre": "Cemento renombrado",
            "precio": "13000.00",
            "rubro": rubro.id,
            "stock_minimo": 8,
        },
        format="json",
    )

    assert response.status_code == 200
    producto.refresh_from_db()
    assert producto.nombre == "Cemento renombrado"
    assert str(producto.precio) == "13000.00"
    assert producto.stock_minimo == 8
    assert producto.stock_actual == 20


def test_patch_modifica_solo_lo_enviado(api_client, producto):
    response = api_client.patch(f"{URL}{producto.id}/", {"precio": "15000.00"}, format="json")

    assert response.status_code == 200
    producto.refresh_from_db()
    assert str(producto.precio) == "15000.00"
    assert producto.nombre == "Cemento Portland 50kg"


def test_patch_con_precio_invalido_da_400(api_client, producto):
    response = api_client.patch(f"{URL}{producto.id}/", {"precio": "-1"}, format="json")

    assert response.status_code == 400
    producto.refresh_from_db()
    assert str(producto.precio) == "12000.00"


def test_patch_con_codigo_de_otro_producto_da_400(api_client, producto, rubro):
    crear(rubro, "ARE-001", "Arena")

    response = api_client.patch(f"{URL}{producto.id}/", {"codigo": "ARE-001"}, format="json")

    assert response.status_code == 400
    assert "codigo" in response.data


def test_borrar_producto_sin_movimientos(api_client, producto):
    assert api_client.delete(f"{URL}{producto.id}/").status_code == 204
    assert not Producto.objects.filter(pk=producto.pk).exists()


@pytest.mark.xfail(
    strict=True,
    reason="BUG: borrar un producto con movimientos lanza ProtectedError y responde 500; "
    "debería ser un error controlado (400/409).",
)
def test_borrar_producto_con_movimientos_da_error_controlado(api_client, producto):
    api_client.post(
        "/api/scm/movimientos-inventario/",
        {"producto": producto.id, "tipo": "ENTRADA", "cantidad": 1},
        format="json",
    )
    api_client.raise_request_exception = False

    response = api_client.delete(f"{URL}{producto.id}/")

    assert response.status_code in (400, 409)
    assert Producto.objects.filter(pk=producto.pk).exists()


def test_borrar_producto_con_movimientos_no_lo_elimina(api_client, producto):
    """Aunque hoy la respuesta sea 500, el producto y su historial deben conservarse."""
    api_client.post(
        "/api/scm/movimientos-inventario/",
        {"producto": producto.id, "tipo": "ENTRADA", "cantidad": 1},
        format="json",
    )
    api_client.raise_request_exception = False

    api_client.delete(f"{URL}{producto.id}/")

    producto.refresh_from_db()
    assert producto.stock_actual == 21
    assert producto.movimientos.count() == 1


def test_detalle_de_producto_inexistente_da_404(api_client):
    assert api_client.get(f"{URL}99999/").status_code == 404


# --- Filtro bajo_stock ------------------------------------------------------


@pytest.fixture
def surtido(rubro):
    crear(rubro, "BAJ-001", "Bajo", stock_actual=2, stock_minimo=5)
    crear(rubro, "IGU-001", "Igual", stock_actual=5, stock_minimo=5)
    crear(rubro, "OK-001", "Suficiente", stock_actual=50, stock_minimo=5)


@pytest.mark.parametrize("valor", ["true", "TRUE", "True", "1"])
def test_bajo_stock_acepta_valores_verdaderos(api_client, surtido, valor):
    response = api_client.get(f"{URL}?bajo_stock={valor}")

    assert sorted(codigos(response)) == ["BAJ-001", "IGU-001"]


@pytest.mark.parametrize("valor", ["false", "0", "", "cualquiera"])
def test_bajo_stock_con_otro_valor_no_filtra(api_client, surtido, valor):
    response = api_client.get(f"{URL}?bajo_stock={valor}")

    assert sorted(codigos(response)) == ["BAJ-001", "IGU-001", "OK-001"]


def test_bajo_stock_sin_productos_devuelve_lista_vacia(api_client, rubro):
    crear(rubro, "OK-001", "Suficiente", stock_actual=50, stock_minimo=5)

    response = api_client.get(f"{URL}?bajo_stock=true")

    assert response.status_code == 200
    assert response.data["count"] == 0


# --- necesita_reposicion ----------------------------------------------------


@pytest.mark.parametrize(
    ("stock_actual", "stock_minimo", "esperado"),
    [(2, 5, True), (5, 5, True), (6, 5, False), (0, 0, True)],
)
def test_necesita_reposicion_en_la_respuesta(
    api_client, rubro, stock_actual, stock_minimo, esperado
):
    p = crear(rubro, "T-001", "T", stock_actual=stock_actual, stock_minimo=stock_minimo)

    response = api_client.get(f"{URL}{p.id}/")

    assert response.data["necesita_reposicion"] is esperado


# --- Búsqueda y orden -------------------------------------------------------


def test_buscar_producto_por_codigo_y_por_nombre(api_client, rubro):
    crear(rubro, "CEM-001", "Cemento")
    crear(rubro, "ARE-001", "Arena fina")

    assert codigos(api_client.get(f"{URL}?search=cem-0")) == ["CEM-001"]
    assert codigos(api_client.get(f"{URL}?search=fina")) == ["ARE-001"]
    assert codigos(api_client.get(f"{URL}?search=noexiste")) == []


def test_orden_por_defecto_es_por_nombre(api_client, rubro):
    crear(rubro, "B", "Zinc")
    crear(rubro, "A", "Arena")

    assert codigos(api_client.get(URL)) == ["A", "B"]


def test_ordering_por_precio_y_por_stock(api_client, rubro):
    crear(rubro, "A", "Arena", precio="500.00", stock_actual=1)
    crear(rubro, "B", "Barro", precio="100.00", stock_actual=9)
    crear(rubro, "C", "Cal", precio="300.00", stock_actual=5)

    assert codigos(api_client.get(f"{URL}?ordering=precio")) == ["B", "C", "A"]
    assert codigos(api_client.get(f"{URL}?ordering=-precio")) == ["A", "C", "B"]
    assert codigos(api_client.get(f"{URL}?ordering=-stock_actual")) == ["B", "C", "A"]


# --- Seguridad --------------------------------------------------------------


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_productos_sin_token_da_401_en_todos_los_metodos(metodo):
    response = getattr(APIClient(), metodo)(URL, {}, format="json")

    assert response.status_code == 401
