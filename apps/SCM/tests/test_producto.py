import pytest
from rest_framework.test import APIClient

from apps.SCM.models import Producto

pytestmark = pytest.mark.django_db


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
