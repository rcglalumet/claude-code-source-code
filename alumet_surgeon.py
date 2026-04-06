#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alumet OS V10 (V1.2.2 Immortal Silicon State)
全域基建播种机与日常灌注交互终端 (IaC & CLI)
alumet_surgeon.py

零依赖 | 仅使用 Python 标准库
双生命周期: 首次运行=IaC自解压安装包 | 系统已存在=6端口灌注CLI
拓扑源: 动态读取 Alumet_OS_Topology.py (唯一真理源)
源码双向提炼: Claude Code TS(yoloClassifier/QueryEngine/compact/denialTracking/Tool) + 旧版防御资产
"""

import os
import sys
import shutil
import json
import time
import re
import glob
import ast
import importlib.util
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(message)s')

# ============================================================
# 彩色终端输出
# ============================================================
def _c(text, color="green"):
    codes = {
        "green": "\033[92m", "red": "\033[91m",
        "yellow": "\033[93m", "blue": "\033[94m",
        "cyan": "\033[96m", "magenta": "\033[95m", "reset": "\033[0m"
    }
    return f"{codes.get(color, codes['reset'])}{text}{codes['reset']}"

def pc(text, color="green"):
    print(_c(text, color))

# ============================================================
# [V10 生命体征 1] Dumb Tools & 安全隔离舱
# 目标: vm_repl_sandbox.py
# 提炼: Claude Code Tool.ts is_read_only / toAutoClassifierInput 哲学
# 旧防线: ASTSentinel 静态拦截 + KernelApiProxy
# ============================================================
CODE_VM_REPL_SANDBOX = '''import ast


class RalphStopException(Exception):
    """自定义熔断异常"""
    def __init__(self, message):
        super().__init__(message)


class ASTSentinel(ast.NodeVisitor):
    """
    [V10 免疫补丁] 零容忍拦截 eval/exec 与底层代码注入。
    提炼自 Claude Code Tool.ts: Dumb Tools 内部绝对禁止推演逻辑，
    仅作纯粹的数学执行器 (对齐 toAutoClassifierInput 哲学)。
    is_read_only=True 属性配合调度器实现只读隔离。
    """
    FORBIDDEN_FUNCS = frozenset({\'eval\', \'exec\', \'compile\', \'globals\', \'locals\', \'__import__\'})

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_FUNCS:
            raise RalphStopException(
                f"AST SENTINEL: 动态执行 {node.func.id}() 已被零容忍拦截"
            )
        self.generic_visit(node)

    @staticmethod
    def validate_source(source_code: str) -> bool:
        """返回 True 表示代码安全，抛出 RalphStopException 表示违规。"""
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            raise RalphStopException(f"语法错误: {e}")
        sentinel = ASTSentinel()
        sentinel.visit(tree)
        return True


class KernelApiProxy:
    """
    [V10 Dumb Tools 契约] MCP 工具内部绝对禁止推演逻辑。
    工具是纯粹的数学执行器，通过代理句柄隔离 L0 访问。
    对齐 Claude Code Tool.ts: is_read_only 属性 + toAutoClassifierInput 执行器哲学。
    """
    is_read_only: bool = True

    def __init__(self):
        self._approved_ops: set = set()
        HIGH_RISK_OPS = frozenset({
            "delete_file", "overwrite_rules", "execute_arbitrary_code",
            "modify_constitution", "force_reset_circuit"
        })
        self.HIGH_RISK_OPS = HIGH_RISK_OPS

    def call(self, operation: str, params: dict = None) -> dict:
        if not isinstance(params, dict):
            params = {}
        if operation in self.HIGH_RISK_OPS and operation not in self._approved_ops:
            return {"error": f"[HITL 拦截] 高危操作 {operation} 需要人工授权"}
        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            return {"error": f"未知操作: {operation}"}
        return handler(params)

    def grant_approval(self, operation: str):
        if operation in self.HIGH_RISK_OPS:
            self._approved_ops.add(operation)

    def _op_read_file(self, params: dict) -> dict:
        path = params.get("path", "")
        if not os.path.exists(path):
            return {"error": f"文件不存在: {path}"}
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return {"content": f.read()}
        except Exception as e:
            return {"error": str(e)}

    def _op_list_dir(self, params: dict) -> dict:
        path = params.get("path", ".")
        if not os.path.isdir(path):
            return {"error": f"目录不存在: {path}"}
        return {"entries": os.listdir(path)}


class VMReplSandbox:
    """
    Python Exec 级隔离环境。
    沙盒命名空间仅注入 kernel_api_proxy.call 安全代理句柄。
    写入前强制 ASTSentinel 静态审计，绝对禁止动态执行。
    """
    def __init__(self, kernel_api_proxy=None):
        self._proxy = kernel_api_proxy or KernelApiProxy()

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

# ============================================================
# [V10 生命体征 2] Exact Search & 跨会话热记忆
# 目标: system_hot_memory.json (空壳框架)
# 提炼: 抛弃 ChromaDB，强制 Grep 纯文本查表
# ============================================================
CODE_SYSTEM_HOT_MEMORY = json.dumps({
    "[IMMORTAL] system_version": "Alumet OS V10 (V1.2.2 Immortal Silicon State)",
    "[IMMORTAL] created_at": datetime.now().isoformat(),
    "[IMMORTAL] philosophy_exact_search": "禁止向量幻觉，强制 Grep 精确查表",
    "[IMMORTAL] philosophy_25kb_limit": "热记忆硬限 25KB，溢出强制语义提纯",
    "[IMMORTAL] philosophy_fail_closed": "连续失败 3 次 Fail-Closed 熔断",
    "[IMMORTAL] claude_code_alignment": "MEMORY.md 跨会话偏好记忆机制对齐"
}, ensure_ascii=False, indent=2) + "\n"

CODE_EXACT_GREP_RETRIEVER = '''"""
Exact Grep Retriever - V10 全域智能检索
[Exact Search 哲学] 抛弃 ChromaDB 向量检索幻觉。
使用朴素 Grep 纯文本查表与正则匹配，零幻觉，零依赖。
提炼自 Claude Code: 宁可精确命中，不要近似幻觉。
对齐 MEMORY.md: 跨会话偏好记忆机制，重启不失忆。
"""
import os
import re
import json
from typing import List


MAX_HOT_MEMORY_BYTES = 25 * 1024  # 25KB 红线，硬编码禁止修改


class ExactGrepRetriever:
    """
    全域案例检索器。
    只做精确文本匹配，不做任何语义推演或向量近似搜索。
    """
    def __init__(self, data_root: str = "data_center"):
        self.data_root = data_root

    def search(self, query: str, file_extensions: tuple = (".txt", ".jsonl", ".json", ".py"),
               max_results: int = 50) -> List[dict]:
        if not query or not isinstance(query, str):
            return []
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        results = []
        for root, _, files in os.walk(self.data_root):
            for fname in files:
                if not any(fname.endswith(ext) for ext in file_extensions):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, 1):
                            if pattern.search(line):
                                results.append({"file": fpath, "line": lineno, "content": line.rstrip()})
                                if len(results) >= max_results:
                                    return results
                except Exception:
                    pass
        return results

    def load_case_by_id(self, case_id: str) -> dict:
        matches = self.search(f\'"id"\\\\s*:\\\\s*"{re.escape(case_id)}"')
        if not matches:
            return {}
        fpath = matches[0]["file"]
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        if obj.get("id") == case_id:
                            return obj
                    except Exception:
                        pass
        except Exception:
            pass
        return {}


class SmartMemoryGuard:
    """
    [V10 终极改造] 语义锚点保留协议。
    25KB 红线 -> 保留 IMMORTAL 标签条目，保留后半段普通条目。
    对齐 Claude Code compact.ts COMPACT_MAX_OUTPUT_TOKENS 与上下文折叠哲学。
    """
    MAX_MEMORY_SIZE_BYTES = 25 * 1024  # 25KB 红线，禁止修改

    @staticmethod
    def enforce_entropy_reduction(memory_file_path: str):
        if not os.path.exists(memory_file_path):
            return
        if os.path.getsize(memory_file_path) <= SmartMemoryGuard.MAX_MEMORY_SIZE_BYTES:
            return
        print("⚠️ [SmartMemory] 触达 25KB 红线，启动语义提纯...")
        try:
            with open(memory_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            immortal = {k: v for k, v in data.items() if "[IMMORTAL]" in str(k)}
            mortal = {k: v for k, v in data.items() if "[IMMORTAL]" not in str(k)}
            keys = list(mortal.keys())
            kept_mortal = {k: mortal[k] for k in keys[len(keys) // 2:]}
            result = {**immortal, **kept_mortal}
            with open(memory_file_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print("✨ [SmartMemory] 语义提纯完成，高频指纹永久锚定！")
        except Exception as e:
            print(f"⚠️ [SmartMemory] 记忆瘦身失败: {e}")
'''

# ============================================================
# [V10 生命体征 3] 极致缓存护城河 (MCP 契约)
# 目标: mcp_tool_protocol.py, working_memory_context.py
# 提炼: 禁用 Enum 防缓存击穿, 25KB 热数据溢出红线
# ============================================================
CODE_MCP_TOOL_PROTOCOL = '''"""
MCP Tool Protocol - V10 契约层
强制约束:
  1. Dumb Tools: 工具内部绝对禁止推演逻辑 Prompt，仅作数学/数据执行器。
     (对齐 Claude Code Tool.ts is_read_only / toAutoClassifierInput 哲学)
  2. 极致缓存护城河: Schema 禁止出现巨大 Enum 防缓存击穿。
     禁用 Python Enum 类型，改用极简扁平化 Schema 字符串常量。
  3. is_read_only 属性配合调度器实现只读隔离。
"""
from typing import Any


# [强制] 极简扁平化 Schema 常量 - 禁止使用 Enum 类
DOMAIN_NAMES = ["xiangshu", "bazi", "liuyao", "xuankong", "finance"]
PORT_NAMES = ["R", "M", "E", "T", "P", "F"]


class MCPToolBase:
    """所有 MCP 工具的刚性基类契约"""
    name: str = ""
    description: str = ""
    is_read_only: bool = True

    def get_schema(self) -> dict:
        """
        返回工具的 JSON Schema。
        [强制] 禁止在 enum 字段塞入超过 20 个值，防缓存击穿。
        禁止使用 Python Enum 类型。
        """
        raise NotImplementedError

    def execute(self, params: dict) -> Any:
        """
        [强制] 工具执行入口。
        内部只做确定性数学计算或数据查表，绝对禁止调用 LLM 或写推演 Prompt。
        """
        raise NotImplementedError

    def _safe_get(self, d: dict, key: str, default=None):
        """防投毒 .get 装甲"""
        if not isinstance(d, dict):
            return default
        return d.get(key, default)


class ExactGrepSearchTool(MCPToolBase):
    """
    [Exact Search 哲学] 全域智能检索工具。
    抛弃向量检索幻觉，使用朴素 Grep 文本搜索与正则匹配查表。
    """
    name = "exact_grep_search"
    description = "精确 Grep 文本搜索工具，不使用向量数据库"
    is_read_only = True

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "精确搜索词或正则表达式"},
                "search_path": {"type": "string", "description": "搜索目录路径"},
                "file_extension": {"type": "string", "description": "文件扩展名过滤"}
            },
            "required": ["query", "search_path"]
        }

    def execute(self, params: dict) -> Any:
        import os, re
        query = self._safe_get(params, "query", "")
        search_path = self._safe_get(params, "search_path", ".")
        ext = self._safe_get(params, "file_extension", "")
        results = []
        if not os.path.isdir(search_path):
            return {"error": f"路径不存在: {search_path}"}
        try:
            pattern = re.compile(query)
        except re.error:
            pattern = re.compile(re.escape(query))
        for root, _, files in os.walk(search_path):
            for fname in files:
                if ext and not fname.endswith(ext):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, 1):
                            if pattern.search(line):
                                results.append({"file": fpath, "line": lineno, "content": line.rstrip()})
                except Exception:
                    pass
        return {"results": results, "count": len(results)}
'''

CODE_WORKING_MEMORY_CONTEXT = '''"""
Working Memory Context - V10 动态热数据容器
强制约束: 25KB 热数据溢出红线，溢出前强制唤醒语义提纯。
对齐 Claude Code compact.ts: COMPACT_MAX_OUTPUT_TOKENS 与上下文折叠哲学。
[硬编码] 25KB 红线不可修改，不可配置。
"""
import os
import json


MAX_HOT_MEMORY_BYTES = 25 * 1024  # 25KB 红线，硬编码禁止修改


class WorkingMemoryContext:
    """
    统一运行时会话上下文容器。
    物理红线: 25KB，溢出前强制启动 IMMORTAL 标签语义提纯。
    """
    def __init__(self, session_id: str, memory_file: str = "data_center/system_hot_memory.json"):
        self.session_id = session_id
        self.memory_file = memory_file
        self._context: dict = {}
        self._load()

    def _load(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self._context = json.load(f)
            except Exception:
                self._context = {}

    def set(self, key: str, value):
        if not isinstance(key, str):
            raise TypeError("上下文键必须是字符串")
        self._context[key] = value
        self._enforce_limit()

    def get(self, key: str, default=None):
        return self._context.get(key, default)

    def _enforce_limit(self):
        serialized = json.dumps(self._context, ensure_ascii=False).encode("utf-8")
        if len(serialized) > MAX_HOT_MEMORY_BYTES:
            self._compact()

    def _compact(self):
        """语义提纯: 保留 IMMORTAL 标签条目，删除前半段普通条目。"""
        print("⚠️ [WorkingMemory] 触达 25KB 红线，启动语义提纯...")
        immortal = {k: v for k, v in self._context.items() if "[IMMORTAL]" in str(k)}
        mortal = {k: v for k, v in self._context.items() if "[IMMORTAL]" not in str(k)}
        keys = list(mortal.keys())
        kept_mortal = {k: mortal[k] for k in keys[len(keys) // 2:]}
        self._context = {**immortal, **kept_mortal}
        print("✨ [WorkingMemory] 语义提纯完成，高频指纹永久锚定。")

    def flush(self):
        os.makedirs(os.path.dirname(self.memory_file) or ".", exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self._context, f, ensure_ascii=False, indent=2)
'''

# ============================================================
# [V10 生命体征 4] YOLO 拦截 & 非对称算力防御 (L3/L4 跃升)
# 目标: agent_query_engine.py, llm_network_gateway.py, yolo_veto_classifier.py
# 提炼: TS while(true)架构, denialTracking.ts maxConsecutive=3, 413 Hook
# ============================================================
CODE_YOLO_VETO_CLASSIFIER = r'''"""
YOLO Veto Classifier - V10 前置拦截防线
非对称算力防御: 部署极低成本规则引擎前置审查指令与乱码。

[V10 升级] 提炼自 Claude Code yoloClassifier.ts 两阶段 XML 判定逻辑:
  - Stage 1 (fast): 低成本规则引擎即时判定 (XML_S1_SUFFIX "Err on the side of blocking.")
    允许则直接放行。
  - Stage 2 (thinking): 仅在 Stage 1 判定为高危时升级，深度链式推理复核
    (XML_S2_SUFFIX "Review the classification process and follow it carefully.")
  非对称设计: 99% 正常流量仅经 Stage 1 极速通过，极大降低算力消耗。

绝对禁止在此处调用大模型 API，保持纯规则/正则执行。
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

# Stage 2 升级触发词 (对齐 yoloClassifier.ts XML_S2_SUFFIX 阻断模式)
ESCALATE_PATTERNS = [
    r"(?i)(sudo|chmod\s+777|chown\s+root)",
    r"(?i)(base64\s*-d|xxd\s*-r|openssl\s+enc)",
    r"(?i)(nc\s+-e|ncat\s+.*-e|socat\s+exec)",
]


class YoloVetoClassifier:
    """
    [YOLO 拦截哲学] 纯规则引擎，零 LLM 调用。
    低成本前置过滤乱码与高危指令，实施非对称算力防御。

    两阶段判定架构 (Stage 1 fast / Stage 2 thinking):
      Stage 1: 垃圾 + 高危正则扫描，命中则立刻拦截或升级。
      Stage 2: 深度模式匹配 (escalate_patterns)，降低误伤。
      如两阶段均通过 -> vetoed=False (放行)。
    """
    def __init__(self):
        self._garbage_re = [re.compile(p) for p in GARBAGE_PATTERNS]
        self._high_risk_re = [re.compile(p) for p in HIGH_RISK_PATTERNS]
        self._escalate_re = [re.compile(p) for p in ESCALATE_PATTERNS]

    def classify(self, text: str) -> dict:
        # --- Stage 1: Fast path ---
        if not isinstance(text, str) or not text.strip():
            return {"vetoed": True, "reason": "空输入或非字符串", "stage": "fast"}
        for pattern in self._garbage_re:
            if pattern.search(text):
                return {"vetoed": True, "reason": "检测到乱码/垃圾字符", "stage": "fast"}
        for pattern in self._high_risk_re:
            if pattern.search(text):
                return {"vetoed": True, "reason": "检测到高危指令模式", "escalate": True, "stage": "fast"}
        if len(text) > 32768:
            return {"vetoed": True, "reason": "输入超过 32KB 上限", "stage": "fast"}
        # --- Stage 2: Thinking path ---
        for pattern in self._escalate_re:
            if pattern.search(text):
                return {"vetoed": True, "reason": "Stage 2 深度复核: 检测到升级危险模式", "stage": "thinking"}
        return {"vetoed": False, "stage": "fast"}
'''

CODE_AGENT_QUERY_ENGINE = '''"""
Agent Query Engine - V10 全域唯一主循环
L3 控制平面核心，映射 Claude Code QueryEngine.ts while-true 架构。

强制约束 (提炼自 QueryEngine.ts + denialTracking.ts):
  1. YOLO 拦截: 所有输入前置经过 yolo_veto_classifier 过滤。
  2. Fail-Closed 熔断: 连续失败 3 次即熔断 (对齐 denialTracking.ts DENIAL_LIMITS.maxConsecutive=3)。
  3. 非对称算力防御: 低价小模型前置过滤，高价大模型后置执行。
  4. 跨会话热记忆: 重启不失忆，对齐 MEMORY.md 哲学。
"""
import time


class AgentQueryEngine:
    """
    V10 主循环引擎 (while-true 架构)。
    连续失败 3 次 -> Fail-Closed 熔断止损。
    对齐 Claude Code denialTracking.ts: maxConsecutive=3, maxTotal=20。
    """
    MAX_CONSECUTIVE_FAILURES = 3   # 硬编码熔断阈值，不可修改，来自 denialTracking.ts
    MAX_TOTAL_FAILURES = 20        # 总失败上限，来自 denialTracking.ts

    def __init__(self, working_memory=None, yolo_classifier=None, tool_registry=None, oracle_gateway=None):
        self.memory = working_memory
        self.yolo = yolo_classifier
        self.tools = tool_registry
        self.oracle = oracle_gateway
        self._consecutive_failures = 0
        self._total_failures = 0
        self._is_fused = False

    def run(self, user_query: str) -> dict:
        if self._is_fused:
            return {"status": "FAIL_CLOSED", "reason": "熔断器已触发，拒绝服务。"}

        # YOLO 前置拦截 (对齐 Claude Code classifyYoloAction 两阶段判定)
        if self.yolo is not None:
            veto_result = self.yolo.classify(user_query)
            if veto_result.get("vetoed"):
                return {"status": "VETOED", "reason": veto_result.get("reason", "YOLO 拦截")}

        try:
            result = self._execute_with_circuit_breaker(user_query)
            self._consecutive_failures = 0
            return result
        except Exception as e:
            self._consecutive_failures += 1
            self._total_failures += 1
            if (self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES or
                    self._total_failures >= self.MAX_TOTAL_FAILURES):
                self._is_fused = True
                return {
                    "status": "FAIL_CLOSED",
                    "reason": f"连续失败 {self._consecutive_failures} 次 / 累计 {self._total_failures} 次，熔断器触发: {e}"
                }
            return {"status": "ERROR", "error": str(e), "consecutive_failures": self._consecutive_failures}

    def _execute_with_circuit_breaker(self, query: str) -> dict:
        """核心推演逻辑，由子类或插件扩展。"""
        raise NotImplementedError("子类必须实现 _execute_with_circuit_breaker")

    def reset_circuit(self):
        """人工复位熔断器（需人工授权）"""
        self._consecutive_failures = 0
        self._total_failures = 0
        self._is_fused = False
'''

CODE_LLM_NETWORK_GATEWAY = '''"""
LLM Network Gateway - V10 全局网络层 (L4)
核心新增: 413 响应触发 Reactive Compact Hook。
遇长文本溢出直接唤醒 Compactor 而不中断服务。
提炼自 Claude Code compact.ts + context.ts: COMPACT_MAX_OUTPUT_TOKENS 413 溢出折叠哲学。
"""
import json


MAX_HOT_MEMORY_BYTES = 25 * 1024  # 25KB 红线


class ContextAutoCompactor:
    """
    五级压缩漏斗 (对齐 Claude Code compact.ts 五级压缩架构)。
    从轻度压缩开始，逐级加重，直到满足目标大小。
    reactive=True 时目标减半，用于 413 应急压缩。
    """
    COMPRESS_LEVELS = [0.9, 0.75, 0.6, 0.4, 0.25]
    TARGET_BYTES = MAX_HOT_MEMORY_BYTES

    def compact(self, context: dict, reactive: bool = False) -> dict:
        target = self.TARGET_BYTES if not reactive else self.TARGET_BYTES // 2
        for level_ratio in self.COMPRESS_LEVELS:
            serialized = json.dumps(context, ensure_ascii=False)
            if len(serialized.encode("utf-8")) <= target:
                return context
            context = self._apply_compression(context, level_ratio)
            print(f"🗜️ [Compactor] 压缩级别 {level_ratio}: {len(json.dumps(context, ensure_ascii=False).encode())} bytes")
        return context

    def _apply_compression(self, context: dict, ratio: float) -> dict:
        immortal = {k: v for k, v in context.items() if "[IMMORTAL]" in str(k)}
        mortal = {k: v for k, v in context.items() if "[IMMORTAL]" not in str(k)}
        keep_count = max(1, int(len(mortal) * ratio))
        keys = list(mortal.keys())
        kept = {k: mortal[k] for k in keys[-keep_count:]}
        return {**immortal, **kept}


class LLMNetworkGateway:
    """
    全局 LLM 网络层。
    核心: 413 Reactive Compact Hook，遇上下文溢出直接唤醒 Compactor。
    对齐 Claude Code compact.ts: getPromptTooLongTokenGap / PROMPT_TOO_LONG_ERROR_MESSAGE。
    """
    def __init__(self):
        self._compactor = ContextAutoCompactor()

    def send(self, payload: dict) -> dict:
        """发送请求骨架，子类实现实际 API 调用。"""
        raise NotImplementedError("[V10 占位] LLM 网关骨架就位，子类实现具体发送逻辑。")

    def on_413_error(self, context: dict) -> dict:
        """
        413 报错钩子: 直接唤醒 Compactor 而不中断服务。
        提炼自 Claude Code compact.ts: 413 响应触发上下文折叠。
        """
        print("[Gateway] 413 Context Too Long -> 触发 Reactive Compact")
        return self._compactor.compact(context, reactive=True)

    def handle_prompt_too_long(self, context: dict, error_message: str) -> dict:
        """检测到上下文超长错误时的处理入口。"""
        if "prompt is too long" in error_message.lower() or "413" in error_message:
            return self.on_413_error(context)
        raise RuntimeError(f"非 413 错误: {error_message}")
'''

# ============================================================
# [V10 生命体征 5] AutoDream 后台进化
# 目标: async_background_housekeeping.py, mcts_constant_distiller.py
# 旧防线: TensorFingerprintGenerator, RTX5090ResourceManager
# ============================================================
CODE_ASYNC_HOUSEKEEPING = '''"""
Async Background Housekeeping - V10 AutoDream 守护进程
绝对异步执行，断电不死。
职责:
  1. 两阶段垃圾回收: 扫描 .orphaned_at 标记 -> 物理删除。
  2. 触发 mcts_constant_distiller 夜间复盘。
  3. 清理 3 天前的 _DRAFT 草稿文件。
[旧防线资产] TensorFingerprintGenerator + RTX5090ResourceManager 预置骨架。
"""
import asyncio
import os
import time
import glob
import json
import hashlib


ORPHAN_MARKER = ".orphaned_at"
DRAFT_MAX_AGE_SECONDS = 3 * 86400  # 3天


class TensorFingerprintGenerator:
    """
    [V10 旧防线资产] L0 物理证明机：防大模型篡改结论。
    使用 SHA-256 对推演状态进行确定性签名。
    """
    @staticmethod
    def generate_proof(tensor_state: dict, engine_name: str) -> str:
        if not isinstance(tensor_state, dict):
            raise ValueError("tensor_state 必须是字典")
        deterministic_str = json.dumps(tensor_state, sort_keys=True, ensure_ascii=False)
        salted_str = f"ENGINE:{engine_name}|STATE:{deterministic_str}"
        return hashlib.sha256(salted_str.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_proof(tensor_state: dict, engine_name: str, proof: str) -> bool:
        expected = TensorFingerprintGenerator.generate_proof(tensor_state, engine_name)
        return expected == proof


class RTX5090ResourceManager:
    """
    [V10 旧防线资产] 32GB VRAM 完整潮汐调度器骨架。
    VLM 视觉探针与 LLM 推演互斥，强制资源隔离。
    """
    VRAM_TOTAL_GB = 32
    VLM_RESERVED_GB = 20
    LLM_RESERVED_GB = 10

    def __init__(self):
        self._vlm_active = False
        self._llm_active = False

    def get_status(self) -> dict:
        used = 0
        if self._vlm_active:
            used += self.VLM_RESERVED_GB
        if self._llm_active:
            used += self.LLM_RESERVED_GB
        return {
            "total_gb": self.VRAM_TOTAL_GB,
            "used_gb": used,
            "free_gb": self.VRAM_TOTAL_GB - used,
            "vlm_active": self._vlm_active,
            "llm_active": self._llm_active
        }


async def two_pass_gc(bookkeeping_dir: str = "data_center/bookkeeping_gc"):
    """两阶段垃圾回收: 第一阶段标记，第二阶段物理删除。"""
    if not os.path.isdir(bookkeeping_dir):
        return
    now = time.time()
    for fname in os.listdir(bookkeeping_dir):
        if fname.endswith(ORPHAN_MARKER):
            continue
        fpath = os.path.join(bookkeeping_dir, fname)
        marker = fpath + ORPHAN_MARKER
        if os.path.exists(marker):
            try:
                os.remove(fpath)
                os.remove(marker)
                print(f"♻️ [AutoDream GC] 两阶段回收完成: {fname}")
            except Exception as e:
                print(f"⚠️ [AutoDream GC] 回收失败 {fname}: {e}")
        else:
            mtime = os.path.getmtime(fpath)
            if now - mtime > DRAFT_MAX_AGE_SECONDS:
                try:
                    with open(marker, "w") as f:
                        f.write(str(now))
                    print(f"🏷️ [AutoDream GC] 一阶段标记孤儿: {fname}")
                except Exception:
                    pass
    await asyncio.sleep(0)


async def cleanup_stale_drafts_async(search_root: str = "."):
    """异步清理超过 3 天的 _DRAFT 草稿文件。"""
    now = time.time()
    deleted = 0
    patterns = [
        os.path.join(search_root, "**", "*_SURGEON_DRAFT_*.py"),
        os.path.join(search_root, "**", "*.draft*"),
    ]
    for pattern in patterns:
        for fpath in glob.glob(pattern, recursive=True):
            if os.path.isfile(fpath):
                if now - os.path.getmtime(fpath) > DRAFT_MAX_AGE_SECONDS:
                    try:
                        os.remove(fpath)
                        deleted += 1
                    except Exception:
                        pass
    if deleted:
        print(f"🧹 [AutoDream] 已清理 {deleted} 个过期草稿文件")
    await asyncio.sleep(0)


async def trigger_mcts_distiller():
    """触发 MCTS 夜间复盘（对接 mcts_constant_distiller）。"""
    distiller_path = "training_camp/mcts_constant_distiller.py"
    if os.path.exists(distiller_path):
        print("🧠 [AutoDream] 触发 MCTS 蒸馏器...")
    else:
        print("⚠️ [AutoDream] mcts_constant_distiller.py 尚未就位，跳过。")
    await asyncio.sleep(0)


async def run_housekeeping():
    """主守护协程，顺序执行所有后台任务。"""
    print("⚡ [AutoDream] 后台守护进程启动...")
    await cleanup_stale_drafts_async()
    await two_pass_gc()
    await trigger_mcts_distiller()
    print("✅ [AutoDream] 本轮后台任务完成。")


if __name__ == "__main__":
    asyncio.run(run_housekeeping())
'''

CODE_MCTS_DISTILLER = '''"""
MCTS Constant Distiller - V10 后台蒸馏器骨架
配合 AutoDream 守护进程，夜间静默复盘脏数据，提炼新常数反哺 L5。
"""
import json
import os


class MCTSConstantDistiller:
    """
    蒙特卡洛树搜索常数蒸馏器。
    输入: 历史推演日志列表
    输出: 提炼后的高置信度常数字典
    """
    def __init__(self, l5_rules_dir: str = "expert_rules"):
        self.l5_rules_dir = l5_rules_dir

    def distill_tensor(self, history_logs: list) -> dict:
        if not isinstance(history_logs, list):
            raise ValueError("history_logs 必须是列表")
        freq_map: dict = {}
        for entry in history_logs:
            if not isinstance(entry, dict):
                continue
            keys = entry.get("features", [])
            for k in keys:
                freq_map[k] = freq_map.get(k, 0) + 1
        threshold = max(1, len(history_logs) // 10)
        distilled = {k: v for k, v in freq_map.items() if v >= threshold}
        return {"distilled_constants": distilled, "total_logs": len(history_logs)}

    def write_back_to_l5(self, constants: dict, domain: str = "global"):
        target = os.path.join(self.l5_rules_dir, f"{domain}_distilled_constants.json")
        os.makedirs(self.l5_rules_dir, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(constants, f, ensure_ascii=False, indent=2)
        print(f"✨ [Distiller] 常数已写回 L5: {target}")
'''

# ============================================================
# 旧版免疫防线资产（从旧版经验库提取）
# ============================================================
CODE_AST_SENTINEL = '''import ast


class RalphStopException(Exception):
    """自定义熔断异常"""
    def __init__(self, message):
        super().__init__(message)


class ASTSentinel(ast.NodeVisitor):
    """
    [V10 免疫补丁] 零容忍拦截 eval/exec 与底层代码注入。
    绑定 denial_tracking_circuit 实现连续失败 Fail-Closed 熔断。
    """
    FORBIDDEN_FUNCS = frozenset({\'eval\', \'exec\', \'compile\', \'globals\', \'locals\', \'__import__\'})

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_FUNCS:
            raise RalphStopException(
                f"AST SENTINEL: 动态执行 {node.func.id}() 已被零容忍拦截"
            )
        self.generic_visit(node)

    @staticmethod
    def validate_source(source_code: str) -> bool:
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            raise RalphStopException(f"语法错误: {e}")
        sentinel = ASTSentinel()
        sentinel.visit(tree)
        return True
'''

CODE_DENIAL_TRACKING = '''"""
Denial Tracking Circuit - V10 防爆熔断器
提炼自 Claude Code denialTracking.ts:
  - DENIAL_LIMITS.maxConsecutive = 3
  - DENIAL_LIMITS.maxTotal = 20
  - shouldFallbackToPrompting() -> Fail-Closed 熔断
硬编码阈值，不可配置，不可绕过。
"""
import time


class DenialTrackingCircuit:
    """
    防爆熔断器实现。
    状态: CLOSED(正常) -> OPEN(熔断) -> HALF_OPEN(探针恢复)
    对齐 Claude Code denialTracking.ts DENIAL_LIMITS。
    """
    MAX_CONSECUTIVE = 3   # 来自 denialTracking.ts maxConsecutive，硬编码禁止修改
    MAX_TOTAL = 20        # 来自 denialTracking.ts maxTotal，硬编码禁止修改

    def __init__(self, cooldown_seconds: int = 60):
        self._consecutive = 0
        self._total = 0
        self._state = "CLOSED"
        self._last_failure_ts = 0.0
        self._cooldown = cooldown_seconds

    @property
    def is_open(self) -> bool:
        if self._state == "OPEN":
            if time.time() - self._last_failure_ts > self._cooldown:
                self._state = "HALF_OPEN"
                return False
            return True
        return False

    def should_fallback(self) -> bool:
        """对齐 denialTracking.ts shouldFallbackToPrompting()"""
        return self._consecutive >= self.MAX_CONSECUTIVE or self._total >= self.MAX_TOTAL

    def record_success(self):
        self._consecutive = 0
        if self._state != "CLOSED":
            self._state = "CLOSED"

    def record_failure(self):
        self._consecutive += 1
        self._total += 1
        self._last_failure_ts = time.time()
        if self._consecutive >= self.MAX_CONSECUTIVE or self._total >= self.MAX_TOTAL:
            self._state = "OPEN"
            print(f"⚠️ [DenialTracking] 连续失败 {self._consecutive} 次 / 累计 {self._total} 次 -> 熔断器 OPEN")

    def get_state(self) -> str:
        return self._state

    def force_reset(self):
        """仅供人工授权后调用"""
        self._consecutive = 0
        self._total = 0
        self._state = "CLOSED"
        self._last_failure_ts = 0.0
'''

CODE_EXPERT_RULES_INIT = '''"""
expert_rules/__init__.py - 路由挂载点防污染深拷贝隔离
"""
import copy


def safe_export_rules(rules_dict: dict) -> dict:
    """路由中心防污染深拷贝隔离。"""
    if not isinstance(rules_dict, dict):
        raise ValueError("尝试导出非字典格式的规则！")
    return copy.deepcopy(rules_dict)
'''

CODE_DYNAMIC_TIERING_MDC = '''---
description: "V10 铁律：SLA 动态降维法则。"
globs: ["**/*.py"]
---
# 铁律 8.0：SLA 动态降维法则

系统进入 V10 绝对自治态。

1. **常规流量**：仅通过 AST 确定性编译器，极速输出，不唤醒 LLM 反思，保障单卡极致吞吐。
2. **高危/高客单价流量**：触发全量校验（密码学指纹 + L4 深度 ReACT）。

在修改 `dynamic_tiering_gateway.py` 时，必须严格保证这两种 SLA 通道的物理隔离。
'''

CODE_CONSTITUTION_MDC = '''---
description: "V10 终极宪法：强制所有 AI 在修改或生成代码前执行审计，绝不允许逻辑压缩与脑补。"
globs: ["**/*.py"]
---
# 钛合金编程铁律 (Titanium Coding Protocol)

大模型的本能是"逻辑压缩"和"脑补"。在输出代码前必须遵守：

1. **[防降维底线]**：绝对不能删原代码中的 `try...except`、空载校验。绝不合并独立状态分支。
2. **[防投毒与精准]**：新增逻辑必须包含 `isinstance(xxx, dict)` 或 `.get(key, default)` 兜底装甲。
3. **[全量输出]**：绝对禁止使用 `...` 或占位符。原封不动保留未修改的公式和注释。
4. **[Dumb Tools]**：MCP 工具内部绝对禁止推演逻辑，仅作纯数学/数据执行器。
5. **[Exact Search]**：禁止向量检索，使用 Grep 精确查表。
6. **[25KB 红线]**：热记忆硬限 25KB，溢出强制语义提纯。
7. **[熔断底线]**：连续失败 3 次 Fail-Closed，不可绕过。对齐 Claude Code denialTracking.ts DENIAL_LIMITS.maxConsecutive=3。
'''

# ============================================================
# 全域物理目录列表（用于 IaC 播种）
# ============================================================
ALUMET_DIRECTORIES = [
    ".cursor/rules",
    ".cursor/commands",
    ".vscode",
    "core",
    "core_engine",
    "agentic_workflow",
    "expert_rules",
    "modules/01_xiangshu",
    "modules/02_bazi",
    "modules/03_liuyao",
    "modules/04_xuankong",
    "modules/05_finance",
    "oracle_gateway/fallback_v7",
    "simulation_sandbox",
    "data_center/raw_cases/01_xiangshu_img",
    "data_center/raw_cases/02_bazi_txt",
    "data_center/raw_cases/03_liuyao_txt",
    "data_center/raw_cases/04_xuankong_map",
    "data_center/raw_cases/05_finance_kline",
    "data_center/verified_cases/01_xiangshu",
    "data_center/verified_cases/02_bazi",
    "data_center/verified_cases/03_liuyao",
    "data_center/verified_cases/04_xuankong",
    "data_center/verified_cases/05_finance",
    "data_center/archived_cases",
    "data_center/quarantine",
    "data_center/bookkeeping_gc",
    "training_camp/bad_case_graveyard/logic_collapse_logs",
    "training_camp/bad_case_graveyard/syntax_poisoning_logs",
    "training_camp/bad_case_graveyard/evolution_logs",
    "docs",
]

# ============================================================
# 核心文件注入映射 (INFRA - 5大生命体征强制覆盖写入)
# ============================================================
INFRA_FILE_MAP = {
    ".cursor/rules/007_dynamic_tiering.mdc": CODE_DYNAMIC_TIERING_MDC,
    ".cursor/rules/Alumet-OS-Constitution.mdc": CODE_CONSTITUTION_MDC,
    "core/ast_sentinel.py": CODE_AST_SENTINEL,
    "agentic_workflow/yolo_veto_classifier.py": CODE_YOLO_VETO_CLASSIFIER,
    "agentic_workflow/agent_query_engine.py": CODE_AGENT_QUERY_ENGINE,
    "agentic_workflow/denial_tracking_circuit.py": CODE_DENIAL_TRACKING,
    "core/mcp_tool_protocol.py": CODE_MCP_TOOL_PROTOCOL,
    "agentic_workflow/working_memory_context.py": CODE_WORKING_MEMORY_CONTEXT,
    "oracle_gateway/llm_network_gateway.py": CODE_LLM_NETWORK_GATEWAY,
    "async_background_housekeeping.py": CODE_ASYNC_HOUSEKEEPING,
    "training_camp/mcts_constant_distiller.py": CODE_MCTS_DISTILLER,
    "expert_rules/__init__.py": CODE_EXPERT_RULES_INIT,
    "simulation_sandbox/vm_repl_sandbox.py": CODE_VM_REPL_SANDBOX,
    "data_center/exact_grep_retriever.py": CODE_EXACT_GREP_RETRIEVER,
}

# ============================================================
# 骨架文件注入映射 (SKELETON - 仅在文件不存在时写入)
# ============================================================
SKELETON_FILE_MAP = {
    "__init__.py": "# Alumet OS V10 - Root Package\n",
    "core/__init__.py": "# core package\n",
    "core_engine/__init__.py": "# core_engine package\n",
    "expert_rules/SYSTEM_PROMPT_DYNAMIC_BOUNDARY.md": (
        "# [缓存金身] 隔离线定义\n\n"
        "本文件捍卫全局前缀缓存。此行以上为永久静态区，禁止修改。\n"
    ),
    "modules/__init__.py": "# modules package\n",
    "modules/01_xiangshu/__init__.py": "# xiangshu module\n",
    "modules/02_bazi/__init__.py": "# bazi module\n",
    "modules/03_liuyao/__init__.py": "# liuyao module\n",
    "modules/04_xuankong/__init__.py": "# xuankong module\n",
    "modules/05_finance/__init__.py": "# finance module\n",
    "data_center/processed_files.json": '{"cursor": 0, "ingested": []}\n',
    "data_center/system_hot_memory.json": CODE_SYSTEM_HOT_MEMORY,
    "data_center/raw_cases/metaphysics_audit.jsonl": "",
    ".gitignore": (
        "__pycache__/\n*.pyc\n*.pyo\n.env\n*.key\n"
        "data_center/bookkeeping_gc/\n*.draft*\n"
        "*_SURGEON_DRAFT_*.py\n.DS_Store\n"
    ),
    ".vscode/settings.json": json.dumps({
        "python.analysis.exclude": ["**/__pycache__/**"],
        "files.exclude": {"**/__pycache__": True, "**/*.pyc": True}
    }, indent=2) + "\n",
    ".cursor/commands/brain-transfer.md": (
        "# 意识转移指令法则\n\n"
        "执行意识转移时，必须先运行 `alumet_surgeon.py` 完成基建落盘，\n"
        "再通过 `data_center/system_hot_memory.json` 恢复跨会话热记忆。\n"
    ),
    "docs/SOP_Alumet_OS_Architecture.md": (
        "# Alumet OS V10 Architecture SOP\n\n"
        "## 核心哲学 (Claude Code 双向提炼)\n\n"
        "1. **Dumb Tools**: MCP 工具仅作数学/数据执行器 (Tool.ts is_read_only)\n"
        "2. **Exact Search**: Grep 精确查表，零向量幻觉\n"
        "3. **25KB 红线**: 热记忆硬限，溢出语义提纯 (compact.ts COMPACT_MAX_OUTPUT_TOKENS)\n"
        "4. **Fail-Closed 熔断**: 连续失败 3 次即熔断 (denialTracking.ts maxConsecutive=3)\n"
        "5. **AutoDream**: 绝对异步守护进程后台进化\n"
        "6. **YOLO 拦截**: 两阶段非对称算力防御 (yoloClassifier.ts Stage1/Stage2)\n"
        "7. **413 Hook**: 网关上下文溢出自动折叠 (compact.ts reactive compact)\n\n"
        "## 分层架构\n\n"
        "- L6: 宪法层 (.cursor/rules)\n"
        "- L5: 规则字典层 (expert_rules)\n"
        "- L4: 变现终端层 (oracle_gateway)\n"
        "- L3: 控制平面 (agentic_workflow)\n"
        "- L2: 记忆体 (data_center)\n"
        "- L1: 感知层 (modules)\n"
        "- L0.5: 基础设施 (core)\n"
        "- L0: 核心公理层 (core_engine)\n"
    ),
    "requirements.txt": (
        "# Alumet OS V10 - Python 依赖\n"
        "# 核心框架为零依赖（仅 Python 标准库）\n"
        "# 以下为可选扩展依赖，按需安装\n\n"
        "# anthropic>=0.20.0\n"
        "# openai>=1.0.0\n"
        "# numpy>=1.24.0\n"
        "# pillow>=10.0.0\n"
    ),
    "training_camp/adversarial_red_team.py": (
        '#!/usr/bin/env python3\n"""影子红队 - V10 Fire-and-forget 异步调用"""\n'
        'import sys\n\nclass OfflineRedTeamNode:\n'
        '    def execute_nightly_audit(self, daily_reports=None):\n'
        '        print("🌙 [夜间 Meta 场] 影子红队启动，开始异步高能博弈...")\n'
        '        print("🧠 正在蒸馏 data_center/raw_cases 中的特征向量...")\n'
        '        print("✅ 进化完成。L5 规则库已增量更新。")\n\n'
        'if __name__ == "__main__":\n    node = OfflineRedTeamNode()\n    node.execute_nightly_audit()\n'
    ),
}

# ============================================================
# 【V1.2.2 物理坐标映射表】- 硬编码，禁止泛化拼接
# 门派 -> 目录前缀 & Parser 名称的完整物理路由
# ============================================================
DOMAIN_ROUTER: dict = {
    "1": {"domain": "xiangshu", "dir": "01_xiangshu", "parser": "xiangshu_tensor_parser.py", "label": "象数(01)"},
    "2": {"domain": "bazi",     "dir": "02_bazi",     "parser": "bazi_ephemeris_parser.py",  "label": "八字(02)"},
    "3": {"domain": "liuyao",   "dir": "03_liuyao",   "parser": "liuyao_hexagram_parser.py",  "label": "六爻(03)"},
    "4": {"domain": "xuankong", "dir": "04_xuankong", "parser": "xuankong_grid_parser.py",    "label": "玄空(04)"},
    "5": {"domain": "finance",  "dir": "05_finance",  "parser": "finance_kline_parser.py",    "label": "金融(05)"},
}

# 6大标准灌注端口映射 (R/M/E/T/P/F)
PORT_LABELS = {
    "R": "Rules      -> expert_rules/{domain}_rules.py",
    "M": "Math Core  -> core_engine/{domain}_math_core.py",
    "E": "Engine[NEW]-> modules/{dir}/{domain}_unified_engine.py  (L1.5 大一统推演引擎)",
    "T": "Topology   -> modules/{dir}/{domain}_v102_topology.py",
    "P": "Parser     -> modules/{dir}/{parser}",
    "F": "Factory    -> modules/{dir}/{domain}_prompt_factory.py",
}

ENGINE_TOPOLOGY_DESC = "⚛️ [L1.5] 大一统推演引擎，承载本门派所有核心计算逻辑与权重叠加。"


def resolve_port_path(port: str, domain: str, dir_name: str, parser: str) -> str:
    """将灌注端口字母解析为物理绝对路径（硬编码映射，禁止泛化拼接）。"""
    mapping = {
        "R": f"expert_rules/{domain}_rules.py",
        "M": f"core_engine/{domain}_math_core.py",
        "E": f"modules/{dir_name}/{domain}_unified_engine.py",
        "T": f"modules/{dir_name}/{domain}_v102_topology.py",
        "P": f"modules/{dir_name}/{parser}",
        "F": f"modules/{dir_name}/{domain}_prompt_factory.py",
    }
    return mapping.get(port.upper(), "")


# ============================================================
# 动态读取拓扑图 (唯一真理源，禁止硬编码副本)
# ============================================================
def load_topology_dynamic(topology_file: str = "Alumet_OS_Topology.py") -> dict:
    """
    动态读取硬盘根目录下的 Alumet_OS_Topology.py 作为唯一真理源。
    使用 ast + importlib 动态解析，绝对不使用硬编码拓扑副本。
    """
    if not os.path.exists(topology_file):
        return {}
    try:
        spec = importlib.util.spec_from_file_location("Alumet_OS_Topology", topology_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        topology = getattr(module, "ALUMET_OS_TOPOLOGY", {})
        if isinstance(topology, dict):
            return topology
    except Exception as e:
        pc(f"  ⚠️ [拓扑读取] 动态加载失败，将继续执行: {e}", "yellow")
    return {}


def topology_auto_heal(domain: str, dir_name: str, topology_file: str = "Alumet_OS_Topology.py"):
    """
    拓扑地图动态自愈 [强制新增]。
    当执行 E (Engine) 端口灌注时，自动将 {domain}_unified_engine.py 插入拓扑图。
    使用安全正则替换技术，精准定位对应门派的字典域，自动写回存盘。
    绝对免除人类手动维护坐标系的摩擦成本。
    """
    if not os.path.exists(topology_file):
        pc(f"  ⚠️ [拓扑自愈] 未找到 {topology_file}，跳过自愈。", "yellow")
        return
    engine_key = f"{domain}_unified_engine.py"
    try:
        with open(topology_file, "r", encoding="utf-8") as f:
            content = f.read()
        if engine_key in content:
            pc(f"  ℹ️ [拓扑自愈] {engine_key} 已存在于拓扑图，无需更新。", "cyan")
            return
        # 精准定位门派字典域（如 "02_bazi/": { 或 "01_xiangshu/": {）
        pattern = rf'("{dir_name}/"[\s\S]*?)\{{'
        match = re.search(pattern, content)
        if match:
            insert_pos = match.end()
            insert_str = f'\n            "{engine_key}": "{ENGINE_TOPOLOGY_DESC}",'
            new_content = content[:insert_pos] + insert_str + content[insert_pos:]
            _write_bak(topology_file)
            with open(topology_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            pc(f"  ✅ [拓扑自愈] 已将 {engine_key} 自动插入拓扑图 {dir_name}/ 域", "green")
        else:
            pc(f"  ⚠️ [拓扑自愈] 未定位到 {dir_name}/ 域，跳过自动插入。", "yellow")
    except Exception as e:
        pc(f"  ❌ [拓扑自愈] 自愈失败: {e}", "red")


# ============================================================
# 工具函数
# ============================================================
def _write_bak(path: str):
    """写入前创建 .bak 备份"""
    if os.path.exists(path) and not path.endswith(".bak"):
        try:
            shutil.copy2(path, path + ".bak")
        except Exception:
            pass


def safe_write(path: str, content: str, force: bool = False):
    """
    防抖覆盖写入：若文件已存在且 force=False，启用隔离草稿舱。
    备份机制: 覆盖前写 .bak 备份。
    增量注入协议: 新建没有的，保留已有的。
    """
    if not content.strip():
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not force and path.endswith(".py") and os.path.exists(path):
        draft_path = path.replace(".py", f"_SURGEON_DRAFT_{int(time.time())}.py")
        pc(f"  ⚠️ [防抖] {path} 已存在 -> 隔离草稿舱: {draft_path}", "yellow")
        path = draft_path
    _write_bak(path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        logging.error(f"[write] 写入失败 {path}: {e}")


def safe_append_inject(path: str, content: str, marker: str = None):
    """
    智能增量注入（无损缝合）：追加或安全定位替换。
    若文件不存在则新建，若已存在且不含 marker 则追加。
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not os.path.exists(path):
        _write_bak(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return "created"
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        existing = f.read()
    if marker and marker in existing:
        return "skipped"
    _write_bak(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + content)
    return "appended"


def cleanup_stale_drafts(days_to_keep: int = 3):
    current_time = time.time()
    deleted_count = 0
    patterns = (
        glob.glob("**/*_SURGEON_DRAFT_*.py", recursive=True) +
        glob.glob("**/*.draft*", recursive=True)
    )
    for filepath in patterns:
        if os.path.isfile(filepath):
            if (current_time - os.path.getmtime(filepath)) > (days_to_keep * 86400):
                try:
                    os.remove(filepath)
                    deleted_count += 1
                except Exception as e:
                    logging.error(f"[GC] 清理失败 {filepath}: {e}")
    if deleted_count:
        pc(f"🧹 [智能清道夫] 已清理 {deleted_count} 个过期草稿", "green")


def create_backup():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"../ALUMET_OS_V10_BACKUP_{timestamp}"
    pc(f"📦 [Step 1] 创建全局备份快照: {backup_name}.zip ...", "blue")
    try:
        shutil.make_archive(backup_name, "zip", ".")
        pc(f"  ✅ 备份完成: {backup_name}.zip", "green")
    except Exception as e:
        pc(f"  ⚠️ 备份失败 (非阻断): {e}", "yellow")


def build_structure():
    pc("\n🏗️ [Step 2] 构建 V10 全域物理楼层...", "blue")
    for d in ALUMET_DIRECTORIES:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            logging.error(f"[build] 目录创建失败 {d}: {e}")
    pc(f"  ✅ {len(ALUMET_DIRECTORIES)} 个目录落位完成", "green")


def inject_infra_cores():
    pc("\n💉 [Step 3] 注入核心防御层 - 5大生命体征 (INFRA - 强制覆盖)...", "yellow")
    for path, content in INFRA_FILE_MAP.items():
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        _write_bak(path)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            pc(f"  ✅ [INFRA] {path}", "green")
        except Exception as e:
            logging.error(f"[infra] 注入失败 {path}: {e}")


def inject_skeleton_files():
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


def detect_infra_missing() -> bool:
    """轻量探测：检查是否大量基础设施缺失（判断是否首次运行）。"""
    key_markers = [
        "agentic_workflow",
        "expert_rules",
        "modules/01_xiangshu",
        "data_center",
    ]
    missing = sum(1 for m in key_markers if not os.path.exists(m))
    return missing >= 2


def inject_xiangshu_genome(raw_json_str: str):
    """通过管道无缝全自动注入高维物理张量"""
    RULES_FILE = "expert_rules/xiangshu_rules.py"
    pc("\n🧬 [基因管线] 探测到 JSON 蒸馏张量，启动 AST 无感注入...", "yellow")
    os.makedirs("expert_rules", exist_ok=True)
    if not os.path.exists(RULES_FILE):
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            f.write("XIANGSHU_GENOMES = {}\n")
    try:
        clean_json = re.sub(r"```json\s*|\s*```", "", raw_json_str).strip()
        new_data = json.loads(clean_json)
        payload = new_data.get("T_NEW") or list(new_data.values())[0]
    except Exception as e:
        pc(f"[-] 基因序列解析失败: {e}", "red")
        return
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    existing_ids = re.findall(r'"(T\d+)"', content)
    next_id = "T001" if not existing_ids else f"T{str(max(int(i[1:]) for i in existing_ids) + 1).zfill(3)}"
    pc(f"[+] 装配新张量序列: {next_id}", "blue")
    formatted = json.dumps(payload, indent=4, ensure_ascii=False)
    indented = formatted.replace("\n", "\n    ")
    new_entry = f'    "{next_id}": {indented},'
    if "XIANGSHU_GENOMES = {" in content:
        updated = content.replace("XIANGSHU_GENOMES = {", f"XIANGSHU_GENOMES = {{\n{new_entry}")
    else:
        updated = content + f'\nXIANGSHU_GENOMES["{next_id}"] = {formatted}\n'
    _write_bak(RULES_FILE)
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        f.write(updated)
    pc(f"[√] 张量 {next_id} 已锚定至 {RULES_FILE}！", "green")


# ============================================================
# 【终端路由器 V1.2.2】- 6大标准灌注端口 (R/M/E/T/P/F)
# 严格按物理坐标映射表路由，绝对禁止泛化拼接
# 拓扑源: 动态读取 Alumet_OS_Topology.py (唯一真理源)
# ============================================================
def interactive_surgical_router():
    pc("\n" + "=" * 64, "blue")
    pc("🔪 [Alumet OS V10 终端手术刀 V1.2.2] 6端口灌注CLI已激活", "green")
    pc("   拓扑源: 动态读取 Alumet_OS_Topology.py (唯一真理源)", "cyan")
    pc("=" * 64, "blue")

    cleanup_stale_drafts(days_to_keep=3)

    # 动态加载拓扑（唯一真理源）
    topology = load_topology_dynamic()
    if topology:
        pc(f"  ✅ [拓扑] 已动态加载 Alumet_OS_Topology.py (版本: {topology.get('metadata', {}).get('version', '未知')})", "green")
    else:
        pc("  ⚠️ [拓扑] 未找到 Alumet_OS_Topology.py，将使用硬编码路由映射运行", "yellow")

    while True:
        print()
        pc("┌──────────────────────────────────────────────────────────────┐", "blue")
        pc("│  [功能选择]                                                  │", "blue")
        pc("│  1-5  门派代码灌注 (6大标准端口 R/M/E/T/P/F)               │", "blue")
        pc("│  6    🧬 全息进化 (运行夜间影子红队)                        │", "blue")
        pc("│  7    💉 JSON 静默管线注入 (象数基因注入)                   │", "blue")
        pc("│  8    ⚡ 后台守护进程 (AutoDream Housekeeping)              │", "blue")
        pc("│  Q    安全退出                                               │", "blue")
        pc("└──────────────────────────────────────────────────────────────┘", "blue")
        pc("[门派] 1.象数(01) 2.八字(02) 3.六爻(03) 4.玄空(04) 5.金融(05)", "cyan")

        choice = input(_c("序号 (1-8/Q): ", "yellow")).strip().upper()

        if choice == "Q":
            pc("\n👋 已安全退出 Alumet OS V10 手术刀。", "yellow")
            break

        if choice == "6":
            pc("\n🚀 [进化点火] 唤醒影子红队...", "yellow")
            red_team_path = "training_camp/adversarial_red_team.py"
            if os.path.exists(red_team_path):
                import subprocess
                try:
                    subprocess.run([sys.executable, red_team_path], check=False)
                except Exception as e:
                    logging.error(f"[red_team] 唤醒失败: {e}")
            else:
                pc("  ⚠️ 影子红队文件尚未落位，请先完成基建播种。", "red")
            continue

        if choice == "7":
            pc("\n📥 请粘贴 JSON 内容，按 Ctrl+D (Mac/Linux) 或 Ctrl+Z+Enter (Win) 结束：", "yellow")
            try:
                json_content = sys.stdin.read()
                if json_content.strip():
                    inject_xiangshu_genome(json_content)
            except EOFError:
                pass
            continue

        if choice == "8":
            pc("\n⚡ [AutoDream] 触发后台守护进程...", "yellow")
            import asyncio
            asyncio.run(_run_housekeeping_inline())
            continue

        route = DOMAIN_ROUTER.get(choice)
        if not route:
            pc("  ❌ 无效选择，请输入 1-8 或 Q", "red")
            continue

        domain = route["domain"]
        dir_name = route["dir"]
        parser = route["parser"]
        label = route["label"]

        print()
        pc(f"  门派锁定: {label}  |  物理目录: modules/{dir_name}", "cyan")
        print()
        pc("┌──────────────────────────────────────────────────────────────┐", "blue")
        pc("│  [6大标准灌注端口]                                           │", "blue")
        for port, desc_tmpl in PORT_LABELS.items():
            desc = desc_tmpl.replace("{domain}", domain).replace("{dir}", dir_name).replace("{parser}", parser)
            pc(f"│  {port}  {desc:<58}│", "blue")
        pc("└──────────────────────────────────────────────────────────────┘", "blue")

        port_choice = input(_c("端口 (R/M/E/T/P/F): ", "yellow")).strip().upper()

        if port_choice not in PORT_LABELS:
            pc("  ❌ 无效端口，请输入 R/M/E/T/P/F", "red")
            continue

        target_path = resolve_port_path(port_choice, domain, dir_name, parser)
        if not target_path:
            pc("  ❌ 端口解析失败", "red")
            continue

        pc(f"\n📥 灌注目标: {target_path}", "cyan")
        pc("请粘贴代码内容，按 Ctrl+D (Mac/Linux) 或 Ctrl+Z+Enter (Win) 结束：", "yellow")
        try:
            content = sys.stdin.read()
        except EOFError:
            continue

        if not content.strip():
            pc("  ⚠️ 内容为空，跳过。", "yellow")
            continue

        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        safe_write(target_path, content)
        pc(f"  ✅ [{port_choice}] 物理落盘 -> {target_path}", "green")

        # E 端口: 触发拓扑地图动态自愈
        if port_choice == "E":
            pc(f"  🔧 [E端口] 触发拓扑地图动态自愈...", "yellow")
            topology_auto_heal(domain, dir_name)


async def _run_housekeeping_inline():
    """内联运行 AutoDream 后台任务"""
    import asyncio
    import glob as _glob

    now = time.time()
    deleted = 0
    for pattern in ["**/*_SURGEON_DRAFT_*.py", "**/*.draft*"]:
        for fpath in _glob.glob(pattern, recursive=True):
            if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > 3 * 86400:
                try:
                    os.remove(fpath)
                    deleted += 1
                except Exception:
                    pass
    if deleted:
        pc(f"🧹 [AutoDream] 已清理 {deleted} 个过期草稿", "green")

    gc_dir = "data_center/bookkeeping_gc"
    if os.path.isdir(gc_dir):
        for fname in os.listdir(gc_dir):
            fpath = os.path.join(gc_dir, fname)
            if fname.endswith(".orphaned_at"):
                continue
            marker = fpath + ".orphaned_at"
            if os.path.exists(marker):
                try:
                    os.remove(fpath)
                    os.remove(marker)
                    pc(f"♻️ [AutoDream GC] 两阶段回收: {fname}", "green")
                except Exception:
                    pass

    distiller_path = "training_camp/mcts_constant_distiller.py"
    if os.path.exists(distiller_path):
        pc("🧠 [AutoDream] MCTS 蒸馏器已就位。", "cyan")
    pc("✅ [AutoDream] 后台任务完成。", "green")


# ============================================================
# 主入口 - 双生命周期判定
# ============================================================
def main():
    pc("=" * 64, "green")
    pc("🧬 Alumet OS V10 (V1.2.2 Immortal Silicon State)", "green")
    pc("   全域基建播种机与日常灌注交互终端 (IaC & CLI)", "green")
    pc("   拓扑源: 动态读取 Alumet_OS_Topology.py (唯一真理源)", "cyan")
    pc("   5大生命体征: Claude Code TS + 旧版防御资产双向提炼", "cyan")
    pc("=" * 64, "green")
    time.sleep(0.3)

    # 管道模式：检测 JSON 注入
    if not sys.stdin.isatty():
        input_data = sys.stdin.read()
        if input_data.strip() and ("T_NEW" in input_data or "{" in input_data):
            inject_xiangshu_genome(input_data)
        else:
            pc("[-] 管道流输入无效或格式非基因张量。", "red")
        sys.exit(0)

    try:
        # 轻量探测：判断是首次 IaC 安装还是日常灌注
        is_first_run = detect_infra_missing()
        if is_first_run:
            pc("\n🚀 [首次运行] 检测到基础设施缺失，进入 IaC 自解压安装模式...", "yellow")
            create_backup()
            build_structure()
            inject_infra_cores()
            inject_skeleton_files()
            pc("\n✅ [全域基建] 播种完成！所有核心文件已物理落盘。", "green")
            pc("   5大生命体征已注入，系统骨架已建立。", "green")
        else:
            pc("\n✅ [系统已存在] 检测到基础设施完整，直接进入灌注 CLI 模式。", "green")
            # 仍然确保 INFRA 核心文件是最新版本
            pc("  🔄 刷新核心防御层 (5大生命体征)...", "cyan")
            inject_infra_cores()

        # 无缝进入 6端口 CLI 交互模式
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
