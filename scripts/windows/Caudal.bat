@echo off
rem Abre Caudal: Docker Desktop, pendrive, docker compose up y navegador.
rem La logica esta en caudal.ps1 (PowerShell). Doble clic para ejecutarlo.
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0caudal.ps1"
