# Build Secure Vault end-to-end: compile the standalone folder build with
# Nuitka, then package it into installer\SecureVaultSetup.exe with Inno Setup.
#
# Folder builds (main.dist\) trip far fewer antivirus heuristics than --onefile.
# Requires: Inno Setup installed (https://jrsoftware.org/isdl.php).
# Set $env:ISCC to ISCC.exe if it's installed somewhere unusual.
#
#   .\build.ps1                        build everything
#   .\build.ps1 -SkipCompile           repackage the existing main.dist\
#   .\build.ps1 -Python C:\py\python.exe   build with a specific interpreter
param(
    [string]$Python,
    [switch]$SkipCompile
)
$ErrorActionPreference = "Stop"

function Find-Python {
    if ($Python) {
        if (-not (Test-Path $Python)) { throw "Python not found: $Python" }
        return $Python
    }
    # The project venv: here, or in a parent — so this also works from a git
    # worktree checked out inside the repo.
    $dir = (Get-Location).Path
    while ($dir) {
        $candidate = Join-Path $dir ".venv\Scripts\python.exe"
        if (Test-Path $candidate) { return $candidate }
        $dir = Split-Path -Parent $dir
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "No Python found. Create .venv, or pass -Python <path to python.exe>."
}

function Find-ISCC {
    if ($env:ISCC -and (Test-Path $env:ISCC)) { return $env:ISCC }

    $paths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
        "E:\Programs\Inno Setup 7\ISCC.exe",
        "E:\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($p in $paths) { if (Test-Path $p) { return $p } }

    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    # Scan the Uninstall registry for any installed Inno Setup.
    $roots = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    )
    foreach ($root in $roots) {
        Get-ChildItem $root -ErrorAction SilentlyContinue | ForEach-Object {
            $props = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
            if ($props.DisplayName -like "Inno Setup*" -and $props.InstallLocation) {
                $cand = Join-Path $props.InstallLocation "ISCC.exe"
                if (Test-Path $cand) { return $cand }
            }
        }
    }
    return $null
}

$python = Find-Python
Write-Host "Using Python: $python"

# One version for the exe metadata and the installer alike, so what Windows
# reports and what the login screen shows can't disagree.
$version = & $python -c "from core.version import VERSION; print(VERSION)"
if (-not $version) { throw "Could not read VERSION from core\version.py" }
$fileVersion = "$version.0"     # Windows file versions are four-part
Write-Host "Version: $version"

# --- Step 1: locate Inno Setup before the long Nuitka build, so a missing
# toolchain fails fast instead of after a multi-minute compile. ---
$iscc = Find-ISCC
if (-not $iscc) {
    Write-Host "ERROR: Inno Setup (ISCC.exe) not found." -ForegroundColor Red
    Write-Host "Install it from https://jrsoftware.org/isdl.php, or set `$env:ISCC to its path."
    exit 1
}
Write-Host "Using ISCC: $iscc"

# --- Step 2: compile the app into main.dist\ with Nuitka. ---
if ($SkipCompile -and (Test-Path ".\main.dist\main.exe")) {
    Write-Host "Skipping the Nuitka build, reusing main.dist\ ..."
} else {
    Write-Host "Building main.dist\ with Nuitka ..."
    & $python -m nuitka `
        --standalone `
        --enable-plugin=tk-inter `
        --include-module=pystray._win32 `
        --include-package=argon2 `
        --include-package-data=customtkinter `
        --include-data-files=UI/icon.ico=UI/icon.ico `
        --include-data-files=localization/locales.json=localization/locales.json `
        --include-data-dir=images=images `
        --windows-icon-from-ico=UI/icon.ico `
        --windows-console-mode=disable `
        --company-name="Secure Vault" `
        --product-name="Secure Vault" `
        --file-description="Secure Vault password manager" `
        --file-version=$fileVersion `
        --product-version=$fileVersion `
        --copyright="Secure Vault" `
        --assume-yes-for-downloads `
        --output-filename=main.exe `
        main.py

    if (-not (Test-Path ".\main.dist\main.exe")) {
        Write-Host "ERROR: build did not produce main.dist\main.exe." -ForegroundColor Red
        exit 1
    }
}

# --- Step 3: package main.dist\ into installer\SecureVaultSetup.exe. ---
Write-Host "Compiling installer ..."
& $iscc "/DMyAppVersion=$version" "installer.iss"
if ($LASTEXITCODE -eq 0) {
    $setup = ".\installer\SecureVaultSetup.exe"
    $mb = "{0:N1} MB" -f ((Get-Item $setup).Length / 1MB)
    Write-Host "`nInstaller created: $setup ($mb, version $version)" -ForegroundColor Green
    Write-Host "Installing it over an older version upgrades in place; the vault in %APPDATA%\SecureVault is untouched."
} else {
    Write-Host "`nInno Setup failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}
