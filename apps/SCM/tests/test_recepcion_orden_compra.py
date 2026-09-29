import pytest

from apps.CompraYProveedores.models import (
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
)
from apps.SCM.models import MovimientoInventario

pytestmark = pytest.mark.django_db


@pytest.fixture
def orden_pendiente(producto):
    proveedor = Proveedor.objects.create(nombre="Prov", cuit="20111222333", producto_id=producto.id)
    orden = OrdenCompra.objects.create(
        proveedor=proveedor,
        estado=EstadoOrdenCompra.objects.get(nombre="Pendiente"),
        fecha="2026-09-20T10:00:00-03:00",
        total="120000.00",
    )
    OrdenCompraDetalle.objects.create(
        orden_compra=orden, producto_id=producto.id, cantidad=10, precio_unitario="12000.00"
    )
    return orden


def cambiar_estado(client, orden, nombre):
    estado = EstadoOrdenCompra.objects.get(nombre=nombre)
    return client.patch(
        f"/api/compras/ordenes-compra/{orden.pk}/",
        {"estado": estado.pk},
        format="json",
    )


def test_estados_de_orden_de_compra_vienen_cargados():
    nombres = set(EstadoOrdenCompra.objects.values_list("nombre", flat=True))
    assert {"Pendiente", "Aprobada", "Rechazada", "Recibida"} <= nombres


def test_marcar_recibida_suma_stock_y_deja_movimiento(api_client, producto, orden_pendiente):
    assert cambiar_estado(api_client, orden_pendiente, "Aprobada").status_code == 200
    producto.refresh_from_db()
    assert producto.stock_actual == 20  # aprobar no toca el stock

    assert cambiar_estado(api_client, orden_pendiente, "Recibida").status_code == 200
    producto.refresh_from_db()
    assert producto.stock_actual == 30

    movimiento = MovimientoInventario.objects.get(producto=producto)
    assert movimiento.tipo == "ENTRADA"
    assert movimiento.cantidad == 10
    assert str(orden_pendiente.pk) in movimiento.observacion


def test_orden_recibida_no_puede_cambiar_de_estado(api_client, producto, orden_pendiente):
    cambiar_estado(api_client, orden_pendiente, "Recibida")
    response = cambiar_estado(api_client, orden_pendiente, "Pendiente")
    assert response.status_code == 400

    orden_pendiente.refresh_from_db()
    assert orden_pendiente.estado.nombre == "Recibida"
    producto.refresh_from_db()
    assert producto.stock_actual == 30


def test_recibida_con_producto_inexistente_no_cambia_nada(api_client, producto, orden_pendiente):
    OrdenCompraDetalle.objects.create(
        orden_compra=orden_pendiente, producto_id=99999, cantidad=1, precio_unitario="1.00"
    )
    response = cambiar_estado(api_client, orden_pendiente, "Recibida")
    assert response.status_code == 400

    orden_pendiente.refresh_from_db()
    assert orden_pendiente.estado.nombre == "Pendiente"
    producto.refresh_from_db()
    assert producto.stock_actual == 20
    assert MovimientoInventario.objects.count() == 0
