"""El catálogo de estados es de solo lectura y viene cargado por migración."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_estados_fijos_cargados_por_migracion(api_client):
    response = api_client.get(reverse("estadoordenventa-list"))
    assert response.status_code == 200
    nombres = {e["nombre"] for e in response.data["results"]}
    assert nombres == {"Pendiente", "Anulada", "Devolución parcial", "Devolución total"}


@pytest.mark.django_db
@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_estados_no_se_pueden_modificar(api_client, metodo):
    url = reverse("estadoordenventa-list")
    response = getattr(api_client, metodo)(url, {"nombre": "Inventado"}, format="json")
    assert response.status_code == 405
