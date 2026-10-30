@echo off
rem Cierra Caudal: copia final y docker compose down.
rem La logica esta en cerrar.ps1 (PowerShell). Doble clic para ejecutarlo.
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cerrar.ps1"
