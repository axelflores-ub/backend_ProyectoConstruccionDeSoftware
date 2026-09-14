import pytest
from django.contrib.auth import get_user_model
from faker import Faker
from rest_framework.test import APIClient

from apps.ContabilidadFinanzas.models import Periodo

fake = Faker()


@pytest.fixture
def api_client(db):
    user = get_user_model().objects.create_user(username="admin", password=fake.password())
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_listar_periodos_happy_path(api_client):
    Periodo.objects.create(anio=2026, mes=1)
    Periodo.objects.create(anio=2026, mes=2)

    response = api_client.get("/api/contabilidad/periodos/")

    assert response.status_code == 200
    assert response.data["count"] == 2


@pytest.mark.django_db
def test_obtener_periodo_por_id(api_client):
    periodo = Periodo.objects.create(anio=2026, mes=3)

    response = api_client.get(f"/api/contabilidad/periodos/{periodo.id}/")

    assert response.status_code == 200
    assert response.data == {"id": periodo.id, "anio": 2026, "mes": 3}


@pytest.mark.django_db
def test_listar_periodos_sin_autenticacion_falla():
    response = APIClient().get("/api/contabilidad/periodos/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_crear_periodo_no_permitido(api_client):
    response = api_client.post("/api/contabilidad/periodos/", {"anio": 2026, "mes": 4})

    assert response.status_code == 405
