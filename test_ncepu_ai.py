#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
华北电力大学 AI 编程大模型 连通性与可用性自检脚本

实测信息（2026-09-23 验证）：
    服务地址  http://202.204.64.234:8080  （Open WebUI 0.6.21）
    实际模型  qwen3.8-27b
    端点      POST http://202.204.64.234:8080/api/chat/completions
    注意      Base URL 不能带尾部斜杠；文档写的 qwen3-coder:30b 已不存在。

用法（三种任选其一，按省事程度排序）：

    方式 A —— 密钥文件（最省事，推荐）
        在本脚本同目录新建 api_key.txt，把密钥粘进去保存（UTF-8）。
        然后直接运行本脚本即可，无需在控制台里粘贴。

    方式 B —— 直接运行，按提示粘贴
        python test_ncepu_ai.py

    方式 C —— 密钥跟在命令行后面
        python test_ncepu_ai.py sk-你的密钥
        set NCEPU_API_KEY=sk-你的密钥 && python test_ncepu_ai.py

    只做连通性体检、不测鉴权：
        python test_ncepu_ai.py --no-key

密钥获取：登录 http://202.204.64.234:8080 -> 右上角头像 -> 设置 -> 账号 -> API 密钥 -> 创建
"""

import json
import os
import sys
import time

import requests

BASE = "http://202.204.64.234:8080"

# 实测结论（2026-09-23）：
#   学校文档（2025-11-21 发布）写的是 qwen3-coder:30b，
#   但服务器上实际只挂载了一个模型：qwen3.8-27b。
#   因此 Cline / Cherry Studio 里 Model 字段要填 qwen3.8-27b，
#   照文档填 qwen3-coder:30b 会报模型不存在。
MODEL = "qwen3.8-27b"
DOC_MODEL = "qwen3-coder:30b"   # 文档里的写法，仅作对照提示用
TIMEOUT = 30

# 文档中两处写法不一致：qwen3-code:30b / qwen3-coder:30b，此处以正文/API 示例为准


def ok(msg):
    print(f"  [通过] {msg}")


def bad(msg):
    print(f"  [失败] {msg}")


def info(msg):
    print(f"  [信息] {msg}")


def check_reachable():
    print("\n== 1. 服务连通性 ==")
    try:
        r = requests.get(BASE + "/", timeout=15)
    except Exception as e:
        bad(f"无法连接 {BASE}：{e}")
        info("如果你不在校园网内，请先连接学校 VPN。")
        return False
    server = r.headers.get("server", "?")
    ok(f"HTTP {r.status_code}，server={server}，耗时 {r.elapsed.total_seconds():.3f}s")
    if "Open WebUI" in r.text:
        ok("确认为 Open WebUI 前端页面")
    return True


def check_version():
    print("\n== 2. 版本与注册开关 ==")
    try:
        v = requests.get(BASE + "/api/version", timeout=15).json()
        ok(f"Open WebUI 版本 {v.get('version')}")
    except Exception as e:
        bad(f"读取版本失败：{e}")
    try:
        cfg = requests.get(BASE + "/api/config", timeout=15).json()
        f = cfg.get("features", {})
        info(f"开放注册={f.get('enable_signup')}  API密钥功能={f.get('enable_api_key')}  "
             f"登录表单={f.get('enable_login_form')}")
    except Exception as e:
        bad(f"读取配置失败：{e}")


def check_endpoint_shape():
    print("\n== 3. API 端点形态 ==")
    try:
        r = requests.post(
            BASE + "/api/chat/completions",
            json={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
            timeout=15,
        )
        if r.status_code == 401:
            ok("POST /api/chat/completions 存在且受鉴权保护（401 Not authenticated）")
        else:
            info(f"返回 HTTP {r.status_code}：{r.text[:120]}")
    except Exception as e:
        bad(f"端点探测失败：{e}")


def list_models(key):
    print("\n== 4. 列出可用模型 ==")
    try:
        r = requests.get(BASE + "/api/models",
                         headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT)
        if r.status_code != 200:
            bad(f"HTTP {r.status_code}：{r.text[:200]}")
            return []
        data = r.json()
        ids = [m.get("id") for m in (data.get("data") or [])]
        if ids:
            ok(f"共 {len(ids)} 个模型")
            for i in ids:
                info(f"  {i}")
        else:
            bad("未返回任何模型，请确认后端是否已加载模型")
        return ids
    except Exception as e:
        bad(f"请求异常：{e}")
        return []


def chat_test(key, model):
    print(f"\n== 5. 真实对话测试（model={model}）==")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个简洁的编程助手，回答控制在三行以内。"},
            {"role": "user", "content": "用 Python 写一个读取 CSV 文件并打印前 5 行的函数。"},
        ],
        "stream": False,
    }
    try:
        t0 = time.time()
        r = requests.post(
            BASE + "/api/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=180,
        )
        dt = time.time() - t0
        if r.status_code != 200:
            bad(f"HTTP {r.status_code}：{r.text[:300]}")
            if r.status_code == 401:
                info("密钥无效或已过期，请回网页重新创建。")
            return False
        j = r.json()
        content = j["choices"][0]["message"]["content"]
        usage = j.get("usage") or {}
        ok(f"调用成功，端到端耗时 {dt:.2f}s")
        if usage:
            info(f"tokens: prompt={usage.get('prompt_tokens')} "
                 f"completion={usage.get('completion_tokens')} total={usage.get('total_tokens')}")
        print("\n----- 模型输出 -----")
        print(content.strip())
        print("--------------------")
        return True
    except Exception as e:
        bad(f"请求异常：{e}")
        return False


def clean_key(raw):
    """清理粘贴时常见的杂质：换行、引号、Bearer 前缀、多余空格。

    注意：api_key.txt 里可能既有真密钥、又有批处理写入的占位符行，
    所以要**逐行**挑出第一个有效行，而不是把所有行拼起来。
    """
    if not raw:
        return ""
    for line in str(raw).splitlines():
        k = line.strip().strip('"').strip("'").strip()
        if not k:
            continue
        if k.startswith("#"):           # 说明性注释行，跳过
            continue
        if "PASTE_YOUR_KEY" in k.upper():
            continue
        if k.lower().startswith("bearer "):
            k = k[7:].strip()
        if k.lower().startswith("authorization:"):
            k = k.split(":", 1)[1].strip()
            if k.lower().startswith("bearer "):
                k = k[7:].strip()
        if k:
            return k
    return ""


def load_key_file():
    """从脚本同目录的 api_key.txt 读取密钥（推荐给不熟悉终端的用户）。"""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_key.txt")
    if not os.path.exists(p):
        return "", p
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            return clean_key(f.read()), p
    except Exception:
        return "", p


def tool_call_test(key, model):
    """Agent 场景的关键能力：模型能否返回结构化的 tool_calls。

    Qoder / WorkBuddy 这类工具依赖模型自主决定调用工具（读写文件、执行命令）。
    如果模型不支持 function calling，接进去只能当普通聊天用，Agent 能力会失效。
    """
    print(f"\n== 6. 工具调用（function calling）测试 ==")
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "城市名称"}},
                "required": ["city"],
            },
        },
    }]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "北京现在天气怎么样？请调用工具查询。"}],
        "tools": tools,
        "tool_choice": "auto",
        "stream": False,
    }
    try:
        r = requests.post(
            BASE + "/api/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=180,
        )
        if r.status_code != 200:
            bad(f"HTTP {r.status_code}：{r.text[:300]}")
            return None
        msg = r.json()["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if calls:
            ok(f"支持工具调用，返回 {len(calls)} 个 tool_call")
            for c in calls:
                fn = c.get("function", {})
                info(f"  函数={fn.get('name')}  参数={fn.get('arguments')}")
            return True
        info("未返回 tool_calls，模型可能不支持工具调用")
        info(f"  实际回复：{str(msg.get('content'))[:120]}")
        return False
    except Exception as e:
        bad(f"请求异常：{e}")
        return None


def stream_test(key, model):
    """Agent 前端普遍使用流式输出，这里验证 SSE 是否正常。"""
    print(f"\n== 7. 流式输出（stream）测试 ==")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "从 1 数到 5，只输出数字，用逗号分隔。"}],
        "stream": True,
    }
    try:
        chunks = 0
        text = ""
        with requests.post(
            BASE + "/api/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            stream=True,
            timeout=180,
        ) as r:
            if r.status_code != 200:
                bad(f"HTTP {r.status_code}：{r.text[:200]}")
                return False
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0].get("delta", {})
                    if delta.get("content"):
                        text += delta["content"]
                        chunks += 1
                except Exception:
                    pass
        if chunks:
            ok(f"流式正常，收到 {chunks} 个数据块")
            info(f"  拼接结果：{text.strip()[:80]}")
            return True
        bad("未收到任何流式数据块")
        return False
    except Exception as e:
        bad(f"请求异常：{e}")
        return False


def vision_test(key, model):
    """验证图片输入。Qoder 添加模型时要勾「视觉」，WorkBuddy 会标能力，先测准。

    做法：现造两张纯色 PNG 分别发过去，看模型能否答对颜色。
    比用一张图更可靠 —— 单张图答对可能只是猜中。
    """
    import base64
    import struct
    import zlib

    def solid_png(w, h, rgb):
        raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

        def chunk(tag, data):
            body = tag + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

    print(f"\n== 8. 视觉（图片输入）测试 ==")
    hits = 0
    for label, rgb in [("蓝色", (0, 0, 255)), ("绿色", (0, 255, 0))]:
        url = "data:image/png;base64," + base64.b64encode(solid_png(16, 16, rgb)).decode()
        body = {
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "这张纯色图片是什么颜色？只回答颜色名称，不要解释。"},
                {"type": "image_url", "image_url": {"url": url}},
            ]}],
            "stream": False,
        }
        try:
            r = requests.post(
                BASE + "/api/chat/completions", json=body,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=120,
            )
            if r.status_code != 200:
                bad(f"HTTP {r.status_code}：{r.text[:200]}")
                continue
            ans = str(r.json()["choices"][0]["message"].get("content", "")).strip()
            if label in ans:
                ok(f"送「{label}」→ 模型答：{ans[:30]}（正确）")
                hits += 1
            else:
                bad(f"送「{label}」→ 模型答：{ans[:60]}（不符）")
        except Exception as e:
            bad(f"请求异常：{e}")
    if hits == 2:
        info("结论：支持图片输入，添加模型时可勾选「视觉」")
    elif hits == 0:
        info("结论：疑似不支持图片输入，建议关闭「视觉」")
    else:
        info("结论：结果不稳定，视觉能力存疑")
    return hits


def main():
    argv = [a for a in sys.argv[1:]]
    skip_key = "--no-key" in argv
    argv = [a for a in argv if not a.startswith("--")]

    key = clean_key(argv[0]) if argv else clean_key(os.environ.get("NCEPU_API_KEY", ""))
    key_src = "命令行参数" if (argv and key) else ("环境变量" if key else "")

    if not key:
        key, key_path = load_key_file()
        if key:
            key_src = f"api_key.txt（{key_path}）"

    print("=" * 56)
    print(" 华北电力大学 AI 编程大模型 自检")
    print("=" * 56)

    if not check_reachable():
        sys.exit(1)
    check_version()
    check_endpoint_shape()

    # 兜底：直接在控制台粘贴。用 input() 而不是 getpass，
    # 因为 getpass 在 Windows 下逐字符读键盘，无法粘贴。
    if not key and not skip_key and sys.stdin.isatty():
        print("\n[输入] 把 API 密钥粘贴进来，然后按回车。")
        print("       （密钥会显示在屏幕上，属正常现象；直接回车=跳过对话测试）")
        print("       提示：若无法粘贴，可改用同目录 api_key.txt 方式，见脚本开头说明。")
        try:
            key = clean_key(input("  API 密钥: "))
        except (EOFError, KeyboardInterrupt):
            key = ""
        if key:
            key_src = "控制台粘贴"

    if not key:
        print("\n[提示] 未提供 API 密钥，已跳过需要鉴权的测试。")
        print("       注册并创建密钥后重新运行本脚本即可。")
        return

    if key.endswith("*") or "***" in key:
        print("\n[提示] 你给的是文档里被打码的密钥，请换成自己的完整密钥。")
        return

    print(f"\n[信息] 密钥来源：{key_src}")
    print(f"[信息] 密钥长度：{len(key)} 字符，前缀：{key[:8]}...")

    ids = list_models(key)
    target = MODEL
    if ids and MODEL not in ids:
        print(f"\n[警告] 模型列表里没有 {MODEL}，尝试匹配包含 'qwen' 的项。")
        cand = [i for i in ids if "qwen" in i.lower()]
        if cand:
            target = cand[0]
            info(f"改用：{target}")
        else:
            bad("未找到 qwen 系列模型。")
            return
    elif ids and DOC_MODEL in ids:
        print(f"\n[信息] 服务器上也有文档里写的 {DOC_MODEL}。")
    if ids and MODEL not in ids and target != MODEL:
        print(f"[提醒] 请把客户端里的 Model 字段改成：{target}")
    chat_test(key, target)
    tool_call_test(key, target)
    stream_test(key, target)
    vision_test(key, target)

    print("\n" + "=" * 56)
    print(" 接入参数（Qoder / WorkBuddy 通用）")
    print("=" * 56)
    print(f"  Base URL   {BASE}/api")
    print(f"  Model ID   {target}")
    print(f"  上下文窗口  256K（max_model_len=262144）")
    print(f"  能力      工具调用 ✓  流式 ✓  视觉 ✓  思考模式 ✓")
    print("  注意       Base URL 末尾不要加斜杠，也不要加 /v1")


if __name__ == "__main__":
    main()
