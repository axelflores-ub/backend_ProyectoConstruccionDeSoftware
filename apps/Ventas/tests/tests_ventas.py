"""Tests del módulo Ventas (clientes, precios, órdenes, anulaciones y notas de crédito).

Precio de venta = precio de compra del proveedor + 30 %. Los productos de prueba se crean
con un proveedor y un precio de compra de 1000, por lo que se venden a 1300.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.CompraYProveedores.models import Proveedor, ProveedorProducto
from apps.SCM.models import MovimientoInventario, Producto

from .. import services
from ..models import (
    Anulacion,
    Cliente,
    EstadoOrdenVenta,
    NotaCredito,
    OrdenVenta,
    OrdenVentaDetalle,
)

URL_CLIENTES = "/api/ventas/clientes/"
URL_ORDENES = "/api/ventas/ordenes-venta/"
URL_ANULACIONES = "/api/ventas/anulaciones/"
URL_NOTAS = "/api/ventas/notas-credito/"
URL_PRODUCTOS_VENTA = "/api/ventas/productos-venta/"
URL_ESTADOS = "/api/ventas/estados-orden-venta/"

CUIL_CLIENTE = "20111111112"


def items(response):
    """Lista de resultados, con o sin paginación."""
    data = response.data
    return data["results"] if isinstance(data, dict) and "results" in data else data


class BaseVentasTest(APITestCase):
    """Datos comunes: usuario autenticado, cliente, proveedor y dos productos con precio."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="usuario_test", password="123456")
        self.client.force_authenticate(user=self.usuario)

        self.cliente = Cliente.objects.create(
            nombre="Cliente Test",
            cuil=CUIL_CLIENTE,
            condicion_iva=Cliente.CondicionIva.CONSUMIDOR_FINAL,
            estado=Cliente.ESTADO_ACTIVO,
        )
        self.proveedor = Proveedor.objects.create(nombre="Proveedor Test", cuit="20999999999")

        # Precio de compra 1000 -> precio de venta 1300.00
        self.producto = self.crear_producto("P-001", "Arena", stock=100, precio_compra="1000")
        # Precio de compra 500 -> precio de venta 650.00
        self.producto2 = self.crear_producto("P-002", "Cemento", stock=50, precio_compra="500")

    # ---- ayudas ----
    def crear_producto(self, codigo, nombre, stock, precio_compra=None, precio_historico="0"):
        producto = Producto.objects.create(
            codigo=codigo, nombre=nombre, stock_actual=stock, precio=Decimal(precio_historico)
        )
        if precio_compra is not None:
            ProveedorProducto.objects.create(
                proveedor=self.proveedor, producto=producto, precio_compra=Decimal(precio_compra)
            )
        return producto

    def estado(self, nombre):
        return EstadoOrdenVenta.objects.get_or_create(nombre=nombre)[0]

    def crear_orden(self, cantidad=2, producto=None, descuento=None, cuil=CUIL_CLIENTE):
        """Genera una orden con el servicio (igual que el endpoint)."""
        detalle = {"producto": producto or self.producto, "cantidad": cantidad}
        if descuento is not None:
            detalle["descuento"] = Decimal(descuento)
        return services.registrar_orden_venta(
            cuil=cuil,
            datos={"forma_pago": "EFECTIVO"},
            detalles=[detalle],
            usuario=self.usuario,
        )

    def stock(self, producto):
        producto.refresh_from_db()
        return producto.stock_actual

    def orden_body(self, cantidad=2, producto=None, **extra):
        body = {
            "cuil": CUIL_CLIENTE,
            "forma_pago": "EFECTIVO",
            "detalles": [{"producto": (producto or self.producto).id, "cantidad": cantidad}],
        }
        body.update(extra)
        return body


# ---------------------------------------------------------------- CLIENTES
class ClienteTests(BaseVentasTest):
    def test_listar_clientes(self):
        response = self.client.get(URL_CLIENTES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(items(response)), 1)
        self.assertEqual(items(response)[0]["nombre"], "Cliente Test")

    def test_obtener_cliente(self):
        response = self.client.get(f"{URL_CLIENTES}{self.cliente.id_cliente}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cuil"], CUIL_CLIENTE)

    def test_cliente_inexistente(self):
        response = self.client.get(f"{URL_CLIENTES}999999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["codigo"], "no_encontrado")

    def test_crear_cliente_normaliza_el_cuil(self):
        response = self.client.post(
            URL_CLIENTES,
            {"nombre": "Nuevo", "cuil": "20-11111111-1", "condicion_iva": "Monotributista"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["cuil"], "20111111111")
        self.assertEqual(response.data["estado"], Cliente.ESTADO_ACTIVO)

    def test_crear_cliente_siempre_queda_activo(self):
        response = self.client.post(
            URL_CLIENTES,
            {"nombre": "Nuevo", "cuil": "20111111111", "condicion_iva": "Exento", "estado": "OF"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["estado"], Cliente.ESTADO_ACTIVO)

    def test_crear_cliente_con_cuil_duplicado(self):
        response = self.client.post(
            URL_CLIENTES,
            {"nombre": "Repetido", "cuil": "20-11111111-2", "condicion_iva": "Exento"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "cuil_duplicado")
        self.assertEqual(Cliente.objects.count(), 1)

    def test_crear_cliente_con_cuil_invalido(self):
        response = self.client.post(
            URL_CLIENTES,
            {"nombre": "Corto", "cuil": "2011111", "condicion_iva": "Exento"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cuil", response.data["errores"])

    def test_condicion_iva_invalida_se_rechaza(self):
        response = self.client.post(
            URL_CLIENTES,
            {"nombre": "X", "cuil": "20222222223", "condicion_iva": "ABC"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("condicion_iva", response.data["errores"])
        self.assertFalse(Cliente.objects.filter(cuil="20222222223").exists())

    def test_condiciones_de_iva_validas(self):
        validas = ["Responsable Inscripto", "Monotributista", "Consumidor Final", "Exento"]
        for i, condicion in enumerate(validas):
            response = self.client.post(
                URL_CLIENTES,
                {"nombre": f"C{i}", "cuil": f"2033333333{i}", "condicion_iva": condicion},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, condicion)

    def test_crear_cliente_sin_condicion_iva(self):
        response = self.client.post(
            URL_CLIENTES, {"nombre": "X", "cuil": "20444444445"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("condicion_iva", response.data["errores"])

    def test_crear_cliente_sin_nombre(self):
        response = self.client.post(
            URL_CLIENTES,
            {"cuil": "20555555556", "condicion_iva": "Exento"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nombre", response.data["errores"])

    def test_modificar_cliente(self):
        response = self.client.put(
            f"{URL_CLIENTES}{self.cliente.id_cliente}/",
            {
                "nombre": "Cliente Modificado",
                "cuil": CUIL_CLIENTE,
                "condicion_iva": "Responsable Inscripto",
                "estado": "AC",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.nombre, "Cliente Modificado")
        self.assertEqual(self.cliente.condicion_iva, "Responsable Inscripto")

    def test_modificar_cliente_con_cuil_de_otro(self):
        otro = Cliente.objects.create(nombre="Otro", cuil="20666666667", condicion_iva="Exento")
        response = self.client.put(
            f"{URL_CLIENTES}{otro.id_cliente}/",
            {"nombre": "Otro", "cuil": CUIL_CLIENTE, "condicion_iva": "Exento"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_baja_logica_con_patch(self):
        response = self.client.patch(
            f"{URL_CLIENTES}{self.cliente.id_cliente}/", {"estado": "OF"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.estado, Cliente.ESTADO_BAJA)

    def test_delete_de_cliente_no_esta_permitido(self):
        response = self.client.delete(f"{URL_CLIENTES}{self.cliente.id_cliente}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Cliente.objects.filter(pk=self.cliente.pk).exists())

    def test_buscar_por_cuil_con_guiones(self):
        Cliente.objects.create(nombre="Otro", cuil="20666666667", condicion_iva="Exento")
        response = self.client.get(URL_CLIENTES, {"cuil": "20-11111111-2"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([c["cuil"] for c in items(response)], [CUIL_CLIENTE])

    def test_buscar_por_cuil_invalido(self):
        response = self.client.get(URL_CLIENTES, {"cuil": "123"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sin_autenticacion(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(URL_CLIENTES)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


# ---------------------------------------------------------------- PRECIOS
class PrecioDeVentaTests(BaseVentasTest):
    def precio(self, codigo):
        response = self.client.get(URL_PRODUCTOS_VENTA)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fila = next(p for p in items(response) if p["codigo"] == codigo)
        valor = fila["precio_venta"]
        return None if valor is None else str(valor)

    def test_calculo_del_margen(self):
        self.assertEqual(services.calcular_precio_venta(Decimal("100")), Decimal("130.00"))
        self.assertEqual(services.calcular_precio_venta(Decimal("99.99")), Decimal("129.99"))

    def test_precio_es_precio_de_compra_mas_30(self):
        self.assertEqual(self.precio("P-001"), "1300.00")
        self.assertEqual(self.precio("P-002"), "650.00")

    def test_con_varios_proveedores_se_usa_el_precio_de_compra_mas_alto(self):
        otro = Proveedor.objects.create(nombre="Otro Proveedor", cuit="20888888888")
        ProveedorProducto.objects.create(proveedor=otro, producto=self.producto, precio_compra=Decimal("1200"))
        self.assertEqual(self.precio("P-001"), "1560.00")

    def test_vinculo_de_baja_no_cuenta(self):
        nuevo = self.crear_producto("P-003", "Ladrillo", stock=10)
        ProveedorProducto.objects.create(
            proveedor=self.proveedor, producto=nuevo, precio_compra=Decimal("100"), activo=0
        )
        self.assertIsNone(self.precio("P-003"))

    def test_producto_sin_proveedor_no_tiene_precio(self):
        self.crear_producto("P-004", "Sin proveedor", stock=10)
        self.assertIsNone(self.precio("P-004"))

    def test_producto_con_precio_de_compra_vacio_no_tiene_precio(self):
        nuevo = self.crear_producto("P-005", "Sin precio de compra", stock=10)
        ProveedorProducto.objects.create(proveedor=self.proveedor, producto=nuevo, precio_compra=None)
        self.assertIsNone(self.precio("P-005"))

    def test_producto_anterior_conserva_su_precio(self):
        self.crear_producto("P-006", "Producto viejo", stock=10, precio_historico="450.00")
        self.assertEqual(self.precio("P-006"), "450.00")

    def test_el_precio_de_compra_manda_sobre_el_historico(self):
        self.crear_producto("P-007", "Mixto", stock=10, precio_compra="1000", precio_historico="450.00")
        self.assertEqual(self.precio("P-007"), "1300.00")


# ---------------------------------------------------------------- ORDENES
class OrdenVentaTests(BaseVentasTest):
    def test_crear_orden(self):
        response = self.client.post(URL_ORDENES, self.orden_body(cantidad=2), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        orden = OrdenVenta.objects.get(pk=response.data["id"])
        self.assertEqual(orden.cliente, self.cliente)
        self.assertEqual(orden.usuario, self.usuario)
        self.assertEqual(orden.estado.nombre, EstadoOrdenVenta.PENDIENTE)
        self.assertEqual(orden.total, Decimal("2600.00"))

        detalle = OrdenVentaDetalle.objects.get(orden_venta=orden)
        self.assertEqual(detalle.cantidad, 2)
        self.assertEqual(detalle.precio_unitario, Decimal("1300.00"))
        self.assertEqual(detalle.subtotal, Decimal("2600.00"))

    def test_crear_orden_descuenta_stock_y_registra_movimiento(self):
        response = self.client.post(URL_ORDENES, self.orden_body(cantidad=2), format="json")
        self.assertEqual(self.stock(self.producto), 98)

        movimiento = MovimientoInventario.objects.get(producto=self.producto)
        self.assertEqual(movimiento.tipo, MovimientoInventario.Tipo.SALIDA)
        self.assertEqual(movimiento.cantidad, 2)
        self.assertEqual(movimiento.observacion, f"Venta - orden #{response.data['id']}")

    def test_crear_orden_con_cuil_con_guiones(self):
        response = self.client.post(URL_ORDENES, self.orden_body(cuil="20-11111111-2"), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_crear_orden_con_varios_productos(self):
        body = self.orden_body()
        body["detalles"] = [
            {"producto": self.producto.id, "cantidad": 2},
            {"producto": self.producto2.id, "cantidad": 3},
        ]
        response = self.client.post(URL_ORDENES, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # 2 x 1300 + 3 x 650 = 4550
        self.assertEqual(OrdenVenta.objects.get().total, Decimal("4550.00"))
        self.assertEqual(self.stock(self.producto), 98)
        self.assertEqual(self.stock(self.producto2), 47)

    def test_crear_orden_con_descuento(self):
        body = self.orden_body()
        body["detalles"][0]["descuento"] = "100.00"
        response = self.client.post(URL_ORDENES, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrdenVenta.objects.get().total, Decimal("2500.00"))

    def test_descuento_mayor_al_subtotal_se_rechaza(self):
        body = self.orden_body(cantidad=2)  # subtotal 2 x 1300 = 2600
        body["detalles"][0]["descuento"] = "2600.01"
        response = self.client.post(URL_ORDENES, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["codigo"], "descuento_supera_subtotal")
        self.assertIn("detalles", response.data["errores"])
        self.assertFalse(OrdenVenta.objects.exists())
        self.assertEqual(self.stock(self.producto), 100)

    def test_descuento_igual_al_subtotal_es_valido(self):
        body = self.orden_body(cantidad=2)
        body["detalles"][0]["descuento"] = "2600.00"
        response = self.client.post(URL_ORDENES, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrdenVenta.objects.get().total, Decimal("0.00"))

    def test_el_total_nunca_es_negativo(self):
        body = self.orden_body()
        body["detalles"] = [
            {"producto": self.producto.id, "cantidad": 1, "descuento": "1300.00"},
            {"producto": self.producto2.id, "cantidad": 1, "descuento": "9999.00"},
        ]
        response = self.client.post(URL_ORDENES, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(OrdenVenta.objects.exists())

    def test_crear_orden_con_comprobante(self):
        response = self.client.post(
            URL_ORDENES,
            self.orden_body(numero_comprobante="B-0002145", tipo_comprobante="FACTURA_B", forma_pago="CREDITO"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["numero_comprobante"], "B-0002145")
        self.assertEqual(response.data["tipo_comprobante"], "FACTURA_B")
        self.assertEqual(response.data["forma_pago"], "CREDITO")

    def test_el_precio_enviado_por_el_cliente_se_ignora(self):
        body = self.orden_body()
        body["detalles"][0]["precio_unitario"] = "1.00"
        body["total"] = "1.00"
        response = self.client.post(URL_ORDENES, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        orden = OrdenVenta.objects.get()
        self.assertEqual(orden.total, Decimal("2600.00"))
        self.assertEqual(orden.detalles.get().precio_unitario, Decimal("1300.00"))

    def test_la_orden_conserva_el_precio_si_cambia_el_precio_de_compra(self):
        orden = self.crear_orden(cantidad=1)
        ProveedorProducto.objects.filter(producto=self.producto).update(precio_compra=Decimal("2000"))
        self.assertEqual(orden.detalles.get().precio_unitario, Decimal("1300.00"))

    def test_orden_sin_productos(self):
        response = self.client.post(URL_ORDENES, self.orden_body(detalles=[]), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(OrdenVenta.objects.exists())

    def test_cantidad_menor_a_uno(self):
        response = self.client.post(URL_ORDENES, self.orden_body(cantidad=0), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_descuento_negativo(self):
        body = self.orden_body()
        body["detalles"][0]["descuento"] = "-5.00"
        response = self.client.post(URL_ORDENES, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_orden_con_producto_inexistente(self):
        body = self.orden_body()
        body["detalles"][0]["producto"] = 999999
        response = self.client.post(URL_ORDENES, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_orden_sin_stock_suficiente(self):
        response = self.client.post(URL_ORDENES, self.orden_body(cantidad=101), format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "stock_insuficiente")
        self.assertIn("disponible: 100", response.data["mensaje"])
        self.assertEqual(self.stock(self.producto), 100)
        self.assertFalse(OrdenVenta.objects.exists())

    def test_se_puede_vender_todo_el_stock(self):
        response = self.client.post(URL_ORDENES, self.orden_body(cantidad=100), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.stock(self.producto), 0)

    def test_producto_repetido_suma_las_cantidades_para_el_stock(self):
        body = self.orden_body()
        body["detalles"] = [
            {"producto": self.producto.id, "cantidad": 60},
            {"producto": self.producto.id, "cantidad": 60},
        ]
        response = self.client.post(URL_ORDENES, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "stock_insuficiente")

    def test_producto_sin_precio_no_se_puede_vender(self):
        sin_precio = self.crear_producto("P-100", "Producto nuevo", stock=10)
        response = self.client.post(URL_ORDENES, self.orden_body(producto=sin_precio), format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "producto_sin_precio")
        self.assertFalse(OrdenVenta.objects.exists())
        self.assertEqual(self.stock(sin_precio), 10)

    def test_producto_anterior_se_vende_a_su_precio_historico(self):
        viejo = self.crear_producto("P-101", "Producto viejo", stock=10, precio_historico="450.00")
        response = self.client.post(URL_ORDENES, self.orden_body(cantidad=2, producto=viejo), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrdenVenta.objects.get().total, Decimal("900.00"))

    def test_un_producto_sin_precio_en_la_orden_la_rechaza_completa(self):
        sin_precio = self.crear_producto("P-102", "Producto nuevo", stock=10)
        body = self.orden_body()
        body["detalles"].append({"producto": sin_precio.id, "cantidad": 1})
        response = self.client.post(URL_ORDENES, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(self.stock(self.producto), 100)

    def test_cliente_inexistente(self):
        response = self.client.post(URL_ORDENES, self.orden_body(cuil="20999999990"), format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["codigo"], "cliente_no_encontrado")

    def test_cliente_de_baja(self):
        self.cliente.estado = Cliente.ESTADO_BAJA
        self.cliente.save()
        response = self.client.post(URL_ORDENES, self.orden_body(), format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "cliente_de_baja")

    def test_comprobante_duplicado(self):
        self.client.post(URL_ORDENES, self.orden_body(numero_comprobante="B-0001"), format="json")
        response = self.client.post(URL_ORDENES, self.orden_body(numero_comprobante="B-0001"), format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "comprobante_duplicado")
        self.assertEqual(OrdenVenta.objects.count(), 1)

    def test_forma_de_pago_invalida(self):
        response = self.client.post(URL_ORDENES, self.orden_body(forma_pago="CHEQUE"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_consultar_orden_con_sus_items(self):
        orden = self.crear_orden(cantidad=2)
        response = self.client.get(f"{URL_ORDENES}{orden.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cliente_cuil"], CUIL_CLIENTE)
        self.assertEqual(response.data["estado_nombre"], EstadoOrdenVenta.PENDIENTE)
        self.assertEqual(len(response.data["detalles"]), 1)
        self.assertEqual(response.data["detalles"][0]["producto_nombre"], "Arena")

    def test_modificar_orden_pendiente(self):
        orden = self.crear_orden()
        response = self.client.patch(
            f"{URL_ORDENES}{orden.id}/",
            {"forma_pago": "TRANSFERENCIA", "numero_comprobante": "A-0001", "tipo_comprobante": "FACTURA_A"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        orden.refresh_from_db()
        self.assertEqual(orden.forma_pago, "TRANSFERENCIA")
        self.assertEqual(orden.numero_comprobante, "A-0001")
        self.assertEqual(orden.total, Decimal("2600.00"))

    def test_modificar_orden_no_modifica_cliente_ni_total(self):
        orden = self.crear_orden()
        otro = Cliente.objects.create(nombre="Otro", cuil="20666666667", condicion_iva="Exento")
        self.client.patch(
            f"{URL_ORDENES}{orden.id}/", {"cliente": otro.id_cliente, "total": "1.00"}, format="json"
        )
        orden.refresh_from_db()
        self.assertEqual(orden.cliente, self.cliente)
        self.assertEqual(orden.total, Decimal("2600.00"))

    def test_modificar_orden_que_no_esta_pendiente(self):
        orden = self.crear_orden()
        services.anular_orden_venta(orden_venta=orden, motivo="x", usuario=self.usuario)
        response = self.client.patch(f"{URL_ORDENES}{orden.id}/", {"forma_pago": "DEBITO"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "orden_no_modificable")

    def test_modificar_con_comprobante_de_otra_orden(self):
        self.client.post(URL_ORDENES, self.orden_body(numero_comprobante="B-0001"), format="json")
        orden = self.crear_orden()
        response = self.client.patch(
            f"{URL_ORDENES}{orden.id}/", {"numero_comprobante": "B-0001"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_las_ordenes_no_se_pueden_borrar(self):
        orden = self.crear_orden()
        response = self.client.delete(f"{URL_ORDENES}{orden.id}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_los_estados_son_de_solo_lectura(self):
        self.assertEqual(self.client.get(URL_ESTADOS).status_code, status.HTTP_200_OK)
        response = self.client.post(URL_ESTADOS, {"nombre": "Inventado"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# ---------------------------------------------------------------- ANULACIONES
class AnulacionTests(BaseVentasTest):
    def test_anular_orden(self):
        orden = self.crear_orden()
        response = self.client.post(
            URL_ANULACIONES,
            {"orden_venta": orden.id, "motivo": "Cliente se arrepintió", "detalle": "Por WhatsApp"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        orden.refresh_from_db()
        self.assertEqual(orden.estado.nombre, EstadoOrdenVenta.ANULADA)
        self.assertEqual(Anulacion.objects.get().motivo, "Cliente se arrepintió")

    def test_anular_repone_el_stock(self):
        orden = self.crear_orden(cantidad=2)  # stock 98
        self.assertEqual(self.stock(self.producto), 98)
        response = self.client.post(URL_ANULACIONES, {"orden_venta": orden.id, "motivo": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.stock(self.producto), 100)

    def test_anular_registra_un_movimiento_de_inventario(self):
        orden = self.crear_orden(cantidad=2)
        self.client.post(URL_ANULACIONES, {"orden_venta": orden.id, "motivo": "x"}, format="json")
        movimiento = MovimientoInventario.objects.get(observacion=f"Anulación - orden #{orden.id}")
        self.assertEqual(movimiento.tipo, MovimientoInventario.Tipo.DEVOLUCION)
        self.assertEqual(movimiento.cantidad, 2)
        self.assertEqual(movimiento.producto, self.producto)
        self.assertEqual(movimiento.usuario, self.usuario)

    def test_anular_repone_todos_los_productos_de_la_orden(self):
        orden = services.registrar_orden_venta(
            cuil=CUIL_CLIENTE,
            datos={"forma_pago": "EFECTIVO"},
            detalles=[
                {"producto": self.producto, "cantidad": 2},
                {"producto": self.producto2, "cantidad": 3},
                {"producto": self.producto, "cantidad": 1},  # mismo producto repetido
            ],
            usuario=self.usuario,
        )
        self.assertEqual((self.stock(self.producto), self.stock(self.producto2)), (97, 47))
        self.client.post(URL_ANULACIONES, {"orden_venta": orden.id, "motivo": "x"}, format="json")
        self.assertEqual((self.stock(self.producto), self.stock(self.producto2)), (100, 50))

    def test_anular_dos_veces_no_repone_dos_veces(self):
        orden = self.crear_orden(cantidad=2)
        self.client.post(URL_ANULACIONES, {"orden_venta": orden.id, "motivo": "1"}, format="json")
        self.client.post(URL_ANULACIONES, {"orden_venta": orden.id, "motivo": "2"}, format="json")
        self.assertEqual(self.stock(self.producto), 100)

    def test_anulacion_rechazada_no_toca_el_stock(self):
        orden = self.crear_orden(cantidad=2)
        self.client.post(
            URL_NOTAS,
            {"orden_venta": orden.id, "detalles": [
                {"producto": self.producto.id, "cantidad_devuelta": 1, "destino": "STOCK_DISPONIBLE"}]},
            format="json",
        )
        stock_antes = self.stock(self.producto)  # 99
        response = self.client.post(URL_ANULACIONES, {"orden_venta": orden.id, "motivo": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(self.stock(self.producto), stock_antes)

    def test_no_se_puede_anular_dos_veces(self):
        orden = self.crear_orden()
        self.client.post(URL_ANULACIONES, {"orden_venta": orden.id, "motivo": "Motivo 1"}, format="json")
        response = self.client.post(URL_ANULACIONES, {"orden_venta": orden.id, "motivo": "Motivo 2"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "orden_ya_anulada")
        self.assertEqual(Anulacion.objects.count(), 1)

    def test_no_se_puede_anular_una_orden_con_devolucion(self):
        orden = self.crear_orden()
        self.client.post(
            URL_NOTAS,
            {"orden_venta": orden.id, "detalles": [
                {"producto": self.producto.id, "cantidad_devuelta": 1, "destino": "STOCK_DISPONIBLE"}]},
            format="json",
        )
        response = self.client.post(URL_ANULACIONES, {"orden_venta": orden.id, "motivo": "Tarde"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "estado_de_orden_invalido")

    def test_anulacion_sin_motivo(self):
        orden = self.crear_orden()
        response = self.client.post(URL_ANULACIONES, {"orden_venta": orden.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("motivo", response.data["errores"])

    def test_anulacion_de_orden_inexistente(self):
        response = self.client.post(URL_ANULACIONES, {"orden_venta": 999999, "motivo": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_una_anulacion_no_se_edita_ni_se_borra(self):
        orden = self.crear_orden()
        self.client.post(URL_ANULACIONES, {"orden_venta": orden.id, "motivo": "x"}, format="json")
        anulacion = Anulacion.objects.get()
        self.assertEqual(
            self.client.delete(f"{URL_ANULACIONES}{anulacion.id}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.patch(f"{URL_ANULACIONES}{anulacion.id}/", {"motivo": "y"}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


# ---------------------------------------------------------------- NOTAS DE CREDITO
class NotaCreditoTests(BaseVentasTest):
    def devolver(self, orden, producto=None, cantidad=1, destino="STOCK_DISPONIBLE", **extra):
        body = {
            "orden_venta": orden.id,
            "detalles": [{
                "producto": (producto or self.producto).id,
                "cantidad_devuelta": cantidad,
                "destino": destino,
            }],
        }
        body.update(extra)
        return self.client.post(URL_NOTAS, body, format="json")

    def test_devolucion_parcial_repone_stock_y_calcula_el_monto(self):
        orden = self.crear_orden(cantidad=2)  # stock 98
        response = self.devolver(orden, cantidad=1)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        nota = NotaCredito.objects.get()
        self.assertEqual(nota.monto, Decimal("1300.00"))
        self.assertEqual(self.stock(self.producto), 99)

        orden.refresh_from_db()
        self.assertEqual(orden.estado.nombre, EstadoOrdenVenta.DEVOLUCION_PARCIAL)

        movimiento = MovimientoInventario.objects.get(tipo=MovimientoInventario.Tipo.DEVOLUCION)
        self.assertEqual(movimiento.cantidad, 1)
        self.assertEqual(movimiento.observacion, f"Devolución - nota de crédito #{nota.pk}")

    def test_devolucion_total_cambia_el_estado(self):
        orden = self.crear_orden(cantidad=2)
        response = self.devolver(orden, cantidad=2)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(NotaCredito.objects.get().monto, Decimal("2600.00"))
        orden.refresh_from_db()
        self.assertEqual(orden.estado.nombre, EstadoOrdenVenta.DEVOLUCION_TOTAL)

    def test_dos_devoluciones_parciales_completan_la_orden(self):
        orden = self.crear_orden(cantidad=3)
        self.assertEqual(self.devolver(orden, cantidad=1).status_code, status.HTTP_201_CREATED)
        orden.refresh_from_db()
        self.assertEqual(orden.estado.nombre, EstadoOrdenVenta.DEVOLUCION_PARCIAL)
        self.assertEqual(self.devolver(orden, cantidad=2).status_code, status.HTTP_201_CREATED)
        orden.refresh_from_db()
        self.assertEqual(orden.estado.nombre, EstadoOrdenVenta.DEVOLUCION_TOTAL)

    def test_producto_danado_no_repone_stock(self):
        orden = self.crear_orden(cantidad=2)  # stock 98
        response = self.devolver(orden, cantidad=1, destino="PRODUCTO_DANADO")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.stock(self.producto), 98)
        self.assertFalse(MovimientoInventario.objects.filter(tipo=MovimientoInventario.Tipo.DEVOLUCION).exists())

    def test_el_monto_enviado_se_ignora(self):
        orden = self.crear_orden(cantidad=2)
        self.devolver(orden, cantidad=1, monto="1.00")
        self.assertEqual(NotaCredito.objects.get().monto, Decimal("1300.00"))

    def test_el_monto_incluye_el_descuento(self):
        orden = self.crear_orden(cantidad=2, descuento="100.00")  # total 2500
        self.devolver(orden, cantidad=1)
        self.assertEqual(NotaCredito.objects.get().monto, Decimal("1250.00"))

    def test_saldo_a_favor_por_defecto_es_falso(self):
        orden = self.crear_orden()
        self.devolver(orden)
        self.assertFalse(NotaCredito.objects.get().saldo_a_favor)

    def test_saldo_a_favor_se_registra(self):
        orden = self.crear_orden()
        self.devolver(orden, saldo_a_favor=True)
        self.assertTrue(NotaCredito.objects.get().saldo_a_favor)

    def test_no_se_puede_devolver_mas_de_lo_vendido(self):
        orden = self.crear_orden(cantidad=2)
        response = self.devolver(orden, cantidad=3)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["codigo"], "cantidad_supera_lo_vendido")
        self.assertFalse(NotaCredito.objects.exists())

    def test_no_se_puede_devolver_mas_de_lo_que_queda(self):
        orden = self.crear_orden(cantidad=3)
        self.devolver(orden, cantidad=2)
        response = self.devolver(orden, cantidad=2)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "devolucion_excedida")
        self.assertEqual(NotaCredito.objects.count(), 1)

    def test_producto_que_no_pertenece_a_la_orden(self):
        orden = self.crear_orden()
        response = self.devolver(orden, producto=self.producto2)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["codigo"], "producto_fuera_de_la_orden")

    def test_devolucion_sin_productos(self):
        orden = self.crear_orden()
        response = self.client.post(URL_NOTAS, {"orden_venta": orden.id, "detalles": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cantidad_devuelta_menor_a_uno(self):
        orden = self.crear_orden()
        response = self.devolver(orden, cantidad=0)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_orden_anulada_no_admite_devolucion(self):
        orden = self.crear_orden()
        services.anular_orden_venta(orden_venta=orden, motivo="x", usuario=self.usuario)
        response = self.devolver(orden)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "estado_de_orden_invalido")

    def test_orden_con_devolucion_total_no_admite_mas(self):
        orden = self.crear_orden(cantidad=1)
        self.devolver(orden, cantidad=1)
        response = self.devolver(orden, cantidad=1)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["codigo"], "estado_de_orden_invalido")
