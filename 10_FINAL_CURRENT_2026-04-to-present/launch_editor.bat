@echo off
rem Clears PYTHONHOME/PYTHONPATH (other software on show PCs can pollute them),
rem then runs the gameshow with the Python installed by install_gameshow.ps1.
set PYTHONHOME=
set PYTHONPATH=
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=%ProgramFiles%\Python312\python.exe"
if not exist "%PY%" set "PY=python"
cd /d "%~dp0"
"%PY%" "%~dp0question_editor.py"
