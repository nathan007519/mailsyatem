@echo off
setlocal
cd /d "%~dp0"
set REPO=https://github.com/nathan007519/mailsyatem.git

echo.
echo === Push mail server project to %REPO% ===
echo Folder: %CD%
echo.

where git >nul 2>nul
if errorlevel 1 (
    echo Git is not installed. Download it from https://git-scm.com/download/win
    echo then run this file again.
    pause & exit /b 1
)

if not exist "main.py" (
    echo main.py not found here. Put this .bat inside the "mailapp" folder
    echo ^(the one containing main.py, mailcore.py and buildozer.spec^).
    pause & exit /b 1
)

rem --- keep junk out of the repo ---
if not exist ".gitignore" (
    (
        echo __pycache__/
        echo *.pyc
        echo .buildozer/
        echo bin/
    ) > .gitignore
)

rem --- git identity (only asked if not already set) ---
for /f "delims=" %%i in ('git config --global user.email 2^>nul') do set GITMAIL=%%i
if "%GITMAIL%"=="" (
    set /p GITNAME=Your name for commits: 
    set /p GITMAIL=Your email for commits: 
    git config --global user.name "%GITNAME%"
    git config --global user.email "%GITMAIL%"
)

if not exist ".git" git init
git checkout -B main >nul 2>nul

git add -A
git commit -m "Mail server Android app + APK build workflow" >nul 2>nul
if errorlevel 1 echo (nothing new to commit, continuing)

git remote remove origin >nul 2>nul
git remote add origin %REPO%

echo.
echo Pushing... (a browser window may open the first time to sign in to GitHub)
git push -u origin main
if errorlevel 1 (
    echo.
    echo Push was rejected. This usually means the repo already has files ^(e.g. a README^).
    set /p FORCE=Overwrite the repo contents with this project? ^(y/n^): 
    if /i "%FORCE%"=="y" (
        git push -u origin main --force
    ) else (
        echo Cancelled.
        pause & exit /b 1
    )
)

if errorlevel 1 (
    echo.
    echo Push failed. Check the message above ^(sign-in problem or repo name^).
    pause & exit /b 1
)

echo.
echo Done! Now open:
echo   https://github.com/nathan007519/mailsyatem/actions
echo and wait for "Build APK" to finish ^(about 30-40 min^), then download the artifact.
echo.
pause
