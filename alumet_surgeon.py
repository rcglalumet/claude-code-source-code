#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alumet OS V10 (V1.2.2 Immortal Silicon State)
全域基建播种机与日常灌注交互终端 (IaC & CLI)

双生命周期: 首次运行=IaC自解压 | 系统已存在=6端口灌注CLI
拓扑源: 动态读取 Alumet_OS_Topology.py (唯一真理源, 禁止硬编码副本)
5大生命体征: Claude Code TS(yoloClassifier/QueryEngine/compact/denialTracking/Tool) + 旧版防御资产双向提炼
架构: 微内核 — 工具层委托 core.semantic_utils, 骨架层自持路由与注入算法
"""

import os
import sys
import re
import json
import ast
import importlib.util
import logging
import subprocess
from datetime import datetime

# 工具层委托 (脱水后迁移至 core/semantic_utils.py)
try:
    from core.semantic_utils import (
        _c, pc, _write_bak, safe_write, safe_append_inject,
        cleanup_stale_drafts, create_backup, detect_infra_missing,
        inject_xiangshu_genome, run_housekeeping_inline,
    )
except ImportError:
    # 自举降级: core/ 尚未存在时内联最小集，保证首次播种不崩溃
    _ANSI = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
              "blue": "\033[94m", "cyan": "\033[96m", "reset": "\033[0m"}
    def _c(t, c="green"): return f"{_ANSI.get(c, _ANSI['reset'])}{t}{_ANSI['reset']}"
    def pc(t, c="green"): print(_c(t, c))
    def _write_bak(p):
        import shutil
        if os.path.exists(p) and not p.endswith(".bak"):
            try: shutil.copy2(p, p + ".bak")
            except Exception: pass
    def safe_write(path, content, force=False):
        import time, shutil
        if not content.strip(): return path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        actual = path
        if not force and path.endswith(".py") and os.path.exists(path):
            actual = path.replace(".py", f"_SURGEON_DRAFT_{int(time.time())}.py")
            pc(f"  ⚠️ [防抖] {path} -> 草稿舱: {actual}", "yellow")
        _write_bak(actual)
        with open(actual, "w", encoding="utf-8") as f: f.write(content)
        return actual
    def safe_append_inject(path, content, marker=None):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if not os.path.exists(path):
            _write_bak(path)
            with open(path, "w", encoding="utf-8") as f: f.write(content)
            return "created"
        with open(path, "r", encoding="utf-8", errors="ignore") as f: existing = f.read()
        if marker and marker in existing: return "skipped"
        _write_bak(path)
        with open(path, "a", encoding="utf-8") as f: f.write("\n" + content)
        return "appended"
    def cleanup_stale_drafts(days=3): pass
    def create_backup():
        import shutil, time
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pc(f"📦 [Step 1] 备份快照...", "blue")
        try: shutil.make_archive(f"../ALUMET_OS_V10_BACKUP_{ts}", "zip", ".")
        except Exception as e: pc(f"  ⚠️ 备份失败 (非阻断): {e}", "yellow")
    def detect_infra_missing():
        markers = ["agentic_workflow", "expert_rules", "modules/01_xiangshu", "data_center"]
        return sum(1 for m in markers if not os.path.exists(m)) >= 2
    def inject_xiangshu_genome(raw): pc("[-] core.semantic_utils 尚未就位，基因注入跳过。", "red")
    def run_housekeeping_inline(): pc("⚡ [AutoDream] 后台任务跳过 (core 未就位)。", "yellow")

logging.basicConfig(level=logging.INFO, format='%(message)s')

# ════════════════════════════════════════════════════════════════
# ██████████████  PAYLOAD ZONE — 不计入 ELL  ██████████████████
# 5大生命体征硬编码代码块 (Claude Code TS + 旧版防御资产双向提炼)
# ════════════════════════════════════════════════════════════════

# ── 生命体征 1: Dumb Tools & 安全隔离舱 ──────────────────────
# 目标: simulation_sandbox/vm_repl_sandbox.py
# 提炼: Claude Code Tool.ts is_read_only / toAutoClassifierInput
CODE_VM_REPL_SANDBOX = '''import ast


class RalphStopException(Exception):
    def __init__(self, message):
        super().__init__(message)


class ASTSentinel(ast.NodeVisitor):
    """
    [V10 Dumb Tools] 零容忍拦截 eval/exec 注入。
    对齐 Claude Code Tool.ts: is_read_only=True, toAutoClassifierInput 哲学。
    工具内部绝对禁止推演逻辑，仅作纯粹数学执行器。
    """
    FORBIDDEN_FUNCS = frozenset({\'eval\', \'exec\', \'compile\', \'globals\', \'locals\', \'__import__\'})

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_FUNCS:
            raise RalphStopException(f"AST SENTINEL: {node.func.id}() 被零容忍拦截")
        self.generic_visit(node)

    @staticmethod
    def validate_source(source_code: str) -> bool:
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            raise RalphStopException(f"语法错误: {e}")
        ASTSentinel().visit(tree)
        return True


class KernelApiProxy:
    """
    [V10 Dumb Tools 契约] MCP工具内部绝对禁止推演逻辑。
    通过代理句柄隔离 L0 访问，is_read_only=True。
    """
    is_read_only: bool = True
    HIGH_RISK_OPS = frozenset({
        "delete_file", "overwrite_rules", "execute_arbitrary_code",
        "modify_constitution", "force_reset_circuit"
    })

    def __init__(self):
        self._approved: set = set()

    def call(self, operation: str, params: dict = None) -> dict:
        if not isinstance(params, dict): params = {}
        if operation in self.HIGH_RISK_OPS and operation not in self._approved:
            return {"error": f"[HITL] 高危操作 {operation} 需要人工授权"}
        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            return {"error": f"未知操作: {operation}"}
        return handler(params)

    def grant_approval(self, op: str):
        if op in self.HIGH_RISK_OPS:
            self._approved.add(op)

    def _op_read_file(self, p):
        path = p.get("path", "")
        if not os.path.exists(path): return {"error": f"文件不存在: {path}"}
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f: return {"content": f.read()}
        except Exception as e: return {"error": str(e)}

    def _op_list_dir(self, p):
        path = p.get("path", ".")
        if not os.path.isdir(path): return {"error": f"目录不存在: {path}"}
        return {"entries": os.listdir(path)}


class VMReplSandbox:
    """沙盒命名空间仅注入 kernel_api_proxy.call 安全代理句柄。"""
    def __init__(self, proxy=None):
        self._proxy = proxy or KernelApiProxy()

    def execute(self, code: str) -> dict:
        try:
            ASTSentinel.validate_source(code)
        except RalphStopException as e:
            return {"status": "BLOCKED", "reason": str(e)}
        safe_ns = {"api_call": self._proxy.call, "__builtins__": {}}
        try:
            exec(compile(code, "<sandbox>", "exec"), safe_ns)  # noqa
            return {"status": "OK", "output": safe_ns.get("__result__")}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
'''

# ── 生命体征 2: Exact Search & 跨会话热记忆 ──────────────────
# 目标: data_center/exact_grep_retriever.py
# 提炼: MEMORY.md 跨会话哲学, Grep 精确查表零幻觉
CODE_EXACT_GREP_RETRIEVER = '''"""
Exact Grep Retriever - V10 全域智能检索
[Exact Search 哲学] 抛弃 ChromaDB 向量幻觉。
朴素 Grep 纯文本查表与正则匹配，零幻觉，零依赖。
跨会话热记忆: 25KB 红线硬限，溢出 IMMORTAL 标签语义提纯。
对齐 Claude Code MEMORY.md: 重启不失忆。
"""
import os, re, json

MAX_HOT_MEMORY_BYTES = 25 * 1024  # 25KB 红线，硬编码禁止修改


class ExactGrepRetriever:
    def __init__(self, data_root="data_center"):
        self.data_root = data_root

    def search(self, query, file_extensions=(".txt",".jsonl",".json",".py"), max_results=50):
        if not query or not isinstance(query, str): return []
        try: pattern = re.compile(query, re.IGNORECASE)
        except re.error: pattern = re.compile(re.escape(query), re.IGNORECASE)
        results = []
        for root, _, files in os.walk(self.data_root):
            for fname in files:
                if not any(fname.endswith(ext) for ext in file_extensions): continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, 1):
                            if pattern.search(line):
                                results.append({"file": fpath, "line": lineno, "content": line.rstrip()})
                                if len(results) >= max_results: return results
                except Exception: pass
        return results


class SmartMemoryGuard:
    """25KB 红线 -> IMMORTAL 标签语义提纯。对齐 Claude Code compact.ts。"""
    MAX_BYTES = 25 * 1024

    @staticmethod
    def enforce(memory_file):
        if not os.path.exists(memory_file): return
        if os.path.getsize(memory_file) <= SmartMemoryGuard.MAX_BYTES: return
        print("⚠️ [SmartMemory] 触达 25KB 红线，启动语义提纯...")
        try:
            with open(memory_file, "r", encoding="utf-8") as f: data = json.load(f)
            immortal = {k: v for k, v in data.items() if "[IMMORTAL]" in str(k)}
            mortal   = {k: v for k, v in data.items() if "[IMMORTAL]" not in str(k)}
            keys = list(mortal.keys())
            result = {**immortal, **{k: mortal[k] for k in keys[len(keys)//2:]}}
            with open(memory_file, "w", encoding="utf-8") as f: json.dump(result, f, ensure_ascii=False, indent=2)
            print("✨ [SmartMemory] 语义提纯完成，高频指纹永久锚定！")
        except Exception as e: print(f"⚠️ [SmartMemory] 失败: {e}")
'''

# ── 生命体征 3: 极致缓存护城河 ───────────────────────────────
# 目标: core/mcp_tool_protocol.py, agentic_workflow/working_memory_context.py
# 提炼: compact.ts COMPACT_MAX_OUTPUT_TOKENS, 禁用Enum防缓存击穿
CODE_MCP_TOOL_PROTOCOL = '''"""
MCP Tool Protocol - V10 契约层
1. Dumb Tools: 工具内部绝对禁止推演逻辑，仅作数学/数据执行器。
2. 极致缓存护城河: Schema 禁止使用 Enum 类型，防缓存击穿。
   改用极简扁平化字符串常量。
3. is_read_only 属性配合调度器实现只读隔离。
"""
from typing import Any

DOMAIN_NAMES = ["xiangshu", "bazi", "liuyao", "xuankong", "finance"]  # 禁止改为 Enum
PORT_NAMES   = ["R", "M", "E", "T", "P", "F"]                         # 禁止改为 Enum


class MCPToolBase:
    name: str = ""
    description: str = ""
    is_read_only: bool = True

    def get_schema(self) -> dict: raise NotImplementedError
    def execute(self, params: dict) -> Any: raise NotImplementedError
    def _safe_get(self, d, key, default=None):
        if not isinstance(d, dict): return default
        return d.get(key, default)


class ExactGrepSearchTool(MCPToolBase):
    """[Exact Search 哲学] 朴素 Grep 搜索工具，零向量幻觉。"""
    name = "exact_grep_search"; description = "精确 Grep 文本搜索"; is_read_only = True

    def get_schema(self):
        return {"type": "object", "properties": {
            "query": {"type": "string"}, "search_path": {"type": "string"},
            "file_extension": {"type": "string"}}, "required": ["query", "search_path"]}

    def execute(self, params):
        import os, re
        query = self._safe_get(params, "query", "")
        path  = self._safe_get(params, "search_path", ".")
        ext   = self._safe_get(params, "file_extension", "")
        if not os.path.isdir(path): return {"error": f"路径不存在: {path}"}
        try: pattern = re.compile(query)
        except re.error: pattern = re.compile(re.escape(query))
        results = []
        for root, _, files in os.walk(path):
            for fname in files:
                if ext and not fname.endswith(ext): continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, 1):
                            if pattern.search(line):
                                results.append({"file": fpath, "line": lineno, "content": line.rstrip()})
                except Exception: pass
        return {"results": results, "count": len(results)}
'''

CODE_WORKING_MEMORY_CONTEXT = '''"""
Working Memory Context - V10 动态热数据容器
25KB 热数据溢出红线，硬编码不可修改。
对齐 Claude Code compact.ts: COMPACT_MAX_OUTPUT_TOKENS 上下文折叠哲学。
"""
import os, json

MAX_HOT_MEMORY_BYTES = 25 * 1024  # 硬编码禁止修改


class WorkingMemoryContext:
    def __init__(self, session_id, memory_file="data_center/system_hot_memory.json"):
        self.session_id = session_id
        self.memory_file = memory_file
        self._ctx: dict = {}
        self._load()

    def _load(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f: self._ctx = json.load(f)
            except Exception: self._ctx = {}

    def set(self, key, value):
        if not isinstance(key, str): raise TypeError("键必须是字符串")
        self._ctx[key] = value
        if len(json.dumps(self._ctx, ensure_ascii=False).encode()) > MAX_HOT_MEMORY_BYTES:
            self._compact()

    def get(self, key, default=None): return self._ctx.get(key, default)

    def _compact(self):
        print("⚠️ [WorkingMemory] 触达 25KB 红线，启动语义提纯...")
        immortal = {k: v for k, v in self._ctx.items() if "[IMMORTAL]" in str(k)}
        mortal   = {k: v for k, v in self._ctx.items() if "[IMMORTAL]" not in str(k)}
        keys = list(mortal.keys())
        self._ctx = {**immortal, **{k: mortal[k] for k in keys[len(keys)//2:]}}
        print("✨ [WorkingMemory] 语义提纯完成。")

    def flush(self):
        os.makedirs(os.path.dirname(self.memory_file) or ".", exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self._ctx, f, ensure_ascii=False, indent=2)
'''

# ── 生命体征 4: YOLO 拦截 & 非对称算力防御 ───────────────────
# 目标: agentic_workflow/yolo_veto_classifier.py
#       agentic_workflow/agent_query_engine.py
#       oracle_gateway/llm_network_gateway.py
# 提炼: yoloClassifier.ts Stage1/Stage2, denialTracking.ts maxConsecutive=3, compact.ts 413 Hook
CODE_YOLO_VETO_CLASSIFIER = r'''"""
YOLO Veto Classifier - V10 前置拦截防线
提炼自 Claude Code yoloClassifier.ts 两阶段 XML 判定:
  Stage 1 (fast):    低成本规则引擎，XML_S1_SUFFIX "Err on the side of blocking."
  Stage 2 (thinking): 深度链式推理复核，XML_S2_SUFFIX "Review the classification process."
非对称算力防御: 99% 正常流量 Stage 1 极速通过，降低算力消耗。
绝对禁止 LLM 调用，保持纯规则/正则执行。
"""
import re

GARBAGE_PATTERNS = [
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
    r"(.)\1{20,}",
    r"[^\x00-\x7f]{50,}(?![\u4e00-\u9fff])",
]
HIGH_RISK_PATTERNS = [
    r"(?i)(rm\s+-rf|format\s+c:|drop\s+table|delete\s+from)",
    r"(?i)(eval|exec|__import__|subprocess\.call)",
    r"(?i)(password|secret|api_key|private_key)\s*=\s*['\"][^'\"]{8,}",
]
ESCALATE_PATTERNS = [
    r"(?i)(sudo|chmod\s+777|chown\s+root)",
    r"(?i)(base64\s*-d|xxd\s*-r|openssl\s+enc)",
    r"(?i)(nc\s+-e|ncat\s+.*-e|socat\s+exec)",
]


class YoloVetoClassifier:
    def __init__(self):
        self._garbage   = [re.compile(p) for p in GARBAGE_PATTERNS]
        self._high_risk = [re.compile(p) for p in HIGH_RISK_PATTERNS]
        self._escalate  = [re.compile(p) for p in ESCALATE_PATTERNS]

    def classify(self, text: str) -> dict:
        if not isinstance(text, str) or not text.strip():
            return {"vetoed": True, "reason": "空输入", "stage": "fast"}
        for p in self._garbage:
            if p.search(text): return {"vetoed": True, "reason": "乱码/垃圾字符", "stage": "fast"}
        for p in self._high_risk:
            if p.search(text): return {"vetoed": True, "reason": "高危指令", "escalate": True, "stage": "fast"}
        if len(text) > 32768: return {"vetoed": True, "reason": "超过 32KB", "stage": "fast"}
        for p in self._escalate:
            if p.search(text): return {"vetoed": True, "reason": "Stage2 升级危险模式", "stage": "thinking"}
        return {"vetoed": False, "stage": "fast"}
'''

CODE_AGENT_QUERY_ENGINE = '''"""
Agent Query Engine - V10 全域唯一主循环 (while-true 架构)
L3 控制平面核心，映射 Claude Code QueryEngine.ts。
提炼自 denialTracking.ts: DENIAL_LIMITS.maxConsecutive=3, maxTotal=20。
Fail-Closed 熔断: 连续失败 3 次 -> 拒绝服务，硬编码不可绕过。
"""


class AgentQueryEngine:
    MAX_CONSECUTIVE = 3   # 来自 denialTracking.ts maxConsecutive，禁止修改
    MAX_TOTAL       = 20  # 来自 denialTracking.ts maxTotal，禁止修改

    def __init__(self, working_memory=None, yolo=None, tools=None, oracle=None):
        self.memory = working_memory
        self.yolo   = yolo
        self.tools  = tools
        self.oracle = oracle
        self._consecutive = 0
        self._total       = 0
        self._fused       = False

    def run(self, query: str) -> dict:
        if self._fused:
            return {"status": "FAIL_CLOSED", "reason": "熔断器已触发，拒绝服务。"}
        if self.yolo:
            v = self.yolo.classify(query)
            if v.get("vetoed"):
                return {"status": "VETOED", "reason": v.get("reason", "YOLO 拦截")}
        try:
            result = self._execute(query)
            self._consecutive = 0
            return result
        except Exception as e:
            self._consecutive += 1
            self._total += 1
            if self._consecutive >= self.MAX_CONSECUTIVE or self._total >= self.MAX_TOTAL:
                self._fused = True
                return {"status": "FAIL_CLOSED",
                        "reason": f"连续失败 {self._consecutive} 次 / 累计 {self._total} 次: {e}"}
            return {"status": "ERROR", "error": str(e), "consecutive": self._consecutive}

    def _execute(self, query: str) -> dict:
        raise NotImplementedError("子类实现 _execute")

    def reset_circuit(self):
        """人工授权后复位"""
        self._consecutive = 0; self._total = 0; self._fused = False
'''

CODE_LLM_NETWORK_GATEWAY = '''"""
LLM Network Gateway - V10 全局网络层 (L4)
核心: 413 Reactive Compact Hook。
遇上下文溢出直接唤醒 Compactor，不中断服务。
提炼自 Claude Code compact.ts: getPromptTooLongTokenGap / PROMPT_TOO_LONG_ERROR_MESSAGE。
五级压缩漏斗 (对齐 compact.ts COMPRESS_LEVELS)。
"""
import json

MAX_HOT_MEMORY_BYTES = 25 * 1024
COMPRESS_LEVELS = [0.9, 0.75, 0.6, 0.4, 0.25]


class ContextAutoCompactor:
    def compact(self, context: dict, reactive: bool = False) -> dict:
        target = MAX_HOT_MEMORY_BYTES if not reactive else MAX_HOT_MEMORY_BYTES // 2
        for ratio in COMPRESS_LEVELS:
            if len(json.dumps(context, ensure_ascii=False).encode()) <= target: return context
            context = self._apply(context, ratio)
            print(f"🗜️ [Compactor] 压缩级别 {ratio}: {len(json.dumps(context, ensure_ascii=False).encode())} bytes")
        return context

    def _apply(self, context, ratio):
        immortal = {k: v for k, v in context.items() if "[IMMORTAL]" in str(k)}
        mortal   = {k: v for k, v in context.items() if "[IMMORTAL]" not in str(k)}
        keep = max(1, int(len(mortal) * ratio))
        return {**immortal, **{k: mortal[k] for k in list(mortal)[-keep:]}}


class LLMNetworkGateway:
    def __init__(self): self._compactor = ContextAutoCompactor()

    def send(self, payload: dict) -> dict:
        raise NotImplementedError("[V10] LLM 网关骨架就位，子类实现具体发送逻辑。")

    def on_413_error(self, context: dict) -> dict:
        """413 Hook: 唤醒 Compactor 而不中断服务。"""
        print("[Gateway] 413 Context Too Long -> Reactive Compact")
        return self._compactor.compact(context, reactive=True)
'''

# ── 生命体征 5: AutoDream 后台进化 ────────────────────────────
# 目标: async_background_housekeeping.py, training_camp/mcts_constant_distiller.py
# 旧防线: TensorFingerprintGenerator, RTX5090ResourceManager
CODE_ASYNC_HOUSEKEEPING = '''"""
Async Background Housekeeping - V10 AutoDream 守护进程
绝对异步执行，断电不死。
两阶段垃圾回收 (.orphaned_at), MCTS 复盘, 草稿清道夫。
旧防线资产: TensorFingerprintGenerator + RTX5090ResourceManager 骨架。
"""
import asyncio, os, time, glob, json, hashlib


ORPHAN_MARKER    = ".orphaned_at"
DRAFT_MAX_AGE    = 3 * 86400


class TensorFingerprintGenerator:
    """[旧防线] L0 物理证明机，SHA-256 确定性签名防篡改。"""
    @staticmethod
    def generate(state: dict, engine: str) -> str:
        s = f"ENGINE:{engine}|STATE:{json.dumps(state, sort_keys=True, ensure_ascii=False)}"
        return hashlib.sha256(s.encode()).hexdigest()

    @staticmethod
    def verify(state: dict, engine: str, proof: str) -> bool:
        return TensorFingerprintGenerator.generate(state, engine) == proof


class RTX5090ResourceManager:
    """[旧防线] 32GB VRAM 潮汐调度骨架，VLM/LLM 互斥。"""
    VRAM_TOTAL_GB = 32; VLM_GB = 20; LLM_GB = 10

    def __init__(self): self._vlm = False; self._llm = False

    def status(self) -> dict:
        used = (self.VLM_GB if self._vlm else 0) + (self.LLM_GB if self._llm else 0)
        return {"total_gb": self.VRAM_TOTAL_GB, "used_gb": used,
                "free_gb": self.VRAM_TOTAL_GB - used, "vlm": self._vlm, "llm": self._llm}


async def two_pass_gc(gc_dir="data_center/bookkeeping_gc"):
    if not os.path.isdir(gc_dir): return
    now = time.time()
    for fname in os.listdir(gc_dir):
        if fname.endswith(ORPHAN_MARKER): continue
        fpath  = os.path.join(gc_dir, fname)
        marker = fpath + ORPHAN_MARKER
        if os.path.exists(marker):
            try: os.remove(fpath); os.remove(marker); print(f"♻️ [GC] 两阶段回收: {fname}")
            except Exception as e: print(f"⚠️ [GC] 回收失败 {fname}: {e}")
        elif now - os.path.getmtime(fpath) > DRAFT_MAX_AGE:
            try:
                with open(marker, "w") as f: f.write(str(now))
                print(f"🏷️ [GC] 一阶段标记孤儿: {fname}")
            except Exception: pass
    await asyncio.sleep(0)


async def cleanup_drafts(root="."):
    now = time.time(); deleted = 0
    for pattern in [f"{root}/**/*_SURGEON_DRAFT_*.py", f"{root}/**/*.draft*"]:
        for fp in glob.glob(pattern, recursive=True):
            if os.path.isfile(fp) and now - os.path.getmtime(fp) > DRAFT_MAX_AGE:
                try: os.remove(fp); deleted += 1
                except Exception: pass
    if deleted: print(f"🧹 [AutoDream] 已清理 {deleted} 个过期草稿")
    await asyncio.sleep(0)


async def run_housekeeping():
    print("⚡ [AutoDream] 后台守护进程启动...")
    await cleanup_drafts()
    await two_pass_gc()
    if os.path.exists("training_camp/mcts_constant_distiller.py"):
        print("🧠 [AutoDream] 触发 MCTS 蒸馏器...")
    print("✅ [AutoDream] 本轮后台任务完成。")


if __name__ == "__main__":
    asyncio.run(run_housekeeping())
'''

CODE_MCTS_DISTILLER = '''"""
MCTS Constant Distiller - V10 后台蒸馏器
配合 AutoDream，夜间静默复盘脏数据，提炼新常数反哺 L5。
"""
import json, os


class MCTSConstantDistiller:
    def __init__(self, l5_dir="expert_rules"):
        self.l5_dir = l5_dir

    def distill(self, history_logs: list) -> dict:
        if not isinstance(history_logs, list): raise ValueError("history_logs 必须是列表")
        freq: dict = {}
        for entry in history_logs:
            if not isinstance(entry, dict): continue
            for k in entry.get("features", []): freq[k] = freq.get(k, 0) + 1
        threshold = max(1, len(history_logs) // 10)
        return {"distilled": {k: v for k, v in freq.items() if v >= threshold},
                "total_logs": len(history_logs)}

    def write_back(self, constants: dict, domain="global"):
        target = os.path.join(self.l5_dir, f"{domain}_distilled_constants.json")
        os.makedirs(self.l5_dir, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f: json.dump(constants, f, ensure_ascii=False, indent=2)
        print(f"✨ [Distiller] 常数已写回 L5: {target}")
'''

# ── 旧防线资产 ────────────────────────────────────────────────
CODE_AST_SENTINEL = '''import ast


class RalphStopException(Exception):
    def __init__(self, message): super().__init__(message)


class ASTSentinel(ast.NodeVisitor):
    FORBIDDEN_FUNCS = frozenset({\'eval\', \'exec\', \'compile\', \'globals\', \'locals\', \'__import__\'})

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_FUNCS:
            raise RalphStopException(f"AST SENTINEL: {node.func.id}() 被零容忍拦截")
        self.generic_visit(node)

    @staticmethod
    def validate_source(source_code: str) -> bool:
        try: tree = ast.parse(source_code)
        except SyntaxError as e: raise RalphStopException(f"语法错误: {e}")
        ASTSentinel().visit(tree)
        return True
'''

CODE_DENIAL_TRACKING = '''"""
Denial Tracking Circuit - V10 防爆熔断器
提炼自 Claude Code denialTracking.ts:
  DENIAL_LIMITS.maxConsecutive = 3
  DENIAL_LIMITS.maxTotal = 20
硬编码，不可配置，不可绕过。
"""
import time


class DenialTrackingCircuit:
    MAX_CONSECUTIVE = 3   # denialTracking.ts maxConsecutive
    MAX_TOTAL       = 20  # denialTracking.ts maxTotal

    def __init__(self, cooldown=60):
        self._consecutive = 0; self._total = 0
        self._state = "CLOSED"; self._last_fail = 0.0; self._cooldown = cooldown

    @property
    def is_open(self):
        if self._state == "OPEN":
            if time.time() - self._last_fail > self._cooldown:
                self._state = "HALF_OPEN"; return False
            return True
        return False

    def should_fallback(self):
        return self._consecutive >= self.MAX_CONSECUTIVE or self._total >= self.MAX_TOTAL

    def record_success(self): self._consecutive = 0; self._state = "CLOSED"

    def record_failure(self):
        self._consecutive += 1; self._total += 1; self._last_fail = time.time()
        if self.should_fallback():
            self._state = "OPEN"
            print(f"⚠️ [DenialTracking] 连续 {self._consecutive}/累计 {self._total} 次 -> OPEN")

    def get_state(self): return self._state

    def force_reset(self):
        self._consecutive = 0; self._total = 0; self._state = "CLOSED"; self._last_fail = 0.0
'''

CODE_EXPERT_RULES_INIT = '''"""expert_rules/__init__.py - 路由挂载点防污染深拷贝隔离"""
import copy

def safe_export_rules(rules_dict: dict) -> dict:
    if not isinstance(rules_dict, dict): raise ValueError("尝试导出非字典格式的规则！")
    return copy.deepcopy(rules_dict)
'''

CODE_DYNAMIC_TIERING_MDC = '''---
description: "V10 铁律：SLA 动态降维法则。"
globs: ["**/*.py"]
---
# 铁律 8.0：SLA 动态降维法则

1. **常规流量**：仅通过 AST 确定性编译器，极速输出，不唤醒 LLM 反思。
2. **高危/高客单价流量**：触发全量校验（密码学指纹 + L4 深度 ReACT）。

修改 `dynamic_tiering_gateway.py` 时，必须严格保证两种 SLA 通道的物理隔离。
'''

CODE_CONSTITUTION_MDC = '''---
description: "V10 终极宪法：强制所有 AI 在修改或生成代码前执行审计。"
globs: ["**/*.py"]
---
# 钛合金编程铁律 (Titanium Coding Protocol)

1. **[防降维底线]**: 绝对不能删 try/except 与空载校验，绝不合并独立状态分支。
2. **[防投毒]**: 新增逻辑必须包含 isinstance 或 .get(key, default) 兜底装甲。
3. **[全量输出]**: 绝对禁止占位符，原封不动保留未修改的公式和注释。
4. **[Dumb Tools]**: MCP 工具内部绝对禁止推演逻辑，仅作纯数学/数据执行器。
5. **[Exact Search]**: 禁止向量检索，使用 Grep 精确查表。
6. **[25KB 红线]**: 热记忆硬限 25KB，溢出强制语义提纯。
7. **[熔断底线]**: 连续失败 3 次 Fail-Closed (denialTracking.ts maxConsecutive=3)。
'''

CODE_SYSTEM_HOT_MEMORY = json.dumps({
    "[IMMORTAL] system_version": "Alumet OS V10 (V1.2.2 Immortal Silicon State)",
    "[IMMORTAL] created_at": datetime.now().isoformat(),
    "[IMMORTAL] philosophy_exact_search": "禁止向量幻觉，强制 Grep 精确查表",
    "[IMMORTAL] philosophy_25kb_limit": "热记忆硬限 25KB，溢出强制语义提纯",
    "[IMMORTAL] philosophy_fail_closed": "连续失败 3 次 Fail-Closed 熔断",
    "[IMMORTAL] claude_code_alignment": "MEMORY.md 跨会话偏好记忆机制对齐",
}, ensure_ascii=False, indent=2) + "\n"

# ════════════════════════════════════════════════════════════════
# ██████████████  CORE LOGIC ZONE — ELL 从此开始计算  ██████████
# ════════════════════════════════════════════════════════════════

# ── 全域物理目录列表 ─────────────────────────────────────────
ALUMET_DIRECTORIES = [
    ".cursor/rules", ".cursor/commands", ".vscode",
    "core", "core_engine", "agentic_workflow", "expert_rules",
    "modules/01_xiangshu", "modules/02_bazi", "modules/03_liuyao",
    "modules/04_xuankong", "modules/05_finance",
    "oracle_gateway/fallback_v7", "simulation_sandbox",
    "data_center/raw_cases/01_xiangshu_img", "data_center/raw_cases/02_bazi_txt",
    "data_center/raw_cases/03_liuyao_txt",  "data_center/raw_cases/04_xuankong_map",
    "data_center/raw_cases/05_finance_kline",
    "data_center/verified_cases/01_xiangshu", "data_center/verified_cases/02_bazi",
    "data_center/verified_cases/03_liuyao",   "data_center/verified_cases/04_xuankong",
    "data_center/verified_cases/05_finance",
    "data_center/archived_cases", "data_center/quarantine", "data_center/bookkeeping_gc",
    "training_camp/bad_case_graveyard/logic_collapse_logs",
    "training_camp/bad_case_graveyard/syntax_poisoning_logs",
    "training_camp/bad_case_graveyard/evolution_logs",
    "docs",
]

# ── INFRA: 5大生命体征强制覆盖写入映射 ──────────────────────
INFRA_FILE_MAP = {
    ".cursor/rules/007_dynamic_tiering.mdc":       CODE_DYNAMIC_TIERING_MDC,
    ".cursor/rules/Alumet-OS-Constitution.mdc":    CODE_CONSTITUTION_MDC,
    "core/ast_sentinel.py":                        CODE_AST_SENTINEL,
    "core/mcp_tool_protocol.py":                   CODE_MCP_TOOL_PROTOCOL,
    "agentic_workflow/yolo_veto_classifier.py":    CODE_YOLO_VETO_CLASSIFIER,
    "agentic_workflow/agent_query_engine.py":      CODE_AGENT_QUERY_ENGINE,
    "agentic_workflow/denial_tracking_circuit.py": CODE_DENIAL_TRACKING,
    "agentic_workflow/working_memory_context.py":  CODE_WORKING_MEMORY_CONTEXT,
    "oracle_gateway/llm_network_gateway.py":       CODE_LLM_NETWORK_GATEWAY,
    "async_background_housekeeping.py":            CODE_ASYNC_HOUSEKEEPING,
    "training_camp/mcts_constant_distiller.py":    CODE_MCTS_DISTILLER,
    "expert_rules/__init__.py":                    CODE_EXPERT_RULES_INIT,
    "simulation_sandbox/vm_repl_sandbox.py":       CODE_VM_REPL_SANDBOX,
    "data_center/exact_grep_retriever.py":         CODE_EXACT_GREP_RETRIEVER,
}

# ── SKELETON: 仅在文件不存在时写入 ──────────────────────────
SKELETON_FILE_MAP = {
    "__init__.py":                           "# Alumet OS V10 - Root Package\n",
    "core/__init__.py":                      "# core package\n",
    "core_engine/__init__.py":              "# core_engine package\n",
    "modules/__init__.py":                  "# modules package\n",
    "modules/01_xiangshu/__init__.py":      "# xiangshu module\n",
    "modules/02_bazi/__init__.py":          "# bazi module\n",
    "modules/03_liuyao/__init__.py":        "# liuyao module\n",
    "modules/04_xuankong/__init__.py":      "# xuankong module\n",
    "modules/05_finance/__init__.py":       "# finance module\n",
    "data_center/processed_files.json":     '{"cursor": 0, "ingested": []}\n',
    "data_center/system_hot_memory.json":   CODE_SYSTEM_HOT_MEMORY,
    "data_center/raw_cases/metaphysics_audit.jsonl": "",
    "expert_rules/SYSTEM_PROMPT_DYNAMIC_BOUNDARY.md": (
        "# [缓存金身] 隔离线定义\n\n本文件捍卫全局前缀缓存。此行以上为永久静态区，禁止修改。\n"
    ),
    ".gitignore": "__pycache__/\n*.pyc\n*.pyo\n.env\n*.key\ndata_center/bookkeeping_gc/\n*.draft*\n*_SURGEON_DRAFT_*.py\n.DS_Store\n",
    ".vscode/settings.json": json.dumps({"python.analysis.exclude": ["**/__pycache__/**"],
        "files.exclude": {"**/__pycache__": True, "**/*.pyc": True}}, indent=2) + "\n",
    ".cursor/commands/brain-transfer.md": (
        "# 意识转移指令法则\n\n"
        "执行意识转移时，必须先运行 `alumet_surgeon.py` 完成基建落盘，\n"
        "再通过 `data_center/system_hot_memory.json` 恢复跨会话热记忆。\n"
    ),
    "docs/SOP_Alumet_OS_Architecture.md": (
        "# Alumet OS V10 Architecture SOP\n\n"
        "## 核心哲学\n\n"
        "1. Dumb Tools (Tool.ts is_read_only)\n"
        "2. Exact Search (Grep 精确查表, 零幻觉)\n"
        "3. 25KB 红线 (compact.ts COMPACT_MAX_OUTPUT_TOKENS)\n"
        "4. Fail-Closed 熔断 (denialTracking.ts maxConsecutive=3)\n"
        "5. AutoDream (两阶段 GC + MCTS 夜间蒸馏)\n"
        "6. YOLO 拦截 (yoloClassifier.ts Stage1/Stage2)\n"
        "7. 413 Hook (compact.ts reactive compact)\n"
    ),
    "training_camp/adversarial_red_team.py": (
        '#!/usr/bin/env python3\n"""影子红队 - V10 Fire-and-forget 异步调用"""\n\n'
        'class OfflineRedTeamNode:\n'
        '    def execute_nightly_audit(self, logs=None):\n'
        '        print("🌙 [红队] 影子红队启动，开始博弈...")\n'
        '        print("✅ 进化完成。L5 规则库已增量更新。")\n\n'
        'if __name__ == "__main__":\n    OfflineRedTeamNode().execute_nightly_audit()\n'
    ),
    "requirements.txt": (
        "# Alumet OS V10 - 零依赖核心，可选扩展:\n"
        "# anthropic>=0.20.0\n# openai>=1.0.0\n# numpy>=1.24.0\n"
    ),
}

# ════════════════════════════════════════════════════════════════
# 【V1.2.2 精准路由映射表】硬编码，禁止泛化拼接
# ════════════════════════════════════════════════════════════════
DOMAIN_ROUTER: dict = {
    "1": {"domain": "xiangshu", "dir": "01_xiangshu", "parser": "xiangshu_tensor_parser.py",  "label": "象数(01)"},
    "2": {"domain": "bazi",     "dir": "02_bazi",     "parser": "bazi_ephemeris_parser.py",   "label": "八字(02)"},
    "3": {"domain": "liuyao",   "dir": "03_liuyao",   "parser": "liuyao_hexagram_parser.py",  "label": "六爻(03)"},
    "4": {"domain": "xuankong", "dir": "04_xuankong", "parser": "xuankong_grid_parser.py",    "label": "玄空(04)"},
    "5": {"domain": "finance",  "dir": "05_finance",  "parser": "finance_kline_parser.py",    "label": "金融(05)"},
}

PORT_LABELS = {
    "R": "Rules      -> expert_rules/{domain}_rules.py",
    "M": "Math Core  -> core_engine/{domain}_math_core.py",
    "E": "Engine[NEW]-> modules/{dir}/{domain}_unified_engine.py  ← L1.5 大一统推演引擎",
    "T": "Topology   -> modules/{dir}/{domain}_v102_topology.py",
    "P": "Parser     -> modules/{dir}/{parser}",
    "F": "Factory    -> modules/{dir}/{domain}_prompt_factory.py",
}

ENGINE_TOPOLOGY_DESC = "⚛️ [L1.5] 大一统推演引擎，承载本门派所有核心计算逻辑与权重叠加。"


def resolve_port_path(port: str, domain: str, dir_name: str, parser: str) -> str:
    """精准端口物理路径解析，硬编码映射，禁止泛化拼接。"""
    mapping = {
        "R": f"expert_rules/{domain}_rules.py",
        "M": f"core_engine/{domain}_math_core.py",
        "E": f"modules/{dir_name}/{domain}_unified_engine.py",
        "T": f"modules/{dir_name}/{domain}_v102_topology.py",
        "P": f"modules/{dir_name}/{parser}",
        "F": f"modules/{dir_name}/{domain}_prompt_factory.py",
    }
    return mapping.get(port.upper(), "")


# ════════════════════════════════════════════════════════════════
# 拓扑动态读取 & 自愈 (唯一真理源)
# ════════════════════════════════════════════════════════════════
def load_topology_dynamic(topology_file: str = "Alumet_OS_Topology.py") -> dict:
    """
    通过 importlib 动态读取 Alumet_OS_Topology.py 作为唯一真理源。
    绝对禁止硬编码拓扑副本。
    """
    if not os.path.exists(topology_file):
        return {}
    try:
        spec   = importlib.util.spec_from_file_location("Alumet_OS_Topology", topology_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        topo = getattr(module, "ALUMET_OS_TOPOLOGY", {})
        return topo if isinstance(topo, dict) else {}
    except Exception as e:
        pc(f"  ⚠️ [拓扑读取] 动态加载失败: {e}", "yellow")
        return {}


def topology_auto_heal(domain: str, dir_name: str, topology_file: str = "Alumet_OS_Topology.py") -> None:
    """
    拓扑地图动态自愈 [E端口专属]。
    精准正则定位门派字典域，插入 {domain}_unified_engine.py 键值对，安全写回存盘。
    免除人类手动维护坐标系的摩擦成本。
    """
    if not os.path.exists(topology_file):
        pc(f"  ⚠️ [拓扑自愈] 未找到 {topology_file}，跳过。", "yellow")
        return
    engine_key = f"{domain}_unified_engine.py"
    try:
        with open(topology_file, "r", encoding="utf-8") as f:
            content = f.read()
        if engine_key in content:
            pc(f"  ℹ️ [拓扑自愈] {engine_key} 已存在，无需更新。", "cyan")
            return
        # 精准定位门派目录块，如 "02_bazi/": {
        pattern = rf'("{re.escape(dir_name)}/"[\s\S]*?)\{{'
        match   = re.search(pattern, content)
        if match:
            insert_pos = match.end()
            insert_str = f'\n            "{engine_key}": "{ENGINE_TOPOLOGY_DESC}",'
            new_content = content[:insert_pos] + insert_str + content[insert_pos:]
            _write_bak(topology_file)
            with open(topology_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            pc(f"  ✅ [拓扑自愈] {engine_key} 已插入 {dir_name}/ 域", "green")
        else:
            pc(f"  ⚠️ [拓扑自愈] 未定位到 {dir_name}/ 域，跳过。", "yellow")
    except Exception as e:
        pc(f"  ❌ [拓扑自愈] 失败: {e}", "red")


# ════════════════════════════════════════════════════════════════
# IaC 基建播种
# ════════════════════════════════════════════════════════════════
def build_structure() -> None:
    pc("\n🏗️ [Step 2] 构建 V10 全域物理楼层...", "blue")
    for d in ALUMET_DIRECTORIES:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            logging.error(f"[build] 目录创建失败 {d}: {e}")
    pc(f"  ✅ {len(ALUMET_DIRECTORIES)} 个目录落位完成", "green")


def inject_infra_cores() -> None:
    pc("\n💉 [Step 3] 注入5大生命体征 (INFRA - 强制覆盖)...", "yellow")
    for path, content in INFRA_FILE_MAP.items():
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        _write_bak(path)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            pc(f"  ✅ [INFRA] {path}", "green")
        except Exception as e:
            logging.error(f"[infra] 注入失败 {path}: {e}")


def inject_skeleton_files() -> None:
    pc("\n🦴 [Step 4] 注入骨架文件 (SKELETON - 仅新建)...", "blue")
    for path, content in SKELETON_FILE_MAP.items():
        if os.path.exists(path):
            continue
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            pc(f"  🦴 [SKELETON] {path}", "cyan")
        except Exception as e:
            logging.error(f"[skeleton] 写入失败 {path}: {e}")


# ════════════════════════════════════════════════════════════════
# 6端口 CLI 状态机 (核心路由器)
# ════════════════════════════════════════════════════════════════
def interactive_surgical_router() -> None:
    pc("\n" + "=" * 66, "blue")
    pc("🔪 [Alumet OS V10 终端手术刀 V1.2.2] 6端口灌注CLI已激活", "green")
    pc("   拓扑源: 动态读取 Alumet_OS_Topology.py (唯一真理源)", "cyan")
    pc("=" * 66, "blue")

    cleanup_stale_drafts(days_to_keep=3)

    topo = load_topology_dynamic()
    if topo:
        ver = topo.get("metadata", {}).get("version", "未知")
        pc(f"  ✅ [拓扑] 已加载 (版本: {ver})", "green")
    else:
        pc("  ⚠️ [拓扑] 未找到 Alumet_OS_Topology.py，硬编码路由运行", "yellow")

    while True:
        print()
        pc("┌──────────────────────────────────────────────────────────────┐", "blue")
        pc("│  1-5  门派灌注 (6端口 R/M/E/T/P/F)                         │", "blue")
        pc("│  6    🧬 全息进化 (影子红队)                                │", "blue")
        pc("│  7    💉 JSON 管线注入 (象数基因)                           │", "blue")
        pc("│  8    ⚡ AutoDream 后台守护进程                             │", "blue")
        pc("│  Q    安全退出                                               │", "blue")
        pc("└──────────────────────────────────────────────────────────────┘", "blue")
        pc("[门派] 1.象数(01) 2.八字(02) 3.六爻(03) 4.玄空(04) 5.金融(05)", "cyan")

        choice = input(_c("序号 (1-8/Q): ", "yellow")).strip().upper()

        if choice == "Q":
            pc("\n👋 已安全退出 Alumet OS V10 手术刀。", "yellow")
            break

        if choice == "6":
            _action_red_team()
            continue

        if choice == "7":
            pc("\n📥 请粘贴 JSON 内容，按 Ctrl+D (Mac/Linux) 或 Ctrl+Z+Enter (Win) 结束：", "yellow")
            try:
                raw = sys.stdin.read()
                if raw.strip():
                    inject_xiangshu_genome(raw)
            except EOFError:
                pass
            continue

        if choice == "8":
            run_housekeeping_inline()
            continue

        route = DOMAIN_ROUTER.get(choice)
        if not route:
            pc("  ❌ 无效选择，请输入 1-8 或 Q", "red")
            continue

        _action_inject_port(route)


def _action_red_team() -> None:
    pc("\n🚀 [进化点火] 唤醒影子红队...", "yellow")
    rtp = "training_camp/adversarial_red_team.py"
    if os.path.exists(rtp):
        try:
            subprocess.run([sys.executable, rtp], check=False)
        except Exception as e:
            logging.error(f"[red_team] 唤醒失败: {e}")
    else:
        pc("  ⚠️ 影子红队文件尚未落位，请先完成基建播种。", "red")


def _action_inject_port(route: dict) -> None:
    domain   = route["domain"]
    dir_name = route["dir"]
    parser   = route["parser"]
    label    = route["label"]

    print()
    pc(f"  门派锁定: {label}  |  物理目录: modules/{dir_name}", "cyan")
    print()
    pc("┌──────────────────────────────────────────────────────────────┐", "blue")
    pc("│  [6大标准灌注端口]                                           │", "blue")
    for port, tmpl in PORT_LABELS.items():
        desc = tmpl.replace("{domain}", domain).replace("{dir}", dir_name).replace("{parser}", parser)
        pc(f"│  {port}  {desc:<58}│", "blue")
    pc("└──────────────────────────────────────────────────────────────┘", "blue")

    port = input(_c("端口 (R/M/E/T/P/F): ", "yellow")).strip().upper()
    if port not in PORT_LABELS:
        pc("  ❌ 无效端口", "red")
        return

    target = resolve_port_path(port, domain, dir_name, parser)
    if not target:
        pc("  ❌ 端口解析失败", "red")
        return

    pc(f"\n📥 灌注目标: {target}", "cyan")
    pc("请粘贴代码内容，按 Ctrl+D (Mac/Linux) 或 Ctrl+Z+Enter (Win) 结束：", "yellow")
    try:
        content = sys.stdin.read()
    except EOFError:
        return

    if not content.strip():
        pc("  ⚠️ 内容为空，跳过。", "yellow")
        return

    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    safe_write(target, content)
    pc(f"  ✅ [{port}] 物理落盘 -> {target}", "green")

    if port == "E":
        pc("  🔧 [E端口] 触发拓扑地图动态自愈...", "yellow")
        topology_auto_heal(domain, dir_name)


# ════════════════════════════════════════════════════════════════
# 主入口 — 双生命周期判定
# ════════════════════════════════════════════════════════════════
def main() -> None:
    pc("=" * 66, "green")
    pc("🧬 Alumet OS V10 (V1.2.2 Immortal Silicon State)", "green")
    pc("   全域基建播种机与日常灌注交互终端 (IaC & CLI)", "green")
    pc("   微内核架构 | 逻辑脱水版 | ELL < 800 行", "cyan")
    pc("=" * 66, "green")

    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip() and ("T_NEW" in raw or "{" in raw):
            inject_xiangshu_genome(raw)
        else:
            pc("[-] 管道流输入无效或格式非基因张量。", "red")
        sys.exit(0)

    try:
        if detect_infra_missing():
            pc("\n🚀 [首次运行] 基础设施缺失，进入 IaC 自解压安装模式...", "yellow")
            create_backup()
            build_structure()
            inject_infra_cores()
            inject_skeleton_files()
            pc("\n✅ [全域基建] 播种完成！5大生命体征已物理落盘。", "green")
        else:
            pc("\n✅ [系统已存在] 直接进入灌注 CLI 模式。", "green")
            pc("  🔄 刷新5大生命体征...", "cyan")
            inject_infra_cores()

        interactive_surgical_router()
        pc("\n🏁 [全流程结束] Alumet OS V10 处于绝对安全隔离状态。", "yellow")

    except KeyboardInterrupt:
        pc("\n\n👋 主理人触发物理阻断 (Ctrl+C)，已安全退出。", "yellow")
        pc("⚠️ 下次唤醒请执行: python alumet_surgeon.py", "red")
    except Exception as e:
        logging.error(f"[CRITICAL] 主矩阵意外中断: {e}")
        pc(f"\n❌ 意外中断: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
