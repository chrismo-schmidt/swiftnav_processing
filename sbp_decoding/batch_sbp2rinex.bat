@echo off
REM This script processes all .sbp files in a specified directory using the sbp2rinex command. s
REM Define in-/output directories
SET "RINEX_OUT=rinex\bike" 
SET "CWDIR=%CD%"

REM Check if the user provided an argument (the directory path)
IF "%~1"=="" (
    echo Usage: %0 [path_to_directory]
    exit /b 1
)

REM Use the first argument as the directory containing .sbp files
SET "SBP_DIR=%~1"

REM Check if the directory exists
IF NOT EXIST "%SBP_DIR%" (
    echo Created driectory: %SBP_DIR%
    exit /b 1
)

:: Create output directory
mkdir "%SBP_DIR%\%RINEX_OUT%"

REM Change to the specified directory
cd /d "%SBP_DIR%"

REM Loop through each .sbp file in the directory
FOR %%F IN (*.sbp) DO (
    REM Execute the sbp2rinex command on the current file
    sbp2rinex "%%F" -d %RINEX_OUT%
)

cd /d %CWDIR%

