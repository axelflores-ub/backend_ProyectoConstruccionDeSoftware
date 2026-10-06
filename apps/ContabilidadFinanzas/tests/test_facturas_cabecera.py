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
def diario(db):
    periodo = Periodo.objects.create(anio=2026, mes=1)
    cierre_mensual = periodo.cierres_mensuales.get()
    return Diario.objects.create(cierre_mensual=cierre_mensual, fecha="2026-01-10T10:00:00Z")


@pytest.fixture
def factura_venta(db):
    factura = FacturaCabecera.objects.create(
        tipo=FacturaCabecera.Tipo.VENTA,
        orden_venta_id=1,
        numero="A-0001",
        fecha="2026-01-10T10:00:00Z",
        impuestos=21,
    )
    FacturaDetalle.objects.create(
        factura=factura, producto_id=5, cantidad=2, precio_unitario=100, subtotal=200
    )
    factura.recalcular_totales()
    factura.save(update_fields=["subtotal", "total"])
    return factura


def payload_venta(**overrides):
    payload = {
        "tipo": "VENTA",
        "orden_venta_id": 1,
        "numero": "A-0001",
        "fecha": "2026-01-10T10:00:00Z",
        "impuestos": "21.00",
        "detalles": [{"producto_id": 5, "cantidad": 2, "precio_unitario": "100.00"}],
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_listar_facturas_happy_path(api_client, factura_venta):
    FacturaCabecera.objects.create(
        tipo=FacturaCabecera.Tipo.COMPRA,
        orden_compra_id=1,
        numero="B-0001",
        fecha="2026-01-11T10:00:00Z",
    )

    response = api_client.get("/api/contabilidad/facturas/")

    assert response.status_code == 200
    assert response.data["count"] == 2


@pytest.mark.django_db
def test_obtener_factura_por_id_incluye_detalles(api_client, factura_venta):
    response = api_client.get(f"/api/contabilidad/facturas/{factura_venta.id}/")

    assert response.status_code == 200
    assert response.data["id"] == factura_venta.id
    assert response.data["numero"] == "A-0001"
    assert response.data["subtotal"] == "200.00"
    assert response.data["total"] == "221.00"
    assert len(response.data["detalles"]) == 1
    assert response.data["detalles"][0]["subtotal"] == "200.00"


@pytest.mark.django_db
def test_obtener_factura_inexistente_da_404(api_client):
    response = api_client.get("/api/contabilidad/facturas/9999/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_listar_facturas_sin_autenticacion_falla():
    response = APIClient().get("/api/contabilidad/facturas/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_crear_factura_venta_happy_path(api_client):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta())

    assert response.status_code == 201
    factura = FacturaCabecera.objects.get()
    assert response.data["id"] == factura.id
    # El subtotal sale de los detalles y el total suma los impuestos: 2 * 100 + 21.
    assert response.data["subtotal"] == "200.00"
    assert response.data["total"] == "221.00"
    assert factura.detalles.count() == 1
    assert factura.detalles.get().subtotal == 200


@pytest.mark.django_db
def test_crear_factura_compra_happy_path(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(tipo="COMPRA", orden_venta_id=None, orden_compra_id=1, numero="B-0001"),
    )

    assert response.status_code == 201
    factura = FacturaCabecera.objects.get()
    assert (factura.tipo, factura.orden_compra_id) == ("COMPRA", 1)


@pytest.mark.django_db
def test_crear_factura_con_diario(api_client, diario):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta(diario=diario.id))

    assert response.status_code == 201
    assert FacturaCabecera.objects.get().diario_id == diario.id


@pytest.mark.django_db
def test_crear_factura_con_varios_detalles_suma_subtotales(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(
            detalles=[
                {"producto_id": 5, "cantidad": 2, "precio_unitario": "100.00"},
                {"producto_id": 6, "cantidad": 3, "precio_unitario": "50.00"},
            ]
        ),
    )

    assert response.status_code == 201
    # 2 * 100 + 3 * 50 = 350, más 21 de impuestos.
    assert response.data["subtotal"] == "350.00"
    assert response.data["total"] == "371.00"


@pytest.mark.django_db
def test_crear_factura_venta_sin_orden_venta_falla(api_client):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta(orden_venta_id=None))

    assert response.status_code == 400
    assert "orden_venta_id" in response.data
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
def test_crear_factura_compra_sin_orden_compra_falla(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(tipo="COMPRA", orden_venta_id=None, numero="B-0001"),
    )

    assert response.status_code == 400
    assert "orden_compra_id" in response.data
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
def test_crear_factura_sin_detalles_falla(api_client):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta(detalles=[]))

    assert response.status_code == 400
    assert "detalles" in response.data
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
def test_crear_factura_con_cantidad_cero_falla(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(detalles=[{"producto_id": 5, "cantidad": 0, "precio_unitario": "100.00"}]),
    )

    assert response.status_code == 400
    assert "detalles" in response.data
    assert not FacturaCabecera.objects.exists()
    assert not FacturaDetalle.objects.exists()


@pytest.mark.django_db
def test_crear_factura_duplicada_falla(api_client, factura_venta):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta())

    assert response.status_code == 400
    assert FacturaCabecera.objects.count() == 1


@pytest.mark.django_db
def test_crear_factura_sin_campos_obligatorios_falla(api_client):
    response = api_client.post("/api/contabilidad/facturas/", {})

    assert response.status_code == 400
    assert set(response.data) == {"tipo", "numero", "fecha", "detalles"}


@pytest.mark.django_db
def test_crear_factura_con_tipo_invalido_falla(api_client):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta(tipo="OTRO"))

    assert response.status_code == 400
    assert "tipo" in response.data
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
def test_crear_factura_no_permite_fijar_totales(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/", payload_venta(subtotal="9999.00", total="9999.00")
    )

    assert response.status_code == 201
    # subtotal y total son de solo lectura: se recalculan a partir de los detalles.
    assert response.data["subtotal"] == "200.00"
    assert response.data["total"] == "221.00"


@pytest.mark.django_db
def test_crear_factura_sin_autenticacion_falla():
    response = APIClient().post("/api/contabilidad/facturas/", payload_venta())

    assert response.status_code == 401
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
def test_modificar_o_borrar_factura_no_permitido(api_client, factura_venta, metodo):
    response = getattr(api_client, metodo)(f"/api/contabilidad/facturas/{factura_venta.id}/")

    assert response.status_code == 405


@pytest.mark.django_db
def test_crear_factura_venta_genera_entrada_en_el_diario(api_client):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta())

    assert response.status_code == 201
    factura = FacturaCabecera.objects.get()
    diario = Diario.objects.get()
    assert factura.diario_id == diario.id
    assert response.data["diario"] == diario.id
    assert diario.descripcion == "Factura de venta A-0001 (orden de venta #1)"
    assert diario.fecha == factura.fecha
    periodo = diario.cierre_mensual.periodo
    assert (periodo.anio, periodo.mes) == (2026, 1)


@pytest.mark.django_db
def test_crear_factura_compra_describe_la_orden_de_compra(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(tipo="COMPRA", orden_venta_id=None, orden_compra_id=7, numero="B-0001"),
    )

    assert response.status_code == 201
    assert Diario.objects.get().descripcion == "Factura de compra B-0001 (orden de compra #7)"


@pytest.mark.django_db
def test_crear_factura_usa_el_cierre_del_periodo_existente(api_client):
    periodo = Periodo.objects.create(anio=2026, mes=1)
    cierre = periodo.cierres_mensuales.get()

    response = api_client.post("/api/contabilidad/facturas/", payload_venta())

    assert response.status_code == 201
    assert Periodo.objects.count() == 1
    assert Diario.objects.get().cierre_mensual_id == cierre.id


@pytest.mark.django_db
def test_crear_factura_crea_el_periodo_si_no_existe(api_client):
    assert not Periodo.objects.exists()

    response = api_client.post("/api/contabilidad/facturas/", payload_venta())

    assert response.status_code == 201
    periodo = Periodo.objects.get()
    assert (periodo.anio, periodo.mes) == (2026, 1)
    assert periodo.cierres_mensuales.get().estado == CierreMensual.Estado.ABIERTO


@pytest.mark.django_db
def test_crear_factura_usa_el_mes_en_hora_local(api_client):
    # 01:00 UTC del 1 de febrero son las 22:00 del 31 de enero en Argentina (UTC-3).
    response = api_client.post(
        "/api/contabilidad/facturas/", payload_venta(fecha="2026-02-01T01:00:00Z")
    )

    assert response.status_code == 201
    periodo = Diario.objects.get().cierre_mensual.periodo
    assert (periodo.anio, periodo.mes) == (2026, 1)


@pytest.mark.django_db
def test_crear_factura_en_periodo_cerrado_falla(api_client):
    periodo = Periodo.objects.create(anio=2026, mes=1)
    periodo.cierres_mensuales.update(estado=CierreMensual.Estado.CERRADO)

    response = api_client.post("/api/contabilidad/facturas/", payload_venta())

    assert response.status_code == 400
    assert "fecha" in response.data
    assert not FacturaCabecera.objects.exists()
    assert not Diario.objects.exists()


@pytest.mark.django_db
def test_cada_factura_genera_su_propia_entrada(api_client):
    api_client.post("/api/contabilidad/facturas/", payload_venta())
    api_client.post("/api/contabilidad/facturas/", payload_venta(numero="A-0002"))

    assert Diario.objects.count() == 2
    assert len({factura.diario_id for factura in FacturaCabecera.objects.all()}) == 2


@pytest.mark.django_db
def test_factura_con_diario_explicito_no_genera_otra_entrada(api_client, diario):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta(diario=diario.id))

    assert response.status_code == 201
    assert Diario.objects.count() == 1
    assert FacturaCabecera.objects.get().diario_id == diario.id


@pytest.mark.django_db
def test_crear_factura_con_diario_de_cierre_cerrado_falla(api_client, diario):
    CierreMensual.objects.filter(pk=diario.cierre_mensual_id).update(
        estado=CierreMensual.Estado.CERRADO
    )

    response = api_client.post("/api/contabilidad/facturas/", payload_venta(diario=diario.id))

    assert response.status_code == 400
    assert "diario" in response.data
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
def test_crear_factura_con_diario_de_cierre_abierto_sigue_funcionando(api_client, diario):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta(diario=diario.id))

    assert response.status_code == 201


@pytest.mark.django_db
def test_la_entrada_de_la_factura_se_ve_en_el_endpoint_de_diarios(api_client):
    api_client.post("/api/contabilidad/facturas/", payload_venta())

    response = api_client.get("/api/contabilidad/diarios/")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["descripcion"] == (
        "Factura de venta A-0001 (orden de venta #1)"
    )


@pytest.mark.django_db
def test_crear_factura_con_precio_negativo_falla(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(detalles=[{"producto_id": 5, "cantidad": 1, "precio_unitario": "-10.00"}]),
    )

    assert response.status_code == 400
    assert "detalles" in response.data
    assert not FacturaCabecera.objects.exists()
    assert not Diario.objects.exists()


@pytest.mark.django_db
def test_crear_factura_con_precio_cero_se_acepta(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(detalles=[{"producto_id": 5, "cantidad": 1, "precio_unitario": "0.00"}]),
    )

    assert response.status_code == 201
    assert response.data["subtotal"] == "0.00"


@pytest.mark.django_db
def test_crear_factura_con_impuestos_negativos_falla(api_client):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta(impuestos="-5.00"))

    assert response.status_code == 400
    assert "impuestos" in response.data
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
def test_crear_factura_con_importe_desmedido_da_400_y_no_error_500(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(
            detalles=[{"producto_id": 5, "cantidad": 2000000000, "precio_unitario": "9999999999.99"}]
        ),
    )

    assert response.status_code == 400
    assert "detalles" in response.data
    assert not FacturaCabecera.objects.exists()
    assert not Diario.objects.exists()


@pytest.mark.django_db
def test_crear_factura_con_renglones_que_suman_de_mas_falla(api_client):
    # Cada renglón entra por separado, pero juntos superan el máximo.
    renglon = {"producto_id": 5, "cantidad": 1, "precio_unitario": "9999999999.99"}

    response = api_client.post(
        "/api/contabilidad/facturas/", payload_venta(detalles=[renglon, renglon])
    )

    assert response.status_code == 400
    assert "detalles" in response.data
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
def test_crear_factura_cuyo_total_con_impuestos_excede_el_maximo_falla(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(
            impuestos="5.00",
            detalles=[{"producto_id": 5, "cantidad": 1, "precio_unitario": "9999999999.00"}],
        ),
    )

    assert response.status_code == 400
    assert "detalles" in response.data
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
def test_crear_factura_con_el_importe_maximo_se_acepta(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(
            impuestos="0",
            detalles=[{"producto_id": 5, "cantidad": 1, "precio_unitario": "9999999999.99"}],
        ),
    )

    assert response.status_code == 201
    assert response.data["total"] == "9999999999.99"


@pytest.mark.django_db
def test_crear_factura_de_venta_con_orden_de_compra_falla(api_client):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta(orden_compra_id=3))

    assert response.status_code == 400
    assert "orden_compra_id" in response.data
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
def test_crear_factura_de_compra_con_orden_de_venta_falla(api_client):
    response = api_client.post(
        "/api/contabilidad/facturas/",
        payload_venta(tipo="COMPRA", orden_compra_id=1, numero="B-0001"),
    )

    assert response.status_code == 400
    assert "orden_venta_id" in response.data
    assert not FacturaCabecera.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("fecha", ["1900-01-01T12:00:00Z", "2101-06-01T12:00:00Z"])
def test_crear_factura_con_anio_fuera_de_rango_falla(api_client, fecha):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta(fecha=fecha))

    assert response.status_code == 400
    assert "fecha" in response.data
    assert not FacturaCabecera.objects.exists()
    assert not Periodo.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("fecha", ["2000-01-01T12:00:00Z", "2100-12-31T12:00:00Z"])
def test_crear_factura_con_anio_limite_se_acepta(api_client, fecha):
    response = api_client.post("/api/contabilidad/facturas/", payload_venta(fecha=fecha))

    assert response.status_code == 201
