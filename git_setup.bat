@echo off
setlocal
echo ===================================================
echo  Create GitHub repo and push (uses gh CLI)
echo ===================================================

set REPO=mea-backlog-tracker-from-pdfs-python

:: Make sure git and gh are installed
git --version >nul 2>&1
if not %errorlevel%==0 (
    echo Git is not installed. Get it from https://git-scm.com/download/win
    pause
    exit /b
)
gh --version >nul 2>&1
if not %errorlevel%==0 (
    echo GitHub CLI ^(gh^) is not installed. Get it from https://cli.github.com/
    pause
    exit /b
)

:: Remove any half-created repo from a previous attempt
if exist .git (
    echo Removing existing .git folder...
    rmdir /s /q .git
)

echo Initializing repository...
git init -b main
git add -A
git commit -m "Initial commit: KTU Grade Card Extractor"

echo.
echo Creating GitHub repo "%REPO%" and pushing...
gh repo create %REPO% --private --source=. --remote=origin --push

echo.
echo ===================================================
echo  Done. Repo: %REPO%
echo  (Created as PRIVATE. To make it public, run:
echo     gh repo edit --visibility public )
echo ===================================================
pause
