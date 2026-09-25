
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import (
    Cliente,
    Producto,
    EstadoOrdenVenta,
    OrdenVenta,
    OrdenVentaDetalle,
)


class VentasTestCase(APITestCase):

    def setUp(self):
        User = get_user_model()

        self.usuario = User.objects.create_user(
            username="usuario_test",
            password="123456"
        )

        self.cliente = Cliente.objects.create(
            nombre="Cliente Test",
            telefono="1122334455",
            email="cliente@test.com",
            direccion="Calle Test 123",
            estado=Cliente.ESTADO_ACTIVO
        )

        self.producto = Producto.objects.create(
            nombre="Producto Test",
            precio=Decimal("100.00"),
            stock=10
        )

        self.producto2 = Producto.objects.create(
            nombre="Producto Test 2",
            precio=Decimal("50.00"),
            stock=20
        )

        self.estado = EstadoOrdenVenta.objects.create(
            nombre="Confirmada",
            descripcion="Orden confirmada"
        )

        self.client.force_authenticate(user=self.usuario)

    # -------------------------
    # CLIENTES
    # -------------------------

    def test_listar_clientes(self):
        response = self.client.get("/api/ventas/clientes/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["nombre"],
            "Cliente Test"
        )

    def test_obtener_cliente(self):
        response = self.client.get(
            f"/api/ventas/clientes/{self.cliente.id_cliente}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["nombre"],
            "Cliente Test"
        )

    def test_modificar_cliente(self):
        data = {
            "nombre": "Cliente Modificado",
            "telefono": "1199999999",
            "email": "modificado@test.com",
            "direccion": "Nueva direccion",
            "estado": "AC"
        }

        response = self.client.put(
            f"/api/ventas/clientes/{self.cliente.id_cliente}/",
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.cliente.refresh_from_db()

        self.assertEqual(
            self.cliente.nombre,
            "Cliente Modificado"
        )

    def test_baja_logica_cliente(self):
        response = self.client.delete(
            f"/api/ventas/clientes/{self.cliente.id_cliente}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.cliente.refresh_from_db()

        self.assertEqual(
            self.cliente.estado,
            Cliente.ESTADO_BAJA
        )

    def test_cliente_inexistente(self):
        response = self.client.get(
            "/api/ventas/clientes/999999/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    # -------------------------
    # PRODUCTOS
    # -------------------------

    def test_listar_productos(self):
        response = self.client.get(
            "/api/ventas/productos/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            len(response.data["results"]),
            2
    )

    def test_crear_producto(self):
        data = {
            "nombre": "Producto Nuevo",
            "precio": "250.00",
            "stock": 15
        }

        response = self.client.post(
            "/api/ventas/productos/",
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertEqual(
            response.data["nombre"],
            "Producto Nuevo"
        )

        self.assertTrue(
            Producto.objects.filter(
                nombre="Producto Nuevo"
            ).exists()
        )

    def test_modificar_producto(self):
        data = {
            "nombre": "Producto Modificado",
            "precio": "150.00",
            "stock": 25
        }

        response = self.client.put(
            f"/api/ventas/productos/{self.producto.id}/",
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.producto.refresh_from_db()

        self.assertEqual(
            self.producto.nombre,
            "Producto Modificado"
        )

    # -------------------------
    # ESTADOS
    # -------------------------

    def test_listar_estados(self):
        response = self.client.get(
            "/api/ventas/estados-orden-venta/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            len(response.data["results"]),
            1
        )

    def test_crear_estado(self):
        data = {
            "nombre": "Completada",
            "descripcion": "Orden completada"
        }

        response = self.client.post(
            "/api/ventas/estados-orden-venta/",
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertTrue(
            EstadoOrdenVenta.objects.filter(
                nombre="Completada"
            ).exists()
        )

    # -------------------------
    # ORDENES DE VENTA
    # -------------------------

    def test_crear_orden_venta(self):
        data = {
            "cliente": self.cliente.id_cliente,
            "forma_pago": "EFECTIVO",
            "detalles": [
                {
                    "producto": self.producto.id,
                    "cantidad": 2
                }
            ]
        }

        response = self.client.post(
            "/api/ventas/ordenes-venta/",
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        orden = OrdenVenta.objects.get(
            cliente=self.cliente
        )

        self.assertEqual(
            orden.total,
            Decimal("200.00")
        )

        self.assertEqual(
            orden.estado.nombre,
            "Pendiente"
        )

        detalle = OrdenVentaDetalle.objects.get(
            orden_venta=orden
        )

        self.assertEqual(
            detalle.cantidad,
            2
        )

        self.assertEqual(
            detalle.precio_unitario,
            Decimal("100.00")
        )

        self.producto.refresh_from_db()

        self.assertEqual(
            self.producto.stock,
            8
        )

    def test_crear_orden_con_varios_productos(self):
        data = {
            "cliente": self.cliente.id_cliente,
            "forma_pago": "DEBITO",
            "detalles": [
                {
                    "producto": self.producto.id,
                    "cantidad": 2
                },
                {
                    "producto": self.producto2.id,
                    "cantidad": 3
                }
            ]
        }

        response = self.client.post(
            "/api/ventas/ordenes-venta/",
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        orden = OrdenVenta.objects.get(
            cliente=self.cliente
        )

        self.assertEqual(
            orden.total,
            Decimal("350.00")
        )

        self.producto.refresh_from_db()
        self.producto2.refresh_from_db()

        self.assertEqual(
            self.producto.stock,
            8
        )

        self.assertEqual(
            self.producto2.stock,
            17
        )

    def test_orden_sin_productos(self):
        data = {
            "cliente": self.cliente.id_cliente,
            "forma_pago": "EFECTIVO",
            "detalles": []
        }

        response = self.client.post(
            "/api/ventas/ordenes-venta/",
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_orden_sin_stock(self):
        data = {
            "cliente": self.cliente.id_cliente,
            "forma_pago": "EFECTIVO",
            "detalles": [
                {
                    "producto": self.producto.id,
                    "cantidad": 100
                }
            ]
        }

        response = self.client.post(
            "/api/ventas/ordenes-venta/",
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.producto.refresh_from_db()

    # -------------------------
    # CAMPOS NUEVOS (campos_base_datos_ventas.docx)
    # -------------------------

    def test_crear_cliente_con_cuil_y_condicion_iva(self):
        data = {
            "nombre": "Cliente Con CUIL",
            "telefono": "1100000000",
            "email": "cuil@test.com",
            "direccion": "Calle Falsa 123",
            "cuil": "20-12345678-9",
            "condicion_iva": "Responsable Inscripto",
            "estado": Cliente.ESTADO_ACTIVO,
        }

        # Nota: el ABM de clientes no tiene endpoint de creación (POST) hoy,
        # así que probamos que el campo se guarda y se expone vía update.
        self.cliente.cuil = data["cuil"]
        self.cliente.condicion_iva = data["condicion_iva"]
        self.cliente.save(update_fields=["cuil", "condicion_iva"])

        response = self.client.get(
            f"/api/ventas/clientes/{self.cliente.id_cliente}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cuil"], "20-12345678-9")
        self.assertEqual(response.data["condicion_iva"], "Responsable Inscripto")

    def test_modificar_cliente_actualiza_cuil(self):
        data = {
            "nombre": self.cliente.nombre,
            "telefono": self.cliente.telefono,
            "email": self.cliente.email,
            "direccion": self.cliente.direccion,
            "cuil": "27-98765432-1",
            "condicion_iva": "Monotributo",
            "estado": "AC",
        }

        response = self.client.put(
            f"/api/ventas/clientes/{self.cliente.id_cliente}/",
            data,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.cuil, "27-98765432-1")
        self.assertEqual(self.cliente.condicion_iva, "Monotributo")

    def test_crear_orden_con_comprobante_y_forma_pago_nueva(self):
        data = {
            "cliente": self.cliente.id_cliente,
            "forma_pago": "CREDITO",
            "numero_comprobante": "B-0002145",
            "tipo_comprobante": "FACTURA_B",
            "detalles": [
                {"producto": self.producto.id, "cantidad": 1}
            ]
        }

        response = self.client.post(
            "/api/ventas/ordenes-venta/",
            data,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["forma_pago"], "CREDITO")
        self.assertEqual(response.data["numero_comprobante"], "B-0002145")
        self.assertEqual(response.data["tipo_comprobante"], "FACTURA_B")

    def test_crear_orden_con_descuento_por_linea(self):
        data = {
            "cliente": self.cliente.id_cliente,
            "forma_pago": "EFECTIVO",
            "detalles": [
                {
                    "producto": self.producto.id,
                    "cantidad": 2,
                    "descuento": "20.00",
                }
            ]
        }

        response = self.client.post(
            "/api/ventas/ordenes-venta/",
            data,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        orden = OrdenVenta.objects.get(cliente=self.cliente)
        # 2 x 100.00 - 20.00 de descuento = 180.00
        self.assertEqual(orden.total, Decimal("180.00"))

        detalle = OrdenVentaDetalle.objects.get(orden_venta=orden)
        self.assertEqual(detalle.descuento, Decimal("20.00"))
        self.assertEqual(detalle.subtotal, Decimal("180.00"))


class AnulacionTestCase(APITestCase):
    """Tests de la tabla nueva 'anulacion' (pantalla Devoluciones -> Anular)."""

    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(username="usuario_test2", password="123456")

        self.cliente = Cliente.objects.create(
            nombre="Cliente Anulacion",
            estado=Cliente.ESTADO_ACTIVO,
        )
        self.producto = Producto.objects.create(
            nombre="Producto Anulacion", precio=Decimal("100.00"), stock=10
        )
        self.estado_pendiente = EstadoOrdenVenta.objects.create(nombre="Pendiente")

        self.orden = OrdenVenta.objects.create(
            cliente=self.cliente,
            usuario=self.usuario,
            estado=self.estado_pendiente,
            forma_pago="EFECTIVO",
            total=Decimal("100.00"),
        )
        OrdenVentaDetalle.objects.create(
            orden_venta=self.orden,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal("100.00"),
        )

        self.client.force_authenticate(user=self.usuario)

    def test_anular_orden(self):
        data = {
            "orden_venta": self.orden.id,
            "motivo": "Cliente se arrepintió",
            "detalle": "Pidió cancelar por WhatsApp",
        }

        response = self.client.post(
            "/api/ventas/anulaciones/",
            data,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado.nombre, "Anulada")

    def test_no_permite_anular_dos_veces(self):
        primera = {
            "orden_venta": self.orden.id,
            "motivo": "Motivo 1",
        }
        response1 = self.client.post(
            "/api/ventas/anulaciones/", primera, format="json"
        )
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        segunda = {
            "orden_venta": self.orden.id,
            "motivo": "Motivo 2",
        }
        response2 = self.client.post(
            "/api/ventas/anulaciones/", segunda, format="json"
        )
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)


class NotaCreditoTestCase(APITestCase):
    """Tests de las tablas nuevas 'nota_credito' y 'detalle_nota_credito'
    (pantalla Devoluciones)."""

    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(username="usuario_test3", password="123456")

        self.cliente = Cliente.objects.create(
            nombre="Cliente NC", estado=Cliente.ESTADO_ACTIVO
        )
        self.producto = Producto.objects.create(
            nombre="Producto NC", precio=Decimal("100.00"), stock=5
        )
        self.producto_danado = Producto.objects.create(
            nombre="Producto NC Dañado", precio=Decimal("50.00"), stock=5
        )
        self.estado_pendiente = EstadoOrdenVenta.objects.create(nombre="Pendiente")

        self.orden = OrdenVenta.objects.create(
            cliente=self.cliente,
            usuario=self.usuario,
            estado=self.estado_pendiente,
            forma_pago="EFECTIVO",
            total=Decimal("150.00"),
        )
        OrdenVentaDetalle.objects.create(
            orden_venta=self.orden, producto=self.producto,
            cantidad=1, precio_unitario=Decimal("100.00"),
        )
        OrdenVentaDetalle.objects.create(
            orden_venta=self.orden, producto=self.producto_danado,
            cantidad=1, precio_unitario=Decimal("50.00"),
        )

        self.client.force_authenticate(user=self.usuario)

    def test_nota_credito_repone_stock_disponible(self):
        data = {
            "orden_venta": self.orden.id,
            "monto": "100.00",
            "saldo_a_favor": False,
            "detalles": [
                {
                    "producto": self.producto.id,
                    "cantidad_devuelta": 1,
                    "destino": "STOCK_DISPONIBLE",
                }
            ],
        }

        response = self.client.post(
            "/api/ventas/notas-credito/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 6)  # 5 + 1 devuelto

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado.nombre, "Devolución parcial")

    def test_nota_credito_producto_danado_no_repone_stock(self):
        data = {
            "orden_venta": self.orden.id,
            "monto": "50.00",
            "saldo_a_favor": True,
            "detalles": [
                {
                    "producto": self.producto_danado.id,
                    "cantidad_devuelta": 1,
                    "destino": "PRODUCTO_DANADO",
                }
            ],
        }

        response = self.client.post(
            "/api/ventas/notas-credito/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.producto_danado.refresh_from_db()
        self.assertEqual(self.producto_danado.stock, 5)  # no cambia

    def test_nota_credito_sin_detalles(self):
        data = {
            "orden_venta": self.orden.id,
            "monto": "50.00",
            "saldo_a_favor": False,
            "detalles": [],
        }

        response = self.client.post(
            "/api/ventas/notas-credito/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

