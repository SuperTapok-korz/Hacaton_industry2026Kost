$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($identity.User.Value -ne "S-1-5-18") {
    throw "Запусти этот файл в PowerShell от имени SYSTEM по инструкции в kiosk/README.md."
}

$namespaceName = "root\cimv2\mdm\dmmap"
$className = "MDM_AssignedAccess"
$instance = Get-CimInstance -Namespace $namespaceName -ClassName $className
if (-not $instance) {
    throw "Windows не вернул объект Assigned Access."
}
$instance.Configuration = $null
$null = Set-CimInstance -CimInstance $instance -ErrorAction Stop
Write-Host "Конфигурация Assigned Access удалена. Выйди из ProctorKiosk и войди в свою обычную учётную запись."
