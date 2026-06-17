# Build Secure Vault end-to-end: compile the standalone folder build with
# Nuitka, then package it into installer\SecureVaultSetup.exe with Inno Setup.
#
# Folder builds (main.dist\) trip far fewer antivirus heuristics than --onefile.
# Requires: Inno Setup installed (https://jrsoftware.org/isdl.php).
# Set $env:ISCC to ISCC.exe if it's installed somewhere unusual.
$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

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
    --file-version=1.0.0.0 `
    --product-version=1.0.0.0 `
    --copyright="Secure Vault" `
    --assume-yes-for-downloads `
    --output-filename=main.exe `
    main.py

if (-not (Test-Path ".\main.dist\main.exe")) {
    Write-Host "ERROR: build did not produce main.dist\main.exe." -ForegroundColor Red
    exit 1
}

# --- Step 3: package main.dist\ into installer\SecureVaultSetup.exe. ---
Write-Host "Compiling installer ..."
& $iscc "installer.iss"
if ($LASTEXITCODE -eq 0) {
    Write-Host "`nInstaller created: installer\SecureVaultSetup.exe" -ForegroundColor Green
} else {
    Write-Host "`nInno Setup failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}
