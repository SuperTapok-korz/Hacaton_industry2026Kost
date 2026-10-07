$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot "venv\Scripts\python.exe"
$model = Join-Path $projectRoot "yolov8n.pt"
$distDirectory = Join-Path $projectRoot "dist\QostanaiProctor"
$archive = Join-Path $projectRoot "dist\QostanaiProctor.zip"
$installer = Join-Path $projectRoot "dist\QostanaiProctorSetup.exe"
$iexpress = Join-Path $env:WINDIR "System32\iexpress.exe"

if (-not (Test-Path $python)) {
    throw "Не найден Python в venv. Сначала создай окружение и установи requirements.txt по инструкции в README.md."
}
if (-not (Test-Path $iexpress)) {
    throw "В Windows не найдена штатная программа IExpress для сборки установщика."
}

Push-Location $projectRoot
try {
    if (-not (Test-Path $model)) {
        Write-Host "Скачиваю модель YOLOv8n (для этого нужен интернет)..."
        & $python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
        if ($LASTEXITCODE -ne 0) {
            throw "Не получилось скачать yolov8n.pt. Запусти приложение с интернетом, затем повтори сборку."
        }
    }

    Write-Host "Закрепляю совместимую версию Qt для сборки..."
    & $python -m pip install --force-reinstall "PySide6==6.8.3"
    if ($LASTEXITCODE -ne 0) { throw "Не удалось установить совместимую версию PySide6." }

    Write-Host "Устанавливаю PyInstaller в виртуальное окружение..."
    & $python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "Не удалось установить PyInstaller." }

    $buildArgs = @(
        "--noconfirm", "--clean", "--windowed", "--onedir",
        "--name", "QostanaiProctor",
        "--collect-all", "mediapipe",
        "--collect-all", "matplotlib",
        "--collect-all", "ultralytics",
        "--collect-all", "torch",
        "--collect-all", "torchvision",
        "--hidden-import", "mediapipe.python._framework_bindings",
        "--hidden-import", "keyboard",
        "main.py"
    )
    Write-Host "Собираю приложение. Это может занять несколько минут и создать большой архив..."
    if (Test-Path $distDirectory) { Remove-Item -LiteralPath $distDirectory -Recurse -Force }
    & $python -m PyInstaller @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Сборка PyInstaller завершилась с ошибкой." }

    Copy-Item -LiteralPath $model -Destination (Join-Path $distDirectory "yolov8n.pt") -Force
    if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
    Compress-Archive -Path (Join-Path $distDirectory "*") -DestinationPath $archive -CompressionLevel Optimal

    $setupDirectory = Join-Path $projectRoot "installer"
    $setupCommand = Join-Path $setupDirectory "Install-QostanaiProctor.cmd"
    $sedPath = Join-Path $setupDirectory "QostanaiProctor.sed"
    New-Item -ItemType Directory -Path $setupDirectory -Force | Out-Null
    @'
@echo off
setlocal
set "APP_HOME=%LOCALAPPDATA%\Programs\QostanaiProctor"
if not exist "%LOCALAPPDATA%\Programs" mkdir "%LOCALAPPDATA%\Programs"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%~dp0QostanaiProctor.zip' -DestinationPath '%APP_HOME%' -Force"
if errorlevel 1 (
  echo Installation failed. Check free disk space and try again.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Qostanai Proctor.lnk'); $s.TargetPath='%APP_HOME%\QostanaiProctor.exe'; $s.WorkingDirectory='%APP_HOME%'; $s.Save(); $m=[Environment]::GetFolderPath('Programs'); $d=Join-Path $m 'Qostanai Proctor'; New-Item -ItemType Directory -Path $d -Force | Out-Null; $s=$w.CreateShortcut((Join-Path $d 'Qostanai Proctor.lnk')); $s.TargetPath='%APP_HOME%\QostanaiProctor.exe'; $s.WorkingDirectory='%APP_HOME%'; $s.Save()"
if errorlevel 1 (
  echo The app is installed, but shortcut creation failed.
  pause
  exit /b 1
)
start "" "%APP_HOME%\QostanaiProctor.exe"
exit /b 0
'@ | Set-Content -LiteralPath $setupCommand -Encoding ASCII

    $sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=1
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=%AdminQuietInstCmd%
UserQuietInstCmd=%UserQuietInstCmd%
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$setupDirectory\
SourceFiles1=$projectRoot\dist\
[SourceFiles0]
%FILE0%=
[SourceFiles1]
%FILE1%=
[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$installer
FriendlyName=Qostanai Proctor
AppLaunched=cmd.exe /c Install-QostanaiProctor.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
FILE0="Install-QostanaiProctor.cmd"
FILE1="QostanaiProctor.zip"
"@
    Set-Content -LiteralPath $sedPath -Value $sed -Encoding ASCII
    if (Test-Path $installer) { Remove-Item -LiteralPath $installer -Force }
    Write-Host "Собираю установщик Windows. Он будет большим из-за распознавания лица и YOLO..."
    & $iexpress /N /Q /M $sedPath
    if (-not (Test-Path $installer) -or (Get-Item $installer).Length -lt 10000000) {
        throw "IExpress не смог создать установщик. Переносимая папка и ZIP уже собраны."
    }
    Write-Host "Готово: $installer"
    Write-Host "При установке файлы помещаются в LocalAppData текущего пользователя, создаются ярлыки и запускается приложение."
}
finally {
    Pop-Location
}
