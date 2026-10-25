import pytest
from django.contrib.auth import get_user_model

from apps.SCM import services
from apps.SCM.models import MovimientoInventario, Producto

pytestmark = pytest.mark.django_db


# --- __str__ y propiedades de los modelos -----------------------------------


def test_str_de_rubro(rubro):
    assert str(rubro) == "Cemento"


def test_str_de_producto(producto):
    assert str(producto) == "CEM-001 - Cemento Portland 50kg"


@pytest.mark.parametrize(
    ("tipo", "etiqueta"),
    [
        ("ENTRADA", "Entrada"),
        ("SALIDA", "Salida"),
        ("AJUSTE", "Ajuste"),
        ("DEVOLUCION", "Devolución"),
    ],
)
def test_str_de_movimiento(producto, tipo, etiqueta):
    usuario = get_user_model().objects.create_user(username="modelos", password="x")
    movimiento = services.registrar_movimiento(
        producto=producto, tipo=tipo, cantidad=1, usuario=usuario
    )

    assert str(movimiento) == f"{etiqueta} #{movimiento.pk} - CEM-001"


@pytest.mark.parametrize(
    ("stock_actual", "stock_minimo", "esperado"),
    [(4, 5, True), (5, 5, True), (6, 5, False)],
)
def test_necesita_reposicion_del_modelo(rubro, stock_actual, stock_minimo, esperado):
    p = Producto(
        codigo="T", nombre="T", precio="1", stock_actual=stock_actual, stock_minimo=stock_minimo
    )

    assert p.necesita_reposicion is esperado


def test_producto_sin_rubro_es_valido_y_expone_rubro_nombre_vacio(api_client):
    response = api_client.post(
        "/api/scm/productos/",
        {"codigo": "SR-1", "nombre": "Sin rubro", "precio": "10.00"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["rubro"] is None
    assert Producto.objects.get(codigo="SR-1").rubro is None


# --- Paginación -------------------------------------------------------------


@pytest.fixture
def veinticinco_productos(rubro):
    Producto.objects.bulk_create(
        [
            Producto(codigo=f"P-{i:02d}", nombre=f"Producto {i:02d}", precio="1", rubro=rubro)
            for i in range(25)
        ]
    )


def test_listado_de_productos_se_pagina_de_a_20(api_client, veinticinco_productos):
    pagina_1 = api_client.get("/api/scm/productos/").data

    assert pagina_1["count"] == 25
    assert len(pagina_1["results"]) == 20
    assert pagina_1["next"] is not None
    assert pagina_1["previous"] is None

    pagina_2 = api_client.get("/api/scm/productos/?page=2").data

    assert len(pagina_2["results"]) == 5
    assert pagina_2["next"] is None
    assert pagina_2["previous"] is not None


def test_pagina_inexistente_da_404(api_client, veinticinco_productos):
    assert api_client.get("/api/scm/productos/?page=3").status_code == 404


def test_paginas_no_repiten_ni_pierden_productos(api_client, veinticinco_productos):
    codigos = []
    for pagina in (1, 2):
        data = api_client.get(f"/api/scm/productos/?page={pagina}").data
        codigos += [p["codigo"] for p in data["results"]]

    assert len(codigos) == len(set(codigos)) == 25


def test_listado_de_movimientos_se_pagina_de_a_20(api_client, producto):
    usuario = get_user_model().objects.create_user(username="paginador", password="x")
    MovimientoInventario.objects.bulk_create(
        [
            MovimientoInventario(producto=producto, usuario=usuario, tipo="ENTRADA", cantidad=1)
            for _ in range(21)
        ]
    )

    pagina_1 = api_client.get("/api/scm/movimientos-inventario/").data
    pagina_2 = api_client.get("/api/scm/movimientos-inventario/?page=2").data

    assert pagina_1["count"] == 21
    assert len(pagina_1["results"]) == 20
    assert len(pagina_2["results"]) == 1
