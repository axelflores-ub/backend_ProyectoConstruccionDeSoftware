"""Generar y modificar órdenes de venta (cliente por CUIL, stock, total, movimientos)."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.SCM.models import MovimientoInventario
from apps.Ventas.models import Cliente, OrdenVenta


def payload(cli, items, **extra):
    return {"cuil": cli.cuil, "forma_pago": "EFECTIVO", "detalles": items, **extra}


def generar(api_client, cli, items, **extra):
    return api_client.post(reverse("ordenventa-list"), payload(cli, items, **extra), format="json")


@pytest.mark.django_db
def test_generar_orden_calcula_total_y_descuenta_stock(api_client, cliente, producto, usuario):
    response = generar(
        api_client, cliente, [{"producto": producto.id, "cantidad": 3, "descuento": "50.00"}]
    )
    assert response.status_code == 201
    assert Decimal(response.data["total"]) == Decimal("250.00")  # 3 x 100 - 50
    assert response.data["estado_nombre"] == "Pendiente"
    assert response.data["cliente"] == cliente.id_cliente
    assert response.data["cliente_nombre"] == "Juan Pérez"

    producto.refresh_from_db()
    assert producto.stock_actual == 7
    assert OrdenVenta.objects.get(pk=response.data["id"]).usuario == usuario


@pytest.mark.django_db
def test_detalle_muestra_cantidad_precio_unitario_y_subtotal(api_client, cliente, producto):
    response = generar(api_client, cliente, [{"producto": producto.id, "cantidad": 2}])
    item = response.data["detalles"][0]
    assert item["cantidad"] == 2
    assert item["precio_unitario"] == "100.00"
    assert item["subtotal"] == "200.00"
    assert item["producto_nombre"] == producto.nombre
    assert "items" not in response.data  # request y response usan el mismo nombre: detalles


@pytest.mark.django_db
def test_precio_unitario_enviado_por_el_cliente_se_ignora(api_client, cliente, producto):
    response = generar(
        api_client,
        cliente,
        [{"producto": producto.id, "cantidad": 1, "precio_unitario": "1.00"}],
    )
    assert response.data["detalles"][0]["precio_unitario"] == "100.00"


@pytest.mark.django_db
def test_cuil_con_guiones_encuentra_al_cliente(api_client, cliente, producto):
    response = api_client.post(
        reverse("ordenventa-list"),
        {
            "cuil": "20-12345678-9",
            "forma_pago": "EFECTIVO",
            "detalles": [{"producto": producto.id, "cantidad": 1}],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["cliente_cuil"] == "20123456789"


@pytest.mark.django_db
def test_el_cliente_no_se_elige_por_id(api_client, cliente, producto):
    otro = Cliente.objects.create(nombre="Otro", cuil="27111111119", condicion_iva="X")
    response = generar(
        api_client, cliente, [{"producto": producto.id, "cantidad": 1}], cliente=otro.id_cliente
    )
    assert response.status_code == 201
    assert response.data["cliente"] == cliente.id_cliente  # manda el CUIL, no el id


@pytest.mark.django_db
def test_cuil_inexistente_da_404(api_client, cliente, producto):
    inexistente = Cliente(cuil="27111111119")
    response = generar(api_client, inexistente, [{"producto": producto.id, "cantidad": 1}])
    assert response.status_code == 404
    assert response.data["codigo"] == "cliente_no_encontrado"


@pytest.mark.django_db
def test_cliente_dado_de_baja_da_409(api_client, cliente, producto):
    cliente.estado = Cliente.ESTADO_BAJA
    cliente.save()
    response = generar(api_client, cliente, [{"producto": producto.id, "cantidad": 1}])
    assert response.status_code == 409
    assert response.data["codigo"] == "cliente_de_baja"


@pytest.mark.django_db
@pytest.mark.parametrize("faltante", ["cuil", "forma_pago", "detalles"])
def test_parametros_obligatorios(api_client, cliente, producto, faltante):
    datos = payload(cliente, [{"producto": producto.id, "cantidad": 1}])
    datos.pop(faltante)
    response = api_client.post(reverse("ordenventa-list"), datos, format="json")
    assert response.status_code == 400
    assert faltante in response.data["errores"]


@pytest.mark.django_db
def test_cuil_mal_formado_da_400(api_client, cliente, producto):
    datos = payload(cliente, [{"producto": producto.id, "cantidad": 1}])
    datos["cuil"] = "123"
    response = api_client.post(reverse("ordenventa-list"), datos, format="json")
    assert response.status_code == 400
    assert "cuil" in response.data["errores"]


@pytest.mark.django_db
def test_generar_orden_deja_movimiento_de_salida(api_client, cliente, producto, usuario):
    response = generar(api_client, cliente, [{"producto": producto.id, "cantidad": 4}])
    movimiento = MovimientoInventario.objects.get()
    assert movimiento.tipo == MovimientoInventario.Tipo.SALIDA
    assert movimiento.cantidad == 4
    assert movimiento.usuario == usuario
    assert f"orden #{response.data['id']}" in movimiento.observacion


@pytest.mark.django_db
def test_mismo_producto_repetido_se_acumula(api_client, cliente, producto):
    response = generar(
        api_client,
        cliente,
        [{"producto": producto.id, "cantidad": 3}, {"producto": producto.id, "cantidad": 2}],
    )
    assert response.status_code == 201
    assert Decimal(response.data["total"]) == Decimal("500.00")
    producto.refresh_from_db()
    assert producto.stock_actual == 5
    assert MovimientoInventario.objects.count() == 1  # un movimiento por producto


@pytest.mark.django_db
def test_stock_insuficiente_da_409_y_no_cambia_nada(api_client, cliente, producto):
    response = generar(api_client, cliente, [{"producto": producto.id, "cantidad": 11}])
    assert response.status_code == 409
    assert response.data["codigo"] == "stock_insuficiente"
    producto.refresh_from_db()
    assert producto.stock_actual == 10
    assert OrdenVenta.objects.count() == 0
    assert MovimientoInventario.objects.count() == 0


@pytest.mark.django_db
def test_stock_insuficiente_por_items_repetidos(api_client, cliente, producto):
    """Ninguno de los ítems supera el stock por separado, pero sumados sí."""
    response = generar(
        api_client,
        cliente,
        [{"producto": producto.id, "cantidad": 6}, {"producto": producto.id, "cantidad": 6}],
    )
    assert response.status_code == 409
    assert OrdenVenta.objects.count() == 0


@pytest.mark.django_db
def test_orden_sin_productos_da_400(api_client, cliente):
    response = generar(api_client, cliente, [])
    assert response.status_code == 400
    assert "detalles" in response.data["errores"]


@pytest.mark.django_db
def test_cantidad_cero_da_400(api_client, cliente, producto):
    response = generar(api_client, cliente, [{"producto": producto.id, "cantidad": 0}])
    assert response.status_code == 400


@pytest.mark.django_db
def test_producto_inexistente_da_400(api_client, cliente):
    response = generar(api_client, cliente, [{"producto": 99999, "cantidad": 1}])
    assert response.status_code == 400


@pytest.mark.django_db
def test_numero_de_comprobante_duplicado_da_409(api_client, cliente, producto):
    items = [{"producto": producto.id, "cantidad": 1}]
    primera = generar(api_client, cliente, items, numero_comprobante="B-0002145")
    segunda = generar(api_client, cliente, items, numero_comprobante="B-0002145")
    assert primera.status_code == 201
    assert segunda.status_code == 409
    assert segunda.data["codigo"] == "comprobante_duplicado"


@pytest.mark.django_db
def test_comprobante_vacio_no_choca_entre_ordenes(api_client, cliente, producto):
    items = [{"producto": producto.id, "cantidad": 1}]
    assert generar(api_client, cliente, items, numero_comprobante="").status_code == 201
    assert generar(api_client, cliente, items, numero_comprobante="").status_code == 201


@pytest.mark.django_db
def test_la_fecha_la_pone_el_servidor_con_el_dia_de_hoy(api_client, cliente, producto):
    response = generar(
        api_client,
        cliente,
        [{"producto": producto.id, "cantidad": 1}],
        fecha="2001-01-01T00:00:00Z",
    )
    fecha = timezone.localtime(OrdenVenta.objects.get(pk=response.data["id"]).fecha).date()
    assert fecha == timezone.localdate()


@pytest.mark.django_db
def test_listar_y_buscar_por_cuil_del_cliente(api_client, orden):
    response = api_client.get(reverse("ordenventa-list"), {"search": "20123456789"})
    assert response.status_code == 200
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_modificar_forma_de_pago_mientras_esta_pendiente(api_client, orden):
    response = api_client.patch(
        reverse("ordenventa-detail", kwargs={"pk": orden.pk}),
        {"forma_pago": "DEBITO"},
        format="json",
    )
    assert response.status_code == 200
    orden.refresh_from_db()
    assert orden.forma_pago == "DEBITO"


@pytest.mark.django_db
def test_el_estado_y_el_cliente_no_se_cambian_por_put(api_client, orden):
    otro = Cliente.objects.create(nombre="Otro", cuil="27111111119", condicion_iva="X")
    api_client.put(
        reverse("ordenventa-detail", kwargs={"pk": orden.pk}),
        {"forma_pago": "DEBITO", "estado": 999, "cliente": otro.id_cliente},
        format="json",
    )
    orden.refresh_from_db()
    assert orden.estado.nombre == "Pendiente"
    assert orden.cliente.cuil == "20123456789"


@pytest.mark.django_db
def test_no_se_modifica_una_orden_que_ya_no_esta_pendiente(api_client, orden):
    api_client.post(
        reverse("anulacion-list"), {"orden_venta": orden.pk, "motivo": "Error"}, format="json"
    )
    response = api_client.patch(
        reverse("ordenventa-detail", kwargs={"pk": orden.pk}),
        {"forma_pago": "DEBITO"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["codigo"] == "orden_no_modificable"


@pytest.mark.django_db
def test_no_se_puede_borrar_una_orden(api_client, orden):
    response = api_client.delete(reverse("ordenventa-detail", kwargs={"pk": orden.pk}))
    assert response.status_code == 405


@pytest.mark.django_db
def test_detalle_de_orden_es_solo_lectura(api_client, orden):
    assert api_client.get(reverse("ordenventadetalle-list")).status_code == 200
    response = api_client.post(reverse("ordenventadetalle-list"), {}, format="json")
    assert response.status_code == 405
