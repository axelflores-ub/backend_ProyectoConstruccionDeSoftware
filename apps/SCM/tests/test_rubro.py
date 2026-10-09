import pytest
from rest_framework.test import APIClient

from apps.SCM.models import Rubro

pytestmark = pytest.mark.django_db


def test_sin_token_da_401():
    assert APIClient().get("/api/scm/rubros/").status_code == 401


def test_crear_rubro_ok(api_client):
    response = api_client.post(
        "/api/scm/rubros/",
        {"nombre": "Ferretería", "descripcion": "Tornillos y herramientas"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["nombre"] == "Ferretería"


def test_nombre_duplicado_da_400(api_client):
    Rubro.objects.create(nombre="Cemento")
    response = api_client.post(
        "/api/scm/rubros/",
        {"nombre": "Cemento"},
        format="json",
    )
    assert response.status_code == 400
    assert "nombre" in response.data


def test_nombre_duplicado_case_insensitive_da_400(api_client):
    Rubro.objects.create(nombre="Cemento")
    response = api_client.post(
        "/api/scm/rubros/",
        {"nombre": "CEMENTO"},
        format="json",
    )
    assert response.status_code == 400
    assert "nombre" in response.data


def test_nombre_duplicado_con_espacios_da_400(api_client):
    Rubro.objects.create(nombre="Cemento")
    response = api_client.post(
        "/api/scm/rubros/",
        {"nombre": "  Cemento  "},
        format="json",
    )
    assert response.status_code == 400
    assert "nombre" in response.data


def test_editar_rubro_con_su_propio_nombre_no_da_400(api_client):
    rubro = Rubro.objects.create(nombre="Cemento")
    response = api_client.patch(
        f"/api/scm/rubros/{rubro.id}/",
        {"nombre": "Cemento", "descripcion": "Nueva descripción"},
        format="json",
    )
    assert response.status_code == 200
