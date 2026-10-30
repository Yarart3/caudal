@echo off
rem Restaura un backup de Caudal sobre una base vacia.
rem La logica esta en restaurar.ps1 (PowerShell). Doble clic para ejecutarlo.
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restaurar.ps1"
