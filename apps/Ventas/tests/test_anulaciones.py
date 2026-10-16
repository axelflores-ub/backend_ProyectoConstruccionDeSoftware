"""Anulación de órdenes de venta."""

import pytest
from django.urls import reverse


def anular(api_client, orden, **extra):
    return api_client.post(
        reverse("anulacion-list"),
        {"orden_venta": orden.pk, "motivo": "Error de carga", **extra},
        format="json",
    )


@pytest.mark.django_db
def test_anular_orden_cambia_su_estado(api_client, orden):
    response = anular(api_client, orden, detalle="Cliente equivocado")
    assert response.status_code == 201
    orden.refresh_from_db()
    assert orden.estado.nombre == "Anulada"


@pytest.mark.django_db
def test_anular_sin_detalle_funciona(api_client, orden):
    assert anular(api_client, orden).status_code == 201


@pytest.mark.django_db
def test_no_se_puede_anular_dos_veces_da_409(api_client, orden):
    assert anular(api_client, orden).status_code == 201
    segunda = anular(api_client, orden)
    assert segunda.status_code == 409
    assert segunda.data["codigo"] == "orden_ya_anulada"


@pytest.mark.django_db
def test_no_se_anula_una_orden_con_devoluciones_da_409(api_client, orden, producto):
    api_client.post(
        reverse("notacredito-list"),
        {
            "orden_venta": orden.pk,
            "detalles": [
                {"producto": producto.id, "cantidad_devuelta": 1, "destino": "STOCK_DISPONIBLE"}
            ],
        },
        format="json",
    )
    response = anular(api_client, orden)
    assert response.status_code == 409
    assert response.data["codigo"] == "estado_de_orden_invalido"


@pytest.mark.django_db
def test_anular_sin_motivo_da_400(api_client, orden):
    response = api_client.post(reverse("anulacion-list"), {"orden_venta": orden.pk}, format="json")
    assert response.status_code == 400
    assert "motivo" in response.data["errores"]


@pytest.mark.django_db
def test_anular_orden_inexistente_da_400(api_client):
    response = api_client.post(
        reverse("anulacion-list"), {"orden_venta": 99999, "motivo": "x"}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_una_anulacion_no_se_edita_ni_se_borra(api_client, orden):
    creada = anular(api_client, orden)
    url = reverse("anulacion-detail", kwargs={"pk": creada.data["id"]})
    assert api_client.put(url, {"motivo": "otro"}, format="json").status_code == 405
    assert api_client.delete(url).status_code == 405
