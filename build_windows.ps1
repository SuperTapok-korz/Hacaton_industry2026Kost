$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot "venv\Scripts\python.exe"
$model = Join-Path $projectRoot "yolov8n.pt"
$distDirectory = Join-Path $projectRoot "dist\QostanaiProctor"
$archive = Join-Path $projectRoot "dist\QostanaiProctor.zip"
$installer = Join-Path $projectRoot "dist\QostanaiProctorSetup.exe"
$csharpCompiler = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$installerSource = Join-Path $projectRoot "installer\SetupLauncher.cs"

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

    if (-not (Test-Path $csharpCompiler)) {
        throw "Не найден компилятор C#, необходимый для создания установщика."
    }
    if (Test-Path $installer) { Remove-Item -LiteralPath $installer -Force }
    $compileArgs = @(
        "/nologo", "/target:winexe", "/optimize+", "/codepage:65001",
        "/reference:System.Windows.Forms.dll",
        "/reference:System.IO.Compression.dll",
        "/resource:$archive,QostanaiProctor.zip",
        "/out:$installer", $installerSource
    )
    Write-Host "Собираю единый установщик Windows..."
    & $csharpCompiler @compileArgs
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $installer)) {
        throw "Не получилось собрать установщик."
    }
    Write-Host "Готово: $installer"
    Write-Host "Установщик проверяет свободное место, распаковывает приложение напрямую, создаёт ярлыки и запускает его."
}
finally {
    Pop-Location
}
