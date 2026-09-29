"""Anulación de órdenes de venta."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_anular_orden_cambia_su_estado(api_client, orden):
    response = api_client.post(
        reverse("anulacion-list"),
        {"orden_venta": orden.pk, "motivo": "Error de carga", "detalle": "Cliente equivocado"},
        format="json",
    )
    assert response.status_code == 201
    orden.refresh_from_db()
    assert orden.estado.nombre == "Anulada"


@pytest.mark.django_db
def test_no_se_puede_anular_dos_veces(api_client, orden):
    datos = {"orden_venta": orden.pk, "motivo": "Error de carga"}
    assert api_client.post(reverse("anulacion-list"), datos, format="json").status_code == 201
    segunda = api_client.post(reverse("anulacion-list"), datos, format="json")
    assert segunda.status_code == 400
    assert "orden_venta" in segunda.data


@pytest.mark.django_db
def test_anular_sin_motivo_falla(api_client, orden):
    response = api_client.post(reverse("anulacion-list"), {"orden_venta": orden.pk}, format="json")
    assert response.status_code == 400
    assert "motivo" in response.data


@pytest.mark.django_db
def test_anular_orden_inexistente_falla(api_client):
    response = api_client.post(
        reverse("anulacion-list"), {"orden_venta": 99999, "motivo": "x"}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_una_anulacion_no_se_edita_ni_se_borra(api_client, orden):
    creada = api_client.post(
        reverse("anulacion-list"), {"orden_venta": orden.pk, "motivo": "x"}, format="json"
    )
    url = reverse("anulacion-detail", kwargs={"pk": creada.data["id"]})
    assert api_client.put(url, {"motivo": "otro"}, format="json").status_code == 405
    assert api_client.delete(url).status_code == 405
