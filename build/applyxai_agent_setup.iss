; Inno Setup script — one installer ships GUI + CLI (required for automation runs).
; Build after both exes exist in dist\:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\applyxai_agent_setup.iss
; Output: dist\ApplyXAI-Agent-Setup.exe

#define MyAppName "ApplyXAI Agent"
#define MyAppVersion "1.1.3"
#define MyAppPublisher "ApplyXAI"
#define MyAppURL "https://applyxai.com"
#define MyAppGuiExe "ApplyXAI-Agent-GUI.exe"
#define MyAppCliExe "ApplyXAI-Agent.exe"

[Setup]
AppId={{A7B4E2C1-9F3D-4A8E-B5C6-1D2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\ApplyXAI\Agent
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=
OutputDir=..\dist
OutputBaseFilename=ApplyXAI-Agent-Setup
SetupIconFile=..\agent\branding\applyxai.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppGuiExe}
; Do not use Restart Manager — it shows "unable to close applications" when the agent is open.
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppGuiExe}"; DestDir: "{app}"; Flags: ignoreversion restartreplace uninsrestartdelete
Source: "..\dist\{#MyAppCliExe}"; DestDir: "{app}"; Flags: ignoreversion restartreplace uninsrestartdelete
[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppGuiExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppGuiExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[UninstallRun]
Filename: "taskkill"; Parameters: "/F /IM {#MyAppGuiExe} /T"; Flags: runhidden skipifdoesntexist
Filename: "taskkill"; Parameters: "/F /IM {#MyAppCliExe} /T"; Flags: runhidden skipifdoesntexist

[Code]
procedure StopAgentProcesses;
var
  ResultCode: Integer;
begin
  { Stop GUI/CLI quietly so install dir files can be replaced without Restart Manager dialogs. }
  Exec('taskkill', '/F /IM {#MyAppGuiExe} /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill', '/F /IM {#MyAppCliExe} /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(400);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  NeedsRestart := False;
  StopAgentProcesses;
end;

function InitializeSetup(): Boolean;
begin
  StopAgentProcesses;
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  UserData: String;
begin
  if CurStep = ssInstall then
    StopAgentProcesses;
  if CurStep = ssPostInstall then
  begin
    UserData := ExpandConstant('{localappdata}') + '\ApplyXAI\agent';
    ForceDirectories(UserData);
  end;
end;
