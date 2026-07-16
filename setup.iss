; Inno Setup script for mcat CAT tool
; Install Inno Setup from https://jrsoftware.org/isinfo.php
; Compile: ISCC.exe setup.iss

#define MyAppName "mcat"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "mcat <skarmohdi960@gmail.com>"
#define MyAppURL "https://github.com/skarmohdi2006/mcat"
#define MyAppExeName "mcat.exe"

[Setup]
; Identity — must stay the same across versions for updates
AppId={{8A2E5D3C-1F4B-4A9E-8C6D-7F3B2E5A1C9D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
LicenseFile=EULA.txt

; Install directory
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Update behaviour — reuse previous location silently on upgrades
UsePreviousAppDir=yes
UsePreviousGroup=yes
DisableDirPage=auto
; DisableReadyPage=auto  ; not supported in this Inno Setup version

; Version metadata for the installer itself
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer

; Output
OutputDir=.
OutputBaseFilename=mcat_setup
SetupIconFile=
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}

ShowLanguageDialog=no

; Auto-close running mcat before install/update/uninstall
CloseApplications=yes
CloseApplicationsFilter=*.exe

; Architecture
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "dist\mcat\mcat.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\mcat\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "EULA.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: postinstall nowait skipifsilent; WorkingDir: "{app}"

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c ""taskkill /f /im {#MyAppExeName} 2>nul"""; Flags: runhidden

[Code]
var
  WasUpdate: Boolean;

function InitializeSetup: Boolean;
var
  PrevVersion: String;
  PrevInstalled: Boolean;
begin
  Result := True;
  PrevInstalled := RegValueExists(HKEY_LOCAL_MACHINE,
    'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#emit SetupSetting("AppId")}_is1',
    'DisplayVersion');
  if not PrevInstalled then
    PrevInstalled := RegValueExists(HKEY_CURRENT_USER,
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#emit SetupSetting("AppId")}_is1',
      'DisplayVersion');
  WasUpdate := PrevInstalled;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if WasUpdate then
      Log('mcat updated successfully')
    else
      Log('mcat installed successfully');
  end;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := 0;
end;
