"""Registro y modificación de órdenes de venta (stock, total, movimientos de inventario)."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.SCM.models import MovimientoInventario
from apps.Ventas.models import OrdenVenta


def payload(cliente, items, **extra):
    return {"cliente": cliente.id_cliente, "forma_pago": "EFECTIVO", "detalles": items, **extra}


@pytest.mark.django_db
def test_registrar_venta_calcula_total_y_descuenta_stock(api_client, cliente, producto, usuario):
    response = api_client.post(
        reverse("ordenventa-list"),
        payload(cliente, [{"producto": producto.id, "cantidad": 3, "descuento": "50.00"}]),
        format="json",
    )
    assert response.status_code == 201
    assert Decimal(response.data["total"]) == Decimal("250.00")  # 3 x 100 - 50
    assert response.data["estado_nombre"] == "Pendiente"
    assert response.data["items"][0]["precio_unitario"] == "100.00"

    producto.refresh_from_db()
    assert producto.stock_actual == 7
    assert OrdenVenta.objects.get(pk=response.data["id"]).usuario == usuario


@pytest.mark.django_db
def test_registrar_venta_deja_movimiento_de_salida(api_client, cliente, producto, usuario):
    response = api_client.post(
        reverse("ordenventa-list"),
        payload(cliente, [{"producto": producto.id, "cantidad": 4}]),
        format="json",
    )
    movimiento = MovimientoInventario.objects.get()
    assert movimiento.tipo == MovimientoInventario.Tipo.SALIDA
    assert movimiento.cantidad == 4
    assert movimiento.usuario == usuario
    assert f"orden #{response.data['id']}" in movimiento.observacion


@pytest.mark.django_db
def test_mismo_producto_repetido_se_acumula(api_client, cliente, producto):
    response = api_client.post(
        reverse("ordenventa-list"),
        payload(
            cliente,
            [{"producto": producto.id, "cantidad": 3}, {"producto": producto.id, "cantidad": 2}],
        ),
        format="json",
    )
    assert response.status_code == 201
    assert Decimal(response.data["total"]) == Decimal("500.00")
    producto.refresh_from_db()
    assert producto.stock_actual == 5
    assert MovimientoInventario.objects.count() == 1  # un movimiento por producto


@pytest.mark.django_db
def test_stock_insuficiente_falla_y_no_cambia_nada(api_client, cliente, producto):
    response = api_client.post(
        reverse("ordenventa-list"),
        payload(cliente, [{"producto": producto.id, "cantidad": 11}]),
        format="json",
    )
    assert response.status_code == 400
    assert "Stock insuficiente" in str(response.data["detalles"])
    producto.refresh_from_db()
    assert producto.stock_actual == 10
    assert OrdenVenta.objects.count() == 0
    assert MovimientoInventario.objects.count() == 0


@pytest.mark.django_db
def test_stock_insuficiente_por_items_repetidos(api_client, cliente, producto):
    """Ninguno de los ítems supera el stock por separado, pero sumados sí."""
    response = api_client.post(
        reverse("ordenventa-list"),
        payload(
            cliente,
            [{"producto": producto.id, "cantidad": 6}, {"producto": producto.id, "cantidad": 6}],
        ),
        format="json",
    )
    assert response.status_code == 400
    assert OrdenVenta.objects.count() == 0


@pytest.mark.django_db
def test_venta_sin_productos_falla(api_client, cliente):
    response = api_client.post(reverse("ordenventa-list"), payload(cliente, []), format="json")
    assert response.status_code == 400
    assert "detalles" in response.data


@pytest.mark.django_db
def test_cantidad_cero_falla(api_client, cliente, producto):
    response = api_client.post(
        reverse("ordenventa-list"),
        payload(cliente, [{"producto": producto.id, "cantidad": 0}]),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_numero_de_comprobante_duplicado_falla(api_client, cliente, crear_producto):
    producto = crear_producto()
    items = [{"producto": producto.id, "cantidad": 1}]
    primera = api_client.post(
        reverse("ordenventa-list"),
        payload(cliente, items, numero_comprobante="B-0002145"),
        format="json",
    )
    segunda = api_client.post(
        reverse("ordenventa-list"),
        payload(cliente, items, numero_comprobante="B-0002145"),
        format="json",
    )
    assert primera.status_code == 201
    assert segunda.status_code == 400


@pytest.mark.django_db
def test_listar_y_buscar_por_cliente(api_client, orden):
    response = api_client.get(reverse("ordenventa-list"), {"search": "Juan"})
    assert response.status_code == 200
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_modificar_forma_de_pago(api_client, orden):
    response = api_client.patch(
        reverse("ordenventa-detail", kwargs={"pk": orden.pk}),
        {"forma_pago": "DEBITO"},
        format="json",
    )
    assert response.status_code == 200
    orden.refresh_from_db()
    assert orden.forma_pago == "DEBITO"


@pytest.mark.django_db
def test_no_se_puede_borrar_una_orden(api_client, orden):
    response = api_client.delete(reverse("ordenventa-detail", kwargs={"pk": orden.pk}))
    assert response.status_code == 405


@pytest.mark.django_db
def test_detalle_de_orden_es_solo_lectura(api_client, orden):
    assert api_client.get(reverse("ordenventadetalle-list")).status_code == 200
    response = api_client.post(reverse("ordenventadetalle-list"), {}, format="json")
    assert response.status_code == 405
