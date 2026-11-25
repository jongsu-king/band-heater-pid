; Inno Setup 6 스크립트: 윈도우 설치 파일을 만든다.
;   먼저 PyInstaller 로 dist\HeaterLog\ 를 만든 뒤 (build_windows.bat 이 둘 다 한다)
;   ISCC.exe packaging\windows\installer.iss
;   결과: dist\Band-Heater-Logger-<버전>-windows-x64-setup.exe
; 버전은 dist\HeaterLog\HeaterLog.exe 의 파일 속성에서 읽는다 (heater_log.py 의 VERSION 과 같다).
; 기본은 지금 사용자용 설치라 관리자 권한이 필요 없다. 첫 화면에서 "모든 사용자용"을 고를 수 있다.
; 이 파일은 한글이 들어 있어 BOM 이 붙은 UTF-8 로 저장해야 한다.
#define AppName "Band Heater PID Logger"
#define AppExe "HeaterLog.exe"
#define Root SourcePath + "..\.."
#ifndef AppVersion
  #define AppVersion GetStringFileInfo(Root + "\dist\HeaterLog\" + AppExe, "ProductVersion")
#endif
#if AppVersion == ""
  #error dist\HeaterLog\HeaterLog.exe 가 없거나 버전 정보가 없습니다. PyInstaller 빌드를 먼저 하세요.
#endif
#define HaveKorean FileExists(CompilerPath + "Languages\Korean.isl")
#if HaveKorean
  #pragma message "Korean.isl found: the installer has Korean and English"
#else
  #pragma message "Korean.isl not found: the installer is English only"
#endif

[Setup]
AppId={{AED7B226-0390-4D06-9414-BBF97850FE7D}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=jongsu-king
AppPublisherURL=https://github.com/jongsu-king/band-heater-pid
AppSupportURL=https://github.com/jongsu-king/band-heater-pid/issues
AppUpdatesURL=https://github.com/jongsu-king/band-heater-pid/releases
DefaultDirName={autopf}\Band Heater PID Logger
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Root}\dist
OutputBaseFilename=Band-Heater-Logger-{#AppVersion}-windows-x64-setup
SetupIconFile={#Root}\packaging\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
LicenseFile={#Root}\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
ShowLanguageDialog=no
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
#if HaveKorean
Name: "ko"; MessagesFile: "compiler:Languages\Korean.isl"
#endif

[CustomMessages]
en.AppTitle=Band Heater PID Logger
en.NoWebView2=This program shows its window with the Microsoft Edge WebView2 Runtime, which was not found on this PC.%n%nWindows 11 and up-to-date Windows 10 already have it. Open the Microsoft download page now?
#if HaveKorean
ko.AppTitle=밴드 히터 PID 기록
ko.NoWebView2=이 프로그램은 Microsoft Edge WebView2 런타임으로 창을 띄우는데, 이 PC에서 찾지 못했습니다.%n%n윈도우 11과 최신 윈도우 10에는 이미 들어 있습니다. Microsoft 다운로드 페이지를 지금 열까요?
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; 새 버전을 덮어 설치할 때 이전 버전의 파일이 남지 않게 한다
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Root}\dist\HeaterLog\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{cm:AppTitle}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{cm:AppTitle}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{cm:AppTitle}}"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2: Boolean;
var
  V: String;
  K: String;
begin
  K := 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\' + K, 'pv', V) and (V <> '') and (V <> '0.0.0.0'))
         or (RegQueryStringValue(HKLM, 'SOFTWARE\' + K, 'pv', V) and (V <> '') and (V <> '0.0.0.0'))
         or (RegQueryStringValue(HKCU, 'Software\' + K, 'pv', V) and (V <> '') and (V <> '0.0.0.0'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Err: Integer;
begin
  if (CurStep = ssPostInstall) and (not WizardSilent) and (not HasWebView2) then
    if MsgBox(CustomMessage('NoWebView2'), mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://developer.microsoft.com/microsoft-edge/webview2/', '', '', SW_SHOWNORMAL, ewNoWait, Err);
end;
