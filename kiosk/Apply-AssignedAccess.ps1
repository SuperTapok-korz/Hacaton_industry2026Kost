$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($identity.User.Value -ne "S-1-5-18") {
    throw "Запусти этот файл в PowerShell от имени SYSTEM по инструкции в kiosk/README.md."
}

$appPath = "C:\QostanaiProctor\QostanaiProctor.exe"
$configPath = Join-Path $PSScriptRoot "AssignedAccess.xml"
if (-not (Test-Path -LiteralPath $appPath)) {
    throw "Не найдено приложение: $appPath. Сначала распакуй сборку в C:\QostanaiProctor."
}
if (-not (Test-Path -LiteralPath $configPath)) {
    throw "Не найден файл конфигурации: $configPath"
}
if (-not (Get-LocalUser -Name "ProctorKiosk" -ErrorAction SilentlyContinue)) {
    throw "Создай стандартную локальную учётную запись ProctorKiosk до применения конфигурации."
}

$namespaceName = "root\cimv2\mdm\dmmap"
$className = "MDM_AssignedAccess"
$instance = Get-CimInstance -Namespace $namespaceName -ClassName $className
if (-not $instance) {
    throw "Windows не вернул объект Assigned Access. Проверь редакцию Windows и запусти PowerShell 64-разрядным."
}
if (-not [string]::IsNullOrWhiteSpace([string]$instance.Configuration)) {
    throw "На компьютере уже задан Assigned Access. Скрипт не будет перезаписывать его конфигурацию."
}

$xml = Get-Content -LiteralPath $configPath -Raw
$instance.Configuration = [System.Net.WebUtility]::HtmlEncode($xml)
$null = Set-CimInstance -CimInstance $instance -ErrorAction Stop
Write-Host "Киоск настроен для ProctorKiosk. Настройка включится при следующем входе этой учётной записи."
