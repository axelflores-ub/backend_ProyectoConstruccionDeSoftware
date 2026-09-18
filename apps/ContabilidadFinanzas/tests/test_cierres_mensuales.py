import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from faker import Faker
from rest_framework.test import APIClient

from apps.ContabilidadFinanzas.models import CierreMensual, Periodo

fake = Faker()


@pytest.fixture
def api_client(db):
    user = get_user_model().objects.create_user(username="admin", password=fake.password())
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def cierre(db):
    return Periodo.objects.create(anio=2026, mes=6).cierres_mensuales.get()


def url_cierre(cierre):
    return f"/api/contabilidad/cierres-mensuales/{cierre.id}/"


@pytest.mark.django_db
def test_crear_periodo_genera_cierre_abierto():
    periodo = Periodo.objects.create(anio=2026, mes=6)

    cierre = CierreMensual.objects.get(periodo=periodo)
    assert cierre.estado == CierreMensual.Estado.ABIERTO
    assert cierre.fecha_cierre is None


@pytest.mark.django_db
def test_cerrar_periodo_happy_path(api_client, cierre):
    antes = timezone.now()

    response = api_client.put(url_cierre(cierre), {"estado": "CERRADO"})

    assert response.status_code == 200
    cierre.refresh_from_db()
    assert cierre.estado == CierreMensual.Estado.CERRADO
    assert cierre.fecha_cierre >= antes
    assert response.data["estado"] == "CERRADO"
    assert response.data["periodo"] == cierre.periodo_id
    assert response.data["fecha_cierre"] is not None


@pytest.mark.django_db
def test_modificar_cierre_ya_cerrado_falla(api_client, cierre):
    fecha_cierre = timezone.now()
    CierreMensual.objects.filter(pk=cierre.pk).update(
        estado=CierreMensual.Estado.CERRADO, fecha_cierre=fecha_cierre
    )

    response = api_client.put(url_cierre(cierre), {"estado": "ABIERTO"})

    assert response.status_code == 400
    assert (
        "El período ya está cerrado y no se puede modificar." in response.data["non_field_errors"]
    )
    cierre.refresh_from_db()
    assert cierre.estado == CierreMensual.Estado.CERRADO
    assert cierre.fecha_cierre == fecha_cierre


@pytest.mark.django_db
def test_cerrar_periodo_sin_estado_falla(api_client, cierre):
    response = api_client.put(url_cierre(cierre), {})

    assert response.status_code == 400
    assert "estado" in response.data
    cierre.refresh_from_db()
    assert cierre.estado == CierreMensual.Estado.ABIERTO


@pytest.mark.django_db
def test_cerrar_periodo_estado_invalido_falla(api_client, cierre):
    response = api_client.put(url_cierre(cierre), {"estado": "PENDIENTE"})

    assert response.status_code == 400
    assert "estado" in response.data


@pytest.mark.django_db
def test_cerrar_periodo_ignora_periodo_y_fecha_enviados(api_client, cierre):
    otro_periodo = Periodo.objects.create(anio=2025, mes=1)

    response = api_client.put(
        url_cierre(cierre),
        {"estado": "CERRADO", "periodo": otro_periodo.id, "fecha_cierre": "2000-01-01T00:00:00Z"},
    )

    assert response.status_code == 200
    cierre.refresh_from_db()
    assert cierre.periodo_id != otro_periodo.id
    assert cierre.fecha_cierre.year != 2000


@pytest.mark.django_db
def test_cerrar_periodo_inexistente_devuelve_404(api_client):
    response = api_client.put("/api/contabilidad/cierres-mensuales/9999/", {"estado": "CERRADO"})

    assert response.status_code == 404


@pytest.mark.django_db
def test_cerrar_periodo_sin_autenticacion_falla(cierre):
    response = APIClient().put(url_cierre(cierre), {"estado": "CERRADO"})

    assert response.status_code == 401
    cierre.refresh_from_db()
    assert cierre.estado == CierreMensual.Estado.ABIERTO


@pytest.mark.django_db
@pytest.mark.parametrize("metodo", ["post", "patch", "delete"])
def test_otros_metodos_de_cierre_no_permitidos(api_client, cierre, metodo):
    url = "/api/contabilidad/cierres-mensuales/" if metodo == "post" else url_cierre(cierre)

    response = getattr(api_client, metodo)(url, {"estado": "CERRADO"})

    assert response.status_code == 405
