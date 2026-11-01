"""Devoluciones: validaciones, monto calculado, estados y reposición de stock."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.SCM.models import MovimientoInventario


def devolver(api_client, orden, items, **extra):
    return api_client.post(
        reverse("notacredito-list"),
        {"orden_venta": orden.pk, "saldo_a_favor": False, "detalles": items, **extra},
        format="json",
    )


def item(producto, cantidad, destino="STOCK_DISPONIBLE"):
    return {"producto": producto.id, "cantidad_devuelta": cantidad, "destino": destino}


@pytest.mark.django_db
def test_devolucion_parcial_repone_stock_y_cambia_estado(api_client, orden, producto):
    # La fixture `orden` vendió 3 unidades: el stock quedó en 7.
    response = devolver(api_client, orden, [item(producto, 2)])
    assert response.status_code == 201
    assert response.data["detalles"][0]["producto_nombre"] == producto.nombre
    assert "items" not in response.data

    producto.refresh_from_db()
    assert producto.stock_actual == 9
    orden.refresh_from_db()
    assert orden.estado.nombre == "Devolución parcial"


@pytest.mark.django_db
def test_devolver_todo_deja_la_orden_en_devolucion_total(api_client, orden, producto):
    response = devolver(api_client, orden, [item(producto, 3)])
    assert response.status_code == 201
    orden.refresh_from_db()
    assert orden.estado.nombre == "Devolución total"


@pytest.mark.django_db
def test_devoluciones_sucesivas_completan_la_devolucion_total(api_client, orden, producto):
    devolver(api_client, orden, [item(producto, 1)])
    orden.refresh_from_db()
    assert orden.estado.nombre == "Devolución parcial"
    assert devolver(api_client, orden, [item(producto, 2)]).status_code == 201
    orden.refresh_from_db()
    assert orden.estado.nombre == "Devolución total"


@pytest.mark.django_db
def test_el_monto_lo_calcula_el_servidor(api_client, orden, producto):
    # Se vendieron 3 x 100 = 300 sin descuento: 2 unidades devueltas = 200.
    response = devolver(api_client, orden, [item(producto, 2)], monto="9999.00")
    assert response.data["monto"] == "200.00"


@pytest.mark.django_db
def test_el_monto_respeta_el_descuento_de_la_venta(api_client, cliente, producto, usuario):
    from apps.Ventas import services

    orden = services.registrar_orden_venta(
        cuil=cliente.cuil,
        datos={"forma_pago": "EFECTIVO"},
        detalles=[{"producto": producto, "cantidad": 3, "descuento": Decimal("30.00")}],
        usuario=usuario,
    )  # se cobraron 270 -> 90 por unidad
    response = devolver(api_client, orden, [item(producto, 2)])
    assert response.data["monto"] == "180.00"


@pytest.mark.django_db
def test_devolucion_a_stock_deja_movimiento(api_client, orden, producto, usuario):
    response = devolver(api_client, orden, [item(producto, 2)])
    movimiento = MovimientoInventario.objects.get(tipo=MovimientoInventario.Tipo.DEVOLUCION)
    assert movimiento.cantidad == 2
    assert movimiento.usuario == usuario
    assert f"nota de crédito #{response.data['id']}" in movimiento.observacion


@pytest.mark.django_db
def test_producto_danado_no_repone_stock_ni_genera_movimiento(api_client, orden, producto):
    response = devolver(api_client, orden, [item(producto, 1, destino="PRODUCTO_DANADO")])
    assert response.status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 7  # sigue igual que tras la venta
    assert not MovimientoInventario.objects.filter(
        tipo=MovimientoInventario.Tipo.DEVOLUCION
    ).exists()


@pytest.mark.django_db
def test_devolucion_mixta(api_client, orden, producto):
    response = devolver(
        api_client, orden, [item(producto, 1), item(producto, 1, destino="PRODUCTO_DANADO")]
    )
    assert response.status_code == 201
    producto.refresh_from_db()
    assert producto.stock_actual == 8  # solo repone la unidad en buen estado


@pytest.mark.django_db
def test_no_se_puede_devolver_mas_de_lo_vendido_da_400(api_client, orden, producto):
    response = devolver(api_client, orden, [item(producto, 5)])
    assert response.status_code == 400
    assert response.data["codigo"] == "cantidad_supera_lo_vendido"
    assert "detalles" in response.data["errores"]
    producto.refresh_from_db()
    assert producto.stock_actual == 7  # nada cambió


@pytest.mark.django_db
def test_items_repetidos_se_suman_contra_lo_vendido(api_client, orden, producto):
    response = devolver(api_client, orden, [item(producto, 2), item(producto, 2)])
    assert response.status_code == 400


@pytest.mark.django_db
def test_no_se_puede_superar_lo_que_queda_por_devolver_da_409(api_client, orden, producto):
    devolver(api_client, orden, [item(producto, 2)])
    response = devolver(api_client, orden, [item(producto, 2)])  # quedaba 1
    assert response.status_code == 409
    assert response.data["codigo"] == "devolucion_excedida"
    assert "quedan 1" in response.data["mensaje"]


@pytest.mark.django_db
def test_producto_que_no_pertenece_a_la_orden_da_400(api_client, orden, crear_producto):
    ajeno = crear_producto(codigo="LAD-001", nombre="Ladrillo")
    response = devolver(api_client, orden, [item(ajeno, 1)])
    assert response.status_code == 400
    assert response.data["codigo"] == "producto_fuera_de_la_orden"


@pytest.mark.django_db
def test_no_se_devuelve_sobre_una_orden_anulada_da_409(api_client, orden, producto):
    api_client.post(
        reverse("anulacion-list"), {"orden_venta": orden.pk, "motivo": "Error"}, format="json"
    )
    response = devolver(api_client, orden, [item(producto, 1)])
    assert response.status_code == 409
    assert response.data["codigo"] == "estado_de_orden_invalido"


@pytest.mark.django_db
def test_no_se_devuelve_sobre_una_orden_ya_devuelta_por_completo_da_409(
    api_client, orden, producto
):
    devolver(api_client, orden, [item(producto, 3)])
    response = devolver(api_client, orden, [item(producto, 1)])
    assert response.status_code == 409


@pytest.mark.django_db
def test_nota_de_credito_sin_productos_da_400(api_client, orden):
    response = devolver(api_client, orden, [])
    assert response.status_code == 400
    assert "detalles" in response.data["errores"]


@pytest.mark.django_db
def test_destino_invalido_da_400(api_client, orden, producto):
    assert devolver(api_client, orden, [item(producto, 1, destino="TIRAR")]).status_code == 400


@pytest.mark.django_db
def test_cantidad_devuelta_cero_da_400(api_client, orden, producto):
    assert devolver(api_client, orden, [item(producto, 0)]).status_code == 400


@pytest.mark.django_db
def test_orden_inexistente_da_400(api_client, producto):
    response = api_client.post(
        reverse("notacredito-list"),
        {"orden_venta": 99999, "detalles": [item(producto, 1)]},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_nota_de_credito_no_se_edita_ni_se_borra(api_client, orden, producto):
    creada = devolver(api_client, orden, [item(producto, 1)])
    url = reverse("notacredito-detail", kwargs={"pk": creada.data["id"]})
    assert api_client.put(url, {}, format="json").status_code == 405
    assert api_client.delete(url).status_code == 405


@pytest.mark.django_db
def test_detalle_de_nota_de_credito_es_solo_lectura(api_client):
    response = api_client.post(reverse("detallenotacredito-list"), {}, format="json")
    assert response.status_code == 405
