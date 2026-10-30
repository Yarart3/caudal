@echo off
rem Cambia la contrasena de un usuario de Caudal.
rem La logica esta en restablecer.ps1 (PowerShell). Doble clic para ejecutarlo.
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restablecer.ps1"
