#!/usr/bin/env bash
# Verifica que el esqueleto del backend "levanta" correctamente.
# Uso (desde la raiz del repo, con el venv y la DB de Docker arriba):
#   docker compose up -d
#   source .venv/bin/activate   # (Windows: .venv/Scripts/activate)
#   bash scripts/verificar_base.sh

set -u
cd "$(dirname "$0")/.."

PY=".venv/Scripts/python.exe"
[ -x "$PY" ] || PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"

ok=0; fail=0
step() {
  local nombre="$1"; shift
  printf '\n=== %s ===\n' "$nombre"
  if "$@"; then
    printf '[OK] %s\n' "$nombre"; ok=$((ok+1))
  else
    printf '[FALLA] %s\n' "$nombre"; fail=$((fail+1))
  fi
}

check_python()   { "$PY" --version; }
check_imports()  { "$PY" -c "import django, rest_framework, rest_framework_simplejwt, drf_spectacular, corsheaders, environ, psycopg; print('imports OK ->', 'Django', django.get_version())"; }
check_check()    { "$PY" manage.py check; }
check_nomig()    { "$PY" manage.py makemigrations --check --dry-run; }
check_db()       { "$PY" -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from django.db import connection; connection.ensure_connection(); print('DB OK ->', connection.vendor, connection.settings_dict['NAME'])"; }
check_migrate()  { "$PY" manage.py migrate --noinput; }
check_static()   { "$PY" manage.py collectstatic --noinput --dry-run >/dev/null; }
check_lint()     { "$PY" -m ruff check .; }

check_server() {
  local port=8129
  "$PY" manage.py runserver "$port" --noreload --skip-checks >/tmp/verificar_rs.log 2>&1 &
  local pid=$!
  sleep 5
  local rc=0
  for path in /api/schema/ /api/docs/ /admin/; do
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' -L "http://127.0.0.1:$port$path")
    echo "  $path -> HTTP $code"
    [ "$code" = "200" ] || rc=1
  done
  local login
  login=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:$port/api/auth/login/")
  echo "  POST /api/auth/login/ (sin body) -> HTTP $login"
  [ "$login" = "400" ] || rc=1
  kill "$pid" 2>/dev/null
  return $rc
}

step "Version de Python"                         check_python
step "Dependencias instaladas e importables"     check_imports
step "manage.py check"                           check_check
step "No hay migraciones pendientes de modelos"  check_nomig
step "Conexion a la base de datos"               check_db
step "migrate"                                   check_migrate
step "collectstatic (dry-run)"                   check_static
step "El servidor levanta y responde"            check_server
step "Lint (ruff)"                               check_lint

printf '\n----------------------------------------\n'
printf 'Resultado: %d OK / %d fallas\n' "$ok" "$fail"
[ "$fail" -eq 0 ] && { echo "La base esta sana. Lista para desarrollar."; exit 0; } || { echo "Revisa las fallas."; exit 1; }
