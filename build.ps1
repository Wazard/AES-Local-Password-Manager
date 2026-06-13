# Build Secure Vault into a single standalone Windows .exe with Nuitka.
# Usage:  .\build.ps1
$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

& $python -m nuitka `
    --standalone --onefile `
    --enable-plugin=tk-inter `
    --include-module=pystray._win32 `
    --include-package=argon2 `
    --include-package-data=customtkinter `
    --include-data-files=UI/icon.ico=UI/icon.ico `
    --include-data-files=localization/locales.json=localization/locales.json `
    --windows-icon-from-ico=UI/icon.ico `
    --windows-console-mode=disable `
    --assume-yes-for-downloads `
    --output-filename=main.exe `
    main.py
