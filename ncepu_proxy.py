#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ncepu_proxy.py — 校园 qwen3.8-27b 本地反代（OpenAI 标准端点适配器）

解决什么问题：
    学校端点只有 http://202.204.64.234:8080/api/chat/completions 这一条路径可用。
    但很多 harness（Cline / Roo Code / Aider / OpenAI SDK / 各类客户端）会自己往
    Base URL 后面拼 /v1/chat/completions，直接填学校地址就会 405。

    本脚本在本机起一个标准 OpenAI 端点，把请求转成学校认的路径：

        harness  →  http://127.0.0.1:8788/v1/chat/completions
                        ↓ 本脚本转换
                    http://202.204.64.234:8080/api/chat/completions

顺带修掉两个已知的坑：
    1. reasoning_effort 传 high / max / minimal 等会被服务端 400 → 自动映射到合法档位
    2. max_tokens 超过 200000 会被拒 → 自动截断

用法：
    <venv python> ncepu_proxy.py                 # 默认监听 127.0.0.1:8788
    <venv python> ncepu_proxy.py --port 9000
    <venv python> ncepu_proxy.py --key sk-xxxx   # 也可用环境变量 NCEPU_API_KEY
                                                  # 或同目录 api_key.txt

harness 里这样填：
    Base URL : http://127.0.0.1:8788/v1
    API Key  : 任意值（本脚本用本地配置的密钥访问学校）
    Model ID : qwen3.8-27b
"""

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import requests
except ImportError:
    print("缺少依赖 requests，请先安装：pip install requests")
    sys.exit(1)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---------------------------------------------------------------- 配置

UPSTREAM_BASE = "http://202.204.64.234:8080/api"
UPSTREAM_CHAT = UPSTREAM_BASE + "/chat/completions"
MODEL_ID = "qwen3.8-27b"
TIMEOUT = 600            # 长任务放宽，单位秒
MAX_OUTPUT_TOKENS = 200000

# 服务端只认 low / medium / xhigh / none，其余一律映射过去，避免 400
EFFORT_MAP = {
    "high": "xhigh",
    "max": "xhigh",
    "maximum": "xhigh",
    "ultra": "xhigh",
    "extreme": "xhigh",
    "minimal": "low",
    "lowest": "low",
}
VALID_EFFORT = {"low", "medium", "xhigh", "none"}

KEY = ""


# ---------------------------------------------------------------- 工具

def clean_key(raw):
    """逐行取第一个有效密钥行（用户可能把密钥粘在占位符上方）。"""
    if not raw:
        return ""
    for line in str(raw).splitlines():
        k = line.strip().strip('"').strip("'").strip()
        if not k or "PASTE_YOUR_KEY" in k.upper():
            continue
        if k.startswith("#"):           # 说明性注释行，跳过
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


def resolve_key(cli_key=None):
    if cli_key:
        return clean_key(cli_key)
    env = os.environ.get("NCEPU_API_KEY")
    if env:
        return clean_key(env)
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "api_key.txt")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return clean_key(f.read())
    return ""


def log(*parts):
    print("[%s]" % time.strftime("%H:%M:%S"), *parts, flush=True)


# ---------------------------------------------------------------- 请求处理

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"     # 流式响应靠连接关闭界定，最省事也最稳
    server_version = "ncepu-proxy/1.0"

    def log_message(self, fmt, *args):
        pass                          # 屏蔽默认的逐请求噪声日志

    # ---------- 内部工具 ----------

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, code, message):
        self._send_json(code, {"error": {"message": message, "type": "proxy_error"}})

    # ---------- 路由 ----------

    def do_GET(self):
        if self.path.rstrip("/") in ("/v1/models", "/models"):
            self._send_json(200, {
                "object": "list",
                "data": [{
                    "id": MODEL_ID,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "ncepu",
                }],
            })
        elif self.path.rstrip("/") in ("/health", "/v1/health", ""):
            self._send_json(200, {"status": "ok", "upstream": UPSTREAM_BASE, "model": MODEL_ID})
        else:
            self._send_error_json(404, "not found: %s" % self.path)

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if path not in ("/v1/chat/completions", "/chat/completions"):
            self._send_error_json(404, "unsupported path: %s（本代理只转发 chat/completions）" % self.path)
            return
        self._handle_chat()

    # ---------- 核心转发 ----------

    def _handle_chat(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self._send_error_json(400, "请求体不是合法 JSON: %s" % exc)
            return

        # 1) 强制模型名（有些 harness 会传自己的显示名）
        original_model = data.get("model")
        data["model"] = MODEL_ID
        if original_model and original_model != MODEL_ID:
            log("模型名映射:", original_model, "->", MODEL_ID)

        # 2) reasoning_effort 兜底映射
        effort = data.get("reasoning_effort")
        if effort is not None:
            e = str(effort).strip().lower()
            if e not in VALID_EFFORT:
                mapped = EFFORT_MAP.get(e, "xhigh")
                data["reasoning_effort"] = mapped
                log("思考强度映射:", effort, "->", mapped)

        # 3) max_tokens 截断
        mt = data.get("max_tokens")
        if isinstance(mt, int) and mt > MAX_OUTPUT_TOKENS:
            data["max_tokens"] = MAX_OUTPUT_TOKENS
            log("max_tokens 截断:", mt, "->", MAX_OUTPUT_TOKENS)

        stream = bool(data.get("stream"))
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer %s" % KEY,
        }

        started = time.time()
        try:
            resp = requests.post(UPSTREAM_CHAT, json=data, headers=headers,
                                 stream=stream, timeout=TIMEOUT)
        except Exception as exc:
            log("上游请求失败:", exc)
            self._send_error_json(502, "无法连接学校服务: %s" % exc)
            return

        log("POST /v1/chat/completions  model=%s stream=%s -> HTTP %d (%.2fs)"
            % (MODEL_ID, stream, resp.status_code, time.time() - started))

        # 上游报错：原样回传，方便 harness 显示真实原因
        if resp.status_code != 200:
            body = resp.content
            self.send_response(resp.status_code)
            self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # 流式：逐块透传
        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                for chunk in resp.iter_content(chunk_size=None):
                    if chunk:
                        self.wfile.write(chunk)
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                log("客户端提前断开连接")
            return

        # 非流式：整包回传
        body = resp.content
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------- 入口

def main():
    global KEY

    ap = argparse.ArgumentParser(description="校园 qwen3.8-27b 本地反代")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1（只允许本机访问）")
    ap.add_argument("--port", type=int, default=8788, help="监听端口，默认 8788")
    ap.add_argument("--key", default=None, help="API Key，缺省时读环境变量 NCEPU_API_KEY 或 api_key.txt")
    args = ap.parse_args()

    KEY = resolve_key(args.key)
    if not KEY:
        print("未找到 API Key。请任选一种方式提供：")
        print("  1) 在脚本同目录放 api_key.txt，第 1 行写 sk-xxx")
        print("  2) 设置环境变量 NCEPU_API_KEY")
        print("  3) 启动时加 --key sk-xxx")
        sys.exit(1)

    print("=" * 62)
    print("  校园 qwen3.8-27b 本地反代已启动")
    print("=" * 62)
    print("  上游   : %s" % UPSTREAM_CHAT)
    print("  模型   : %s" % MODEL_ID)
    print("  密钥   : %s...%s（已加载）" % (KEY[:6], KEY[-4:]) if len(KEY) > 12 else "  密钥   : 已加载")
    print("  监听   : http://%s:%d" % (args.host, args.port))
    print("")
    print("  harness 里填：")
    print("    Base URL : http://%s:%d/v1" % (args.host, args.port))
    print("    API Key  : 任意值")
    print("    Model ID : %s" % MODEL_ID)
    print("")
    print("  自检：curl http://%s:%d/health" % (args.host, args.port))
    print("  停止：Ctrl+C")
    print("=" * 62, flush=True)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        server.server_close()


if __name__ == "__main__":
    main()
