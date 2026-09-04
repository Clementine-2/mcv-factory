# MCV Factory（基地車工廠）

**語言：** [English](README.md) · [简体中文](README.zh-CN.md) · **繁體中文**

> ⚠️ **正在積極開發中** — 介面與介面可能隨時調整，暫不建議用於生產環境。

> 一款 Windows 桌面「專案工廠」：把高階需求變成經過驗證、有證據支撑的軟體專案。
> 前端是 Fluent/WPF，後端是隔離的 Python「工廠核心」（Factory Core），負責產生、驗證與恢復工程脚手架。

MCV Factory（基地車工廠）得名於《命令與征服：紅色警戒》裡的基地車 MCV（程式碼中代號 Project Factory），是一款**以人為本**的工具：CLI / UI 負責收集意圖，核心負責產出專案藍圖，而關於產生專案的每一條聲明都有證據產物背書，而不是空口斷言。

- **工廠核心版本：** `0.14.30`
- **介面外殼：** UX5.1 — Windows 11 Fluent（WPF / .NET，WPF-UI 4.3.0）
- **許可證：** [MIT](./LICENSE)

---

## 目錄

- [這是什麼](#這是什麼)
- [架構](#架構)
- [倉庫結構](#倉庫結構)
- [環境需求](#環境需求)
- [建置與執行（Windows）](#建置與執行windows)
- [Python 橋接](#python-橋接)
- [安全模型](#安全模型)
- [貢獻](#貢獻)
- [許可證](#許可證)

---

## 這是什麼

MCV Factory 接收一條需求（自由文字或引導式表單），對它進行語意推理，然後產出工程脚手架與一組**驗證聲明**。每一條聲明都會對照真實產物校驗；任何看起來像密鑰的內容，在持久化或傳送到外部服務之前都會被統一脫敏。

兩個部分協同運作：

1. **工廠核心**（`core/`）— 一個 Python 核心（`project-factory-blueprint-kernel`），負責需求正規化、語意推理、藍圖產生、驗證套件與失敗恢復，透過 JSON 橋被呼叫。
2. **使用者介面外殼**（`shell/` + `backend/`）— 一個自包含的 Windows WPF 應用程式（FluentWindow、Mica、NavigationView），透過常駐的 Python 後端程序與核心通訊。

---

## 架構

```
┌─────────────────────────────┐      JSON over stdin/stdout        ┌──────────────────────────────┐
│  WPF Shell (shell/)         │ ───────────────────────────────▶  │  Python backend (backend/)    │
│  FluentWindow / Mica / NV   │      line-delimited `id` match     │  resident process bridge      │
└─────────────────────────────┘ ◀───────────────────────────────  └───────────────┬──────────────┘
                                                                                   │ invokes
                                                                                   ▼
                                                                          ┌────────────────────────────┐
                                                                          │  Factory Core (core/src)    │
                                                                          │  normalize → reason →       │
                                                                          │  generate → verify → recover│
                                                                          └────────────────────────────┘
```

- 介面外殼啟動**一個**常駐 Python 程序，按行交換 JSON 請求/回應，用每行唯一的 `id` 匹配。這項設計取代了舊的「每次呼叫都拉起子程序」的模型，消除了介面卡頓。
- 核心完全隔離：執行在獨立的 venv 中，絕不更動系統 Python。可選 AI 輔助只讀取**環境變數名稱**對應的憑證，永不把實際值寫入磁碟。

---

## 倉庫結構

```
ProjectFactory/
├── core/                     # 工廠核心（Python kernel）
│   ├── pyproject.toml        # project-factory-blueprint-kernel 0.14.30
│   ├── requirements.txt      # jsonschema==4.26.0, PyYAML==6.0.3
│   ├── src/project_factory/  # kernel source (package = src layout)
│   ├── tests/                # test suite
│   ├── docs/ schemas/ scripts/ fixtures/ golden_outputs/ compatibility/
├── shell/                    # WPF / .NET 桌面用戶端（ProjectFactory.Workbench）
│   ├── App.xaml(.cs) MainWindow.xaml(.cs) app.manifest
│   ├── Models/ Services/ Views/ Assets/
│   └── ProjectFactory.Workbench.csproj
├── backend/                  # Python 橋接層（由介面外殼驅動）
│   └── project_factory_bridge.py (availability, gui_catalog, module_store, …)
├── installer/                # NSIS 3.12 安裝包原始碼（BUILD_INSTALLER.*, *.nsi）
├── tools/                    # QA / 生命週期驗證腳本
├── factory_resources/        # 資源宇宙（YAML / Markdown 目錄）
├── bootstrap_windows.py      # Windows 首次執行引導
├── hot_upgrade_launch.py     # 原地升級 / 啟動助手
├── THIRD_PARTY_NOTICES.md    # 第三方授權彙總
├── LICENSE                   # MIT
├── README.md  CONTRIBUTING.md  SECURITY.md  CODE_OF_CONDUCT.md  .gitignore
```

---

## 環境需求

桌面版面向 **Windows 10 / 11**。

| 元件             | 版本               | 說明                                            |
|------------------|--------------------|-------------------------------------------------|
| .NET SDK         | 9.0.x（固定）        | 用於建置/發佈 WPF 外殼（目標框架 `net9.0-windows`）   |
| WPF-UI (NuGet)   | 4.3.0（固定）        | Fluent 控制項；建置時由 NuGet 拉取                  |
| Python           | 64 位元 3.11+        | 僅用於建立隔離的 Core venv                        |
| NSIS             | 3.12（Modern UI 2） | 僅建置安裝包時需要                                 |

Python 執行時期依賴（安裝到隔離 venv，絕不裝入系統環境）：

```
jsonschema==4.26.0
PyYAML==6.0.3
```

---

## 建置與執行（Windows）

### 1. 工廠核心（Python）

```powershell
cd core
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
# 冒煙測試：
.\.venv\Scripts\python -m project_factory --help
```

### 2. WPF 介面外殼

```powershell
cd shell
dotnet build -c Release
# 或產生自包含、可攜的建置：
dotnet publish -c Release -r win-x64 --self-contained true -o publish_win64
```

### 3. 橋接與啟動

介面外殼期望 Python 後端位於已安裝應用程式旁邊。本機執行時，`bootstrap_windows.py` 負責準備隔離的 Core venv；`hot_upgrade_launch.py` 負責原地升級/啟動。`installer/` 下的安裝器原始碼會產生一個按使用者安裝的 `ProjectFactory` 程式（位於 `%LOCALAPPDATA%\Programs\ProjectFactory`）。

> 編排完整 Windows 安裝包建置的公開腳本位於 `installer/`（NSIS）。它們會在使用前按雜湊校驗固定的工具鏈封存。

---

## Python 橋接

`backend/project_factory_bridge.py` 是一個**常駐**程序：介面外殼每行寫一條 JSON 請求（每條帶唯一 `id`），並按 `id` 讀取對應回應。這保證了介面回應流暢，也避免了每次操作都重新啟動一個 Python 直譯器。

請求範例（一行）：

```json
{"id": 1, "action": "status"}
```

---

## 安全模型

- **不硬編碼任何密鑰。** API Key / Token 只透過**環境變數名稱**讀取；核心絕不把實際值寫入磁碟。
- **密鑰脫敏。** 在持久化或傳送文字到任何外部服務之前，核心會脫敏憑證內容（`sk-…`、`ghp_…`、`AKIA…`、`Bearer …`、`api_key=…` 等）。見 `core/src/project_factory/normalizer.py`。
- **隔離執行。** 核心執行在獨立 venv 中，不觸碰系統 Python 套件。
- 產生的工程範本使用僅限開發環境的預設值（例如脚手架 `docker-compose` 中的範例 `POSTGRES_PASSWORD: app`）——這只是教學範例，不是 MCV Factory 自身的憑證。

漏洞請按 [SECURITY.md](./SECURITY.md) 報告。

---

## 貢獻

感謝你的關注！開發環境搭建、測試執行方式與 PR 流程見 [CONTRIBUTING.md](./CONTRIBUTING.md)。參與貢獻即表示你同意你的貢獻按 MIT 授權授權。

---

## 許可證

以 [MIT 許可證](./LICENSE) 發佈。