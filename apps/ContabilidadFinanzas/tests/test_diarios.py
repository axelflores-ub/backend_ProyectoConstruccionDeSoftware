import pytest
from django.contrib.auth import get_user_model
from faker import Faker
from rest_framework.test import APIClient

from apps.ContabilidadFinanzas.models import Diario, Periodo

fake = Faker()


@pytest.fixture
def api_client(db):
    user = get_user_model().objects.create_user(username="admin", password=fake.password())
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def cierre_mensual(db):
    periodo = Periodo.objects.create(anio=2026, mes=1)
    return periodo.cierres_mensuales.get()


@pytest.mark.django_db
def test_listar_diarios_happy_path(api_client, cierre_mensual):
    Diario.objects.create(cierre_mensual=cierre_mensual, fecha="2026-01-10T10:00:00Z")
    Diario.objects.create(cierre_mensual=cierre_mensual, fecha="2026-01-15T10:00:00Z")

    response = api_client.get("/api/contabilidad/diarios/")

    assert response.status_code == 200
    assert response.data["count"] == 2


@pytest.mark.django_db
def test_obtener_diario_por_id(api_client, cierre_mensual):
    diario = Diario.objects.create(
        cierre_mensual=cierre_mensual,
        fecha="2026-01-10T10:00:00Z",
        descripcion="Asiento de prueba",
    )

    response = api_client.get(f"/api/contabilidad/diarios/{diario.id}/")

    assert response.status_code == 200
    assert response.data["id"] == diario.id
    assert response.data["descripcion"] == "Asiento de prueba"


@pytest.mark.django_db
def test_listar_diarios_sin_autenticacion_falla():
    response = APIClient().get("/api/contabilidad/diarios/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_crear_diario_no_permitido(api_client, cierre_mensual):
    response = api_client.post(
        "/api/contabilidad/diarios/",
        {"cierre_mensual": cierre_mensual.id, "fecha": "2026-01-10T10:00:00Z"},
    )

    assert response.status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
def test_modificar_o_borrar_diario_no_permitido(api_client, cierre_mensual, metodo):
    diario = Diario.objects.create(cierre_mensual=cierre_mensual, fecha="2026-01-10T10:00:00Z")

    response = getattr(api_client, metodo)(f"/api/contabilidad/diarios/{diario.id}/")

    assert response.status_code == 405
