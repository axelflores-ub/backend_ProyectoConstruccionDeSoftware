<#
    Verifica que el esqueleto del backend "levanta" correctamente.
    Pensado para correr una vez, después de seguir el README, para confirmar
    que la base está sana antes de que el equipo empiece a desarrollar.

    Uso (desde la raíz del repo, con el venv creado y la DB de Docker arriba):
        docker compose up -d
        .\.venv\Scripts\Activate.ps1
        .\scripts\verificar_base.ps1
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$ok = 0; $fail = 0
function Step($nombre, $accion) {
    Write-Host ("`n=== {0} ===" -f $nombre) -ForegroundColor Cyan
    try {
        & $accion
        Write-Host ("[OK] {0}" -f $nombre) -ForegroundColor Green
        $script:ok++
    } catch {
        Write-Host ("[FALLA] {0}: {1}" -f $nombre, $_.Exception.Message) -ForegroundColor Red
        $script:fail++
    }
}

Step "Version de Python" {
    & $py --version
}

Step "Dependencias instaladas e importables" {
    & $py -c "import django, rest_framework, rest_framework_simplejwt, drf_spectacular, corsheaders, environ, psycopg; print('imports OK ->', 'Django', django.get_version())"
    if ($LASTEXITCODE -ne 0) { throw "faltan dependencias: pip install -r requirements-dev.txt" }
}

Step "manage.py check (system checks)" {
    & $py manage.py check
    if ($LASTEXITCODE -ne 0) { throw "system checks con errores" }
}

Step "No hay migraciones pendientes de modelos" {
    & $py manage.py makemigrations --check --dry-run
    if ($LASTEXITCODE -ne 0) { throw "hay cambios de modelos sin migrar (esperado 'No changes detected' en el esqueleto)" }
}

Step "Conexion a la base de datos" {
    & $py -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from django.db import connection; connection.ensure_connection(); print('DB OK ->', connection.vendor, connection.settings_dict['NAME'])"
    if ($LASTEXITCODE -ne 0) { throw "no se puede conectar a la DB. Revisa que 'docker compose up -d' este corriendo y el DATABASE_URL del .env" }
}

Step "migrate (aplica migraciones internas de Django)" {
    & $py manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw "migrate fallo" }
}

Step "collectstatic (dry-run)" {
    & $py manage.py collectstatic --noinput --dry-run | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0) { throw "collectstatic fallo" }
}

Step "El servidor levanta y responde" {
    $port = 8129
    $proc = Start-Process -FilePath $py -ArgumentList "manage.py runserver $port --noreload --skip-checks" -PassThru -WindowStyle Hidden
    try {
        Start-Sleep -Seconds 5
        $rutas = @(
            @{ url = "http://127.0.0.1:$port/api/schema/"; esperado = 200 },
            @{ url = "http://127.0.0.1:$port/api/docs/";   esperado = 200 },
            @{ url = "http://127.0.0.1:$port/admin/";      esperado = 200 }  # 302 -> redirige a login (200 tras follow)
        )
        foreach ($r in $rutas) {
            $resp = Invoke-WebRequest -UseBasicParsing -Uri $r.url -MaximumRedirection 5
            Write-Host ("  {0} -> HTTP {1}" -f $r.url, $resp.StatusCode)
            if ($resp.StatusCode -ne $r.esperado) { throw ("{0} devolvio {1}" -f $r.url, $resp.StatusCode) }
        }
        # Login JWT: sin body debe responder 400 (endpoint vivo), no 404/500
        try {
            Invoke-WebRequest -UseBasicParsing -Method Post -Uri "http://127.0.0.1:$port/api/auth/login/" -Body "{}" -ContentType "application/json" | Out-Null
            $code = 200
        } catch {
            $code = [int]$_.Exception.Response.StatusCode
        }
        Write-Host ("  POST /api/auth/login/ (sin body) -> HTTP {0}" -f $code)
        if ($code -ne 400) { throw "el endpoint de login no esta respondiendo como se espera (HTTP $code)" }
    } finally {
        if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
    }
}

Step "Lint (ruff)" {
    & $py -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "ruff encontro problemas" }
}

Write-Host ("`n----------------------------------------")
Write-Host ("Resultado: {0} OK / {1} fallas" -f $ok, $fail) -ForegroundColor ($(if ($fail -eq 0) { "Green" } else { "Red" }))
if ($fail -eq 0) {
    Write-Host "La base esta sana. Lista para desarrollar." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Revisa las fallas de arriba." -ForegroundColor Red
    exit 1
}
