from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from faker import Faker
from rest_framework.test import APIClient

from apps.ContabilidadFinanzas.models import (
    CierreMensual,
    Diario,
    FacturaCabecera,
    FacturaDetalle,
    Periodo,
)

fake = Faker()


@pytest.fixture
def api_client(db):
    user = get_user_model().objects.create_user(username="admin", password=fake.password())
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def factura(db):
    return FacturaCabecera.objects.create(
        tipo=FacturaCabecera.Tipo.VENTA,
        orden_venta_id=1,
        numero="A-0001",
        fecha="2026-01-10T10:00:00Z",
        impuestos=21,
    )


def crear_detalle(factura, **overrides):
    campos = {"producto_id": 5, "cantidad": 2, "precio_unitario": 100, "subtotal": 200}
    campos.update(overrides)
    return FacturaDetalle.objects.create(factura=factura, **campos)


def payload_detalle(factura, **overrides):
    payload = {
        "factura": factura.id,
        "producto_id": 5,
        "cantidad": 2,
        "precio_unitario": "100.00",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_listar_detalles_happy_path(api_client, factura):
    crear_detalle(factura)
    crear_detalle(factura, producto_id=6)

    response = api_client.get("/api/contabilidad/facturas-detalle/")

    assert response.status_code == 200
    assert response.data["count"] == 2


@pytest.mark.django_db
def test_listar_detalles_filtrando_por_factura(api_client, factura):
    crear_detalle(factura)
    otra_factura = FacturaCabecera.objects.create(
        tipo=FacturaCabecera.Tipo.COMPRA,
        orden_compra_id=1,
        numero="B-0001",
        fecha="2026-01-11T10:00:00Z",
    )
    crear_detalle(otra_factura, producto_id=9)

    response = api_client.get(f"/api/contabilidad/facturas-detalle/?factura={factura.id}")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["factura"] == factura.id


@pytest.mark.django_db
def test_obtener_detalle_por_id(api_client, factura):
    detalle = crear_detalle(factura)

    response = api_client.get(f"/api/contabilidad/facturas-detalle/{detalle.id}/")

    assert response.status_code == 200
    assert response.data["id"] == detalle.id
    assert response.data["factura"] == factura.id
    assert response.data["producto_id"] == 5
    assert response.data["cantidad"] == 2
    assert response.data["precio_unitario"] == "100.00"
    assert response.data["subtotal"] == "200.00"


@pytest.mark.django_db
def test_obtener_detalle_inexistente_da_404(api_client):
    response = api_client.get("/api/contabilidad/facturas-detalle/9999/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_listar_detalles_sin_autenticacion_falla():
    response = APIClient().get("/api/contabilidad/facturas-detalle/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_crear_detalle_happy_path(api_client, factura):
    response = api_client.post("/api/contabilidad/facturas-detalle/", payload_detalle(factura))

    assert response.status_code == 201
    detalle = FacturaDetalle.objects.get()
    assert response.data["id"] == detalle.id
    # El subtotal se calcula solo: 2 * 100.
    assert response.data["subtotal"] == "200.00"
    assert detalle.subtotal == 200


@pytest.mark.django_db
def test_crear_detalle_actualiza_totales_de_la_factura(api_client, factura):
    api_client.post("/api/contabilidad/facturas-detalle/", payload_detalle(factura))

    factura.refresh_from_db()
    assert factura.subtotal == 200
    # total = subtotal + impuestos (21).
    assert factura.total == 221


@pytest.mark.django_db
def test_crear_varios_detalles_acumula_totales_de_la_factura(api_client, factura):
    api_client.post("/api/contabilidad/facturas-detalle/", payload_detalle(factura))
    api_client.post(
        "/api/contabilidad/facturas-detalle/",
        payload_detalle(factura, producto_id=6, cantidad=3, precio_unitario="50.00"),
    )

    factura.refresh_from_db()
    # 2 * 100 + 3 * 50 = 350, más 21 de impuestos.
    assert factura.subtotal == 350
    assert factura.total == 371


@pytest.mark.django_db
def test_crear_detalle_aparece_en_la_cabecera(api_client, factura):
    api_client.post("/api/contabilidad/facturas-detalle/", payload_detalle(factura))

    response = api_client.get(f"/api/contabilidad/facturas/{factura.id}/")

    assert response.status_code == 200
    assert len(response.data["detalles"]) == 1
    assert response.data["total"] == "221.00"


@pytest.mark.django_db
def test_crear_detalle_con_cantidad_cero_falla(api_client, factura):
    response = api_client.post(
        "/api/contabilidad/facturas-detalle/", payload_detalle(factura, cantidad=0)
    )

    assert response.status_code == 400
    assert "cantidad" in response.data
    assert not FacturaDetalle.objects.exists()


@pytest.mark.django_db
def test_crear_detalle_sin_factura_falla(api_client, factura):
    payload = payload_detalle(factura)
    del payload["factura"]

    response = api_client.post("/api/contabilidad/facturas-detalle/", payload)

    assert response.status_code == 400
    assert "factura" in response.data
    assert not FacturaDetalle.objects.exists()


@pytest.mark.django_db
def test_crear_detalle_con_factura_inexistente_falla(api_client, factura):
    payload = payload_detalle(factura) | {"factura": 9999}

    response = api_client.post("/api/contabilidad/facturas-detalle/", payload)

    assert response.status_code == 400
    assert "factura" in response.data
    assert not FacturaDetalle.objects.exists()


@pytest.mark.django_db
def test_crear_detalle_sin_campos_obligatorios_falla(api_client):
    response = api_client.post("/api/contabilidad/facturas-detalle/", {})

    assert response.status_code == 400
    assert set(response.data) == {"factura", "producto_id", "cantidad", "precio_unitario"}


@pytest.mark.django_db
def test_crear_detalle_no_permite_fijar_subtotal(api_client, factura):
    response = api_client.post(
        "/api/contabilidad/facturas-detalle/", payload_detalle(factura, subtotal="9999.00")
    )

    assert response.status_code == 201
    # subtotal es de solo lectura: sale de cantidad * precio_unitario.
    assert response.data["subtotal"] == "200.00"


@pytest.mark.django_db
def test_crear_detalle_sin_autenticacion_falla(factura):
    response = APIClient().post("/api/contabilidad/facturas-detalle/", payload_detalle(factura))

    assert response.status_code == 401
    assert not FacturaDetalle.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
def test_modificar_o_borrar_detalle_no_permitido(api_client, factura, metodo):
    detalle = crear_detalle(factura)

    response = getattr(api_client, metodo)(f"/api/contabilidad/facturas-detalle/{detalle.id}/")

    assert response.status_code == 405


@pytest.mark.django_db
def test_agregar_detalle_a_factura_con_diario_de_periodo_cerrado_falla(api_client, factura):
    periodo = Periodo.objects.create(anio=2026, mes=1)
    cierre = periodo.cierres_mensuales.get()
    factura.diario = Diario.objects.create(cierre_mensual=cierre, fecha=factura.fecha)
    factura.save()
    periodo.cierres_mensuales.update(estado=CierreMensual.Estado.CERRADO)

    response = api_client.post("/api/contabilidad/facturas-detalle/", payload_detalle(factura))

    assert response.status_code == 400
    assert "factura" in response.data
    assert not FacturaDetalle.objects.exists()


@pytest.mark.django_db
def test_agregar_detalle_a_factura_sin_diario_respeta_el_cierre_de_su_periodo(
    api_client, factura
):
    # La factura es del 10/01/2026 y no tiene diario: se usa el cierre de su período.
    periodo = Periodo.objects.create(anio=2026, mes=1)
    periodo.cierres_mensuales.update(estado=CierreMensual.Estado.CERRADO)

    response = api_client.post("/api/contabilidad/facturas-detalle/", payload_detalle(factura))

    assert response.status_code == 400
    assert "factura" in response.data
    assert not FacturaDetalle.objects.exists()


@pytest.mark.django_db
def test_agregar_detalle_a_factura_de_periodo_abierto_sigue_funcionando(api_client, factura):
    Periodo.objects.create(anio=2026, mes=1)

    response = api_client.post("/api/contabilidad/facturas-detalle/", payload_detalle(factura))

    assert response.status_code == 201
    assert FacturaDetalle.objects.count() == 1


@pytest.mark.django_db
def test_crear_detalle_con_precio_negativo_falla(api_client, factura):
    response = api_client.post(
        "/api/contabilidad/facturas-detalle/", payload_detalle(factura, precio_unitario="-1.00")
    )

    assert response.status_code == 400
    assert "precio_unitario" in response.data
    assert not FacturaDetalle.objects.exists()


@pytest.mark.django_db
def test_crear_detalle_que_hace_exceder_el_maximo_de_la_factura_da_400(api_client, factura):
    factura.impuestos = 0
    factura.save()
    crear_detalle(factura, cantidad=1, precio_unitario=Decimal("9999999999.00"), subtotal=Decimal("9999999999.00"))
    factura.recalcular_totales()
    factura.save(update_fields=["subtotal", "total"])

    response = api_client.post(
        "/api/contabilidad/facturas-detalle/",
        payload_detalle(factura, cantidad=1, precio_unitario="5.00"),
    )

    assert response.status_code == 400
    assert "non_field_errors" in response.data
    assert FacturaDetalle.objects.count() == 1
