from django.apps import AppConfig


class ScmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.SCM"
    label = "scm"
    verbose_name = "SCM (productos e inventario)"
