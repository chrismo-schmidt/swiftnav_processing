@echo off
REM This script processes all .sbp files created by SWIFTNav in a given directory to RINEX. 

REM Define in-/output directories
SET "RINEX_OUT=rinex\bike" 
SET "SOLUTION_OUT=solution" 
SET "CORR_IN=correction_data"
SET "CWDIR=%CD%"


REM Check if the user provided an argument (the directory path)
IF "%~1"=="" (
    echo Usage: %0 [path_to_directory]
	echo 
	echo The given directory must contain a subdirectory [path_to_directory]\%CORR_IN% with one .conf file for the RTKLIB configuration and one .crx file with the base station correction data. 
    exit /b 1
)

REM Use the first argument as the directory containing .sbp files
SET "SBP_DIR=%~1"

REM Check if the directory exists
IF NOT EXIST "%SBP_DIR%" (
    echo Created driectory: %SBP_DIR%
    exit /b 1
)

REM Check if the correction data directory exists
IF NOT EXIST "%SBP_DIR%\%CORR_IN%" (
    echo The given directory must contain a subdirectory %CORR_IN%! Couldn't find %SBP_DIR%\%CORR_IN%
    exit /b 1
)

REM Check if the rtklib config file exists
IF NOT EXIST "%SBP_DIR%\%CORR_IN%\*.conf" (
    echo The correction data directory must contain an rtkpost config file! Couldn't find %SBP_DIR%\%CORR_IN%\*.conf
    exit /b 1
)

REM Check if the correction data file
IF NOT EXIST "%SBP_DIR%\%CORR_IN%\*.crx" (
    echo The correction data directory must contain an rtkpost config file! Couldn't find %SBP_DIR%\%CORR_IN%\*.conf
    exit /b 1
)

:: Create output directories
mkdir "%SBP_DIR%\%RINEX_OUT%"
mkdir "%SBP_DIR%\%SOLUTION_OUT%"

REM Change to the specified directory
cd /d "%SBP_DIR%"

REM Get the config filename
cd %CORR_IN%
FOR %%F IN (*.conf) DO (
	SET "CONF_FNAME=%%F"
	echo Found config file %CORR_IN%\%CONF_FNAME%
)

REM Get the correction data filename
FOR %%F IN (*.crx) DO (
	SET "CORR_FNAME=%%F"
	echo Found correction data file %CORR_IN%\%CORR_FNAME%
)
cd ..

REM Loop through each .sbp file in the directory
FOR %%F IN (*.sbp) DO (

	REM Get filename
	echo Processing file: %%~nF
	echo.

	echo Converting SBP to RINEX
    REM Execute the sbp2rinex command on the current file
    sbp2rinex "%%F" -d %RINEX_OUT%
	
	echo Applying RTK corrections
	REM Run postprocessing on the RINEX files
	rnx2rtkp -k %CORR_IN%\%CONF_FNAME% -o %SOLUTION_OUT%\%%~nF.pos %RINEX_OUT%\%%~nF.obs %CORR_IN%\*.crx %RINEX_OUT%\%%~nF.nav
	echo - pos output  : %SOLUTION_OUT%\%%~nF.pos
	echo.
)

cd /d "%CWDIR%"
echo Finished post-processing! The results can be found in %SBP_DIR%\%SOLUTION_OUT%



