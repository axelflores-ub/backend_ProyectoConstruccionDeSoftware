import pytest
from rest_framework.test import APIClient

from apps.SCM.models import Rubro

pytestmark = pytest.mark.django_db

URL = "/api/scm/rubros/"


def test_listar_rubros_ordenados_por_nombre(api_client):
    Rubro.objects.create(nombre="Pinturas")
    Rubro.objects.create(nombre="Arena")
    Rubro.objects.create(nombre="Herramientas")

    response = api_client.get(URL)

    assert response.status_code == 200
    assert [r["nombre"] for r in response.data["results"]] == ["Arena", "Herramientas", "Pinturas"]


def test_listar_rubros_con_ordering_descendente(api_client):
    Rubro.objects.create(nombre="Arena")
    Rubro.objects.create(nombre="Pinturas")

    response = api_client.get(f"{URL}?ordering=-nombre")

    assert [r["nombre"] for r in response.data["results"]] == ["Pinturas", "Arena"]


def test_buscar_rubro_por_nombre(api_client):
    Rubro.objects.create(nombre="Pinturas")
    Rubro.objects.create(nombre="Arena")

    response = api_client.get(f"{URL}?search=pint")

    assert response.status_code == 200
    assert [r["nombre"] for r in response.data["results"]] == ["Pinturas"]


def test_detalle_de_rubro(api_client, rubro):
    response = api_client.get(f"{URL}{rubro.id}/")

    assert response.status_code == 200
    assert response.data == {
        "id": rubro.id,
        "nombre": "Cemento",
        "descripcion": "Bolsas y a granel",
    }


def test_detalle_de_rubro_inexistente_da_404(api_client):
    assert api_client.get(f"{URL}99999/").status_code == 404


def test_crear_rubro_sin_nombre_da_400(api_client):
    response = api_client.post(URL, {"descripcion": "Sin nombre"}, format="json")

    assert response.status_code == 400
    assert "nombre" in response.data


def test_put_reemplaza_el_rubro(api_client, rubro):
    response = api_client.put(
        f"{URL}{rubro.id}/", {"nombre": "Cales", "descripcion": "Cal hidratada"}, format="json"
    )

    assert response.status_code == 200
    rubro.refresh_from_db()
    assert (rubro.nombre, rubro.descripcion) == ("Cales", "Cal hidratada")


def test_patch_modifica_solo_lo_enviado(api_client, rubro):
    response = api_client.patch(f"{URL}{rubro.id}/", {"descripcion": "Nueva"}, format="json")

    assert response.status_code == 200
    rubro.refresh_from_db()
    assert rubro.nombre == "Cemento"
    assert rubro.descripcion == "Nueva"


def test_editar_rubro_con_nombre_de_otro_da_400(api_client, rubro):
    Rubro.objects.create(nombre="Arena")

    response = api_client.patch(f"{URL}{rubro.id}/", {"nombre": "arena"}, format="json")

    assert response.status_code == 400
    assert "nombre" in response.data
    rubro.refresh_from_db()
    assert rubro.nombre == "Cemento"


def test_borrar_rubro_sin_productos(api_client):
    rubro = Rubro.objects.create(nombre="Vacío")

    assert api_client.delete(f"{URL}{rubro.id}/").status_code == 204
    assert not Rubro.objects.filter(pk=rubro.pk).exists()


@pytest.mark.xfail(
    strict=True,
    reason="BUG: borrar un rubro con productos lanza ProtectedError y responde 500; "
    "debería ser un error controlado (400/409).",
)
def test_borrar_rubro_con_productos_da_error_controlado(api_client, producto):
    api_client.raise_request_exception = False

    response = api_client.delete(f"{URL}{producto.rubro_id}/")

    assert response.status_code in (400, 409)
    assert Rubro.objects.filter(pk=producto.rubro_id).exists()


def test_borrar_rubro_con_productos_no_lo_elimina(api_client, producto):
    """Aunque hoy la respuesta sea 500, el rubro y su producto deben seguir existiendo."""
    api_client.raise_request_exception = False

    api_client.delete(f"{URL}{producto.rubro_id}/")

    assert Rubro.objects.filter(pk=producto.rubro_id).exists()
    producto.refresh_from_db()
    assert producto.rubro_id is not None


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_rubros_sin_token_da_401(metodo):
    response = getattr(APIClient(), metodo)(URL, {"nombre": "X"}, format="json")

    assert response.status_code == 401
