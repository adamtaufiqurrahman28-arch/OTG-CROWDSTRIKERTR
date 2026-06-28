@echo off
setlocal

REM ============================================================
REM Falcon Sensor CID Reinstall via RTR
REM
REM Parameter:
REM %1 = Destination CID
REM
REM Expected folder:
REM C:\ProgramData\CSMigration
REM   - migrate_falcon_sensor.bat
REM   - WindowsSensor.exe
REM   - CsUninstallTool.exe
REM ============================================================

set "DESTINATION_CID=%~1"

set "WORKDIR=C:\ProgramData\CSMigration"
set "INSTALLER=%WORKDIR%\WindowsSensor.exe"
set "UNINSTALLER=%WORKDIR%\CsUninstallTool.exe"
set "LOGFILE=%WORKDIR%\falcon_cid_reinstall.log"

if not exist "%WORKDIR%" (
    mkdir "%WORKDIR%"
)

echo ============================================================ >> "%LOGFILE%"
echo Falcon CID Reinstall Started: %date% %time% >> "%LOGFILE%"
echo Hostname: %COMPUTERNAME% >> "%LOGFILE%"
echo Destination CID: %DESTINATION_CID% >> "%LOGFILE%"
echo Workdir: %WORKDIR% >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"

if "%DESTINATION_CID%"=="" (
    echo [ERROR] Destination CID belum diisi. >> "%LOGFILE%"
    echo Usage: migrate_falcon_sensor.bat ^<DESTINATION_CID^> >> "%LOGFILE%"
    exit /b 1
)

if not exist "%INSTALLER%" (
    echo [ERROR] Installer tidak ditemukan: %INSTALLER% >> "%LOGFILE%"
    exit /b 1
)

if not exist "%UNINSTALLER%" (
    echo [ERROR] CsUninstallTool tidak ditemukan: %UNINSTALLER% >> "%LOGFILE%"
    exit /b 1
)

echo [INFO] OS Information: >> "%LOGFILE%"
wmic os get Caption,Version,OSArchitecture >> "%LOGFILE%" 2>&1

echo [INFO] Checking Falcon service before uninstall... >> "%LOGFILE%"
sc query CSFalconService >> "%LOGFILE%" 2>&1

echo [INFO] Starting Falcon Sensor uninstall... >> "%LOGFILE%"

"%UNINSTALLER%" /quiet >> "%LOGFILE%" 2>&1

set "UNINSTALL_EXIT_CODE=%ERRORLEVEL%"
echo [INFO] Uninstall exit code: %UNINSTALL_EXIT_CODE% >> "%LOGFILE%"

echo [INFO] Waiting 60 seconds before reinstall... >> "%LOGFILE%"
ping 127.0.0.1 -n 61 > nul

echo [INFO] Starting Falcon Sensor install to Destination CID... >> "%LOGFILE%"

"%INSTALLER%" /install /quiet /norestart CID=%DESTINATION_CID% GROUPING_TAGS="CID-Reinstall-RTR" >> "%LOGFILE%" 2>&1

set "INSTALL_EXIT_CODE=%ERRORLEVEL%"
echo [INFO] Install exit code: %INSTALL_EXIT_CODE% >> "%LOGFILE%"

echo [INFO] Waiting 90 seconds for Falcon service initialization... >> "%LOGFILE%"
ping 127.0.0.1 -n 91 > nul

echo [INFO] Checking Falcon service after install... >> "%LOGFILE%"
sc query CSFalconService >> "%LOGFILE%" 2>&1

echo ============================================================ >> "%LOGFILE%"
echo Falcon CID Reinstall Finished: %date% %time% >> "%LOGFILE%"
echo Validate host visibility from Destination CID. >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"

exit /b %INSTALL_EXIT_CODE%
