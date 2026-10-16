"""Todos los endpoints exigen un token JWT válido y responden con el error estándar."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

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
def test_listar_sin_token_da_401(anon_client, nombre):
    response = anon_client.get(reverse(nombre))
    assert response.status_code == 401
    assert response.data["codigo"] == "no_autenticado"


@pytest.mark.django_db
def test_crear_cliente_sin_token_da_401(anon_client):
    response = anon_client.post(reverse("cliente-list"), {"nombre": "Ana"}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_token_invalido_da_401():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer esto.no.es.un.token")
    response = client.get(reverse("cliente-list"))
    assert response.status_code == 401
    assert response.data["codigo"] == "token_invalido"


@pytest.mark.django_db
@pytest.mark.parametrize("nombre", NOMBRES_LISTA)
def test_listar_con_token_funciona(api_client, nombre):
    assert api_client.get(reverse(nombre)).status_code == 200
