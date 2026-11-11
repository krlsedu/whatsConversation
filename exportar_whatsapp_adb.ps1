# ==============================================================================
# Script PowerShell: Extracao ADB + Descriptografia (.crypt15) + Transcricao CscTracker AI
# Opera 100% dentro do diretorio corrente do projeto (.\dados_whatsapp)
# ==============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$Chave64Digitos = "",

    [Parameter(Mandatory=$false)]
    [string]$TelefoneContato = "",

    [Parameter(Mandatory=$false)]
    [string]$NomeContato = "Suelen Boff",

    [Parameter(Mandatory=$false)]
    [string]$MeuNome = "Carlos Eduardo",

    [Parameter(Mandatory=$false)]
    [string]$TokenCscTracker = ""
)

$ErrorActionPreference = "Stop"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"

if (-not (Test-Path $adb)) {
    Write-Error "ADB nao encontrado em: $adb. Verifique o caminho do Android SDK."
    exit 1
}

# Diretorio de trabalho criado dentro do diretorio corrente (sem usar C:\ raiz)
$BaseDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$PastaDados = Join-Path $BaseDir "dados_whatsapp"
$PastaRaw = Join-Path $PastaDados "raw_android"

New-Item -ItemType Directory -Force -Path $PastaRaw | Out-Null

Write-Host "1. Verificando dispositivo Android conectado via ADB..." -ForegroundColor Cyan
& $adb devices

# Detecta caminho do WhatsApp no aparelho
$baseWaPath = "/sdcard/Android/media/com.whatsapp/WhatsApp"
$checkPath = (& $adb shell "if [ -d '$baseWaPath/Databases' ]; then echo 'NEW'; elif [ -d '/sdcard/WhatsApp/Databases' ]; then echo 'OLD'; else echo 'NONE'; fi").Trim()

if ($checkPath -eq "OLD") {
    $baseWaPath = "/sdcard/WhatsApp"
} elseif ($checkPath -eq "NONE") {
    Write-Error "Pasta Databases do WhatsApp nao encontrada no aparelho. Verifique se fez o backup local no WhatsApp."
    exit 1
}

$crypt15Path = Join-Path $PastaRaw "msgstore.db.crypt15"
$sqlitePath = Join-Path $PastaDados "msgstore.db"

if (-not (Test-Path $crypt15Path)) {
    Write-Host "2. Copiando msgstore.db.crypt15 para .\dados_whatsapp\raw_android..." -ForegroundColor Cyan
    & $adb pull "$baseWaPath/Databases/msgstore.db.crypt15" $crypt15Path
} else {
    Write-Host "2. msgstore.db.crypt15 ja existe em .\dados_whatsapp\raw_android (pule ou apague para baixar novamente)." -ForegroundColor Yellow
}

$voiceNotesLocal = Join-Path $PastaRaw "WhatsApp Voice Notes"
if (-not (Test-Path $voiceNotesLocal)) {
    Write-Host "3. Copiando Notas de Voz (WhatsApp Voice Notes) para .\dados_whatsapp\raw_android..." -ForegroundColor Cyan
    & $adb pull "$baseWaPath/Media/WhatsApp Voice Notes" $voiceNotesLocal
} else {
    Write-Host "3. Pasta WhatsApp Voice Notes ja existe localmente." -ForegroundColor Yellow
}

$waAudioLocal = Join-Path $PastaRaw "WhatsApp Audio"
if (-not (Test-Path $waAudioLocal)) {
    Write-Host "4. Copiando Audios (WhatsApp Audio) para .\dados_whatsapp\raw_android..." -ForegroundColor Cyan
    & $adb pull "$baseWaPath/Media/WhatsApp Audio" $waAudioLocal
} else {
    Write-Host "4. Pasta WhatsApp Audio ja existe localmente." -ForegroundColor Yellow
}

$waImagesLocal = Join-Path $PastaRaw "WhatsApp Images"
if (-not (Test-Path $waImagesLocal)) {
    Write-Host "5. Copiando Imagens (WhatsApp Images) para .\dados_whatsapp\raw_android..." -ForegroundColor Cyan
    & $adb pull "$baseWaPath/Media/WhatsApp Images" $waImagesLocal
} else {
    Write-Host "5. Pasta WhatsApp Images ja existe localmente." -ForegroundColor Yellow
}

Write-Host "6. Garantindo dependencias Python (requests, wa-crypt-tools, reportlab, pillow)..." -ForegroundColor Cyan
python -m pip install --upgrade requests wa-crypt-tools reportlab pillow

if (-not (Test-Path $sqlitePath)) {
    if ([string]::IsNullOrWhiteSpace($Chave64Digitos)) {
        $Chave64Digitos = Read-Host "Digite a Chave de Criptografia de 64 digitos do WhatsApp (sem espacos)"
    }
    $ChaveLimpa = ($Chave64Digitos -replace "\s+", "").Trim()

    Write-Host "7. Descriptografando msgstore.db.crypt15 -> .\dados_whatsapp\msgstore.db..." -ForegroundColor Cyan
    wadecrypt $ChaveLimpa $crypt15Path $sqlitePath
} else {
    Write-Host "7. Banco .\dados_whatsapp\msgstore.db ja esta descriptografado." -ForegroundColor Green
}

if ([string]::IsNullOrWhiteSpace($TelefoneContato)) {
    $TelefoneContato = Read-Host "Digite os ultimos 8 ou 9 digitos do telefone da Suelen (ex: 999998888)"
}

if (-not [string]::IsNullOrWhiteSpace($TokenCscTracker)) {
    $env:TOKEN_CSCTRACKER = $TokenCscTracker
} elseif ([string]::IsNullOrWhiteSpace($env:TOKEN_CSCTRACKER)) {
    $inputToken = Read-Host "Digite seu TOKEN_CSCTRACKER (ou pressione Enter para gerar sem transcrever audios agora)"
    if (-not [string]::IsNullOrWhiteSpace($inputToken)) {
        $env:TOKEN_CSCTRACKER = $inputToken.Trim()
    }
}

$scriptPy = Join-Path $BaseDir "whatsapp_media_processor.py"
Write-Host "8. Executando whatsapp_media_processor.py (Extracao SQLite + Transcricao CscTracker AI + Geracao PDF)..." -ForegroundColor Cyan
python $scriptPy --db $sqlitePath --media-dir $PastaRaw --phone $TelefoneContato --contact-name $NomeContato --my-name $MeuNome --work-dir $PastaDados --pdf --verbose
