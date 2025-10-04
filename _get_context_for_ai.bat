@echo off
setlocal enabledelayedexpansion

:: Ask user for file extensions
set /p extensions="Enter file extensions you want to send in context (space separated, e.g. py txt c cpp kt java): "

:: Ask user for excluded file names
set /p exclude="Enter exact file names to exclude (space separated, e.g. main.py config.json Readme.md): "

:: Convert exclude list into something easier to check
set "excludelist= %exclude% "

:: Output file
set outputfile=all_code_context.txt
> "%outputfile%" echo ==== Combined code files ====
echo Searching for: %extensions%
echo Excluding: %exclude%
echo Output will be in "%outputfile%"
echo.

:: Loop over each extension
for %%e in (%extensions%) do (
    echo --- Extension: %%e ---
    for /r %%f in (*.%%e) do (
        set "filename=%%~nxf"
        set "foldername=%%~pnf"

        set "skipfile=false"

        :: Skip if file or any folder in its path starts with "."
        echo !foldername! | findstr /r "\\\.[^\\]*" >nul && set "skipfile=true"
        if "!filename:~0,1!"=="." set "skipfile=true"

        :: Check if filename is in the exclusion list
        if "!skipfile!"=="false" (
            echo "!excludelist!" | findstr /i " !filename! " >nul
            if not errorlevel 1 (
                echo Skipping excluded file: %%f
                set "skipfile=true"
            )
        )

        if "!skipfile!"=="true" (
            rem Do nothing for this file
        ) else (
            echo ==== FILE: %%f ==== >> "%outputfile%"
            type "%%f" >> "%outputfile%"
            echo. >> "%outputfile%"
            echo. >> "%outputfile%"
        )
    )
)

echo Done! All matching files combined into "%outputfile%"
pause
