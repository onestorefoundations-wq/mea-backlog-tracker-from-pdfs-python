@echo off
setlocal
echo ===================================================
echo  Create GitHub repo and push (uses gh CLI, HTTPS)
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

:: Use HTTPS for git operations (avoids SSH publickey errors)
gh config set git_protocol https >nul 2>&1

:: Init repo + first commit if not already done
if not exist .git (
    echo Initializing repository...
    git init -b main
    git add -A
    git commit -m "Initial commit: KTU Grade Card Extractor"
) else (
    echo Repository already initialized. Staging any changes...
    git add -A
    git commit -m "Update" 2>nul
)

:: Resolve the GitHub account/owner for the HTTPS URL
for /f "delims=" %%u in ('gh api user --jq ".login" 2^>nul') do set OWNER=%%u
if "%OWNER%"=="" (
    echo Could not determine GitHub user. Are you logged in?  Run: gh auth login
    pause
    exit /b
)

:: Create the repo if it does not exist yet (ignore error if it already exists)
gh repo view %OWNER%/%REPO% >nul 2>&1
if not %errorlevel%==0 (
    echo Creating GitHub repo "%REPO%"...
    gh repo create %REPO% --private --source=. --remote=origin --disable-issues=false
)

:: Force the remote to HTTPS (overwrites any SSH remote from a previous run)
git remote remove origin >nul 2>&1
git remote add origin https://github.com/%OWNER%/%REPO%.git

echo Pushing to https://github.com/%OWNER%/%REPO% ...
git push -u origin main

echo.
echo ===================================================
echo  Done. Repo: https://github.com/%OWNER%/%REPO%
echo  (Created as PRIVATE. To make it public, run:
echo     gh repo edit --visibility public )
echo ===================================================
pause
