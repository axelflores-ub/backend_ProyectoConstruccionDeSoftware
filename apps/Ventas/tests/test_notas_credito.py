"""Devoluciones: notas de crédito, reposición de stock y movimientos de inventario."""

import pytest
from django.urls import reverse

from apps.SCM.models import MovimientoInventario


def payload(orden, items, **extra):
    return {
        "orden_venta": orden.pk,
        "monto": "100.00",
        "saldo_a_favor": False,
        "detalles": items,
        **extra,
    }


def item(producto, cantidad, destino="STOCK_DISPONIBLE"):
    return {"producto": producto.id, "cantidad_devuelta": cantidad, "destino": destino}


@pytest.mark.django_db
def test_devolucion_a_stock_repone_stock_y_cambia_estado(api_client, orden, producto):
    # La fixture `orden` vendió 3 unidades: el stock quedó en 7.
    response = api_client.post(
        reverse("notacredito-list"), payload(orden, [item(producto, 2)]), format="json"
    )
    assert response.status_code == 201
    assert response.data["items"][0]["producto_nombre"] == producto.nombre

    producto.refresh_from_db()
    assert producto.stock_actual == 9
    orden.refresh_from_db()
    assert orden.estado.nombre == "Devolución parcial"


@pytest.mark.django_db
def test_devolucion_a_stock_deja_movimiento(api_client, orden, producto, usuario):
    response = api_client.post(
        reverse("notacredito-list"), payload(orden, [item(producto, 2)]), format="json"
    )
    movimiento = MovimientoInventario.objects.get(tipo=MovimientoInventario.Tipo.DEVOLUCION)
    assert movimiento.cantidad == 2
    assert movimiento.usuario == usuario
    assert f"nota de crédito #{response.data['id']}" in movimiento.observacion


@pytest.mark.django_db
def test_producto_danado_no_repone_stock_ni_genera_movimiento(api_client, orden, producto):
    response = api_client.post(
        reverse("notacredito-list"),
        payload(orden, [item(producto, 1, destino="PRODUCTO_DANADO")]),
        format="json",
    )
    assert response.status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 7  # sigue igual que tras la venta
    assert not MovimientoInventario.objects.filter(
        tipo=MovimientoInventario.Tipo.DEVOLUCION
    ).exists()


@pytest.mark.django_db
def test_devolucion_mixta(api_client, orden, producto):
    response = api_client.post(
        reverse("notacredito-list"),
        payload(orden, [item(producto, 1), item(producto, 1, destino="PRODUCTO_DANADO")]),
        format="json",
    )
    assert response.status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 8  # solo repone la unidad en buen estado


@pytest.mark.django_db
def test_nota_de_credito_sin_productos_falla(api_client, orden):
    response = api_client.post(reverse("notacredito-list"), payload(orden, []), format="json")
    assert response.status_code == 400
    assert "detalles" in response.data


@pytest.mark.django_db
def test_destino_invalido_falla(api_client, orden, producto):
    response = api_client.post(
        reverse("notacredito-list"),
        payload(orden, [item(producto, 1, destino="TIRAR")]),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_cantidad_devuelta_cero_falla(api_client, orden, producto):
    response = api_client.post(
        reverse("notacredito-list"), payload(orden, [item(producto, 0)]), format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_nota_de_credito_no_se_edita_ni_se_borra(api_client, orden, producto):
    creada = api_client.post(
        reverse("notacredito-list"), payload(orden, [item(producto, 1)]), format="json"
    )
    url = reverse("notacredito-detail", kwargs={"pk": creada.data["id"]})
    assert api_client.put(url, {}, format="json").status_code == 405
    assert api_client.delete(url).status_code == 405


@pytest.mark.django_db
def test_detalle_de_nota_de_credito_es_solo_lectura(api_client):
    response = api_client.post(reverse("detallenotacredito-list"), {}, format="json")
    assert response.status_code == 405


@pytest.mark.django_db
def test_no_se_puede_devolver_mas_de_lo_vendido(api_client, orden, producto):
    # La orden vendió 3 unidades; intentar devolver 5 da 400 y no toca el stock.
    response = api_client.post(
        reverse("notacredito-list"), payload(orden, [item(producto, 5)]), format="json"
    )
    assert response.status_code == 400
    assert "detalles" in response.data
    producto.refresh_from_db()
    assert producto.stock_actual == 7
    assert not MovimientoInventario.objects.filter(
        tipo=MovimientoInventario.Tipo.DEVOLUCION
    ).exists()


@pytest.mark.django_db
def test_devolver_exactamente_lo_vendido_pasa(api_client, orden, producto):
    response = api_client.post(
        reverse("notacredito-list"), payload(orden, [item(producto, 3)]), format="json"
    )
    assert response.status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 10


@pytest.mark.django_db
def test_devoluciones_acumuladas_no_pueden_superar_lo_vendido(api_client, orden, producto):
    url = reverse("notacredito-list")
    assert (
        api_client.post(url, payload(orden, [item(producto, 2)]), format="json").status_code == 201
    )

    # Quedaba 1 disponible: pedir 2 más se pasa de las 3 vendidas.
    segunda = api_client.post(url, payload(orden, [item(producto, 2)]), format="json")
    assert segunda.status_code == 400
    assert "disponibles para devolver 1" in str(segunda.data["detalles"])

    producto.refresh_from_db()
    assert producto.stock_actual == 9

    # Devolver la que quedaba sí pasa.
    assert (
        api_client.post(url, payload(orden, [item(producto, 1)]), format="json").status_code == 201
    )
    producto.refresh_from_db()
    assert producto.stock_actual == 10


@pytest.mark.django_db
def test_producto_repetido_en_la_misma_nota_se_suma(api_client, orden, producto):
    # 2 + 2 = 4 unidades sobre 3 vendidas: ninguna línea se pasa sola, pero juntas sí.
    response = api_client.post(
        reverse("notacredito-list"),
        payload(orden, [item(producto, 2), item(producto, 2)]),
        format="json",
    )
    assert response.status_code == 400
    producto.refresh_from_db()
    assert producto.stock_actual == 7


@pytest.mark.django_db
def test_producto_danado_tambien_cuenta_como_devuelto(api_client, orden, producto):
    url = reverse("notacredito-list")
    api_client.post(
        url, payload(orden, [item(producto, 2, destino="PRODUCTO_DANADO")]), format="json"
    )
    response = api_client.post(url, payload(orden, [item(producto, 2)]), format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_devolver_producto_que_no_pertenece_a_la_orden_falla(api_client, orden, crear_producto):
    ajeno = crear_producto(codigo="LAD-001", nombre="Ladrillo común")
    response = api_client.post(
        reverse("notacredito-list"), payload(orden, [item(ajeno, 1)]), format="json"
    )
    assert response.status_code == 400
    assert "no pertenece" in str(response.data["detalles"])


@pytest.mark.django_db
def test_no_se_puede_devolver_sobre_una_orden_anulada(api_client, orden, producto):
    api_client.post(
        reverse("anulacion-list"), {"orden_venta": orden.pk, "motivo": "x"}, format="json"
    )
    response = api_client.post(
        reverse("notacredito-list"), payload(orden, [item(producto, 1)]), format="json"
    )
    assert response.status_code == 400
    producto.refresh_from_db()
    assert producto.stock_actual == 10  # lo repuso la anulación, la nota no sumó nada
