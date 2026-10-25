import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from apps.CompraYProveedores.models import (
    EstadoOrdenCompra,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
)
from apps.SCM import services
from apps.SCM.models import MovimientoInventario, Producto

pytestmark = pytest.mark.django_db


@pytest.fixture
def usuario():
    return get_user_model().objects.create_user(username="servicio", password="x")


@pytest.fixture
def orden(db):
    proveedor = Proveedor.objects.create(nombre="Prov", cuit="20111222333")
    return OrdenCompra.objects.create(
        proveedor=proveedor,
        estado=EstadoOrdenCompra.objects.get(nombre="Aprobada"),
        fecha="2026-09-20T10:00:00-03:00",
        total="0.00",
    )


def agregar_renglon(orden, producto_id, cantidad):
    return OrdenCompraDetalle.objects.create(
        orden_compra=orden, producto_id=producto_id, cantidad=cantidad, precio_unitario="1.00"
    )


# --- registrar_movimiento ---------------------------------------------------


def test_devolucion_suma_stock(producto, usuario):
    services.registrar_movimiento(producto=producto, tipo="DEVOLUCION", cantidad=4, usuario=usuario)
    producto.refresh_from_db()
    assert producto.stock_actual == 24


def test_registrar_movimiento_guarda_usuario_y_observacion(producto, usuario):
    movimiento = services.registrar_movimiento(
        producto=producto,
        tipo="ENTRADA",
        cantidad=5,
        usuario=usuario,
        observacion="Ingreso manual",
    )
    movimiento.refresh_from_db()
    assert movimiento.usuario == usuario
    assert movimiento.producto == producto
    assert movimiento.tipo == "ENTRADA"
    assert movimiento.cantidad == 5
    assert movimiento.observacion == "Ingreso manual"


def test_ajuste_negativo_que_deja_stock_bajo_cero_se_rechaza(producto, usuario):
    with pytest.raises(ValidationError):
        services.registrar_movimiento(
            producto=producto, tipo="AJUSTE", cantidad=-21, usuario=usuario
        )
    producto.refresh_from_db()
    assert producto.stock_actual == 20


def test_ajuste_negativo_hasta_cero_se_permite(producto, usuario):
    services.registrar_movimiento(producto=producto, tipo="AJUSTE", cantidad=-20, usuario=usuario)
    producto.refresh_from_db()
    assert producto.stock_actual == 0


def test_movimiento_rechazado_no_deja_registro_ni_cambia_stock(producto, usuario):
    with pytest.raises(ValidationError):
        services.registrar_movimiento(
            producto=producto, tipo="SALIDA", cantidad=21, usuario=usuario
        )
    producto.refresh_from_db()
    assert producto.stock_actual == 20
    assert MovimientoInventario.objects.count() == 0


def test_tipo_desconocido_lanza_value_error_y_no_modifica_nada(producto, usuario):
    with pytest.raises(ValueError):
        services.registrar_movimiento(
            producto=producto, tipo="INVENTADO", cantidad=1, usuario=usuario
        )
    producto.refresh_from_db()
    assert producto.stock_actual == 20
    assert MovimientoInventario.objects.count() == 0


# --- registrar_recepcion_orden_compra ---------------------------------------


def test_recepcion_con_varios_renglones_genera_una_entrada_por_renglon(
    producto, rubro, usuario, orden
):
    otro = Producto.objects.create(
        codigo="ARE-001", nombre="Arena", precio="1", rubro=rubro, stock_actual=3
    )
    agregar_renglon(orden, producto.id, 10)
    agregar_renglon(orden, otro.id, 7)

    movimientos = services.registrar_recepcion_orden_compra(orden, usuario)

    assert len(movimientos) == 2
    assert {m.tipo for m in movimientos} == {"ENTRADA"}
    producto.refresh_from_db()
    otro.refresh_from_db()
    assert producto.stock_actual == 30
    assert otro.stock_actual == 10
    assert MovimientoInventario.objects.count() == 2
    assert all(str(orden.pk) in m.observacion for m in movimientos)


def test_recepcion_con_renglon_invalido_revierte_los_anteriores(producto, usuario, orden):
    agregar_renglon(orden, producto.id, 10)
    agregar_renglon(orden, 99999, 1)

    with pytest.raises(ValidationError):
        services.registrar_recepcion_orden_compra(orden, usuario)

    producto.refresh_from_db()
    assert producto.stock_actual == 20
    assert MovimientoInventario.objects.count() == 0
