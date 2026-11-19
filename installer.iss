; Inno Setup script for Secure Vault.
;
; Normally compiled by .\build.ps1, which builds main.dist\ with Nuitka first
; and passes the version in from core\version.py. You can also open this
; directly in the Inno Setup Compiler, provided main.dist\ already exists.
;
; Installs per-user (no admin needed). Vault, backups and settings live in
; %APPDATA%\SecureVault, so the install folder stays disposable: upgrading or
; uninstalling never touches user data.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "Secure Vault"
#define MyAppExeName "main.exe"
#define MyAppPublisher "Secure Vault"

[Setup]
; This GUID is what makes an install an *upgrade*. Windows matches installed
; products by AppId, so changing it would leave the old version installed
; alongside the new one, with two entries in Apps & features. Never change it.
AppId={{8F3C1E2A-9B4D-4C7E-A1F2-5E6D7C8B9A01}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={code:DefaultInstallDir}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=SecureVaultSetup
SetupIconFile=UI\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
; Upgrades: reuse the folder the previous version went to instead of asking
; again, and refuse to run two setups at once.
UsePreviousAppDir=yes
SetupMutex=SecureVaultSetup
; The app keeps running in the tray, where it holds this mutex (see
; core/single_instance.py). Without this, Setup would try to overwrite a
; running main.exe; with it, the user is asked to quit first.
AppMutex=Local\SecureVault_SingleInstance
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "main.dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; The app registers securevault:// itself at runtime (HKCU, no admin). Claiming
; the key here means uninstalling takes it away again, instead of leaving a
; protocol handler pointing at a deleted exe.
Root: HKCU; Subkey: "Software\Classes\securevault"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1';

function InstalledByThisSetup(): Boolean;
begin
  Result := RegKeyExists(HKEY_CURRENT_USER, UninstallKey);
end;

{ Find a copy that was put in place by hand (an unzipped main.dist\, say)
  rather than installed. The app registers the securevault:// handler with its
  own path, so that key is a reliable pointer to where it is running from. }
function HandPlacedInstallDir(): String;
var
  Command, Dir: String;
  Quote: Integer;
begin
  Result := '';
  if not RegQueryStringValue(HKEY_CURRENT_USER,
       'Software\Classes\securevault\shell\open\command', '', Command) then
    exit;
  { Command looks like:  "C:\somewhere\main.exe" "%1"  }
  if (Length(Command) > 0) and (Command[1] = '"') then
  begin
    Delete(Command, 1, 1);
    Quote := Pos('"', Command);
    if Quote > 0 then
      Command := Copy(Command, 1, Quote - 1);
  end;
  Dir := ExtractFileDir(Command);
  if (Dir <> '') and FileExists(AddBackslash(Dir) + '{#MyAppExeName}') then
    Result := Dir;
end;

{ Where to install by default. A previous install by this setup wins on its own
  (UsePreviousAppDir); this only helps the first time, so that upgrading a
  hand-placed copy replaces it instead of quietly installing a second one. }
function DefaultInstallDir(Param: String): String;
var
  Existing: String;
begin
  Result := ExpandConstant('{localappdata}\Programs\SecureVault');
  if InstalledByThisSetup() then
    exit;
  Existing := HandPlacedInstallDir();
  if Existing <> '' then
    Result := Existing;
end;

{ Upgrades are silent about the fact that the vault is untouched — say so, once,
  so nobody uninstalls "to reinstall cleanly" and panics about their accounts. }
function InitializeSetup(): Boolean;
var
  Previous, Existing: String;
begin
  Result := True;
  if RegQueryStringValue(HKEY_CURRENT_USER, UninstallKey, 'DisplayVersion', Previous) then
  begin
    if Previous <> '{#MyAppVersion}' then
      MsgBox('Secure Vault ' + Previous + ' is installed and will be updated to '
             + '{#MyAppVersion}.'#13#10#13#10
             + 'Your vault, backups and settings are kept — they live in'#13#10
             + ExpandConstant('{userappdata}\SecureVault') + #13#10
             + 'and are not touched by this update.', mbInformation, MB_OK);
  end
  else
  begin
    Existing := HandPlacedInstallDir();
    if Existing <> '' then
      MsgBox('A copy of Secure Vault was found in'#13#10
             + Existing + #13#10#13#10
             + 'It was not installed by this setup, so it will be replaced in '
             + 'that folder — check the destination on the next page.'#13#10#13#10
             + 'Your vault, backups and settings live in'#13#10
             + ExpandConstant('{userappdata}\SecureVault') + #13#10
             + 'and are not touched.', mbInformation, MB_OK);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    MsgBox('Secure Vault has been removed.'#13#10#13#10
           + 'Your vault and its backups were left in place, in'#13#10
           + ExpandConstant('{userappdata}\SecureVault') + #13#10#13#10
           + 'Delete that folder by hand if you really want the data gone.',
           mbInformation, MB_OK);
end;
