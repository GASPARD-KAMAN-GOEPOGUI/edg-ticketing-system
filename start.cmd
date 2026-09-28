@echo off
REM start.cmd - lance EDG Connect (MySQL + backend + frontend) en mode reseau local.
REM Double-cliquable depuis l'explorateur : evite d'avoir a regler l'ExecutionPolicy
REM PowerShell, et fonctionne meme si le chemin du projet contient des espaces ou
REM des parentheses.
REM
REM Les arguments sont transmis tels quels a start.ps1, par exemple :
REM   start.cmd -IpAddress 192.168.1.25
REM   start.cmd -BackendPort 8001 -FrontendPort 3001

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
