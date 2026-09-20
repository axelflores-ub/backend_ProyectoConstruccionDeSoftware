"""
Ruteo raíz del proyecto.

Todo cuelga de /api/. Cada módulo publicará su propio router en
apps/<Modulo>/urls.py. A medida que un módulo tenga endpoints, descomentá
su línea `include(...)` de abajo.
"""
from django.contrib import admin
from django.urls import include, path  # noqa: F401
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # Autenticación JWT
    path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # Documentación OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    # --- Módulos del negocio (descomentar cuando cada uno tenga su router) ---
    # path("api/core/", include("apps.core.urls")),
    path("api/compras/", include("apps.CompraYProveedores.urls")),
    path("api/ventas/", include("apps.Ventas.urls")),
    # path("api/scm/", include("apps.SCM.urls")),
    path("api/contabilidad/", include("apps.ContabilidadFinanzas.urls")),
]
