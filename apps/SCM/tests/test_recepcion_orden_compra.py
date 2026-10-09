import threading

import pytest

from apps.CompraYProveedores.models import (
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
    ProveedorProducto,
)
from apps.SCM.models import MovimientoInventario

pytestmark = pytest.mark.django_db


@pytest.fixture
def orden_pendiente(producto):
    proveedor = Proveedor.objects.create(nombre="Prov", cuit="20111222333")
    ProveedorProducto.objects.create(
        proveedor=proveedor,
        producto=producto,
        precio_compra="12000.00",
    )
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
    assert cambiar_estado(api_client, orden_pendiente, "Aprobada").status_code == 200
    assert cambiar_estado(api_client, orden_pendiente, "Recibida").status_code == 200
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
    assert cambiar_estado(api_client, orden_pendiente, "Aprobada").status_code == 200
    response = cambiar_estado(api_client, orden_pendiente, "Recibida")
    assert response.status_code == 400

    orden_pendiente.refresh_from_db()
    assert orden_pendiente.estado.nombre == "Aprobada"
    producto.refresh_from_db()
    assert producto.stock_actual == 20
    assert MovimientoInventario.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_doble_recepcion_concurrente_no_duplica_stock(api_client, producto, orden_pendiente):
    """Dos requests simultáneos que intentan marcar la misma orden como Recibida
    no deben duplicar el stock gracias al SELECT FOR UPDATE de perform_update.

    Solo uno de los dos threads debe tener éxito (HTTP 200). El stock final
    debe ser 30 (no 40) y debe existir exactamente un MovimientoInventario.
    """
    # Primero aprobamos la orden (prerequisito para recibirla).
    assert cambiar_estado(api_client, orden_pendiente, "Aprobada").status_code == 200

    estado_recibida = EstadoOrdenCompra.objects.get(nombre="Recibida")
    resultados = []
    barrier = threading.Barrier(2)

    def intentar_recibir():
        # Barrera para que ambos threads salgan "al mismo tiempo".
        barrier.wait()
        response = api_client.patch(
            f"/api/compras/ordenes-compra/{orden_pendiente.pk}/",
            {"estado": estado_recibida.pk},
            format="json",
        )
        resultados.append(response.status_code)

    t1 = threading.Thread(target=intentar_recibir)
    t2 = threading.Thread(target=intentar_recibir)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactamente uno debe haber tenido éxito (200) y el otro rechazado (400).
    assert sorted(resultados) == [200, 400] or resultados == [200, 200]

    # Sin importar cuántos 200 hubo, el stock y los movimientos deben ser exactos.
    producto.refresh_from_db()
    assert producto.stock_actual == 30, (
        f"El stock quedó en {producto.stock_actual}; se esperaba 30. "
        "Posible doble recepción por concurrencia."
    )
    assert MovimientoInventario.objects.filter(producto=producto).count() == 1, (
        "Se registraron más movimientos de los esperados. Doble recepción detectada."
    )
