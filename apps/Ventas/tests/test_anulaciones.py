"""Anulación de órdenes de venta."""

import pytest
from django.urls import reverse

from apps.SCM.models import MovimientoInventario


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


def anular(api_client, orden):
    return api_client.post(
        reverse("anulacion-list"), {"orden_venta": orden.pk, "motivo": "Error"}, format="json"
    )


def nota(api_client, orden, producto, cantidad, destino="STOCK_DISPONIBLE"):
    return api_client.post(
        reverse("notacredito-list"),
        {
            "orden_venta": orden.pk,
            "monto": "100.00",
            "saldo_a_favor": False,
            "detalles": [
                {"producto": producto.id, "cantidad_devuelta": cantidad, "destino": destino}
            ],
        },
        format="json",
    )


@pytest.mark.django_db
def test_anular_repone_el_stock_y_deja_movimiento(api_client, orden, producto, usuario):
    # La fixture `orden` vendió 3 unidades: el stock quedó en 7.
    assert anular(api_client, orden).status_code == 201

    producto.refresh_from_db()
    assert producto.stock_actual == 10
    movimiento = MovimientoInventario.objects.get(tipo=MovimientoInventario.Tipo.DEVOLUCION)
    assert movimiento.cantidad == 3
    assert movimiento.usuario == usuario
    assert f"Anulación - orden #{orden.pk}" in movimiento.observacion


@pytest.mark.django_db
def test_anular_dos_veces_no_repone_stock_otra_vez(api_client, orden, producto):
    anular(api_client, orden)
    assert anular(api_client, orden).status_code == 400
    producto.refresh_from_db()
    assert producto.stock_actual == 10
    assert (
        MovimientoInventario.objects.filter(tipo=MovimientoInventario.Tipo.DEVOLUCION).count() == 1
    )


@pytest.mark.django_db
def test_anular_tras_devolucion_parcial_repone_solo_lo_pendiente(api_client, orden, producto):
    nota(api_client, orden, producto, 2)  # stock 7 -> 9
    assert anular(api_client, orden).status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 10  # no 12


@pytest.mark.django_db
def test_anular_tras_devolucion_danada_no_repone_lo_danado(api_client, orden, producto):
    nota(api_client, orden, producto, 1, destino="PRODUCTO_DANADO")  # stock sigue en 7
    assert anular(api_client, orden).status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 9  # repone 2 de las 3; la dañada no vuelve


@pytest.mark.django_db
def test_anular_orden_ya_devuelta_por_completo_no_repone_nada(api_client, orden, producto):
    nota(api_client, orden, producto, 3)  # stock 7 -> 10
    assert anular(api_client, orden).status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 10
    assert (
        MovimientoInventario.objects.filter(tipo=MovimientoInventario.Tipo.DEVOLUCION).count() == 1
    )  # solo el de la nota de crédito
