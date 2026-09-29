"""Todos los endpoints del módulo exigen autenticación (regla del README)."""

import pytest
from django.urls import reverse

NOMBRES_LISTA = [
    "cliente-list",
    "estadoordenventa-list",
    "ordenventa-list",
    "ordenventadetalle-list",
    "anulacion-list",
    "notacredito-list",
    "detallenotacredito-list",
]


@pytest.mark.django_db
@pytest.mark.parametrize("nombre", NOMBRES_LISTA)
def test_listar_sin_token_es_rechazado(anon_client, nombre):
    response = anon_client.get(reverse(nombre))
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_crear_cliente_sin_token_es_rechazado(anon_client):
    response = anon_client.post(reverse("cliente-list"), {"nombre": "Ana"}, format="json")
    assert response.status_code in (401, 403)


@pytest.mark.django_db
@pytest.mark.parametrize("nombre", NOMBRES_LISTA)
def test_listar_con_token_funciona(api_client, nombre):
    assert api_client.get(reverse(nombre)).status_code == 200
