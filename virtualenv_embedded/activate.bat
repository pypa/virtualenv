@echo off
::Print SET VIRTUAL_ENV with no new line and no trailing spaces
python -c "fd=open(\"%TEMP%\VirtEnv.bat\",\"w\");fd.write(\"SET VIRTUAL_ENV=\");fd.close()"
::add the absolute path of the parent directory to the set script
python -c "import os; print os.path.abspath(\"%~dp0\..\")">>%TEMP%\VirtEnv.bat
::call the set script
call %TEMP%\VirtEnv.bat
::delete the set script
del %TEMP%\VirtEnv.bat

if defined _OLD_VIRTUAL_PROMPT (
    set "PROMPT=%_OLD_VIRTUAL_PROMPT%"
) else (
    if not defined PROMPT (
        set "PROMPT=$P$G"
    )
	set "_OLD_VIRTUAL_PROMPT=%PROMPT%"	
)
set "PROMPT=(windows.x64) %PROMPT%"

if not defined _OLD_VIRTUAL_PYTHONHOME (
    set "_OLD_VIRTUAL_PYTHONHOME=%PYTHONHOME%"
)
set PYTHONHOME=

if defined _OLD_VIRTUAL_PATH (
    set "PATH=%_OLD_VIRTUAL_PATH%"
) else (
    set "_OLD_VIRTUAL_PATH=%PATH%"
)
set "PATH=%VIRTUAL_ENV%\Scripts;%PATH%"

:END
