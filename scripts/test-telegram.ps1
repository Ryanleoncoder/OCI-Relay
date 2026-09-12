#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Verifica se o token do bot e a allowlist do .env estão corretos.

.DESCRIPTION
    Lê as credenciais do .env — nunca por parâmetro. Segredo passado como
    argumento fica gravado em texto puro no histórico do PSReadLine
    (ConsoleHost_history.txt), fora do controle do .gitignore.

    Chama getMe para validar o token e, opcionalmente, envia uma mensagem
    de teste para o primeiro chat da allowlist.

.EXAMPLE
    ./scripts/test-telegram.ps1
    ./scripts/test-telegram.ps1 -Enviar
#>

param(
    [switch]$Enviar
)

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $raiz ".env"

if (-not (Test-Path $envPath)) {
    Write-Host "erro: .env nao encontrado em $envPath" -ForegroundColor Red
    Write-Host "      copie o .env.example e preencha." -ForegroundColor Red
    exit 1
}

# Parser mínimo de .env: ignora comentários e linhas vazias.
$config = @{}
foreach ($linha in Get-Content $envPath) {
    if ($linha -match '^\s*#' -or $linha -notmatch '=') { continue }
    $chave, $valor = $linha -split '=', 2
    $config[$chave.Trim()] = $valor.Trim().Trim('"').Trim("'")
}

$token = $config["TELEGRAM_BOT_TOKEN"]
if (-not $token) {
    Write-Host "erro: TELEGRAM_BOT_TOKEN vazio no .env" -ForegroundColor Red
    exit 1
}

# ── Valida o token ───────────────────────────────────────────────────────
try {
    $bot = (Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/getMe" `
                              -TimeoutSec 20).result
    Write-Host "token valido  -> @$($bot.username) (id $($bot.id))" -ForegroundColor Green
} catch {
    Write-Host "token INVALIDO -> $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ── Allowlist ────────────────────────────────────────────────────────────
$permitidos = @()
if ($config["TELEGRAM_ALLOWED_CHAT_IDS"]) {
    $permitidos = $config["TELEGRAM_ALLOWED_CHAT_IDS"] -split ',' |
                  ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

if ($permitidos.Count -eq 0) {
    Write-Host "allowlist     -> VAZIA: qualquer pessoa pode usar o bot" -ForegroundColor Yellow
} else {
    Write-Host "allowlist     -> $($permitidos -join ', ')" -ForegroundColor Green
}

# ── Comandos registrados ─────────────────────────────────────────────────
try {
    $cmds = (Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/getMyCommands" `
                               -TimeoutSec 20).result
    Write-Host "comandos      -> $($cmds.Count) registrados no menu" -ForegroundColor Green
} catch {
    Write-Host "comandos      -> falha ao consultar" -ForegroundColor Yellow
}

# ── Mensagem de teste ────────────────────────────────────────────────────
if (-not $Enviar) {
    Write-Host ""
    Write-Host "use -Enviar para mandar uma mensagem de teste." -ForegroundColor DarkGray
    exit 0
}

if ($permitidos.Count -eq 0) {
    Write-Host "sem chat na allowlist para enviar." -ForegroundColor Red
    exit 1
}

$corpo = @{
    chat_id = $permitidos[0]
    text    = "OCI Relay: teste de conectividade. Se voce leu isso, o bot esta funcionando."
} | ConvertTo-Json

try {
    $r = Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/sendMessage" `
                           -Method Post -Body $corpo `
                           -ContentType "application/json" -TimeoutSec 20
    Write-Host "mensagem enviada (message_id $($r.result.message_id))" -ForegroundColor Green
} catch {
    Write-Host "falha ao enviar: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "dica: voce precisa ter enviado /start ao bot pelo menos uma vez." -ForegroundColor Yellow
    exit 1
}
