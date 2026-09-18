"""
Configuración de la aplicación CompraYProveedores.

Define la configuración de la aplicación Django para el módulo de Compras y Proveedores.
"""
from django.apps import AppConfig


class CompraYProveedoresConfig(AppConfig):
    """Configuración de la app CompraYProveedores.
    
    Atributos:
        default_auto_field: Campo auto-incrementable por defecto (BigAutoField).
        name: Nombre del paquete de la aplicación.
        label: Etiqueta interna de la aplicación en Django.
        verbose_name: Nombre legible de la aplicación.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.CompraYProveedores"
    label = "compra_y_proveedores"
    verbose_name = "Compras y Proveedores"
