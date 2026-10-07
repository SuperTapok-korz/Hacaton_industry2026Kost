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
