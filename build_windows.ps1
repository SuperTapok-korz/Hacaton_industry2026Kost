$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot "venv\Scripts\python.exe"
$model = Join-Path $projectRoot "yolov8n.pt"
$distDirectory = Join-Path $projectRoot "dist\QostanaiProctor"
$archive = Join-Path $projectRoot "dist\QostanaiProctor.zip"

if (-not (Test-Path $python)) {
    throw "Не найден Python в venv. Сначала создай окружение и установи requirements.txt по инструкции в README.md."
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
        "--noconfirm", "--windowed", "--onedir",
        "--name", "QostanaiProctor",
        "--collect-all", "mediapipe",
        "--collect-all", "matplotlib",
        "--collect-all", "ultralytics",
        "--collect-all", "torch",
        "--collect-all", "torchvision",
        "--hidden-import", "mediapipe.python._framework_bindings",
        "main.py"
    )
    Write-Host "Собираю приложение. Это может занять несколько минут и создать большой архив..."
    & $python -m PyInstaller @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Сборка PyInstaller завершилась с ошибкой." }

    Copy-Item -LiteralPath $model -Destination (Join-Path $distDirectory "yolov8n.pt") -Force
    if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
    Compress-Archive -Path (Join-Path $distDirectory "*") -DestinationPath $archive -CompressionLevel Optimal
    Write-Host "Готово: $archive"
    Write-Host "Папку reports приложение создаст отдельно для каждого пользователя в LocalAppData."
}
finally {
    Pop-Location
}
