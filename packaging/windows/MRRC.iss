#define MyAppName "MRRC"
#define MyAppVersion "5.8.4"
#define MyAppPublisher "cheenle"
#define MyAppURL "https://github.com/cheenle/mrrc"
#define MyAppServerName "MRRC-Server.exe"
#define MyAppLauncherName "MRRC-Launcher.exe"
#define MyAppProxyName "ATR1000-Proxy.exe"

[Setup]
AppId={{7E8E8ED8-4FB3-525F-C65A-25FAF767E3F4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\MRRC
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\windows
OutputBaseFilename=MRRC-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\..\dist\windows\MRRC\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppLauncherName}"
Name: "{group}\{#MyAppName} Server"; Filename: "{app}\{#MyAppServerName}"
Name: "{group}\{#MyAppName} ATR1000 Proxy"; Filename: "{app}\{#MyAppProxyName}"
Name: "{group}\Edit Configuration"; Filename: "notepad.exe"; Parameters: """{localappdata}\MRRC\MRRC.conf"""
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppLauncherName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppLauncherName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Messages]
FinishedHeadingLabel=Completing {#MyAppName} Setup
FinishedLabel=Setup has finished installing {#MyAppName} on your computer.%n%nLaunch "{#MyAppName}" from the Start Menu to start the server and open the web UI.%n%nEdit %LOCALAPPDATA%\MRRC\MRRC.conf to set your serial port (e.g. COM3) and radio model.
