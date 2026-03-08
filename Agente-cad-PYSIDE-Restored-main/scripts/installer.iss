#define MyAppName "AgenteCAD"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "VisionEstrutural"
#define MyAppURL "https://visionestrutural.com.br"
#define MyAppExeName "main.exe"
#ifndef OutputBaseFilename
  #define OutputBaseFilename "AgenteCAD_Setup_v1.0.0"
#endif

[Setup]
; Basic Information
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/suporte
AppUpdatesURL={#MyAppURL}/downloads

; Installation Directory
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
; "ArchitecturesInstallIn64BitMode=x64" ensures it installs to Program Files (not x86) on 64-bit systems
ArchitecturesInstallIn64BitMode=x64

; Output
OutputDir=..\releases
OutputBaseFilename={#OutputBaseFilename}
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Admin privileges required for writing to Program Files
PrivilegesRequired=admin

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The main executable and all dependencies
Source: "..\dist\AgenteCAD\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: synchronizing "dist/AgenteCAD" ensures we get the Nuitka bundle + keys + Tufup metadata

[Icons]
Name: "{autoprograms}\AgenteCAD"; Filename: "{app}\main.exe"; IconFilename: "{app}\assets\icon.ico"
Name: "{autodesktop}\AgenteCAD"; Filename: "{app}\main.exe"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon
Name: "{autoprograms}\AgenteCAD Update"; Filename: "{app}\update.exe"; IconFilename: "{app}\assets\icon.ico"

[Run]
Filename: "{app}\main.exe"; Description: "{cm:LaunchProgram,AgenteCAD}"; Flags: nowait postinstall skipifsilent
