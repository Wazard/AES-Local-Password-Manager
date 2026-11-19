"""The app version, in one place.

`build.ps1` reads VERSION from this file and stamps it into both the compiled
exe's metadata and the installer, so the number shown in Windows' installed-apps
list, the exe properties and the login screen can't drift apart.
"""
VERSION = "1.3.0"
