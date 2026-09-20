
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
            "forma_pago": "TARJETA",
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

