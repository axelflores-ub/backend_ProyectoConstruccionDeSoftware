import pytest
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIClient

from apps.ContabilidadFinanzas import views

BASE = "/api/contabilidad"

ENDPOINTS = [
    ("get", f"{BASE}/periodos/"),
    ("get", f"{BASE}/periodos/1/"),
    ("post", f"{BASE}/periodos/"),
    ("put", f"{BASE}/periodos/1/"),
    ("get", f"{BASE}/cierres-mensuales/"),
    ("get", f"{BASE}/cierres-mensuales/1/"),
    ("put", f"{BASE}/cierres-mensuales/1/"),
    ("get", f"{BASE}/diarios/"),
    ("get", f"{BASE}/diarios/1/"),
    ("get", f"{BASE}/facturas/"),
    ("get", f"{BASE}/facturas/1/"),
    ("post", f"{BASE}/facturas/"),
    ("get", f"{BASE}/facturas-detalle/"),
    ("get", f"{BASE}/facturas-detalle/1/"),
    ("post", f"{BASE}/facturas-detalle/"),
]

VIEWSETS = [
    views.PeriodoViewSet,
    views.CierreMensualViewSet,
    views.DiarioViewSet,
    views.FacturaCabeceraViewSet,
    views.FacturaDetalleViewSet,
]


@pytest.mark.django_db
@pytest.mark.parametrize(("metodo", "url"), ENDPOINTS)
def test_endpoint_sin_token_devuelve_401(metodo, url):
    response = getattr(APIClient(), metodo)(url, {}, format="json")

    assert response.status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize(("metodo", "url"), ENDPOINTS)
def test_endpoint_con_token_invalido_devuelve_401(metodo, url):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer token-invalido")

    response = getattr(client, metodo)(url, {}, format="json")

    assert response.status_code == 401


@pytest.mark.parametrize("viewset", VIEWSETS)
def test_viewset_exige_autenticacion_explicita(viewset):
    assert viewset.permission_classes == [IsAuthenticated]
    assert viewset.authentication_classes
