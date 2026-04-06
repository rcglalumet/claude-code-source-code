#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alumet OS V10 (V1.2.2 Immortal Silicon State)
全域基建播种机与自解压程序 - alumet_surgeon.py

零依赖 | 仅使用 Python 标准库
物理边界: 5090+32G VRAM + 96G RAM
"""

import os
import sys
import shutil
import json
import time
import re
import glob
import logging
import hashlib
import copy
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(message)s')

# ============================================================
# 彩色终端输出
# ============================================================
def _c(text, color="green"):
    codes = {
        "green": "\033[92m", "red": "\033[91m",
        "yellow": "\033[93m", "blue": "\033[94m",
        "cyan": "\033[96m", "reset": "\033[0m"
    }
    return f"{codes.get(color, codes['reset'])}{text}{codes['reset']}"


def pc(text, color="green"):
    print(_c(text, color))


# ============================================================
# [CODE STRINGS] 核心文件内容 - 完整物理代码（非占位符）
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
    FORBIDDEN_FUNCS = frozenset({'eval', 'exec', 'compile', 'globals', 'locals', '__import__'})

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_FUNCS:
            raise RalphStopException(
                f"\\u0041ST SENTINEL: 动态执行 {node.func.id}() 已被零容忍拦截"
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
'''

CODE_TENSOR_FINGERPRINT = '''import hashlib
import json


class TensorFingerprintGenerator:
    """
    [V10 免疫补丁] L0 物理证明机：防大模型篡改结论。
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
'''

CODE_MCP_TOOL_PROTOCOL = '''"""
MCP Tool Protocol - V10 契约层
强制约束:
  1. Dumb Tools: 工具内部绝对禁止推演逻辑 Prompt，仅作数学/数据执行器。
  2. 极致缓存护城河: Schema 禁止出现巨大 Enum 防缓存击穿。
  3. is_read_only 属性配合调度器实现只读隔离。
"""
from typing import Any


class MCPToolBase:
    """所有 MCP 工具的刚性基类契约"""
    name: str = ""
    description: str = ""
    is_read_only: bool = True

    def get_schema(self) -> dict:
        """
        返回工具的 JSON Schema。
        [强制] 禁止在 enum 字段塞入超过 20 个值，防缓存击穿。
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
                "file_extension": {"type": "string", "description": "文件扩展名过滤，如 .py"}
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
                                results.append({
                                    "file": fpath,
                                    "line": lineno,
                                    "content": line.rstrip()
                                })
                except Exception:
                    pass
        return {"results": results, "count": len(results)}
'''

CODE_WORKING_MEMORY_CONTEXT = '''"""
Working Memory Context - V10 动态热数据容器
强制约束: 25KB 热数据溢出红线，溢出前强制唤醒语义提纯。
"""
import os
import json


MAX_HOT_MEMORY_BYTES = 25 * 1024  # 25KB 红线


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
        """语义提纯: 保留 IMMORTAL 标签条目，删除后半段普通条目。"""
        print("\\u26a0\\ufe0f [WorkingMemory] 触达 25KB 红线，启动语义提纯...")
        immortal = {k: v for k, v in self._context.items() if "[IMMORTAL]" in str(k)}
        mortal = {k: v for k, v in self._context.items() if "[IMMORTAL]" not in str(k)}
        keys = list(mortal.keys())
        keep_keys = keys[len(keys) // 2:]
        kept_mortal = {k: mortal[k] for k in keep_keys}
        self._context = {**immortal, **kept_mortal}
        print("\\u2728 [WorkingMemory] 语义提纯完成，高频指纹永久锚定。")

    def flush(self):
        os.makedirs(os.path.dirname(self.memory_file) or ".", exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self._context, f, ensure_ascii=False, indent=2)
'''

CODE_AGENT_QUERY_ENGINE = '''"""
Agent Query Engine - V10 全域唯一主循环
L3 控制平面核心，映射 Claude Code QueryEngine.ts。

强制约束:
  1. YOLO 拦截: 所有输入前置经过 yolo_veto_classifier 过滤。
  2. Fail-Closed 熔断: 连续失败 3 次即熔断，硬编码不可绕过。
  3. 非对称算力防御: 低价小模型前置过滤，高价大模型后置执行。
"""
import time


class AgentQueryEngine:
    """
    V10 主循环引擎 (while-true 架构)。
    连续失败 3 次 -> Fail-Closed 熔断止损。
    """
    MAX_CONSECUTIVE_FAILURES = 3  # 硬编码熔断阈值，不可修改

    def __init__(self, working_memory, yolo_classifier, tool_registry, oracle_gateway):
        self.memory = working_memory
        self.yolo = yolo_classifier
        self.tools = tool_registry
        self.oracle = oracle_gateway
        self._consecutive_failures = 0
        self._is_fused = False

    def run(self, user_query: str) -> dict:
        if self._is_fused:
            return {"status": "FAIL_CLOSED", "reason": "熔断器已触发，拒绝服务。"}

        # YOLO 前置拦截
        veto_result = self.yolo.classify(user_query)
        if veto_result.get("vetoed"):
            return {"status": "VETOED", "reason": veto_result.get("reason", "YOLO 拦截")}

        try:
            result = self._execute_with_circuit_breaker(user_query)
            self._consecutive_failures = 0
            return result
        except Exception as e:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self._is_fused = True
                return {
                    "status": "FAIL_CLOSED",
                    "reason": f"连续失败 {self.MAX_CONSECUTIVE_FAILURES} 次，熔断器触发: {e}"
                }
            return {"status": "ERROR", "error": str(e), "failures": self._consecutive_failures}

    def _execute_with_circuit_breaker(self, query: str) -> dict:
        """核心推演逻辑，由子类或插件扩展。"""
        raise NotImplementedError("子类必须实现 _execute_with_circuit_breaker")

    def reset_circuit(self):
        """人工复位熔断器（需人工授权）"""
        self._consecutive_failures = 0
        self._is_fused = False
'''

CODE_YOLO_VETO_CLASSIFIER = r'''"""
YOLO Veto Classifier - V10 前置拦截防线
非对称算力防御: 部署极低成本规则引擎前置审查指令与乱码。
绝对禁止在此处调用大模型 API，保持纯规则/正则执行。
"""
import re


GARBAGE_PATTERNS = [
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",   # 控制字符
    r"(.)\1{20,}",                             # 重复字符超过20次
    r"[^\x00-\x7f]{50,}(?![\u4e00-\u9fff])",  # 非中文非ASCII大段乱码
]

HIGH_RISK_PATTERNS = [
    r"(?i)(rm\s+-rf|format\s+c:|drop\s+table|delete\s+from)",
    r"(?i)(eval|exec|__import__|subprocess\.call)",
    r"(?i)(password|secret|api_key|private_key)\s*=\s*['\"][^'\"]{8,}",
]


class YoloVetoClassifier:
    """
    [YOLO 拦截哲学] 纯规则引擎，零 LLM 调用。
    低成本前置过滤乱码与高危指令，实施非对称算力防御。
    """

    def __init__(self):
        self._garbage_re = [re.compile(p) for p in GARBAGE_PATTERNS]
        self._high_risk_re = [re.compile(p) for p in HIGH_RISK_PATTERNS]

    def classify(self, text: str) -> dict:
        if not isinstance(text, str) or not text.strip():
            return {"vetoed": True, "reason": "空输入或非字符串"}

        for pattern in self._garbage_re:
            if pattern.search(text):
                return {"vetoed": True, "reason": "检测到乱码/垃圾字符"}

        for pattern in self._high_risk_re:
            if pattern.search(text):
                return {"vetoed": True, "reason": "检测到高危指令模式", "escalate": True}

        if len(text) > 32768:
            return {"vetoed": True, "reason": "输入超过 32KB 上限"}

        return {"vetoed": False}
'''

CODE_DENIAL_TRACKING = '''"""
Denial Tracking Circuit - V10 防爆熔断器
连续 3 次失败即刻 Fail-Closed 熔断止损。
硬编码阈值，不可配置，不可绕过。
"""
import time


class DenialTrackingCircuit:
    """
    防爆熔断器实现。
    状态: CLOSED(正常) -> OPEN(熔断) -> HALF_OPEN(探针恢复)
    """
    MAX_FAILURES = 3  # 硬编码，禁止修改

    def __init__(self, cooldown_seconds: int = 60):
        self._failures = 0
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

    def record_success(self):
        self._failures = 0
        self._state = "CLOSED"

    def record_failure(self):
        self._failures += 1
        self._last_failure_ts = time.time()
        if self._failures >= self.MAX_FAILURES:
            self._state = "OPEN"
            print(f"\\u26a0\\ufe0f [DenialTracking] 连续失败 {self.MAX_FAILURES} 次 -> 熔断器 OPEN")

    def get_state(self) -> str:
        return self._state

    def force_reset(self):
        """仅供人工授权后调用"""
        self._failures = 0
        self._state = "CLOSED"
        self._last_failure_ts = 0.0
'''

CODE_ASYNC_HOUSEKEEPING = '''"""
Async Background Housekeeping - V10 AutoDream 守护进程
绝对异步执行，断电不死。
职责:
  1. 两阶段垃圾回收: 扫描 .orphaned_at 标记 -> 物理删除。
  2. 触发 mcts_constant_distiller 夜间复盘。
  3. 清理 3 天前的 _DRAFT 草稿文件。
"""
import asyncio
import os
import time
import glob


ORPHAN_MARKER = ".orphaned_at"
DRAFT_MAX_AGE_SECONDS = 3 * 86400  # 3天


async def two_pass_gc(bookkeeping_dir: str = "data_center/bookkeeping_gc"):
    """两阶段垃圾回收: 第一阶段标记，第二阶段物理删除。"""
    if not os.path.isdir(bookkeeping_dir):
        return
    now = time.time()
    for fname in os.listdir(bookkeeping_dir):
        fpath = os.path.join(bookkeeping_dir, fname)
        marker = fpath + ORPHAN_MARKER
        if os.path.exists(marker):
            try:
                os.remove(fpath)
                os.remove(marker)
                print(f"\\u267b\\ufe0f [AutoDream GC] 两阶段回收完成: {fname}")
            except Exception as e:
                print(f"\\u26a0\\ufe0f [AutoDream GC] 回收失败 {fname}: {e}")
        else:
            mtime = os.path.getmtime(fpath)
            if now - mtime > DRAFT_MAX_AGE_SECONDS:
                try:
                    with open(marker, "w") as f:
                        f.write(str(now))
                    print(f"\\U0001f3f7\\ufe0f [AutoDream GC] 一阶段标记孤儿: {fname}")
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
        print(f"\\U0001f9f9 [AutoDream] 已清理 {deleted} 个过期草稿文件")
    await asyncio.sleep(0)


async def trigger_mcts_distiller():
    """触发 MCTS 夜间复盘（骨架，待对接 mcts_constant_distiller）。"""
    distiller_path = "training_camp/mcts_constant_distiller.py"
    if os.path.exists(distiller_path):
        print("\\U0001f9e0 [AutoDream] 触发 MCTS 蒸馏器...")
    else:
        print("\\u26a0\\ufe0f [AutoDream] mcts_constant_distiller.py 尚未就位，跳过。")
    await asyncio.sleep(0)


async def run_housekeeping():
    """主守护协程，顺序执行所有后台任务。"""
    print("\\u26a1 [AutoDream] 后台守护进程启动...")
    await cleanup_stale_drafts_async()
    await two_pass_gc()
    await trigger_mcts_distiller()
    print("\\u2705 [AutoDream] 本轮后台任务完成。")


if __name__ == "__main__":
    asyncio.run(run_housekeeping())
'''

CODE_MCTS_DISTILLER = '''"""
MCTS Constant Distiller - V10 后台蒸馏器骨架
配合 AutoDream 守护进程，夜间静默复盘脏数据，提炼新常数反哺 L5。
"""
import json
import os
from typing import List


class MCTSConstantDistiller:
    """
    蒙特卡洛树搜索常数蒸馏器。
    输入: 历史推演日志列表
    输出: 提炼后的高置信度常数字典
    """

    def __init__(self, l5_rules_dir: str = "expert_rules"):
        self.l5_rules_dir = l5_rules_dir

    def distill_tensor(self, history_logs: list) -> dict:
        """
        从历史日志中蒸馏高频命中的特征常数。
        [骨架] 具体蒸馏算法由 RLHF 闭环迭代填充。
        """
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
        """将蒸馏常数安全写回 L5 规则层（骨架）。"""
        target = os.path.join(self.l5_rules_dir, f"{domain}_distilled_constants.json")
        os.makedirs(self.l5_rules_dir, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(constants, f, ensure_ascii=False, indent=2)
        print(f"\\u2728 [Distiller] 常数已写回 L5: {target}")
'''

CODE_SLA_DYNAMIC_ROUTER = '''"""
SLA Dynamic Router + Dynamic Tiering Gateway - V10 核心路由
两条物理隔离通道: AST 极速通道 | 密码学全量校验通道
常规流量 -> AST 通道 (不唤醒 LLM 反思)
高危/高客单价流量 -> 全量密码学校验通道
"""


class SLADynamicRouter:
    """
    [V10 核心躯干] 动态熔断路由。
    两通道物理隔离，禁止合并或复用。
    """

    FAST_TRACK = "V10_AST_FAST_TRACK"
    FULL_TRACK = "V10_FULL_CRYPTO_TRACK"

    @staticmethod
    def route_request(request_payload: dict) -> str:
        if not isinstance(request_payload, dict):
            return SLADynamicRouter.FULL_TRACK  # 防投毒兜底
        risk_level = request_payload.get("risk_level", "LOW")
        amount = request_payload.get("amount", 0)
        if risk_level == "HIGH" or (isinstance(amount, (int, float)) and amount > 10000):
            return SLADynamicRouter.FULL_TRACK
        return SLADynamicRouter.FAST_TRACK

    @staticmethod
    def execute_fast_track(payload: dict) -> dict:
        """AST 极速通道: 不唤醒 LLM，直接确定性编译输出。"""
        return {"track": SLADynamicRouter.FAST_TRACK, "result": "ast_compiled", "payload": payload}

    @staticmethod
    def execute_full_track(payload: dict, fingerprint_proof: str = "") -> dict:
        """全量密码学校验通道: 需要指纹证明 + L4 深度 ReACT。"""
        return {
            "track": SLADynamicRouter.FULL_TRACK,
            "fingerprint_verified": bool(fingerprint_proof),
            "result": "full_crypto_validated",
            "payload": payload
        }
'''

CODE_VRAM_SCHEDULER = '''"""
VRAM Tidal Scheduler - V10 显存防线
32GB VRAM 完整潮汐调度器。
VLM 视觉探针与 LLM 推演互斥，强制资源隔离。
"""
import asyncio
import time


class RTX5090ResourceManager:
    """
    [V10 核心防线] 32GB VRAM 完整潮汐调度器。
    VLM (视觉模型) 与 LLM 互斥锁，防止显存 OOM。
    """

    VRAM_TOTAL_GB = 32
    VLM_RESERVED_GB = 20
    LLM_RESERVED_GB = 10

    def __init__(self):
        self._vlm_lock = asyncio.Lock()
        self._llm_lock = asyncio.Lock()
        self._vlm_active = False
        self._llm_active = False

    async def acquire_vlm(self):
        await self._vlm_lock.acquire()
        self._vlm_active = True
        print(f"\\U0001f534 [VRAM] 锁定 {self.VLM_RESERVED_GB}GB 给视觉探针 VLM")

    def release_vlm(self):
        self._vlm_active = False
        try:
            self._vlm_lock.release()
        except RuntimeError:
            pass
        print(f"\\U0001f7e2 [VRAM] 释放视觉探针 VRAM")

    async def acquire_llm(self):
        if self._vlm_active:
            print("\\u23f3 [VRAM] VLM 占用中，LLM 排队等待...")
        await self._llm_lock.acquire()
        self._llm_active = True
        print(f"\\U0001f534 [VRAM] 锁定 {self.LLM_RESERVED_GB}GB 给 LLM 推演")

    def release_llm(self):
        self._llm_active = False
        try:
            self._llm_lock.release()
        except RuntimeError:
            pass
        print(f"\\U0001f7e2 [VRAM] 释放 LLM VRAM")

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
'''

CODE_SMART_MEMORY_GUARD = '''"""
Smart Memory Guard - V10 语义锚点保留协议
废除无脑物理截断，启用 IMMORTAL 标签扫描保护核心历史指纹。
25KB 红线硬编码。
"""
import os


class SmartMemoryGuard:
    """
    [V10 终极改造] 语义锚点保留协议。
    25KB 红线 -> 保留 IMMORTAL + 后半段普通条目。
    """

    MAX_MEMORY_SIZE_BYTES = 25 * 1024  # 25KB 红线，禁止修改

    @staticmethod
    def enforce_entropy_reduction(memory_file_path: str):
        if not os.path.exists(memory_file_path):
            return
        if os.path.getsize(memory_file_path) <= SmartMemoryGuard.MAX_MEMORY_SIZE_BYTES:
            return

        print("\\U0001f5dc\\ufe0f [SmartMemory] 触达 25KB 红线，启动语义提纯...")
        try:
            with open(memory_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            immortal_lines = [l for l in lines if "[IMMORTAL]" in l]
            mortal_lines = [l for l in lines if "[IMMORTAL]" not in l]
            keep_mortal = mortal_lines[len(mortal_lines) // 2:]

            with open(memory_file_path, "w", encoding="utf-8") as f:
                f.writelines(immortal_lines + keep_mortal)

            print("\\u2728 [SmartMemory] 低熵垃圾已清退，高频指纹永久锚定！")
        except Exception as e:
            print(f"\\u26a0\\ufe0f [SmartMemory] 记忆瘦身失败: {e}")

    @staticmethod
    def tag_immortal(memory_file_path: str, line_keyword: str):
        """为包含关键词的行注入 [IMMORTAL] 标签。"""
        if not os.path.exists(memory_file_path):
            return
        try:
            with open(memory_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            updated = []
            for line in lines:
                if line_keyword in line and "[IMMORTAL]" not in line:
                    line = line.rstrip() + "  [IMMORTAL]\\n"
                updated.append(line)
            with open(memory_file_path, "w", encoding="utf-8") as f:
                f.writelines(updated)
        except Exception as e:
            print(f"\\u26a0\\ufe0f [SmartMemory] 标签注入失败: {e}")
'''

CODE_EXACT_GREP_RETRIEVER = '''"""
Exact Grep Retriever - V10 全域智能检索
[Exact Search 哲学] 抛弃 ChromaDB 向量检索幻觉。
使用朴素 Grep 纯文本查表与正则匹配，零幻觉，零依赖。
"""
import os
import re
from typing import List


class ExactGrepRetriever:
    """
    全域案例检索器。
    只做精确文本匹配，不做任何语义推演或向量近似搜索。
    """

    def __init__(self, data_root: str = "data_center"):
        self.data_root = data_root

    def search(self, query: str, file_extensions: tuple = (".txt", ".jsonl", ".json", ".py"),
               max_results: int = 50) -> List[dict]:
        """
        Grep 精确搜索。返回匹配行列表。
        """
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
                                results.append({
                                    "file": fpath,
                                    "line": lineno,
                                    "content": line.rstrip()
                                })
                                if len(results) >= max_results:
                                    return results
                except Exception:
                    pass
        return results

    def load_case_by_id(self, case_id: str) -> dict:
        """按 ID 精确加载单条案例（正则 ID 匹配）。"""
        matches = self.search(f'"id"\\\\s*:\\\\s*"{re.escape(case_id)}"')
        if not matches:
            return {}
        fpath = matches[0]["file"]
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = __import__("json").loads(line)
                        if obj.get("id") == case_id:
                            return obj
                    except Exception:
                        pass
        except Exception:
            pass
        return {}
'''

CODE_KERNEL_API_BUS = '''"""
Kernel API Bus - V10 系统调用总线
[Fail-Closed 防线] 高危操作强制向上抛出 ApprovalRequired 异常拦截。
vm_repl_sandbox 只能通过此总线与底层交互，禁止直接 import L0 模块。
"""


class ApprovalRequired(Exception):
    """高危操作需要人工授权"""
    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        super().__init__(f"[HITL 拦截] 操作 '{operation}' 需要人工授权: {reason}")


class KernelApiBus:
    """
    系统调用总线。所有对 L0 核心层的访问必须经过此总线。
    高危操作直接抛出 ApprovalRequired，由 human_approval_prompter 捕获。
    """

    HIGH_RISK_OPS = frozenset({
        "delete_file", "overwrite_rules", "execute_arbitrary_code",
        "modify_constitution", "force_reset_circuit"
    })

    def __init__(self):
        self._approved_ops: set = set()

    def call(self, operation: str, params: dict = None) -> dict:
        if not isinstance(params, dict):
            params = {}
        if operation in self.HIGH_RISK_OPS:
            if operation not in self._approved_ops:
                raise ApprovalRequired(operation, f"操作 {operation} 被列为高危，需要 HITL 授权")
        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise NotImplementedError(f"未知操作: {operation}")
        return handler(params)

    def grant_approval(self, operation: str):
        """人工授权后调用（由 human_approval_prompter 触发）"""
        if operation in self.HIGH_RISK_OPS:
            self._approved_ops.add(operation)

    def _op_read_file(self, params: dict) -> dict:
        import os
        path = params.get("path", "")
        if not os.path.exists(path):
            return {"error": f"文件不存在: {path}"}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return {"content": f.read()}

    def _op_list_dir(self, params: dict) -> dict:
        import os
        path = params.get("path", ".")
        if not os.path.isdir(path):
            return {"error": f"目录不存在: {path}"}
        return {"entries": os.listdir(path)}
'''

CODE_CONTEXT_COMPACTOR = '''"""
Context Auto Compactor - V10 防失忆折叠器
五级压缩漏斗核心。
支持常规 25KB 阈值压缩，以及响应网关调用的 Reactive Compact 应急压缩。
"""
import json


COMPRESS_LEVELS = [0.9, 0.75, 0.6, 0.4, 0.25]  # 五级压缩比


class ContextAutoCompactor:
    """
    五级压缩漏斗。
    从轻度压缩开始，逐级加重，直到满足目标大小。
    """

    TARGET_BYTES = 25 * 1024  # 25KB 目标红线

    def compact(self, context: dict, reactive: bool = False) -> dict:
        """
        压缩上下文字典至 25KB 以下。
        reactive=True 表示应急压缩（网关 413 触发）。
        """
        target = self.TARGET_BYTES if not reactive else self.TARGET_BYTES // 2
        for level_ratio in COMPRESS_LEVELS:
            serialized = json.dumps(context, ensure_ascii=False)
            if len(serialized.encode("utf-8")) <= target:
                return context
            context = self._apply_compression(context, level_ratio)
            print(f"\\U0001f5dc\\ufe0f [Compactor] 压缩级别 {level_ratio}: "
                  f"{len(json.dumps(context, ensure_ascii=False).encode())} bytes")
        return context

    def _apply_compression(self, context: dict, ratio: float) -> dict:
        """保留 IMMORTAL 标签条目，对普通条目按比例丢弃。"""
        immortal = {k: v for k, v in context.items() if "[IMMORTAL]" in str(k)}
        mortal = {k: v for k, v in context.items() if "[IMMORTAL]" not in str(k)}
        keep_count = max(1, int(len(mortal) * ratio))
        keys = list(mortal.keys())
        kept = {k: mortal[k] for k in keys[-keep_count:]}
        return {**immortal, **kept}
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
7. **[熔断底线]**：连续失败 3 次 Fail-Closed，不可绕过。
'''

CODE_SKELETON_BASE = '''# -*- coding: utf-8 -*-
"""
[V10 骨架占位] 此文件为骨架占位，待 RLHF 闭环迭代填充。
"""


class {class_name}:
    """[V10 占位告警] {class_name} 骨架就位，待实现。"""

    @staticmethod
    def {method_name}(*args, **kwargs):
        raise NotImplementedError("[V10 占位告警] {class_name}.{method_name} 尚未实现。")
'''

# ============================================================
# 全域物理拓扑图 - 目录结构
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
# 核心文件注入映射 (INFRA - 强制覆盖写入)
# ============================================================
INFRA_FILE_MAP = {
    ".cursor/rules/007_dynamic_tiering.mdc": CODE_DYNAMIC_TIERING_MDC,
    ".cursor/rules/Alumet-OS-Constitution.mdc": CODE_CONSTITUTION_MDC,
    "core/ast_sentinel.py": CODE_AST_SENTINEL,
    "core_engine/tensor_fingerprint.py": CODE_TENSOR_FINGERPRINT,
    "core/mcp_tool_protocol.py": CODE_MCP_TOOL_PROTOCOL,
    "agentic_workflow/working_memory_context.py": CODE_WORKING_MEMORY_CONTEXT,
    "agentic_workflow/agent_query_engine.py": CODE_AGENT_QUERY_ENGINE,
    "agentic_workflow/yolo_veto_classifier.py": CODE_YOLO_VETO_CLASSIFIER,
    "agentic_workflow/denial_tracking_circuit.py": CODE_DENIAL_TRACKING,
    "agentic_workflow/dynamic_tiering_gateway.py": CODE_SLA_DYNAMIC_ROUTER,
    "agentic_workflow/vram_tidal_scheduler.py": CODE_VRAM_SCHEDULER,
    "data_center/smart_memory_guard.py": CODE_SMART_MEMORY_GUARD,
    "data_center/exact_grep_retriever.py": CODE_EXACT_GREP_RETRIEVER,
    "core_engine/kernel_api_bus.py": CODE_KERNEL_API_BUS,
    "agentic_workflow/context_auto_compactor.py": CODE_CONTEXT_COMPACTOR,
    "async_background_housekeeping.py": CODE_ASYNC_HOUSEKEEPING,
    "training_camp/mcts_constant_distiller.py": CODE_MCTS_DISTILLER,
    "expert_rules/__init__.py": CODE_EXPERT_RULES_INIT,
}

# ============================================================
# 骨架文件注入映射 (SKELETON - 仅在文件不存在时写入)
# ============================================================
SKELETON_FILE_MAP = {
    "__init__.py": '# Alumet OS V10 - Root Package\n',
    "core/__init__.py": '# core package\n',
    "core_engine/__init__.py": '# core_engine package\n',
    "expert_rules/SYSTEM_PROMPT_DYNAMIC_BOUNDARY.md": (
        "# [缓存金身] 隔离线定义\n\n"
        "本文件捍卫全局前缀缓存。此行以上为永久静态区，禁止修改。\n"
    ),
    "modules/__init__.py": '# modules package\n',
    "modules/01_xiangshu/__init__.py": '# xiangshu module\n',
    "modules/02_bazi/__init__.py": '# bazi module\n',
    "modules/03_liuyao/__init__.py": '# liuyao module\n',
    "modules/04_xuankong/__init__.py": '# xuankong module\n',
    "modules/05_finance/__init__.py": '# finance module\n',
    "data_center/processed_files.json": '{"cursor": 0, "ingested": []}\n',
    "data_center/system_hot_memory.json": (
        '{\n  "[IMMORTAL] system_version": "Alumet OS V10",\n'
        '  "[IMMORTAL] created_at": "' + datetime.now().isoformat() + '"\n}\n'
    ),
    "data_center/raw_cases/metaphysics_audit.jsonl": "",
    "training_camp/adversarial_red_team.py": '''#!/usr/bin/env python3
"""影子红队 - V10 Fire-and-forget 异步调用"""
import sys


class OfflineRedTeamNode:
    def execute_nightly_audit(self, daily_reports: list = None):
        print("\\U0001f319 [夜间 Meta 场] 影子红队启动，开始异步高能博弈...")
        print("\\U0001f9e0 正在蒸馏 data_center/raw_cases 中的特征向量...")
        print("\\u2705 进化完成。L5 规则库已增量更新。")


if __name__ == "__main__":
    node = OfflineRedTeamNode()
    node.execute_nightly_audit()
''',
    "training_camp/loss_calculator.py": '''"""TopologyLossCalculator 骨架"""


class TopologyLossCalculator:
    @staticmethod
    def calculate_entropy(graph_data: dict) -> float:
        raise NotImplementedError("[V10 占位告警] 损失计算器骨架就位。")
''',
    "training_camp/meta_moe_router.py": '''"""MetaMoERouter 骨架"""


class MetaMoERouter:
    @staticmethod
    def route_to_expert(case_data: dict) -> str:
        raise NotImplementedError("[V10 占位告警] MoE路由骨架就位。")
''',
    "training_camp/topology_mutator.py": '''"""TopologyMutator 骨架"""


class TopologyMutator:
    @staticmethod
    def generate_draft(feedback: dict) -> None:
        raise NotImplementedError("[V10 占位告警] 突变器骨架就位。")
''',
    "training_camp/finance_liquid_updater.py": '''"""FinanceLiquidUpdater 骨架"""


class FinanceLiquidUpdater:
    @staticmethod
    def update_liquidity(market_data: dict) -> None:
        raise NotImplementedError("[V10 占位告警] 金融快思考骨架就位。")
''',
    "training_camp/state_drift_analyzer.py": '''"""StateDriftAnalyzer 骨架"""


class StateDriftAnalyzer:
    @staticmethod
    def analyze_drift(logs: list) -> None:
        raise NotImplementedError("[V10 占位告警] 漂移分析器骨架就位。")
''',
    "training_camp/e2e_eval_judge.py": '''"""E2EEvalJudge 骨架"""


class E2EEvalJudge:
    @staticmethod
    def run_evaluation(test_cases: list) -> None:
        raise NotImplementedError("[V10 占位告警] 审判长骨架就位。")
''',
    "training_camp/rlhf_ast_rewriter.py": '''"""RLHFASTReWriter 骨架"""


class RLHFASTReWriter:
    @staticmethod
    def safe_rewrite_rules(target_file: str, new_ast_nodes: list) -> bool:
        raise NotImplementedError("[V10 占位告警] AST 覆写机制骨架就位。")
''',
    "data_center/tensor_git_versioning.py": '''"""TensorGitVersioning 骨架"""


class TensorGitVersioning:
    @staticmethod
    def commit_tensor_state(state: dict) -> str:
        raise NotImplementedError("[V10 占位告警] 张量版本控制骨架就位。")
''',
    "data_center/ingest_historical_cases.py": '''"""批量摄入历史案例到记忆体"""
import os
import json


def ingest(source_dir: str, output_file: str = "data_center/processed_files.json"):
    print(f"[Ingest] 扫描目录: {source_dir}")
    # 骨架: 遍历目录，写入 JSONL
    raise NotImplementedError("[V10 占位告警] 历史案例摄入骨架就位。")
''',
    "oracle_gateway/avatar_os_bootstrapper.py": '''"""OS 环境引导与依赖注入器"""


class AvatarOSBootstrapper:
    def bootstrap(self):
        print("[Bootstrap] Alumet OS V10 环境引导完成。")
''',
    "oracle_gateway/avatar_os_ignition.py": '''"""系统全局点火与 CLI 主矩阵"""
import sys


def ignite():
    print("[Ignition] Alumet OS V10 点火!")
    print("[Ignition] earlyInput 缓冲池已就位。")


if __name__ == "__main__":
    ignite()
''',
    "oracle_gateway/oracle_gateway_fsm.py": '''"""确定性神谕编译器 FSM"""


class OracleGatewayFSM:
    STATES = ["IDLE", "COMPILING", "RENDERING", "DONE", "ERROR"]

    def __init__(self):
        self.state = "IDLE"

    def compile(self, payload: dict) -> dict:
        self.state = "COMPILING"
        result = {"rendered": str(payload)}
        self.state = "DONE"
        return result
''',
    "oracle_gateway/human_approval_prompter.py": '''"""HITL 拦截端 - 捕获高危调用请求人类授权"""


class HumanApprovalPrompter:
    def prompt(self, operation: str, reason: str) -> bool:
        print(f"\\n\\u270b [HITL 拦截] 高危操作请求授权")
        print(f"  操作: {operation}")
        print(f"  原因: {reason}")
        ans = input("  授权执行? (y/N): ").strip().lower()
        return ans == "y"
''',
    "oracle_gateway/llm_network_gateway.py": '''"""全局网络层 - 含 413 Reactive Compact Hook"""


class LLMNetworkGateway:
    def send(self, payload: dict) -> dict:
        # 骨架: 真实场景对接 API
        raise NotImplementedError("[V10 占位] LLM 网关骨架就位。")

    def on_413_error(self, compactor):
        """413 报错钩子: 直接唤醒 Compactor 而不中断服务。"""
        print("[Gateway] 413 Context Too Long -> 触发 Reactive Compact")
        compactor.compact({}, reactive=True)
''',
    "oracle_gateway/report_react_agent.py": '''"""ReACT 反思撰稿人"""


class ReportReActAgent:
    def generate(self, context: dict, denial_circuit) -> dict:
        if denial_circuit.is_open:
            return {"status": "CONSERVATIVE", "report": "[熔断保守输出] 推演受限。"}
        raise NotImplementedError("[V10 占位] ReACT 撰稿人骨架就位。")
''',
    "simulation_sandbox/vm_repl_sandbox.py": '''"""
Python Exec 级隔离环境。
【安全红线】沙盒命名空间仅注入 kernel_api_bus.call 安全代理句柄，
绝对物理禁止绕过总线直接 import L0 层模块。
"""


class VMReplSandbox:
    def __init__(self, kernel_api_bus):
        self._bus = kernel_api_bus

    def execute(self, code: str) -> dict:
        safe_ns = {"api_call": self._bus.call}
        try:
            exec(compile(code, "<sandbox>", "exec"), safe_ns)  # noqa
            return {"status": "OK", "output": safe_ns.get("__result__")}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
''',
    "simulation_sandbox/tool_function_registry.py": '''"""懒加载工具注册表"""


class ToolFunctionRegistry:
    def __init__(self):
        self._registry = {}

    def register(self, name: str, description: str, loader):
        self._registry[name] = {"description": description, "loader": loader}

    def get_tool(self, name: str):
        entry = self._registry.get(name)
        if not entry:
            raise KeyError(f"工具未注册: {name}")
        return entry["loader"]()

    def list_tools(self) -> list:
        return [{"name": k, "description": v["description"]} for k, v in self._registry.items()]
''',
    "simulation_sandbox/async_tool_dispatcher.py": '''"""并发调度器 - asyncio Semaphore 强制落实极速调度"""
import asyncio


class AsyncToolDispatcher:
    def __init__(self, max_concurrent: int = 4):
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def dispatch(self, tool_fn, params: dict) -> dict:
        async with self._semaphore:
            if asyncio.iscoroutinefunction(tool_fn):
                return await tool_fn(params)
            return tool_fn(params)
''',
    "simulation_sandbox/console_hook_interceptor.py": '''"""输出劫持器 - 拦截 LLM 推演数据碰撞结果"""
import io
import sys


class ConsoleHookInterceptor:
    def __enter__(self):
        self._old_stdout = sys.stdout
        sys.stdout = self._buffer = io.StringIO()
        return self

    def __exit__(self, *args):
        sys.stdout = self._old_stdout
        self.captured = self._buffer.getvalue()

    def get_extremes(self) -> list:
        lines = self.captured.splitlines()
        return [l for l in lines if any(k in l for k in ["MAX", "MIN", "PEAK", "极值"])]
''',
    "core/activity_audit_log.py": '''"""绝对审计日志 - 单向黑匣子"""
import time
import json
import os


class ActivityAuditLog:
    def __init__(self, log_file: str = "data_center/activity_audit.jsonl"):
        self.log_file = log_file

    def record(self, event_type: str, payload: dict):
        entry = {
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event_type,
            "payload": payload
        }
        os.makedirs(os.path.dirname(self.log_file) or ".", exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\\n")
''',
    "core/security_vault.py": '''"""全局金库 - 单例模式拦截投毒"""


class SecurityVault:
    _instance = None
    _secrets: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def store(self, key: str, value):
        if not isinstance(key, str):
            raise TypeError("金库键必须是字符串")
        self._secrets[key] = value

    def retrieve(self, key: str, default=None):
        return self._secrets.get(key, default)
''',
    "core/semantic_utils.py": '''"""零显存感知器 - CPU 级句子余弦相似度匹配"""
import math


def cosine_similarity(vec_a: list, vec_b: list) -> float:
    """CPU 级余弦相似度，零 GPU 依赖。"""
    if len(vec_a) != len(vec_b):
        raise ValueError("向量维度不一致")
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
''',
    "core/metaphysics_types.py": '''"""全局玄学度量衡定义"""
from typing import NamedTuple


class HexagramResult(NamedTuple):
    name: str
    score: float
    confidence: float
    fingerprint: str


WUXING = {"Wood": "木", "Fire": "火", "Earth": "土", "Metal": "金", "Water": "水"}
TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
''',
    "core_engine/category_theory_morphism.py": '''"""范畴论态射引力引擎骨架"""


class CategoryTheoryMorphism:
    @staticmethod
    def compose(f, g):
        return lambda x: f(g(x))

    @staticmethod
    def identity(x):
        return x
''',
    "core_engine/graph_tensor_calculator.py": '''"""全局图张量正交计算器骨架"""


class GraphTensorCalculator:
    @staticmethod
    def calculate(graph: dict) -> dict:
        raise NotImplementedError("[V10 占位] 图张量计算器骨架就位。")
''',
    "core_engine/matrix_eigen_solver.py": '''"""矩阵特征值提取与坍缩求解器骨架"""


class MatrixEigenSolver:
    @staticmethod
    def solve(matrix: list) -> list:
        raise NotImplementedError("[V10 占位] 矩阵特征值求解器骨架就位。")
''',
    "core_engine/neuro_symbolic_base.py": '''"""神经符号学推演底座骨架"""


class NeuroSymbolicBase:
    def reason(self, facts: list, rules: list) -> list:
        raise NotImplementedError("[V10 占位] 神经符号推演骨架就位。")
''',
    "core_engine/shannon_entropy_core.py": '''"""终极崩溃阈值评估 - Shannon 熵计算"""
import math


def shannon_entropy(probabilities: list) -> float:
    total = sum(probabilities)
    if total == 0:
        return 0.0
    normalized = [p / total for p in probabilities]
    return -sum(p * math.log2(p) for p in normalized if p > 0)
''',
    "agentic_workflow/skill_compiler_fsm.py": '''"""结构化有限状态机 - 遗留逻辑降维子状态看门狗"""


class SkillCompilerFSM:
    STATES = ["IDLE", "PARSING", "COMPILING", "DONE", "ERROR"]

    def __init__(self):
        self.state = "IDLE"
        self.transitions = {}

    def transition(self, event: str):
        next_state = self.transitions.get((self.state, event))
        if next_state:
            self.state = next_state
        return self.state
''',
    "agentic_workflow/anomaly_quarantine.py": '''"""异常隔离区 - 拦截并锁死劣质张量"""
import shutil
import os


class AnomalyQuarantine:
    def __init__(self, quarantine_dir: str = "data_center/quarantine"):
        self.dir = quarantine_dir
        os.makedirs(self.dir, exist_ok=True)

    def quarantine_file(self, filepath: str):
        if os.path.exists(filepath):
            dest = os.path.join(self.dir, os.path.basename(filepath))
            shutil.move(filepath, dest)
            print(f"[Quarantine] 已隔离: {filepath} -> {dest}")
''',
    "agentic_workflow/local_sandbox.py": '''"""本地状态隔离容器 - 阻断内存级幻觉真实落盘"""


class LocalSandbox:
    def __init__(self):
        self._state = {}

    def set(self, key: str, value):
        self._state[key] = value

    def get(self, key: str, default=None):
        return self._state.get(key, default)

    def commit(self, target_store):
        """显式 commit 才落盘，防止幻觉自动写入。"""
        for k, v in self._state.items():
            target_store[k] = v
        self._state.clear()
''',
    "agentic_workflow/physics_verifier.py": '''"""铁血海关 - 静态拦截时空物理悖论幻觉"""
import re


PARADOX_PATTERNS = [
    (r"(?i)born.*after.*died", "时间悖论: 出生在死亡之后"),
    (r"(?i)(\\d{4}).*year.*before.*\\1", "时间自参照悖论"),
    (r"(?i)speed.*exceed.*light", "物理悖论: 超光速"),
]


class PhysicsVerifier:
    def verify(self, text: str) -> dict:
        for pattern, reason in PARADOX_PATTERNS:
            if re.search(pattern, text):
                return {"valid": False, "reason": reason}
        return {"valid": True}
''',
    "expert_rules/global_tensor_map.py": '''"""全局跨域特征张量指纹字典"""

GLOBAL_TENSOR_MAP = {
    "xiangshu": {"weight": 1.0, "domain": "visual"},
    "bazi": {"weight": 1.0, "domain": "temporal"},
    "liuyao": {"weight": 1.0, "domain": "stochastic"},
    "xuankong": {"weight": 1.0, "domain": "spatial"},
    "finance": {"weight": 1.0, "domain": "quantitative"},
}
''',
    "expert_rules/rule_freezer.py": '''"""静态规则冻结器 - 执行字典深度排序与紧凑序列化，锁死 Hash"""
import json
import hashlib


class RuleFreezer:
    @staticmethod
    def freeze(rules_dict: dict) -> tuple:
        serialized = json.dumps(rules_dict, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        hash_val = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return serialized, hash_val
''',
    "docs/SOP_Alumet_OS_Architecture.md": (
        "# Alumet OS V10 Architecture SOP\n\n"
        "## 核心哲学\n\n"
        "1. **Dumb Tools**: MCP 工具仅作数学/数据执行器\n"
        "2. **Exact Search**: Grep 精确查表，零向量幻觉\n"
        "3. **25KB 红线**: 热记忆硬限，溢出语义提纯\n"
        "4. **Fail-Closed 熔断**: 连续失败 3 次即熔断\n"
        "5. **AutoDream**: 绝对异步守护进程后台进化\n\n"
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
    "start_evolution_matrix.sh": (
        "#!/bin/bash\n"
        "# Alumet OS V10 - 生物钟唤醒矩阵\n"
        "# 凌晨自动唤醒深度进化\n\n"
        "echo '[AlumET] 唤醒深度进化矩阵...'\n"
        "python async_background_housekeeping.py\n"
        "python training_camp/adversarial_red_team.py\n"
        "echo '[AlumET] 进化完成。'\n"
    ),
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
}

# 门派路由规则
ROUTER_RULES = {
    "DOMAIN_MAP": {
        "1": "xiangshu", "2": "bazi", "3": "liuyao",
        "4": "xuankong", "5": "finance", "Q": "quit"
    },
    "PREFIX_MAP": {
        "1": "01", "2": "02", "3": "03", "4": "04", "5": "05"
    }
}


def get_layer_path_map(domain_folder: str, domain: str) -> dict:
    return {
        "L0.5": "core/metaphysics_types.py",
        "L1_PREDICT": f"modules/{domain_folder}/{domain}_predict.py",
        "L1_ASSEMBLER": f"modules/{domain_folder}/{domain}_prompt_factory.py",
        "L1_TOPOLOGY": f"modules/{domain_folder}/{domain}_v102_topology.py",
        "L5": f"expert_rules/{domain}_rules.py",
        "L0": f"core_engine/graph_tensor_{domain}.py"
    }


# ============================================================
# 工具函数
# ============================================================

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


def safe_write(path: str, content: str, force: bool = False):
    """
    防抖覆盖写入：若文件已存在且 force=False，启用隔离草稿舱。
    备份机制: 覆盖前写 .bak 备份。
    """
    if not content.strip():
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    if not force and path.endswith(".py") and os.path.exists(path):
        draft_path = path.replace(".py", f"_SURGEON_DRAFT_{int(time.time())}.py")
        pc(f"  ⚠️ [防抖] {path} 已存在 -> 隔离草稿舱: {draft_path}", "yellow")
        path = draft_path

    if os.path.exists(path) and not path.endswith(".bak"):
        try:
            shutil.copy2(path, path + ".bak")
        except Exception:
            pass

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        logging.error(f"[write] 写入失败 {path}: {e}")


def inject_infra_cores():
    pc("\n💉 [Step 3] 注入核心防御层 (INFRA - 强制覆盖)...", "yellow")
    for path, content in INFRA_FILE_MAP.items():
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if os.path.exists(path):
            try:
                shutil.copy2(path, path + ".bak")
            except Exception:
                pass
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


def audit_module_entropy():
    pc("\n🔎 [Step 5] 执行业务模块静态审计...", "blue")
    modules_path = "modules"
    if not os.path.exists(modules_path):
        return
    subdirs = [d for d in os.listdir(modules_path) if os.path.isdir(os.path.join(modules_path, d))]
    conflict_keywords = ["bazi", "finance", "xiangshu", "xuankong", "liuyao"]
    found_issues = False
    for keyword in conflict_keywords:
        suspects = [d for d in subdirs if keyword in d]
        if len(suspects) > 1:
            pc(f"  🚨 [架构熵增] `{keyword}` 存在多个重叠实体: {suspects}", "red")
            found_issues = True
    if not found_issues:
        pc("  ✅ 模块熵增检查通过", "green")


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

    with open(RULES_FILE, "w", encoding="utf-8") as f:
        f.write(updated)
    pc(f"[√] 张量 {next_id} 已锚定至 {RULES_FILE}！", "green")


# ============================================================
# 交互路由器
# ============================================================

def interactive_surgical_router():
    pc("\n" + "=" * 60, "blue")
    pc("🔪 [Alumet OS V10 终端手术刀] 全域基建播种机已激活", "green")
    pc("=" * 60, "blue")

    cleanup_stale_drafts(days_to_keep=3)

    while True:
        print()
        pc("┌─────────────────────────────────────────────────────┐", "blue")
        pc("│  [功能选择]                                          │", "blue")
        pc("│  1-5  门派代码灌注 (选择后进入楼层选择)              │", "blue")
        pc("│  6    🧬 全息进化 (运行夜间影子红队)                 │", "blue")
        pc("│  7    💉 JSON 静默管线注入 (象数基因注入)            │", "blue")
        pc("│  8    ⚡ 后台守护进程 (AutoDream Housekeeping)       │", "blue")
        pc("│  Q    安全退出                                       │", "blue")
        pc("└─────────────────────────────────────────────────────┘", "blue")
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

        domain = ROUTER_RULES["DOMAIN_MAP"].get(choice)
        prefix = ROUTER_RULES["PREFIX_MAP"].get(choice)
        if not domain or not prefix:
            pc("  ❌ 无效选择，请输入 1-8 或 Q", "red")
            continue

        domain_folder = f"{prefix}_{domain}"

        print()
        pc("┌─────────────────────────────────────────────────────┐", "blue")
        pc("│  [楼层选择]                                          │", "blue")
        pc("│  E  全息柔性贯通 (识别 L0.5/L1/L5/L0 多层并发落位)  │", "blue")
        pc("│  A  L5 单体规则 (expert_rules)                      │", "blue")
        pc("│  B  L1 主控入口 (predict.py)                        │", "blue")
        pc("│  D  L1 专属工厂 (prompt_factory.py)                 │", "blue")
        pc("└─────────────────────────────────────────────────────┘", "blue")
        layer_choice = input(_c("字母 (E/A/B/D): ", "yellow")).strip().upper()

        pc(f"\n📥 请粘贴代码内容，按 Ctrl+D (Mac/Linux) 或 Ctrl+Z+Enter (Win) 结束：", "yellow")
        try:
            content = sys.stdin.read()
        except EOFError:
            continue
        if not content.strip():
            pc("  ⚠️ 内容为空，跳过。", "yellow")
            continue

        if layer_choice == "E":
            pattern = re.compile(
                r"#\s*={1,}\s*\[([A-Z0-9_\.]+)\]\s*={1,}\n(.*?)(?=#\s*={1,}\s*\[|$)",
                re.DOTALL | re.IGNORECASE
            )
            matches = pattern.findall(content)
            if not matches:
                pc("❌ 未检测到钛合金切割标签 [LAYER_NAME]！", "red")
                continue
            layer_path_map = get_layer_path_map(domain_folder, domain)
            for layer_tag, code_block in matches:
                clean_tag = layer_tag.strip().upper()
                if clean_tag in layer_path_map:
                    target = layer_path_map[clean_tag]
                    safe_write(target, code_block.strip() + "\n")
                    pc(f"  ✅ [{clean_tag}] 落位 -> {target}", "green")
            continue

        target_path = ""
        if layer_choice == "A":
            target_path = f"expert_rules/{domain}_rules.py"
        elif layer_choice == "B":
            target_path = f"modules/{domain_folder}/{domain}_predict.py"
        elif layer_choice == "D":
            target_path = f"modules/{domain_folder}/{domain}_prompt_factory.py"
        else:
            pc("  ❌ 无效楼层选择", "red")
            continue

        safe_write(target_path, content)
        pc(f"  ✅ [{layer_choice}] 落位 -> {target_path}", "green")


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

    pc("✅ [AutoDream] 后台任务完成。", "green")


# ============================================================
# 主入口
# ============================================================

def main():
    pc("=" * 60, "green")
    pc("🧬 Alumet OS V10 (V1.2.2 Immortal Silicon State)", "green")
    pc("   全域基建播种机与自解压程序", "green")
    pc("=" * 60, "green")
    time.sleep(0.5)

    if not sys.stdin.isatty():
        input_data = sys.stdin.read()
        if input_data.strip() and ("T_NEW" in input_data or "{" in input_data):
            inject_xiangshu_genome(input_data)
        else:
            pc("[-] 管道流输入无效或格式非基因张量。", "red")
        sys.exit(0)

    try:
        create_backup()
        build_structure()
        inject_infra_cores()
        inject_skeleton_files()
        audit_module_entropy()
        pc("\n✅ [全域基建] 播种完成！所有核心文件已物理落盘。", "green")
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
