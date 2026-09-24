# 校园 qwen3.8-27b —— Harness 接入指南

> 面向对象：想把华北电力大学的 `qwen3.8-27b` 接到各类编码 Agent / CLI / 客户端的用户
> 整理日期：2026-09-24 ｜ 服务端参数均为实测

---

## 一、先搞清楚这件事：harness 分两类

**这是整份指南最重要的一节。** 学校端点很特殊——只有一条路径能用：

```
✅ http://202.204.64.234:8080/api/chat/completions
❌ http://202.204.64.234:8080/api/v1/chat/completions   → 405
❌ http://202.204.64.234:8080/api//chat/completions     → 405（尾斜杠导致）
❌ http://202.204.64.234:8080/v1/chat/completions       → 405
```

而不同 harness 拿到你填的 Base URL 后，**自己拼接的路径不一样**：

| 类型 | 拼接行为 | 填 `.../api` 的结果 | 代表工具 |
|---|---|---|---|
| **A 类** | 只拼 `/chat/completions` | ✅ `.../api/chat/completions` 正确 | OpenAI Python/Node SDK、Continue、Dify、WorkBuddy（自定义协议关闭）、curl |
| **B 类** | 强制拼 `/v1/chat/completions` | ❌ 405 | 多数桌面客户端、部分版本的 Cline / Roo Code、Aider |

### 怎么判断你的工具属于哪类

1. **直接试**：Base URL 填 `http://202.204.64.234:8080/api`，发一条消息。
   - 正常回复 → A 类，收工
   - 报 405 / 404 → B 类，往下看
2. **B 类的解法**（二选一）：
   - 找工具里有没有「自定义完整路径」「Use custom path」之类的选项
   - **直接用第五节的本机反代**（推荐，一次配好所有工具都能用）

---

## 二、获取 API Key（官方入口）

官方文档说明：网页、客户端、Cline 插件、API 调用四种方式**使用前均需在学校网站注册用户**，
其中后三种还需创建 API 密钥。

| 入口 | 地址 | 用途 |
|---|---|---|
| **Open WebUI 网页端** | http://202.204.64.234:8080 | 注册 / 登录 / 创建 API 密钥 / 直接对话 |
| **学校官方教程** | https://lab.ncepu.edu.cn/bslc/rjzy/0b468cf674694cf6b9feaf95883a7352.htm | 原始文档（含注册、密钥创建、客户端配置截图） |

### 创建 API 密钥（官方步骤）

1. 浏览器打开 http://202.204.64.234:8080 ，**注册账号**并登录
2. 点击右上角**圆形头像**图标
3. 选择「**设置**」
4. 选择「**账号**」
5. 点击「**API 密钥**」
6. 点击「**创建新安全密钥**」
7. 点击「**保存**」，复制生成的 `sk-` 开头的密钥

> ✅ **拿到密钥后放哪里**：本包的自检脚本与本地反代都从同目录 `api_key.txt` 读取 ——
> 把密钥粘到**第 1 行**即可。也可用 `--key sk-xxx` 或环境变量 `NCEPU_API_KEY`。

### 官方文档的三处错误（实测勘误）

文档发布于 2025-11-21，部分内容已过时，**照抄会踩坑**：

| # | 文档写的 | 实际情况 |
|---|---|---|
| 1 | 模型名 `qwen3-coder:30b`（客户端那节又写成 `qwen3-code:30b`） | 已换成 `qwen3.8-27b`，服务器上**只有这一个模型**。照文档填会报模型不存在 |
| 2 | Cline 那节 Base URL 写 `http://202.204.64.234:8080/api/`（**带尾斜杠**） | 会拼成 `/api//chat/completions` → 405。应去掉尾斜杠 |
| 3 | Cline 那节超链接损坏，显示成 `http://202.204.64.234:11434%EF%BC%8CModel/` | 链接本身失效，忽略即可 |

> 文档第 4 节的 API 调用示例里，**URL 是对的**（`http://202.204.64.234:8080/api/chat/completions`），
> 只有 `model` 字段需要改成 `qwen3.8-27b`。

### 文档推荐的客户端（Cherry Studio / ChatWise）

官方教程给了 Cherry Studio 的配置示例，注意**两处要改**：

| 字段 | 文档写的 | 应该填 |
|---|---|---|
| 模型服务 | OpenRouter | OpenRouter（照填即可 —— 它只是借这个通道走自定义地址） |
| API 地址 | `http://202.204.64.234:8080/api/` | `http://202.204.64.234:8080/api`（**去掉尾斜杠**） |
| 模型 | `qwen3-code:30b` | `qwen3.8-27b` |

---

## 三、通用参数（所有 harness 共用）

| 参数 | 值 |
|---|---|
| Base URL（直连） | `http://202.204.64.234:8080/api` |
| Base URL（走反代） | `http://127.0.0.1:8788/v1` |
| Model ID | `qwen3.8-27b` |
| API Key | `api_key.txt` 第 1 行（`sk-` 开头，35 位） |
| 协议 | OpenAI 兼容 → **Chat Completions API**（不是 Responses API） |
| 上下文 | 256K（`max_model_len=262144`，输入+输出**合计**） |

### 三条铁律

1. **Base URL 末尾不加斜杠** → 加了会变成 `//chat/completions`，405
2. **不加 `/v1`**（除非走反代）→ `/v1/...` 一律 405
3. **模型名是 `qwen3.8-27b`**，不是学校文档写的 `qwen3-coder:30b` → 填错报模型不存在

### 服务端实况（本次实测新增）

| 项 | 值 |
|---|---|
| 推理引擎 | **vLLM 0.29.1.dev1**（`system_fingerprint` 字段暴露） |
| 并行方式 | **TP=4**（4 卡张量并行，说明学校至少部署了 4 张卡） |
| 流式 delta | 思考内容通过 `delta.reasoning` 逐块下发（做前端要注意解析这个字段） |
| 视觉 | 图片输入可用，`usage.prompt_tokens_details.multimodal_tokens` 会记录图像 token 数 |

---

## 四、逐 harness 配置

### 4.1 ✅ 已验证可用（本次实测）

**OpenAI Python SDK**（A 类，直接可用）

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://202.204.64.234:8080/api",   # 注意：没有 /v1
    api_key="sk-你的密钥",
)

resp = client.chat.completions.create(
    model="qwen3.8-27b",
    messages=[{"role": "user", "content": "你好"}],
    max_tokens=512,
)
print(resp.choices[0].message.content)
print(resp.choices[0].message.reasoning)   # 思考内容在这里，不是 reasoning_content
```

**curl**（A 类）

```bash
curl http://202.204.64.234:8080/api/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-你的密钥" \
  -d '{"model":"qwen3.8-27b","messages":[{"role":"user","content":"你好"}]}'
```

**Qoder / WorkBuddy**（A 类）→ 详细步骤见 `接入参数.md`

---

### 4.2 IDE 插件

#### Cline（VSCode 扩展）

| 字段 | 填 |
|---|---|
| API Provider | `OpenAI Compatible` |
| Base URL | `http://127.0.0.1:8788/v1`（走反代最稳）；若坚持直连填 `http://202.204.64.234:8080/api` |
| API Key | `sk-...` |
| Model ID | `qwen3.8-27b` |
| Context Window | 手动填 `131072`（别用默认值，会浪费上下文或超限） |
| Supports Images | ☑ 勾（实测视觉可用） |

> ⚠️ 学校官方文档那节写的是 `http://202.204.64.234:8080/api/`（**带尾斜杠**），
> 实测会拼成 `/api//chat/completions` → 405。照抄文档会踩坑，改成不带斜杠的。

#### Roo Code（VSCode 扩展）

配置项与 Cline 完全一致（API Provider 同样选 `OpenAI Compatible`）：
Base URL `http://127.0.0.1:8788/v1`、Model `qwen3.8-27b`、勾选图片支持。

#### Continue.dev

`~/.continue/config.yaml`：

```yaml
models:
  - name: NCEPU Qwen3.8-27B
    provider: openai
    model: qwen3.8-27b
    apiBase: http://202.204.64.234:8080/api     # A 类拼法；若报 405 改成 http://127.0.0.1:8788/v1
    apiKey: sk-你的密钥
    contextLength: 131072
    roles:
      - chat
      - edit
      - apply
```

---

### 4.3 CLI 工具

#### Aider

```bash
export OPENAI_API_BASE=http://202.204.64.234:8080/api
export OPENAI_API_KEY=sk-你的密钥

aider --model openai/qwen3.8-27b
```

> 若报 405/404，把 `OPENAI_API_BASE` 改成 `http://127.0.0.1:8788/v1`（Aider 内部走 litellm，拼接策略随版本变动）。

#### Claude Code 等 Anthropic 协议工具

Claude Code 说的是 **Anthropic Messages API**（`/v1/messages`），不能直连 OpenAI 兼容端点，
需要一个转换层。用 LiteLLM：

```yaml
# litellm.yaml
model_list:
  - model_name: qwen3.8-27b
    litellm_params:
      model: openai/qwen3.8-27b
      api_base: http://202.204.64.234:8080/api
      api_key: os.environ/NCEPU_API_KEY
```

```bash
pip install "litellm[proxy]"
export NCEPU_API_KEY=sk-你的密钥
litellm --config litellm.yaml --port 4000

# 另开一个终端，让 Claude Code 指向本地转换层
export ANTHROPIC_BASE_URL=http://127.0.0.1:4000
export ANTHROPIC_AUTH_TOKEN=sk-1234
claude
```

> 此路径**未实测**（LiteLLM 转换层的 Anthropic 端点兼容性随版本变化）。
> 另外 27B 模型跑 Claude Code 那种长链路 Agent 任务会比较吃力，建议先小任务试水。

---

### 4.4 桌面客户端

**Cherry Studio / ChatBox / LobeChat / NextChat** 等：

| 字段 | 填 |
|---|---|
| 供应商 | `OpenAI` 或「自定义 OpenAI 兼容」 |
| API 地址 | 先试 `http://202.204.64.234:8080/api`；报 405 就填 `http://127.0.0.1:8788/v1` |
| API Key | `sk-...` |
| 模型名称 | `qwen3.8-27b`（手动添加，别指望自动拉列表） |

> 反代同时接受 `/v1/chat/completions` 和 `/chat/completions`，
> 所以填 `http://127.0.0.1:8788/v1` 或 `http://127.0.0.1:8788` 都能命中，不用纠结。

---

### 4.5 平台类（Dify / n8n / FastGPT）

**Dify**：模型供应商 → `OpenAI-API-compatible`

| 字段 | 填 |
|---|---|
| API Base URL | `http://202.204.64.234:8080/api` |
| API Key | `sk-...` |
| Model Name | `qwen3.8-27b` |
| Model Type | LLM |
| 功能开关 | Vision ☑ ｜ Function Calling ☑ ｜ Stream Function ☑ |

**n8n**：用 `OpenAI Chat Model` 节点 + 「OpenAI Compatible」凭据，
Base URL 填 `http://127.0.0.1:8788/v1`（n8n 的凭据校验会调 `/models`，反代已提供该接口）。

**FastGPT**：OpenAI 兼容渠道，Base URL `http://202.204.64.234:8080/api`。

---

## 五、本地反代方案（解决所有 B 类 harness）

### 5.1 它做什么

```
harness ──→ http://127.0.0.1:8788/v1/chat/completions
                     ↓ ncepu_proxy.py 转换
             http://202.204.64.234:8080/api/chat/completions
```

顺带修掉两个已知的坑：

| 问题 | 反代的处理 |
|---|---|
| harness 传 `reasoning_effort: high` → 服务端 400 | 自动映射 `high → xhigh`（同理 `max`/`ultra` → `xhigh`，`minimal` → `low`） |
| harness 传 `max_tokens` 过大 → 400 | 自动截断到 200000 |
| harness 传自己的模型显示名 | 强制改写成 `qwen3.8-27b` |

### 5.2 启动

```bash
# 方式一：双击 start-proxy.bat（推荐，会自动装依赖）
# 方式二：命令行手动启动
python ncepu_proxy.py
```

密钥自动从同目录 `api_key.txt` 读取（也可用 `--key sk-xxx` 或环境变量 `NCEPU_API_KEY`）。

启动后终端会打印：

```
  上游   : http://202.204.64.234:8080/api/chat/completions
  模型   : qwen3.8-27b
  监听   : http://127.0.0.1:8788
  harness 里填：
    Base URL : http://127.0.0.1:8788/v1
    API Key  : 任意值
    Model ID : qwen3.8-27b
```

### 5.3 harness 侧填法

| 字段 | 值 |
|---|---|
| Base URL | `http://127.0.0.1:8788/v1`（若工具又自动加 `/v1`，改填 `http://127.0.0.1:8788`） |
| API Key | 任意值（反代用本地配置的密钥访问学校） |
| Model ID | `qwen3.8-27b` |

### 5.4 自检

```bash
curl http://127.0.0.1:8788/health          # {"status": "ok", ...}
curl http://127.0.0.1:8788/v1/models       # 模型列表，供客户端自动拉取
```

### 5.5 注意事项

- 默认只监听 `127.0.0.1`，**外部访问不到**（安全默认值）
- 流式与非流式都已实测通过
- 反代本身不做缓存、不落盘，只是转发
- 关掉终端窗口 = 停止服务，harness 会连不上

---

## 六、模型能力与限制（决定 harness 里怎么勾）

| 能力 | 实测 | 配置建议 |
|---|---|---|
| 文本对话 | ✅ | — |
| 工具调用 | ✅ | 勾选 Function Calling / Tools，**不勾 Agent 能力全废** |
| 流式 SSE | ✅ | 正常开启 |
| 视觉 | ✅ | 勾选 Vision / Images |
| 思考模式 | ✅ | 思考内容在 **`reasoning`** 字段（不是 `reasoning_content`），流式在 `delta.reasoning` |
| 关闭思考 | ✅ | 请求体加 `chat_template_kwargs: {"enable_thinking": false}`；提示词 `/no_think` **无效** |

### ⚠️ 坑一：思考强度只有三档真实可用

`reasoning_effort` 实测结果：

| 传入 | 结果 |
|---|---|
| `low` / `medium` / `xhigh` | ✅ |
| `none` | ✅（等于关思考） |
| **`high`** | ❌ 400：`Supported types are xhigh (default), medium, and low.` |
| `max` / `maximum` / `minimal` / `ultra` / `extreme` | ❌ 拒绝 |

界面上是「低/中/高/超高/极致」五档 → **只勾 低、中、超高**，勾「高」「极致」运行时会 400。
（走反代可自动映射，不勾也不会报错。）

### ⚠️ 坑二：输入 + 输出 ≤ 262144

是**总和**，不是各自独立：

| 请求 | 结果 |
|---|---|
| `max_tokens=200000` | ✅ |
| `max_tokens=262144` | ❌ 400 |
| `max_tokens=300000` | ❌ 400 |

**建议 harness 里填：输入 128K + 输出 32K**（合计 160K 留余量）。

---

## 七、排错对照表

| 现象 | 原因 | 处理 |
|---|---|---|
| `405 Method Not Allowed` | Base URL 带尾斜杠，或 harness 拼了 `/v1` | 去掉尾斜杠；或用反代 `http://127.0.0.1:8788/v1` |
| `404 Not Found` | 路径不对（如 `/openai/v1/...`） | 检查 Base URL |
| `401 Not authenticated` | 密钥错/过期/带空格 | 网页重建密钥，重新写入 `api_key.txt` |
| `model not found` | 模型名写错 | 改成 `qwen3.8-27b` |
| `400 Unexpected reasoning effort high` | 思考强度选了「高」 | 只勾低/中/超高，或用反代自动映射 |
| `400 maximum context length is 262144` | 输入+输出超限 | 输入 128K + 输出 32K |
| 连接超时 | 当前网络到不了 `202.204.64.234` | 该 IP 属教育网公网段，换网络环境或确认是否需校园网 |
| 工具调用被当普通文本输出 | harness 没开 Function Calling | 在模型配置里勾选工具调用 |
| 思考内容混进正文 | harness 不识别 `reasoning` 字段 | 正常现象，多数工具会忽略或另存；反代不改写该字段 |

**万能第一步**：先跑自检脚本定位问题

```cmd
check-ncepu-ai.bat
```

---

## 八、安全提醒

- **数据流向**：所有对话内容都会发往学校服务器，敏感/涉密内容**不要用**
- **密钥**：`api_key.txt` 是明文，别提交到 Git、别分享
- **反代**：默认只听 `127.0.0.1`，不要改成 `0.0.0.0`（那等于把学校配额开放给同网段所有人）
- **配额**：校园服务是共享资源，别跑大规模批量推理

---

## 附：相关文件

| 文件 | 用途 |
|---|---|
| `使用说明.md` | 新手入口：3 步上手 + 文件清单 + 常见问题 |
| `接入参数.md` | Qoder / WorkBuddy 详细配置 + 坑位说明 |
| `start-proxy.bat` | 双击启动本地反代（解决 405） |
| `api_key.txt` | 密钥文件，需自行填写（第 1 行） |
| `ncepu_proxy.py` | 本机反代，解决 B 类 harness 的路径问题 |
| `test_ncepu_ai.py` | 8 项自检脚本 |
| `check-ncepu-ai.bat` | 双击即用的自检入口 |
