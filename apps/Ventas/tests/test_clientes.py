"""ABM de clientes: alta, búsqueda por CUIL, edición y baja lógica (PATCH)."""

import pytest
from django.urls import reverse

from apps.Ventas.models import Cliente


def detalle(cliente):
    return reverse("cliente-detail", kwargs={"id_cliente": cliente.id_cliente})


def alta(api_client, **extra):
    datos = {
        "nombre": "Ana Gómez",
        "cuil": "27111111119",
        "condicion_iva": "Monotributista",
        **extra,
    }
    return api_client.post(reverse("cliente-list"), datos, format="json")


@pytest.mark.django_db
def test_crear_cliente(api_client):
    response = alta(api_client)
    assert response.status_code == 201
    assert response.data["estado"] == Cliente.ESTADO_ACTIVO
    assert Cliente.objects.filter(nombre="Ana Gómez").exists()


@pytest.mark.django_db
def test_crear_cliente_siempre_nace_activo(api_client):
    assert alta(api_client, estado="OF").data["estado"] == "AC"


@pytest.mark.django_db
def test_cuil_con_guiones_se_guarda_sin_guiones(api_client):
    response = alta(api_client, cuil="27-11111111-9")
    assert response.status_code == 201
    assert response.data["cuil"] == "27111111119"


@pytest.mark.django_db
@pytest.mark.parametrize("cuil", ["2712345", "271111111190", "abcdefghijk"])
def test_cuil_invalido_da_400(api_client, cuil):
    response = alta(api_client, cuil=cuil)
    assert response.status_code == 400
    assert "cuil" in response.data["errores"]


@pytest.mark.django_db
@pytest.mark.parametrize("faltante", ["nombre", "cuil", "condicion_iva"])
def test_campos_obligatorios_del_alta(api_client, faltante):
    datos = {"nombre": "Ana", "cuil": "27111111119", "condicion_iva": "Monotributista"}
    datos.pop(faltante)
    response = api_client.post(reverse("cliente-list"), datos, format="json")
    assert response.status_code == 400
    assert faltante in response.data["errores"]


@pytest.mark.django_db
def test_cuil_duplicado_da_409_tambien_con_otro_formato(api_client, cliente):
    response = alta(api_client, cuil="20-12345678-9")  # mismo CUIL que `cliente`
    assert response.status_code == 409
    assert response.data["codigo"] == "cuil_duplicado"


@pytest.mark.django_db
def test_listado_es_paginado(api_client):
    for i in range(25):
        Cliente.objects.create(nombre=f"Cliente {i}", cuil=f"2000000{i:04d}", condicion_iva="X")
    response = api_client.get(reverse("cliente-list"))
    assert response.status_code == 200
    assert response.data["count"] == 25
    assert len(response.data["results"]) == 20
    assert response.data["next"] is not None


@pytest.mark.django_db
def test_buscar_por_cuil_exacto(api_client, cliente):
    Cliente.objects.create(nombre="Otro", cuil="20999999999", condicion_iva="X")
    response = api_client.get(reverse("cliente-list"), {"cuil": "20-12345678-9"})
    assert response.status_code == 200
    assert [c["nombre"] for c in response.data["results"]] == ["Juan Pérez"]


@pytest.mark.django_db
def test_buscar_por_cuil_inexistente_devuelve_lista_vacia(api_client, cliente):
    response = api_client.get(reverse("cliente-list"), {"cuil": "27111111119"})
    assert response.status_code == 200
    assert response.data["count"] == 0


@pytest.mark.django_db
@pytest.mark.parametrize("cuil", ["", "123", "20-1234"])
def test_buscar_por_cuil_incompleto_da_400(api_client, cuil):
    response = api_client.get(reverse("cliente-list"), {"cuil": cuil})
    assert response.status_code == 400
    assert "cuil" in response.data["errores"]


@pytest.mark.django_db
def test_busqueda_libre_por_nombre(api_client, cliente):
    response = api_client.get(reverse("cliente-list"), {"search": "Juan"})
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_obtener_cliente(api_client, cliente):
    response = api_client.get(detalle(cliente))
    assert response.status_code == 200
    assert response.data["id_cliente"] == cliente.id_cliente


@pytest.mark.django_db
def test_actualizar_cliente(api_client, cliente):
    response = api_client.put(
        detalle(cliente),
        {
            "nombre": "Juan P. Actualizado",
            "cuil": cliente.cuil,
            "condicion_iva": "Consumidor Final",
        },
        format="json",
    )
    assert response.status_code == 200
    cliente.refresh_from_db()
    assert cliente.nombre == "Juan P. Actualizado"


@pytest.mark.django_db
def test_baja_logica_con_patch_no_borra_el_cliente(api_client, cliente):
    response = api_client.patch(detalle(cliente), {"estado": "OF"}, format="json")
    assert response.status_code == 200
    assert response.data["estado"] == "OF"
    cliente.refresh_from_db()
    assert cliente.estado == Cliente.ESTADO_BAJA


@pytest.mark.django_db
def test_reactivar_cliente_con_patch(api_client, cliente):
    api_client.patch(detalle(cliente), {"estado": "OF"}, format="json")
    response = api_client.patch(detalle(cliente), {"estado": "AC"}, format="json")
    assert response.data["estado"] == "AC"


@pytest.mark.django_db
def test_estado_invalido_da_400(api_client, cliente):
    response = api_client.patch(detalle(cliente), {"estado": "XX"}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_no_existe_baja_fisica(api_client, cliente):
    response = api_client.delete(detalle(cliente))
    assert response.status_code == 405
    assert Cliente.objects.filter(pk=cliente.pk).exists()
