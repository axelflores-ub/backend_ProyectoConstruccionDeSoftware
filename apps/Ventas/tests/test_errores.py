"""Formato estándar de los errores: {"codigo", "mensaje", "errores"?}."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_error_de_validacion_tiene_formato_estandar(api_client):
    response = api_client.post(reverse("cliente-list"), {}, format="json")
    assert response.status_code == 400
    assert response.data["codigo"] == "datos_invalidos"
    assert response.data["mensaje"]
    assert set(response.data["errores"]) == {"nombre", "cuil", "condicion_iva"}


@pytest.mark.django_db
def test_recurso_inexistente_da_404_estandar(api_client):
    response = api_client.get(reverse("cliente-detail", kwargs={"id_cliente": 99999}))
    assert response.status_code == 404
    assert response.data["codigo"] == "no_encontrado"
    assert "errores" not in response.data


@pytest.mark.django_db
def test_metodo_no_permitido_da_405_estandar(api_client, cliente):
    url = reverse("cliente-detail", kwargs={"id_cliente": cliente.id_cliente})
    response = api_client.delete(url)
    assert response.status_code == 405
    assert response.data["codigo"] == "metodo_no_permitido"


@pytest.mark.django_db
def test_error_de_negocio_trae_codigo_especifico(api_client, cliente, producto):
    response = api_client.post(
        reverse("ordenventa-list"),
        {
            "cuil": cliente.cuil,
            "forma_pago": "EFECTIVO",
            "detalles": [{"producto": producto.id, "cantidad": 99}],
        },
        format="json",
    )
    assert response.status_code == 409
    assert response.data["codigo"] == "stock_insuficiente"
    assert "Stock insuficiente" in response.data["mensaje"]
