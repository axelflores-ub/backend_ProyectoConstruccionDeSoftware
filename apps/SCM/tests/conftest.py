import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.SCM.models import Producto, Rubro


@pytest.fixture
def api_client():
    usuario = get_user_model().objects.create_user(username="tester", password="x")
    client = APIClient()
    client.force_authenticate(user=usuario)
    return client


@pytest.fixture
def rubro():
    return Rubro.objects.create(nombre="Cemento", descripcion="Bolsas y a granel")


@pytest.fixture
def producto(rubro):
    return Producto.objects.create(
        codigo="CEM-001",
        nombre="Cemento Portland 50kg",
        precio="12000.00",
        rubro=rubro,
        stock_actual=20,
        stock_minimo=5,
    )
