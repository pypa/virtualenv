@echo off
goto Main

:GetVirtualEnvName
rem If the foldername of the virtual env contains a dot, (ex: .vip)
rem part of the foldername will end up in the extension part of the path.
rem Because of that, we'll combine the extension and name parts of the
rem path.
set PROMPT=(%~n1%~x1) %PROMPT%
goto :EOF

:Main
rem Set virtualenv Root
set VIRTUAL_ENV=%~dp0
if "%VIRTUAL_ENV:~-1%"=="\" set VIRTUAL_ENV=%VIRTUAL_ENV:~0,-1%
set VIRTUAL_ENV=%VIRTUAL_ENV:\Scripts=%

rem Reset to any old virtual environments.
if not defined PROMPT set PROMPT=$P$G
if defined _OLD_VIRTUAL_PROMPT set PROMPT=%_OLD_VIRTUAL_PROMPT%
if defined _OLD_VIRTUAL_PYTHONHOME set PYTHONHOME=%_OLD_VIRTUAL_PYTHONHOME%
set _OLD_VIRTUAL_PROMPT=%PROMPT%

rem Set up our prompt.
call :GetVirtualEnvName "%VIRTUAL_ENV%"

rem Backup old variables.
if defined PYTHONHOME (
     set _OLD_VIRTUAL_PYTHONHOME=%PYTHONHOME%
     set PYTHONHOME=
)

rem Check if we need to reset
if defined _OLD_VIRTUAL_PATH (
	set PATH=%_OLD_VIRTUAL_PATH%
	goto SKIPPATH
)
set _OLD_VIRTUAL_PATH=%PATH%

:SKIPPATH
setlocal
set BINDIR=%~dp0
if "%BINDIR:~-1%"=="\" set BINDIR=%BINDIR:~0,-1%
set PATH=%BINDIR%;%PATH%

rem Not really necessary, but clean up any blank entries.
endlocal & set PATH=%PATH:;;=;%
