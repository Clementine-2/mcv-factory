Unicode True
RequestExecutionLevel user
SetCompressor /SOLID lzma
CRCCheck on
ShowInstDetails show
ShowUninstDetails show

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "nsDialogs.nsh"

!define PRODUCT_NAME "基地车生产厂"
!define PRODUCT_VERSION "0.14.30"
!define PRODUCT_UX "UX5.1 Fluent"
!define PRODUCT_PUBLISHER "Base Vehicle Factory"
!define PRODUCT_REGKEY "Software\ProjectFactory"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProjectFactory"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION} · ${PRODUCT_UX}"
OutFile "dist\ProjectFactory-Setup-${PRODUCT_VERSION}-UX5.1.exe"
InstallDir "$LOCALAPPDATA\Programs\ProjectFactory"
InstallDirRegKey HKCU "${PRODUCT_REGKEY}" "InstallDir"
BrandingText "基地车生产厂 · Fluent / WPF UI / NSIS"

!define MUI_ICON "..\shell\Assets\app.ico"
!define MUI_UNICON "..\shell\Assets\app.ico"
!define MUI_ABORTWARNING
!define MUI_LANGDLL_REGISTRY_ROOT "HKCU"
!define MUI_LANGDLL_REGISTRY_KEY "${PRODUCT_REGKEY}"
!define MUI_LANGDLL_REGISTRY_VALUENAME "InstallerLanguage"
!define MUI_WELCOMEPAGE_TITLE "安装 基地车生产厂"
!define MUI_WELCOMEPAGE_TEXT "这将安装 基地车生产厂 ${PRODUCT_VERSION} · ${PRODUCT_UX}。$\r$\n$\r$\n正式界面采用 .NET 10 + WPF UI 的 Windows 11 Fluent/Mica 桌面壳；Python 只作为隔离的业务 Core，不再负责绘制 GUI。$\r$\n$\r$\n默认按当前用户安装，不需要管理员权限。"
!define MUI_FINISHPAGE_TITLE "基地车生产厂 已准备就绪"
!define MUI_FINISHPAGE_TEXT "Fluent 桌面壳和 Python Core 运行时已经安装并验证。用户设置、历史、日志与项目资产不放在程序目录内，卸载默认保留。"
!define MUI_FINISHPAGE_RUN "$INSTDIR\app\ProjectFactory.exe"
!define MUI_FINISHPAGE_RUN_TEXT "启动 基地车生产厂"
!define MUI_FINISHPAGE_NOREBOOTSUPPORT

Var StartMenuFolder
Var PythonExe
Var PythonArgs
Var SourceControl
Var ConnectionControl
Var ProxyControl
Var DesktopControl
Var SourceKey
Var ConnectionKey
Var CustomProxy
Var DesktopShortcut

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
Page custom RuntimeOptionsCreate RuntimeOptionsLeave
!define MUI_STARTMENUPAGE_DEFAULTFOLDER "基地车生产厂"
!define MUI_STARTMENUPAGE_REGISTRY_ROOT HKCU
!define MUI_STARTMENUPAGE_REGISTRY_KEY "${PRODUCT_REGKEY}"
!define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "StartMenuFolder"
!insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_RESERVEFILE_LANGDLL

Function .onInit
  !insertmacro MUI_LANGDLL_DISPLAY
  StrCpy $SourceKey "auto"
  StrCpy $ConnectionKey "direct"
  StrCpy $CustomProxy ""
  StrCpy $DesktopShortcut "0"
  Call LocatePython
FunctionEnd

Function LocatePython
  StrCpy $PythonExe ""
  StrCpy $PythonArgs ""

  SearchPath $0 "py.exe"
  ${If} $0 != ""
    nsExec::ExecToStack /TIMEOUT=20000 '"$0" -3 -c "import sys,struct; raise SystemExit(0 if sys.version_info >= (3,11) and struct.calcsize(chr(80))*8 == 64 else 9)"'
    Pop $1
    Pop $2
    ${If} $1 == "0"
      StrCpy $PythonExe "$0"
      StrCpy $PythonArgs "-3"
      Return
    ${EndIf}
  ${EndIf}

  SearchPath $0 "python.exe"
  ${If} $0 != ""
    nsExec::ExecToStack /TIMEOUT=20000 '"$0" -c "import sys,struct; raise SystemExit(0 if sys.version_info >= (3,11) and struct.calcsize(chr(80))*8 == 64 else 9)"'
    Pop $1
    Pop $2
    ${If} $1 == "0"
      StrCpy $PythonExe "$0"
      StrCpy $PythonArgs ""
      Return
    ${EndIf}
  ${EndIf}

  MessageBox MB_ICONSTOP|MB_OK "未找到可用的 64 位 Python 3.11+。$\r$\n$\r$\n基地车生产厂 的业务 Core 使用隔离 Python 运行时，但需要一个标准 64 位 Python 3.11 或更新版本作为 venv 基础。UX5 不再要求 tkinter。"
  Abort
FunctionEnd

Function RuntimeOptionsCreate
  !insertmacro MUI_HEADER_TEXT "Python Core 运行时" "选择首次准备 Core 依赖时使用的包源与连接方式。"
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 2u 100% 26u "推荐默认：自动镜像池 + 强制直连。失败时自动切换镜像并有限重试。WPF/.NET 桌面壳已经随安装包部署，不经过 PyPI。"
  Pop $0

  ${NSD_CreateLabel} 0 36u 28% 12u "Python 包源"
  Pop $0
  ${NSD_CreateDropList} 30% 32u 70% 110u ""
  Pop $SourceControl
  ${NSD_CB_AddString} $SourceControl "自动镜像池（推荐）"
  ${NSD_CB_AddString} $SourceControl "清华 TUNA"
  ${NSD_CB_AddString} $SourceControl "北外 BFSU"
  ${NSD_CB_AddString} $SourceControl "中科大 USTC"
  ${NSD_CB_AddString} $SourceControl "阿里云"
  ${NSD_CB_AddString} $SourceControl "华为云"
  ${NSD_CB_AddString} $SourceControl "官方 PyPI"
  ${NSD_CB_SelectStringExact} $SourceControl "自动镜像池（推荐）"

  ${NSD_CreateLabel} 0 66u 28% 12u "连接方式"
  Pop $0
  ${NSD_CreateDropList} 30% 62u 70% 110u ""
  Pop $ConnectionControl
  ${NSD_CB_AddString} $ConnectionControl "强制直连（忽略代理）"
  ${NSD_CB_AddString} $ConnectionControl "当前系统/代理配置"
  ${NSD_CB_AddString} $ConnectionControl "自定义代理"
  ${NSD_CB_SelectStringExact} $ConnectionControl "强制直连（忽略代理）"

  ${NSD_CreateLabel} 0 96u 28% 12u "自定义代理"
  Pop $0
  ${NSD_CreateText} 30% 92u 70% 14u ""
  Pop $ProxyControl

  ${NSD_CreateCheckbox} 0 128u 100% 16u "创建桌面快捷方式"
  Pop $DesktopControl
  ${NSD_Uncheck} $DesktopControl

  ${NSD_CreateLabel} 0 158u 100% 34u "隐私提示：代理 URL 中的凭据只通过当前安装进程临时传给 bootstrap，不写注册表；应用设置也不会保存 API key，只保存环境变量名称。"
  Pop $0

  nsDialogs::Show
FunctionEnd

Function RuntimeOptionsLeave
  ${NSD_GetText} $SourceControl $0
  ${If} $0 == "清华 TUNA"
    StrCpy $SourceKey "tuna"
  ${ElseIf} $0 == "北外 BFSU"
    StrCpy $SourceKey "bfsu"
  ${ElseIf} $0 == "中科大 USTC"
    StrCpy $SourceKey "ustc"
  ${ElseIf} $0 == "阿里云"
    StrCpy $SourceKey "aliyun"
  ${ElseIf} $0 == "华为云"
    StrCpy $SourceKey "huawei"
  ${ElseIf} $0 == "官方 PyPI"
    StrCpy $SourceKey "pypi"
  ${Else}
    StrCpy $SourceKey "auto"
  ${EndIf}

  ${NSD_GetText} $ConnectionControl $0
  ${If} $0 == "当前系统/代理配置"
    StrCpy $ConnectionKey "current"
  ${ElseIf} $0 == "自定义代理"
    StrCpy $ConnectionKey "custom"
  ${Else}
    StrCpy $ConnectionKey "direct"
  ${EndIf}

  ${NSD_GetText} $ProxyControl $CustomProxy
  ${If} $ConnectionKey == "custom"
    ${If} $CustomProxy == ""
      MessageBox MB_ICONEXCLAMATION|MB_OK "选择了自定义代理，但代理地址为空。"
      Abort
    ${EndIf}
  ${EndIf}

  ${NSD_GetState} $DesktopControl $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $DesktopShortcut "1"
  ${Else}
    StrCpy $DesktopShortcut "0"
  ${EndIf}
FunctionEnd

Function PrepareRuntime
  DetailPrint "准备 基地车生产厂 Python Core 隔离运行时..."
  DetailPrint "包源=$SourceKey；连接=$ConnectionKey"

  ${If} $ConnectionKey == "custom"
    System::Call 'Kernel32::SetEnvironmentVariable(t, t)i("PROJECT_FACTORY_SETUP_PROXY", "$CustomProxy").r0'
  ${Else}
    System::Call 'Kernel32::SetEnvironmentVariable(t, t)i("PROJECT_FACTORY_SETUP_PROXY", "").r0'
  ${EndIf}

  ${If} $PythonArgs == ""
    nsExec::ExecToLog /TIMEOUT=1200000 '"$PythonExe" "$INSTDIR\bootstrap_windows.py" --prepare-only --source $SourceKey --connection $ConnectionKey'
  ${Else}
    nsExec::ExecToLog /TIMEOUT=1200000 '"$PythonExe" $PythonArgs "$INSTDIR\bootstrap_windows.py" --prepare-only --source $SourceKey --connection $ConnectionKey'
  ${EndIf}
  Pop $0
  System::Call 'Kernel32::SetEnvironmentVariable(t, t)i("PROJECT_FACTORY_SETUP_PROXY", "").r1'

  ${If} $0 == "timeout"
    MessageBox MB_ICONSTOP|MB_OK "Python Core 运行时准备超时，安装已停止。详细日志：%LOCALAPPDATA%\ProjectFactory\logs\bootstrap.log"
    Abort
  ${ElseIf} $0 == "error"
    MessageBox MB_ICONSTOP|MB_OK "无法启动 Python Core runtime 准备程序。详细日志：%LOCALAPPDATA%\ProjectFactory\logs\bootstrap.log"
    Abort
  ${ElseIf} $0 != "0"
    MessageBox MB_ICONSTOP|MB_OK "Python Core 运行时准备失败（退出码 $0）。安装不会标记为成功。$\r$\n$\r$\n详细日志：%LOCALAPPDATA%\ProjectFactory\logs\bootstrap.log"
    Abort
  ${EndIf}
FunctionEnd

Function un.onInit
  !insertmacro MUI_UNGETLANGUAGE
  ReadRegStr $INSTDIR HKCU "${PRODUCT_REGKEY}" "InstallDir"
  ${If} $INSTDIR == ""
    StrCpy $INSTDIR "$LOCALAPPDATA\Programs\ProjectFactory"
  ${EndIf}
FunctionEnd

Function CloseInstalledProcesses
  DetailPrint "检查并安全退出正在运行的实例 ($INSTDIR)..."
  ${If} ${FileExists} "$INSTDIR"
    InitPluginsDir
    File /oname=$PLUGINSDIR\CloseProcesses.ps1 "CloseProcesses.ps1"
    nsExec::ExecToLog /TIMEOUT=15000 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\CloseProcesses.ps1" -TargetDir "$INSTDIR"'
    Pop $0
  ${EndIf}
FunctionEnd

Function un.CloseInstalledProcesses
  DetailPrint "检查并安全退出正在运行的实例 ($INSTDIR)..."
  ${If} ${FileExists} "$INSTDIR"
    ${If} ${FileExists} "$INSTDIR\installer\CloseProcesses.ps1"
      ExecWait 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\installer\CloseProcesses.ps1" -TargetDir "$INSTDIR"'
    ${EndIf}
  ${EndIf}
FunctionEnd

Section "-基地车生产厂" SEC_CORE
  SetShellVarContext current
  Call CloseInstalledProcesses
  SetOutPath "$INSTDIR"
  WriteRegStr HKCU "${PRODUCT_REGKEY}" "InstallerLanguage" $LANGUAGE

  File "..\BUNDLE_INFO.json"
  File "..\README_FIRST.md"
  File "..\RELEASE_NOTES.md"
  File "..\THIRD_PARTY_NOTICES.md"
  File "..\VERIFICATION.md"
  File "..\UX5_DESIGN_NOTES.md"
  File "..\bootstrap_windows.py"
  File "..\RECOVERY_Runtime.bat"

  SetOutPath "$INSTDIR\backend"
  File "..\backend\network_ops.py"
  File "..\backend\project_factory_bridge.py"

  SetOutPath "$INSTDIR\wheel"
  File "..\wheel\project_factory_blueprint_kernel-0.14.30-py3-none-any.whl"

  SetOutPath "$INSTDIR\app"
  File /r "publish\*.*"

  SetOutPath "$INSTDIR\installer"
  File "ProjectFactoryInstaller.nsi"
  File "CloseProcesses.ps1"
  File "BUILD_INSTALLER.ps1"
  File "BUILD_INSTALLER.bat"

  ; R1 永久修复：安装包内携带钉死的机器工具（npm 10.9.2 / uv 0.10.0）。
  ; 根因：旧安装器从不打包 tools/，导致安装后 Node/Web 产品线落到系统 npm（版本不符）
  ; 被 registry.inspect_provider 的版本门禁整条杀掉。源位于 work/core/.tools
  ; （相对 installer 目录为 ..\..\core\.tools）。与 PythonBridgeClient 注入的 PATH 契约一致。
  SetOutPath "$INSTDIR\tools\npm1092"
  File /r "..\core\.tools\npm1092\*.*"
  SetOutPath "$INSTDIR\tools\uv010"
  File /r "..\core\.tools\uv010\*.*"

  Call PrepareRuntime

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  WriteRegStr HKCU "${PRODUCT_REGKEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${PRODUCT_REGKEY}" "Version" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_REGKEY}" "UX" "UX5.1"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\app\ProjectFactory.exe"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoRepair" 1

  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
    CreateShortCut "$SMPROGRAMS\$StartMenuFolder\基地车生产厂.lnk" "$INSTDIR\app\ProjectFactory.exe"
    CreateShortCut "$SMPROGRAMS\$StartMenuFolder\修复 Python Core 运行时.lnk" "$INSTDIR\RECOVERY_Runtime.bat"
    CreateShortCut "$SMPROGRAMS\$StartMenuFolder\卸载 基地车生产厂.lnk" "$INSTDIR\Uninstall.exe"
  !insertmacro MUI_STARTMENU_WRITE_END

  ${If} $DesktopShortcut == "1"
    CreateShortCut "$DESKTOP\基地车生产厂.lnk" "$INSTDIR\app\ProjectFactory.exe"
  ${EndIf}
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  Call un.CloseInstalledProcesses

  Delete "$DESKTOP\基地车生产厂.lnk"
  Delete "$SMPROGRAMS\基地车生产厂\基地车生产厂.lnk"
  Delete "$SMPROGRAMS\基地车生产厂\修复 Python Core 运行时.lnk"
  Delete "$SMPROGRAMS\基地车生产厂\卸载 基地车生产厂.lnk"
  RMDir "$SMPROGRAMS\基地车生产厂"

  ; Only installer-owned directories are recursively removed.
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\.pf_runtime"
  RMDir /r "$INSTDIR\backend"
  RMDir /r "$INSTDIR\wheel"
  RMDir /r "$INSTDIR\installer"
  RMDir /r "$INSTDIR\tools"

  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\BUNDLE_INFO.json"
  Delete "$INSTDIR\README_FIRST.md"
  Delete "$INSTDIR\RELEASE_NOTES.md"
  Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
  Delete "$INSTDIR\VERIFICATION.md"
  Delete "$INSTDIR\UX5_DESIGN_NOTES.md"
  Delete "$INSTDIR\bootstrap_windows.py"
  Delete "$INSTDIR\RECOVERY_Runtime.bat"

  ; Deliberately preserve %LOCALAPPDATA%\ProjectFactory and user project outputs.
  RMDir "$INSTDIR"

  DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKCU "${PRODUCT_REGKEY}"
SectionEnd
