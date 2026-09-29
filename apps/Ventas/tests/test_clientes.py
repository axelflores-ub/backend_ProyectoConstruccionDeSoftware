"""ABM de clientes: alta, listado paginado, búsqueda, edición y baja lógica."""

import pytest
from django.urls import reverse

from apps.Ventas.models import Cliente


def detalle(cliente):
    return reverse("cliente-detail", kwargs={"id_cliente": cliente.id_cliente})


@pytest.mark.django_db
def test_crear_cliente(api_client):
    response = api_client.post(
        reverse("cliente-list"),
        {"nombre": "Ana Gómez", "cuil": "27111111119", "condicion_iva": "Monotributista"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["estado"] == Cliente.ESTADO_ACTIVO
    assert Cliente.objects.filter(nombre="Ana Gómez").exists()


@pytest.mark.django_db
def test_crear_cliente_siempre_nace_activo(api_client):
    response = api_client.post(
        reverse("cliente-list"), {"nombre": "Ana", "estado": "OF"}, format="json"
    )
    assert response.status_code == 201
    assert response.data["estado"] == "AC"


@pytest.mark.django_db
def test_crear_cliente_sin_nombre_falla(api_client):
    response = api_client.post(reverse("cliente-list"), {"telefono": "123"}, format="json")
    assert response.status_code == 400
    assert "nombre" in response.data


@pytest.mark.django_db
def test_listado_es_paginado(api_client):
    for i in range(25):
        Cliente.objects.create(nombre=f"Cliente {i}")
    response = api_client.get(reverse("cliente-list"))
    assert response.status_code == 200
    assert response.data["count"] == 25
    assert len(response.data["results"]) == 20
    assert response.data["next"] is not None


@pytest.mark.django_db
def test_buscar_cliente_por_cuil(api_client, cliente):
    Cliente.objects.create(nombre="Otro", cuil="20999999999")
    response = api_client.get(reverse("cliente-list"), {"search": "20123456789"})
    assert response.status_code == 200
    assert [c["nombre"] for c in response.data["results"]] == ["Juan Pérez"]


@pytest.mark.django_db
def test_obtener_cliente(api_client, cliente):
    response = api_client.get(detalle(cliente))
    assert response.status_code == 200
    assert response.data["id_cliente"] == cliente.id_cliente


@pytest.mark.django_db
def test_obtener_cliente_inexistente_da_404(api_client):
    response = api_client.get(reverse("cliente-detail", kwargs={"id_cliente": 99999}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_actualizar_cliente(api_client, cliente):
    response = api_client.put(
        detalle(cliente), {"nombre": "Juan P. Actualizado", "estado": "AC"}, format="json"
    )
    assert response.status_code == 200
    cliente.refresh_from_db()
    assert cliente.nombre == "Juan P. Actualizado"


@pytest.mark.django_db
def test_baja_logica_no_borra_el_cliente(api_client, cliente):
    response = api_client.delete(detalle(cliente))
    assert response.status_code == 200
    assert response.data["cliente"]["estado"] == "OF"
    cliente.refresh_from_db()  # sigue existiendo, solo cambió el estado
    assert cliente.estado == Cliente.ESTADO_BAJA
