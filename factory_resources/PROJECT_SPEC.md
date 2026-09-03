# PROJECT_SPEC — 任意项目的坐标纸

阶段 A.1。只建账，不改 Core。

一个真实项目很少是「一种框架」。它通常是：造什么、在哪跑、存什么、怎么交、怎么测、怎么升级。  
以前用种类名单去逼近，名单再长也会被组合打爆。现在改成**有限的正交轴**。

线性代数里的直觉：基底向量要少、要互相独立；空间里的点是坐标，不要给每个点起一个新轴的名字。

---

## 一张纸长什么样

```yaml
# 最小例子：Python FastAPI 服务
work_products: [http-service]
runtime:
  language: python
  execution: long-running-server
framework:
  body: fastapi
state: []
integration: []
delivery:
  artifacts: [container-image]
  channels: []
repo:
  topology: single-package
quality:
  gates: [unit]
security: []
ops: [logging, health-check]
compatibility:
  os: [linux]
  arch: [x64]
lifecycle:
  upgrade: factory-lock
```

复杂例子不是新种类：

```text
FastAPI + React + Postgres + Redis + Celery
+ Docker + GitHub Actions + OpenTelemetry + OAuth + MCP
```

拆开以后：

| 轴 | 取值 |
|---|---|
| work_products | `http-service`, `web-spa`, `mcp-server` |
| execution | `long-running-server` + `queue-worker` |
| language | python + typescript（按包） |
| body | fastapi + react |
| state | postgres, redis, queue |
| integration | oauth-oidc |
| delivery | container-image |
| repo | monorepo 或 frontend-backend-split |
| quality | unit, integration, e2e |
| ops | opentelemetry |
| ci | github-actions（delivery/ops overlay，不是 kind） |

禁止把这一行焊成一个 Profile 名。

---

## 各轴是什么（以及不是什么）

| 轴 | 回答 | 不是 |
|---|---|---|
| **Work product** | 成品形态：CLI、库、HTTP 服务、扩展… | 不是「FastAPI 项目」这种供应商名 |
| **Execution** | 谁来叫醒它：进程、系统服务、Lambda、定时批次… | 不是语言 |
| **Language** | 语言根 | 不是框架 |
| **Framework / body** | 车身轮子，供应商 | 不是新 kind |
| **State** | 状态往哪放 | 不是「我用了 Postgres 所以这是数据库项目」——除非 repo 本身就是 migration 仓 |
| **Integration** | 对外协议与事件 | 不是执行模型 |
| **Delivery** | 打成什么包、送到哪 | 不是 CI 品牌本身 |
| **Repo topology** | 一个仓里几摊代码 | 不是产品种类 |
| **Quality** | 测什么类型 | 不是 pytest 这个工具名（工具是供应商） |
| **Security** | 密钥、SBOM、签名、许可证 | |
| **Ops** | 日志指标追踪、健康检查 | |
| **Compatibility** | OS / Arch / 浏览器 / 运行时矩阵 | |
| **Lifecycle** | 升级模板、弃用产线、破坏性变更 | |

同一轴上换供应商，不换轴。Postgres 和 SQLite 都是 `relational-db`。GitHub Actions 和 GitLab CI 都是 `ci-pipeline`。

---

## Profile 以后怎么长

**Profile = 某 kind + 某语言根上的默认绑定**（再加极少的默认执行模型）。  
可选轴全部是能力开关 / overlay，由 Blueprint 填，不靠新产线名。

0.14.1 已有的四条，用这张纸写就是：

| 现产线 | work_product | language | execution 默认 |
|---|---|---|---|
| python-cli | cli | python | interactive-cli |
| python-library | library | python | in-process-library |
| node-library | library | javascript | in-process-library |
| browser-extension-js | browser-extension | javascript | browser-runtime |

下一刀 `python-mcp-server` 若开工，也只是：kind=`mcp-server`，language=`python`，execution=`stdio-or-streamable-http`。不要顺便把 Postgres 焊进这条产线的名字。

---

## 覆盖率怎么算过

`coverage_fixtures/` 里每一条口语需求，必须填得出上面这张纸，且 **不得为此发明新 kind**。  
映射失败才允许：加维度值、或极少情况下加 kind（见宪法）。  
加轮子永远比加 kind 优先。
