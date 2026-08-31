# CorralónDB — Backend

Sistema de gestión para un corralón de materiales de construcción.
Backend de **APIs REST** que consume un frontend independiente.

> **Estado: esqueleto.** Este repo trae la **estructura armada y validada**
> (proyecto Django, módulos, Docker, configuración), pero **sin lógica de negocio**:
> `models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py` de cada módulo
> están vacíos y **no hay migraciones**. Cada equipo implementa su módulo en su
> rama `feature/nombreDeUS`.

---

## 1. Stack de herramientas

| Herramienta | Para qué la usamos |
|---|---|
| **Python 3.12** | Lenguaje del backend. (Funciona 3.11–3.13; ver nota de versión abajo). |
| **Django 5.1** | Framework web. Arquitectura **MVT**, ORM, migraciones, admin. |
| **Django REST Framework (DRF)** | Construcción de las APIs REST (serializers, viewsets, routers, permisos). |
| **SimpleJWT** | Autenticación por tokens JWT (`access` / `refresh`) para el frontend. |
| **drf-spectacular** | Documentación OpenAPI/Swagger autogenerada en `/api/docs/`. |
| **PostgreSQL 16** | Base de datos relacional. Se llama **`corralonDB`**. |
| **Docker + docker-compose** | Levanta **solo la base de datos** en un contenedor para que **todo el equipo trabaje contra la misma DB**. |
| **TypeScript** | Lenguaje del **frontend** (repositorio/carpeta aparte, aún no incluido). Se comunica con este backend **exclusivamente por las APIs**. |
| **Postman** | Herramienta con la que probamos manualmente las APIs. Cada quien arma su colección local (no se versiona en el repo). |
| **pytest + pytest-django** | Pruebas automáticas de las APIs. |
| **ruff** | Linter y formateador. |

### ¿Por qué Docker solo para la base?

El pedido es que **todos tengan la misma base de datos**. En vez de que cada
integrante instale y configure PostgreSQL a mano (versiones distintas, contraseñas
distintas, datos distintos), `docker-compose` levanta un PostgreSQL 16 idéntico
para todos con:

- **Base:** `corralonDB`
- **Usuario:** `corralon`
- **Password:** `1234567890`
- **Puerto:** `5432` (mapeado a `localhost:5432`)
- Los datos persisten en el volumen `corralon_pgdata` aunque apagues el contenedor.

Django y (a futuro) el frontend corren **localmente**, no en Docker.

---

## 2. Estructura del proyecto

```
backend_ProyectoConstruccionDeSoftware/
├── config/                      # Proyecto Django (settings, urls raíz, wsgi/asgi)
│   ├── settings.py
│   └── urls.py                  # Enruta /api/... ; los include() de cada módulo están comentados
├── apps/                        # Una app Django POR MÓDULO del negocio
│   ├── core/                    # Usuarios y privilegios (base transversal)
│   ├── CompraYProveedores/      # Proveedores, órdenes de compra y sus estados
│   ├── Ventas/                  # Clientes, órdenes de venta y sus estados
│   ├── SCM/                     # Productos, rubros y movimientos de inventario
│   └── ContabilidadFinanzas/    # Facturas, diario, cierres mensuales, períodos
├── docker/
│   └── initdb/                  # (opcional) .sql que se corre al crear la DB por primera vez
├── docs/
│   └── DER.dbml                 # Diagrama entidad-relación (fuente de verdad del modelo)
├── scripts/
│   ├── verificar_base.ps1       # Chequeo integral "¿levanta todo?" (Windows)
│   └── verificar_base.sh        # idem (Linux/mac)
├── docker-compose.yml           # Servicio `db` (PostgreSQL)
├── requirements.txt             # Dependencias de ejecución
├── requirements-dev.txt         # + dependencias de desarrollo (tests, lint)
├── .env.example                 # Plantilla de variables de entorno
└── manage.py
```

Cada app de módulo tiene **siempre la misma anatomía** (ver sección 8). Los
archivos vienen **vacíos**, listos para completar:

```
apps/<Modulo>/
├── apps.py          # Config de la app (name + label). YA está hecho, no tocar.
├── models.py        # (vacío) Tablas (ORM)
├── serializers.py   # (vacío) JSON <-> objetos, validaciones
├── views.py         # (vacío) ViewSets con la lógica de cada endpoint
├── urls.py          # (vacío salvo `urlpatterns = []`) Router del módulo
├── admin.py         # (vacío) Registro de modelos en el Django Admin
├── migrations/      # solo __init__.py (se generan al crear los modelos)
└── tests/           # solo __init__.py (agregá acá tus test_*.py)
```

### Qué va a vivir en cada módulo (mapeo DER → módulos)

| Módulo | Tablas del DER que le corresponden |
|---|---|
| **core** | `usuario`, `privilegio` |
| **CompraYProveedores** | `proveedor`, `orden_compra`, `orden_compra_detalle`, `estado_orden_compra` |
| **Ventas** | `cliente`, `orden_venta`, `orden_venta_detalle`, `estado_orden_venta` |
| **SCM** | `producto`, `rubro`, `movimiento_inventario` |
| **ContabilidadFinanzas** | `factura_cabecera`, `factura_detalle`, `diario`, `cierre_mensual`, `periodo` |

El DER completo está en [`docs/DER.dbml`](docs/DER.dbml) (se puede pegar en
<https://dbdiagram.io> para verlo igual que la imagen original). **Es la fuente de
verdad:** los `db_table` de los modelos deben respetar esos nombres.

### Nota sobre el modelo de Usuario

El DER tiene tablas `usuario` y `privilegio` propias. Si el equipo decide usar un
**modelo de Usuario propio** (email como login, FK a `privilegio`):

1. Crear la clase `Usuario` en `apps/core/models.py`.
2. Descomentar `AUTH_USER_MODEL = "core.Usuario"` en `config/settings.py`.
3. Hacerlo **antes de la primera `migrate`** (cambiar el user model después es muy costoso).

Si no, Django usa su `auth.User` por defecto y `usuario`/`privilegio` quedan como
modelos de negocio comunes.

---

## 3. Requisitos previos

- **Docker Desktop** (para la base de datos).
- **Python 3.12** recomendado.
  > `psycopg` (driver de PostgreSQL) necesita ruedas precompiladas. En 3.12/3.13
  > funciona sin problemas. En Python 3.14, `requirements.txt` apunta a
  > `psycopg[binary]==3.2.13`, que sí tiene ruedas para 3.14.
- **Git**.
- **Postman** (para probar las APIs).

---

## 4. Puesta en marcha (paso a paso)

Todos los comandos se corren desde la raíz del repo. Se muestran para
**PowerShell (Windows)**; entre paréntesis el equivalente en bash/Linux/macOS.

### 4.1. Clonar y ubicarse

```powershell
git clone <URL-del-repo>
cd backend_ProyectoConstruccionDeSoftware
```

### 4.2. Levantar la base de datos (Docker)

```powershell
docker compose up -d          # levanta el contenedor `corralon_db` en segundo plano
docker compose ps             # verificar que está "healthy"
```

Esto deja PostgreSQL escuchando en `localhost:5432` con la base `corralonDB`.

- **Apagarla** (sin borrar datos): `docker compose stop`
- **Apagarla y borrar TODO** (incluye datos): `docker compose down -v`

### 4.3. Entorno virtual e instalación de dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # (bash: source .venv/bin/activate)
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 4.4. Variables de entorno

```powershell
Copy-Item .env.example .env           # (bash: cp .env.example .env)
```

El `.env` por defecto ya apunta a la base de Docker:

```
DATABASE_URL=postgres://corralon:1234567890@localhost:5432/corralonDB
```

**El `.env` no se commitea.**

### 4.5. Migraciones

Todavía **no hay modelos**, así que solo se crean las tablas internas de Django
(auth, sesiones, admin):

```powershell
python manage.py migrate
```

Cuando un módulo agregue modelos, el flujo es:

```powershell
python manage.py makemigrations <Modulo>   # genera apps/<Modulo>/migrations/000X_*.py
python manage.py migrate                    # aplica a la base
```

### 4.6. Usuario administrador

```powershell
python manage.py createsuperuser
```

### 4.7. Levantar el servidor de la API

```powershell
python manage.py runserver
```

Queda en **`http://localhost:8000`**. Dejá esta terminal abierta mientras probás.

### 4.8. Verificación rápida

| Recurso | URL | Estado |
|---|---|---|
| Django Admin | <http://localhost:8000/admin/> | ✅ funciona ya |
| Documentación Swagger | <http://localhost:8000/api/docs/> | ✅ funciona (vacía hasta que haya endpoints) |
| Esquema OpenAPI (JSON) | <http://localhost:8000/api/schema/> | ✅ funciona |
| Login JWT | `POST http://localhost:8000/api/auth/login/` | ✅ funciona con tu superusuario |
| Endpoints de módulos (`/api/scm/...`, etc.) | — | ⏳ aparecen cuando descomentás el `include()` en `config/urls.py` |

### 4.9. Verificar toda la base de una (script)

Con la DB de Docker arriba y el venv activado:

```powershell
.\scripts\verificar_base.ps1        # (bash/Linux/mac: bash scripts/verificar_base.sh)
```

Corre, en orden, y marca `[OK]` / `[FALLA]`:

1. Versión de Python
2. Dependencias importables (Django, DRF, SimpleJWT, spectacular, cors, psycopg)
3. `manage.py check`
4. Que no haya migraciones de modelos pendientes (en el esqueleto: "No changes detected")
5. **Conexión real a la base de datos** (acá se prueba que el PostgreSQL de Docker está OK)
6. `migrate`
7. `collectstatic --dry-run`
8. Que el servidor levante y respondan `/api/schema/`, `/api/docs/`, `/admin/` y `/api/auth/login/`
9. `ruff check`

Salida esperada: `Resultado: 9 OK / 0 fallas — La base esta sana.`

> Si hay un PostgreSQL local ocupando el **5432**, el paso 5 (o `docker compose up`)
> va a fallar. Solución: pará el Postgres local, **o** levantá Docker con otro
> puerto y ajustá el `.env`:
> ```powershell
> $env:DB_HOST_PORT = "5433"; docker compose up -d
> # y en .env:  DATABASE_URL=postgres://corralon:1234567890@localhost:5433/corralonDB
> ```

---

## 5. Resumen de comandos (chuleta)

```powershell
# --- Base de datos (Docker) ---
docker compose up -d                 # levantar la DB
docker compose stop                  # apagar la DB (conserva datos)
docker compose down -v               # apagar y BORRAR datos + volumen
docker compose ps                    # estado del contenedor
docker compose logs -f db            # logs de PostgreSQL

# --- Entorno Python ---
.\.venv\Scripts\Activate.ps1         # activar venv (Windows)
pip install -r requirements-dev.txt  # instalar dependencias

# --- Django ---
python manage.py migrate             # aplicar migraciones
python manage.py makemigrations <M>  # generar migraciones tras crear/cambiar models.py
python manage.py createsuperuser     # crear usuario administrador
python manage.py runserver           # levantar API en localhost:8000
python manage.py check               # chequear el proyecto sin levantarlo
python manage.py shell               # consola interactiva con el ORM

# --- Calidad ---
pytest                               # correr todas las pruebas
pytest apps/Ventas                   # pruebas de un módulo
ruff check .                         # lint
ruff format .                        # formatear
```

---

## 6. Migrar y manejar datos con la base en Docker

La base vive en el contenedor, pero **las migraciones de Django se corren
localmente** (Django está en tu venv, no en Docker) apuntando al contenedor vía
`DATABASE_URL`.

### 6.1. Flujo de migración

```powershell
# 1) Creaste/cambiaste un models.py -> generar la migración
python manage.py makemigrations <Modulo>       # ej: python manage.py makemigrations Ventas

# 2) Revisá el archivo generado en apps/<Modulo>/migrations/ y commiteálo

# 3) Aplicar a la base del contenedor
python manage.py migrate

# 4) Ver estado
python manage.py showmigrations
```

> Las migraciones **se versionan en git**. Cuando alguien hace `pull` y aparecen
> migraciones nuevas, corre `python manage.py migrate` y todos quedan con el
> mismo esquema.

### 6.2. Consola de PostgreSQL del contenedor

```powershell
docker compose exec db psql -U corralon -d corralonDB
# \dt   -> listar tablas   |   \d producto -> describir tabla   |   \q -> salir
```

### 6.3. Cargar un `.sql` dentro del contenedor

```powershell
Get-Content .\docs\datos.sql | docker compose exec -T db psql -U corralon -d corralonDB
# o dejar el .sql en docker/initdb/ ANTES del primer `up` (solo corre al crear el volumen)
```

### 6.4. Backup y restore

```powershell
docker compose exec -T db pg_dump -U corralon -d corralonDB > backup_corralon.sql
Get-Content .\backup_corralon.sql | docker compose exec -T db psql -U corralon -d corralonDB
```

### 6.5. Resetear la base desde cero

```powershell
docker compose down -v        # borra el volumen corralon_pgdata
docker compose up -d          # base nueva y vacía
python manage.py migrate      # recrear tablas
```

### 6.6. Fixtures de Django (datos de prueba versionables)

```powershell
python manage.py dumpdata scm --indent 2 > apps/SCM/fixtures/scm_demo.json
python manage.py loaddata scm_demo
```

---

## 7. Probar las APIs (Swagger UI y Postman)

Hay dos formas de probar los endpoints. **Swagger** es la más rápida para un
chequeo manual; **Postman** conviene para armar colecciones y flujos repetibles.

### 7.1. Con Swagger UI (rápido, sin instalar nada)

Con el server levantado, abrí <http://localhost:8000/api/docs/>. Es la
documentación interactiva que genera **drf-spectacular** a partir del código: se
actualiza sola a medida que agregás serializers y viewsets.

1. Se listan todos los endpoints agrupados por módulo, con su esquema de
   request/response.
2. Para endpoints protegidos, primero autenticá:
   - Expandí `POST /api/auth/login/` → **Try it out** → completá
     `{ "username": "TU_SUPERUSUARIO", "password": "TU_PASSWORD" }` → **Execute**.
   - Copiá el valor de `access` de la respuesta.
   - Botón **Authorize** (arriba a la derecha) → pegá `Bearer <access>` → **Authorize**.
3. Ahora cualquier endpoint se prueba con **Try it out** → completar parámetros /
   body → **Execute**. Swagger muestra la URL (`curl` equivalente), el status y el
   cuerpo de la respuesta.
4. El esquema crudo OpenAPI está en <http://localhost:8000/api/schema/> (sirve
   para importarlo en Postman, Insomnia, generar clientes, etc.).

> En el estado actual (esqueleto) Swagger solo muestra los endpoints de `auth/` y
> la documentación. Cada recurso de módulo aparece cuando implementás su ViewSet
> y descomentás el `include()` en `config/urls.py`.

### 7.2. Con Postman

> La colección de Postman **no se versiona en el repo**. Armá la tuya a mano con
> los endpoints que vayas creando, o importá el esquema OpenAPI: en Postman →
> **Import** → pegá `http://localhost:8000/api/schema/` y Postman genera la
> colección sola.

#### 7.2.1. Configurar el entorno

Creá en Postman un *environment* con:

| Variable | Valor |
|---|---|
| `base_url` | `http://localhost:8000` |
| `access_token` | *(se completa al hacer login)* |
| `refresh_token` | *(se completa al hacer login)* |

Seteá la autenticación **a nivel colección** como *Bearer Token* con valor
`{{access_token}}`, así todos los requests la heredan.

#### 7.2.2. Autenticarse (token JWT)

1. `POST {{base_url}}/api/auth/login/` con body JSON:
   ```json
   { "username": "TU_SUPERUSUARIO", "password": "TU_PASSWORD" }
   ```
   > Si más adelante activás el modelo de Usuario propio con email, el campo pasa
   > a ser `"email"` en lugar de `"username"`.
2. La respuesta trae `access` y `refresh`. Guardalos con este *test script* del request:
   ```javascript
   const d = pm.response.json();
   if (d.access) pm.environment.set('access_token', d.access);
   if (d.refresh) pm.environment.set('refresh_token', d.refresh);
   ```
3. El resto de los requests van con `Authorization: Bearer {{access_token}}`.
4. Cuando el `access` expira (60 min): `POST {{base_url}}/api/auth/refresh/` con
   `{ "refresh": "{{refresh_token}}" }`.

### 7.3. Endpoints previstos (cuando cada módulo los implemente)

Aplica tanto para Swagger como para Postman.

Prefijo común: `http://localhost:8000/api/`

| Módulo | Prefijo | Recursos sugeridos |
|---|---|---|
| Auth | `auth/` | `login/`, `refresh/`, `verify/` *(ya funcionan)* |
| Core | `core/` | `privilegios/`, `usuarios/` |
| SCM | `scm/` | `rubros/`, `productos/`, `movimientos-inventario/` |
| Compras | `compras/` | `proveedores/`, `estados-orden-compra/`, `ordenes-compra/` |
| Ventas | `ventas/` | `clientes/`, `estados-orden-venta/`, `ordenes-venta/` |
| Contabilidad | `contabilidad/` | `periodos/`, `cierres-mensuales/`, `diarios/`, `facturas/` |

Cada recurso debería soportar el CRUD REST estándar:

| Acción | Método | URL |
|---|---|---|
| Listar (paginado, `?search=`, `?ordering=`) | `GET` | `/api/scm/productos/` |
| Ver uno | `GET` | `/api/scm/productos/1/` |
| Crear | `POST` | `/api/scm/productos/` |
| Reemplazar | `PUT` | `/api/scm/productos/1/` |
| Modificar parcial | `PATCH` | `/api/scm/productos/1/` |
| Borrar | `DELETE` | `/api/scm/productos/1/` |

---

## 8. Cómo desarrollar: MVT, y qué poner en cada archivo

### 8.1. MVT en Django y por qué el "Template" no está acá

Django usa el patrón **MVT (Model – View – Template)**:

- **Model:** definición de los datos y su persistencia (el ORM). → `models.py`
- **View:** recibe la request, ejecuta la lógica y arma la response. → `views.py`
- **Template:** capa de presentación HTML.

En este proyecto **la capa Template está desacoplada del backend**: no
renderizamos HTML. El frontend es una aplicación **TypeScript aparte** que se
comunica con el backend **solo por las APIs REST** (JSON sobre HTTP).

Consecuencias prácticas:

- `settings.py` tiene `TEMPLATES["DIRS"] = []` y no hay carpeta `templates/`
  propia (Django Admin y la *browsable API* de DRF traen sus templates internos).
- La "View" de MVT, en la práctica, es un **ViewSet de DRF** que devuelve JSON.
- Entre la View y el Model se agrega una capa que Django puro no tiene: el
  **Serializer** (de DRF), que traduce JSON ↔ objetos del ORM y valida.

Flujo de una request:

```
Frontend (TS)
   │  HTTP + JSON  (Authorization: Bearer <jwt>)
   ▼
config/urls.py ──► apps/<Modulo>/urls.py (router)
   │
   ▼
views.py  (ViewSet)  ── autenticación / permisos ──►
   │
   ▼
serializers.py  (valida, convierte JSON→dict)
   │
   ▼
models.py  (ORM)  ──►  PostgreSQL (contenedor Docker)
   │
   ▼
serializers.py  (convierte objeto→JSON)
   │
   ▼
Response JSON  ──►  Frontend
```

### 8.2. `models.py` — los datos

- Una clase = una tabla. Cada atributo = una columna.
- `db_table` fija el nombre de la tabla **igual al del DER** (`producto`,
  `orden_compra`, …).
- Relaciones con `ForeignKey`. `on_delete=PROTECT` para no borrar en cascada
  datos maestros; `CASCADE` solo en los "detalle" respecto de su cabecera.
- Relaciones **entre módulos** se referencian por string con el *label* de la
  app: `ForeignKey("scm.Producto", ...)`.
- Sugerido: una base abstracta común (`creado_en` / `actualizado_en`) para
  auditoría.
- Métodos de negocio simples viven en el modelo (ej. `recalcular_total()`).
- **Regla:** después de tocar `models.py` → `makemigrations <Modulo>` + `migrate`,
  y commitear la migración.

### 8.3. `serializers.py` — traducción y validación

- `ModelSerializer` genera los campos a partir del modelo.
- `fields` **explícito** (nunca `"__all__"`): controla qué se expone.
- `read_only_fields` para lo que calcula el backend (`total`, `subtotal`) o no
  debe setear el cliente.
- Cabecera + detalle: el serializer de la cabecera **anida** el de detalle
  (`detalles = OrdenVentaDetalleSerializer(many=True)`) y sobreescribe
  `create()` / `update()` dentro de una transacción.
- Validaciones de negocio: métodos `validate_<campo>()` o `validate()`.

### 8.4. `views.py` — la lógica de cada endpoint

- Usar **`ModelViewSet`**: da `list`, `retrieve`, `create`, `update`,
  `partial_update`, `destroy` en una sola clase.
- `queryset`: siempre con `select_related` / `prefetch_related` (evita N+1).
- `serializer_class`: el serializer del recurso (o `get_serializer_class()` si
  varía por acción).
- Permisos: por defecto **todo requiere JWT** (`IsAuthenticated`, configurado
  global en `settings.py`). Para abrir un endpoint puntual, `get_permissions()`.
- `search_fields` / `ordering_fields`: habilitan `?search=` y `?ordering=`.
- Acciones extra: decorador `@action`.

### 8.5. `urls.py` — el ruteo

- Cada módulo crea un `DefaultRouter()` y registra sus ViewSets:
  `router.register("productos", ProductoViewSet, basename="producto")`.
- Exponer `urlpatterns = router.urls`.
- En `config/urls.py`, **descomentar** el `include()` del módulo:
  `path("api/scm/", include("apps.SCM.urls"))`.

### 8.6. `admin.py` — back-office

- Registrar cada modelo permite ABM desde `http://localhost:8000/admin/` sin
  escribir endpoints. Útil para cargar datos maestros durante el desarrollo.
- Cabecera + detalle → `TabularInline`.

### 8.7. `tests/` — pruebas automáticas

- `pytest` + `APIClient` de DRF. Un archivo `test_*.py` por área dentro de
  `apps/<Modulo>/tests/`.
- Autenticación en tests: `client.force_authenticate(user=...)`.
- Se ejecutan contra una base de test efímera (no toca `corralonDB`).
- Correr todo: `pytest`. Un módulo: `pytest apps/Ventas`.

### 8.8. `config/settings.py` — configuración (ya hecha)

- Lee todo lo sensible del `.env` con `django-environ`.
- `AUTH_USER_MODEL` está **comentado**: ver "Nota sobre el modelo de Usuario".
- `REST_FRAMEWORK`: auth JWT + sesión, `IsAuthenticated` por defecto,
  paginación de a 20, filtros de búsqueda y orden.
- `SIMPLE_JWT`: vida del `access` (60 min) y `refresh` (7 días).
- `CORS_ALLOWED_ORIGINS`: orígenes del frontend habilitados.

---

## 9. Reglas, convenciones y nomenclatura

### 9.1. Git y ramas

- **`main`**: siempre estable y desplegable. No se commitea directo.
- Una rama por **User Story**: **`feature/nombreDeUS`**
  (ej. `feature/alta-orden-compra`, `feature/reporte-stock`).
- Otros prefijos: `fix/…` (bug), `chore/…` (tareas técnicas),
  `hotfix/…` (urgente sobre producción).
- Flujo: crear rama desde `main` → commits → push → **Pull Request** → al menos
  **1 review aprobada** + checks (tests + lint) en verde → merge (squash) → borrar la rama.
- **Commits** en imperativo y en español, estilo *Conventional Commits*:
  ```
  feat(ventas): alta de orden de venta con detalle
  fix(scm): corrige cálculo de stock en movimientos de salida
  docs: actualiza instrucciones de Docker
  test(compras): agrega casos de recálculo de total
  refactor(core): extrae permiso TienePrivilegio
  ```
- **No se commitea:** `.env`, `.venv/`, `__pycache__/`, `db.sqlite3`,
  `staticfiles/`, `postman/`, dumps de datos. (Ya está en `.gitignore`.)
- **Sí se commitea:** las **migraciones** (`apps/*/migrations/000x_*.py`).

### 9.2. Python / Django

- **PEP 8**, `line-length = 100`. `ruff check .` y `ruff format .` antes de pushear.
- Imports ordenados por `ruff` (isort): stdlib → terceros → locales.
- **Nombres:**
  - Módulos/archivos y variables/funciones: `snake_case`.
  - Clases (modelos, serializers, viewsets): `PascalCase`
    (`OrdenCompra`, `OrdenCompraSerializer`, `OrdenCompraViewSet`).
  - Constantes: `MAYUSCULAS_CON_GUION_BAJO`.
  - Apps de módulo: carpeta en `PascalCase` (`CompraYProveedores`), *label* en
    `snake_case` (`compra_y_proveedores`) — ya definido en cada `apps.py`.
- **Modelos:**
  - Nombre de clase en **singular** (`Producto`, no `Productos`).
  - `db_table` explícito = nombre del DER, en `snake_case` singular.
  - Siempre `__str__`, `class Meta` con `ordering` y `verbose_name`.
  - `related_name` explícito y en plural (`producto.movimientos`).
  - Campos monetarios: `DecimalField(max_digits=12, decimal_places=2)` (nunca `float`).
  - Enumerados: `models.TextChoices`.
- **Serializers:** `fields` explícito, nunca `"__all__"`. Sufijo `Serializer`.
- **ViewSets:** sufijo `ViewSet`. `queryset` con `select_related`/`prefetch_related`.
- **Lógica de negocio:** en el modelo o en un `services.py` del módulo, **no** en
  la view ni en el serializer si es compleja.
- **Nada de imports directos entre views de módulos**; si un módulo necesita a
  otro, se llama por sus modelos/servicios.

### 9.3. Diseño de las APIs (REST)

- Recursos en **plural** y `kebab-case`: `/api/compras/ordenes-compra/`.
- Verbos HTTP con su semántica: `GET` (leer), `POST` (crear), `PUT`/`PATCH`
  (actualizar), `DELETE` (borrar). El verbo va en el método, **no en la URL**
  (`/ordenes-compra/` ✅ ; `/crearOrdenCompra/` ❌).
- Códigos de estado correctos: `200`, `201 Created`, `204 No Content`,
  `400` (validación), `401` (sin token), `403` (sin permiso), `404`.
- Respuestas siempre en JSON. Fechas en ISO-8601 UTC (`2026-08-28T10:00:00Z`).
- Paginación, `?search=` y `?ordering=` ya vienen del `settings` global.
- Cambios que rompen compatibilidad → coordinar con frontend (versionar si hace falta).

### 9.4. Base de datos

- Nombres de tablas y columnas en `snake_case` (los fija el modelo).
- Toda modificación de esquema pasa por una **migración** (jamás SQL manual en
  `corralonDB`).
- Claves foráneas con `on_delete` pensado: `PROTECT` para maestros, `CASCADE`
  solo cabecera→detalle.

### 9.5. Definition of Done de una US

- [ ] Rama `feature/nombreDeUS` a partir de `main`.
- [ ] Modelos + migración generada y commiteada.
- [ ] Serializers con validaciones.
- [ ] ViewSet + ruta en el router del módulo + `include()` descomentado en `config/urls.py`.
- [ ] Pruebas `pytest` del happy-path y de al menos un error.
- [ ] `ruff check .` sin errores.
- [ ] Endpoints probados manualmente con Postman (login + happy-path).
- [ ] Documentación Swagger revisada (`/api/docs/`).
- [ ] PR con descripción + captura de Postman, review aprobada, checks en verde.

---

## 10. Problemas frecuentes

| Síntoma | Causa / Solución |
|---|---|
| `connection refused` / `password authentication failed for user "corralon"` | El contenedor no está levantado o hay otro PostgreSQL ocupando el 5432. `docker compose up -d`; si tenés Postgres local, apagalo o cambiá el puerto host en `docker-compose.yml`. |
| `relation "..." does not exist` | Faltan migraciones: `python manage.py migrate`. |
| `no such table` al correr `pytest` | Normal: pytest usa su propia base de test; revisá que `pytest.ini` tenga `DJANGO_SETTINGS_MODULE = config.settings`. |
| `error building wheel for psycopg` | Python sin ruedas para tu versión. Usá Python 3.12 o ajustá la versión de `psycopg[binary]` en `requirements.txt`. |
| `404` en `/api/scm/...` | El `include()` del módulo sigue comentado en `config/urls.py`, o el router no registra ese recurso. |
| `401 Unauthorized` en Postman | Falta el token o expiró: hacer login (o refresh). |
| Cambié `models.py` y no impacta | `python manage.py makemigrations <Modulo>` y `python manage.py migrate`. |
