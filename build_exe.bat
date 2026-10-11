@echo off
chcp 65001 >nul
REM Сборка WordSnap: Portable ZIP и инсталлятор Windows Setup.exe
where py >nul 2>nul && (set PY=py) || (set PY=python)

echo ==========================================================
echo  Сборка WordSnap (Portable ZIP + Windows Setup.exe)
echo ==========================================================
%PY% -X utf8 build_dist.py
if errorlevel 1 (
  echo [ERROR] Сборка завершилась с ошибкой.
  pause & exit /b 1
)

echo.
echo ==========================================================
echo  Сборка успешно завершена! Файлы лежат в папке release\
echo ==========================================================
explorer "%CD%\release"
pause
