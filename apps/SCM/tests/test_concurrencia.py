import threading

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from rest_framework.exceptions import ValidationError

from apps.SCM import services
from apps.SCM.models import MovimientoInventario, Producto


def ejecutar_en_paralelo(funcion, cantidad_de_hilos):
    """Lanza `funcion` en N hilos que arrancan a la vez y devuelve sus resultados."""
    barrera = threading.Barrier(cantidad_de_hilos)
    resultados = []

    def trabajo():
        try:
            barrera.wait()
            resultados.append(funcion())
        except Exception as error:  # noqa: BLE001 - el test inspecciona cualquier fallo
            resultados.append(error)
        finally:
            connection.close()  # cada hilo abre su propia conexión

    hilos = [threading.Thread(target=trabajo) for _ in range(cantidad_de_hilos)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    return resultados


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_dos_salidas_simultaneas_no_dejan_el_stock_negativo(producto):
    """Con stock 20, dos salidas de 15 a la vez: solo una puede tener éxito."""
    usuario = get_user_model().objects.create_user(username="concurrente", password="x")

    resultados = ejecutar_en_paralelo(
        lambda: services.registrar_movimiento(
            producto=producto, tipo="SALIDA", cantidad=15, usuario=usuario
        ),
        cantidad_de_hilos=2,
    )

    exitos = [r for r in resultados if isinstance(r, MovimientoInventario)]
    rechazos = [r for r in resultados if isinstance(r, ValidationError)]
    assert len(exitos) == 1, resultados
    assert len(rechazos) == 1, resultados

    producto.refresh_from_db()
    assert producto.stock_actual == 5
    assert MovimientoInventario.objects.filter(producto=producto).count() == 1


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_entradas_simultaneas_no_pierden_actualizaciones(producto):
    """Cinco entradas de 1 a la vez deben sumar exactamente 5 (sin lost update)."""
    usuario = get_user_model().objects.create_user(username="concurrente2", password="x")

    resultados = ejecutar_en_paralelo(
        lambda: services.registrar_movimiento(
            producto=producto, tipo="ENTRADA", cantidad=1, usuario=usuario
        ),
        cantidad_de_hilos=5,
    )

    assert all(isinstance(r, MovimientoInventario) for r in resultados), resultados
    assert Producto.objects.get(pk=producto.pk).stock_actual == 25
    assert MovimientoInventario.objects.filter(producto=producto).count() == 5
