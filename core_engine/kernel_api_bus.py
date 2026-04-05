"""
core_engine/kernel_api_bus.py
-------------------------------
Alumet OS — Fail-Closed 系统调用总线与人工防线（Ring 0 内核保护区）

核心使命：
  作为 L0 底层与所有上层模块（特别是沙盒 VmReplSandbox）之间的唯一通信管道，
  彻底切断门派模块的自主权，将所有系统调用纳入内核审计与权限控制之下。

架构地位：
  VmReplSandbox                    （L3 用户态沙盒）
       │ kernel_call(tool_name, **kwargs)
       ▼
  KernelApiBus.call()              （L1 内核 API 总线 ← 本模块）
       │ 权限路由 → HITL 拦截 → 工具注册表查找 → 审计日志
       ▼
  BaseTool.execute()               （L2 工具实现层）

  任何试图绕过 KernelApiBus 直接调用 BaseTool 的代码，
  即视为"内核旁路攻击"，应在代码审查阶段被拒绝合并。

HITL（Human-In-The-Loop）拦截机制：
  当检测到以下高危写操作时，绝对拒绝自动执行：
    - 试图修改 L5 常数规则（核心约束参数）
    - 试图删除核心资产（模型权重、主配置文件、审计日志等）
    - 试图更改内核路由规则（权限矩阵本身）
    - 试图访问 HITL 豁免名单（自我授权）

  拦截后抛出 ApprovalRequiredException，携带完整的操作描述与风险评级，
  由上层 human_approval_prompter 捕获并挂起任务，等待人类 Y/N 授权。

Fail-Closed 语义：
  当内核总线遭遇任何未预期错误时，默认拒绝（Closed），而非默认放行（Open）。
  宁可让合法的工具调用失败，也不允许让危险的操作在不确定状态下通过。
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 权限等级枚举
# ---------------------------------------------------------------------------

class PermissionLevel(Enum):
    """
    内核权限等级，从低到高排列。

    等级设计原则（Ring 模型）：
      SAFE    → 只读、幂等、无副作用，任何调用方均可发起
      TRUSTED → 有限写操作，需要已注册的受信任调用方身份
      KERNEL  → 修改内核状态，必须经过 HITL 人工确认
      DENIED  → 永久禁止，无论何种身份均不得执行
    """
    SAFE = 0       # 只读操作（查询、读取、列举）
    TRUSTED = 1    # 受信任写操作（创建、更新非核心资源）
    KERNEL = 2     # 内核级操作（修改系统配置、权限规则）→ 触发 HITL
    DENIED = 3     # 永久封禁（高危操作，永不自动执行）


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------

class KernelBusError(Exception):
    """内核总线基础异常，所有内核相关异常的父类。"""


class ApprovalRequiredException(KernelBusError):
    """
    HITL 人工确认等待异常。

    当工具调用触发 HITL 拦截时抛出此异常。
    上层 human_approval_prompter 必须捕获此异常，
    向操作人员展示 operation_description 与 risk_level，
    等待 Y/N 确认后决定是否继续执行。

    设计意图：
      此异常携带足够的信息让人类做出明智决策：
        - 操作描述：做什么？
        - 风险等级：有多危险？
        - 受影响资源：影响什么？
        - 申请方身份：谁发起的？
      人类批准后，审批令牌（approval_token）可传回总线执行。
    """

    def __init__(
        self,
        operation: str,
        tool_name: str,
        risk_level: PermissionLevel,
        affected_resources: list[str],
        requester_id: str,
    ) -> None:
        self.operation = operation
        self.tool_name = tool_name
        self.risk_level = risk_level
        self.affected_resources = affected_resources
        self.requester_id = requester_id
        self.approval_token = _generate_approval_token(tool_name, requester_id)

        super().__init__(
            f"[HITL 拦截] 工具 '{tool_name}' 请求执行高危操作，需要人工授权。\n"
            f"  操作描述：{operation}\n"
            f"  风险等级：{risk_level.name}\n"
            f"  受影响资源：{affected_resources}\n"
            f"  申请方：{requester_id}\n"
            f"  审批令牌：{self.approval_token}\n"
            "  请调用 human_approval_prompter 将此异常提交人工审批。"
        )


class PermissionDeniedException(KernelBusError):
    """永久权限拒绝异常（DENIED 级别操作，无法通过 HITL 解锁）。"""


class ToolNotRegisteredException(KernelBusError):
    """工具未在内核总线注册（可能是旁路攻击尝试）。"""


# ---------------------------------------------------------------------------
# 审计日志条目
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """
    内核审计日志的单条记录。

    内核总线的每一次 call() 调用都产生一条审计条目，无论成功还是失败。
    审计日志是事后追溯与合规审查的核心数据，必须不可篡改地持久化。
    （本实现为内存审计，生产环境应对接 append-only 存储后端。）
    """

    timestamp: float
    requester_id: str
    tool_name: str
    kwargs_summary: str   # 参数摘要（不存储完整参数，防止密钥泄漏）
    permission_level: PermissionLevel
    outcome: str          # "success" | "hitl_blocked" | "denied" | "error"
    error_detail: str = ""


# ---------------------------------------------------------------------------
# 高危操作特征规则（HITL 路由规则表）
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HitlRule:
    """
    单条 HITL 拦截规则。

    匹配逻辑：
      工具名与 tool_name_prefix 匹配，且调用参数中存在任一 dangerous_arg_keywords，
      则触发此规则，将调用升级为 HITL 拦截或永久拒绝。
    """
    tool_name_prefix: str           # 工具名前缀匹配（如 "delete_"、"modify_kernel_"）
    dangerous_arg_keywords: tuple[str, ...]  # 参数值中的危险关键词
    required_level: PermissionLevel  # 触发后映射到的权限等级
    description: str                 # 人类可读的风险描述


# 内核 HITL 路由规则表（静态定义，不可在运行时动态修改）
# 规则匹配顺序：从上到下，首次命中即生效，不继续匹配后续规则。
_HITL_RULES: list[HitlRule] = [
    # 规则 R1：修改 L5 常数规则（核心约束参数）
    HitlRule(
        tool_name_prefix="modify_",
        dangerous_arg_keywords=("l5_constant", "hard_limit", "kernel_rule", "permission_matrix"),
        required_level=PermissionLevel.KERNEL,
        description="试图修改 L5 常数规则或内核权限矩阵，此操作将影响所有 Agent 的行为边界",
    ),
    # 规则 R2：删除核心资产（模型权重、主配置、审计日志）
    HitlRule(
        tool_name_prefix="delete_",
        dangerous_arg_keywords=("model_weights", "core_config", "audit_log", "master_key", ".env"),
        required_level=PermissionLevel.DENIED,
        description="试图删除核心资产（模型权重/配置/审计日志/密钥），此操作永久禁止自动执行",
    ),
    # 规则 R3：修改核心资产
    HitlRule(
        tool_name_prefix="write_",
        dangerous_arg_keywords=("core_config", "kernel_route", "hitl_whitelist", "master_key"),
        required_level=PermissionLevel.KERNEL,
        description="试图修改内核路由规则或 HITL 豁免名单，需要人工确认",
    ),
    # 规则 R4：自我授权（试图访问 HITL 豁免名单，实现自我解锁）
    HitlRule(
        tool_name_prefix="",  # 匹配所有工具名
        dangerous_arg_keywords=("hitl_bypass", "approval_whitelist", "self_approve"),
        required_level=PermissionLevel.DENIED,
        description="检测到自我授权尝试（试图绕过 HITL 机制），永久拒绝",
    ),
    # 规则 R5：进程/系统级操作
    HitlRule(
        tool_name_prefix="exec_",
        dangerous_arg_keywords=("shell", "subprocess", "os_command", "system"),
        required_level=PermissionLevel.DENIED,
        description="试图通过工具执行系统 shell 命令，永久拒绝（应通过沙盒执行路径）",
    ),
]


# ---------------------------------------------------------------------------
# 内核 API 总线主体
# ---------------------------------------------------------------------------

class KernelApiBus:
    """
    Alumet OS 内核 API 总线（Ring 0 保护区）。

    所有来自沙盒、Agent 引擎、插件系统的工具调用，
    必须且只能通过本类的 call() 方法进入内核执行层。

    核心职责：
      1. 身份识别：从调用上下文中提取申请方 ID
      2. 权限路由：按 HITL 规则表评估所需权限级别
      3. HITL 拦截：KERNEL 级别抛出 ApprovalRequiredException
      4. 永久拒绝：DENIED 级别抛出 PermissionDeniedException
      5. 工具分发：通过注册的执行器分发工具调用
      6. 审计记录：每次调用产生不可篡改的审计条目
      7. Fail-Closed：所有未预期错误均以拒绝方式处理
    """

    def __init__(self) -> None:
        # 工具执行器注册表：tool_name → callable(tool_name, kwargs) → Any
        # 通过注册机制隔离执行层，总线本身不持有工具实现，防止直接引用泄漏
        self._executors: dict[str, Any] = {}

        # 不可变审计日志（内存版本，生产环境需对接 append-only 后端）
        self._audit_log: list[AuditEntry] = []

        # 已批准的 HITL 审批令牌集合（令牌使用后立即作废，防止重放攻击）
        self._approved_tokens: set[str] = set()

    # ------------------------------------------------------------------
    # 工具执行器注册接口
    # ------------------------------------------------------------------

    def register_executor(
        self,
        tool_name: str,
        executor: Any,
        *,
        overwrite: bool = False,
    ) -> None:
        """
        向内核总线注册工具执行器。

        设计原则：
          - 执行器在进程启动阶段集中注册，运行时禁止动态注册（防止注入攻击）。
          - 若 tool_name 已被注册且 overwrite=False，抛出 ValueError 阻断。
          - 沙盒代码通过 KernelApiProxy → KernelApiBus 调用，
            始终无法直接访问此注册接口（沙盒的命名空间真空化已封死）。
        """
        if tool_name in self._executors and not overwrite:
            raise ValueError(
                f"[注册冲突] 工具 '{tool_name}' 已在内核总线注册。"
                "若确需覆盖，请显式传入 overwrite=True 并记录变更原因。"
            )
        self._executors[tool_name] = executor
        logger.info("[内核注册] 工具 '%s' 已注册到内核总线。", tool_name)

    # ------------------------------------------------------------------
    # 核心系统调用接口（沙盒的唯一句柄）
    # ------------------------------------------------------------------

    def call(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        *,
        requester_id: str = "anonymous",
        approval_token: str | None = None,
    ) -> Any:
        """
        内核系统调用入口——沙盒与所有上层模块的唯一合法通信管道。

        调用流程（严格顺序，不可跳过）：
          Step 1：工具名合法性验证（防注入）
          Step 2：HITL 权限路由评估
          Step 3：KERNEL 级别 → 检查审批令牌，无令牌则抛出 ApprovalRequiredException
          Step 4：DENIED 级别 → 直接抛出 PermissionDeniedException
          Step 5：工具注册表查找（未找到视为旁路攻击尝试）
          Step 6：工具执行（Fail-Closed：任何异常均封装后重新抛出）
          Step 7：审计记录（成功与失败均记录）

        Args:
            tool_name:      要调用的工具名称。
            kwargs:         工具调用参数字典。
            requester_id:   申请方身份标识（沙盒会话 ID、Agent 任务 ID 等）。
            approval_token: HITL 批准后返回的一次性令牌（可选）。

        Returns:
            工具执行结果（具体类型由工具实现决定）。

        Raises:
            ApprovalRequiredException: KERNEL 级别操作，需要人工确认。
            PermissionDeniedException: DENIED 级别操作，永久拒绝。
            ToolNotRegisteredException: 工具未注册（可能是旁路攻击）。
            KernelBusError: 其他内核总线错误（Fail-Closed 封装）。
        """
        start_time = time.monotonic()

        # Step 1：工具名合法性验证
        # 工具名只允许字母、数字、下划线，防止路径注入与命令注入
        if not _is_valid_tool_name(tool_name):
            self._record_audit(
                requester_id, tool_name, kwargs,
                PermissionLevel.DENIED, "denied",
                "工具名包含非法字符（仅允许字母/数字/下划线）",
            )
            raise PermissionDeniedException(
                f"[非法工具名] '{tool_name}' 包含非法字符，拒绝执行。"
                "工具名只允许使用字母、数字、下划线（a-z, 0-9, _）。"
            )

        # Step 2：HITL 权限路由评估
        matched_rule, required_level = _evaluate_permission(tool_name, kwargs)

        # Step 3：KERNEL 级别 → 检查审批令牌
        if required_level == PermissionLevel.KERNEL:
            expected_token = _generate_approval_token(tool_name, requester_id)

            if approval_token != expected_token or approval_token not in self._approved_tokens:
                # 无有效审批令牌，触发 HITL 拦截
                self._record_audit(
                    requester_id, tool_name, kwargs,
                    required_level, "hitl_blocked",
                    matched_rule.description if matched_rule else "KERNEL 级别操作",
                )
                affected = _extract_affected_resources(kwargs)
                raise ApprovalRequiredException(
                    operation=matched_rule.description if matched_rule else "内核级别操作",
                    tool_name=tool_name,
                    risk_level=required_level,
                    affected_resources=affected,
                    requester_id=requester_id,
                )
            else:
                # 令牌有效，消耗后继续执行（防止重放攻击）
                self._approved_tokens.discard(approval_token)
                logger.info(
                    "[HITL 批准] 工具 '%s' 的审批令牌已验证，令牌已作废，继续执行。",
                    tool_name,
                )

        # Step 4：DENIED 级别 → 永久拒绝，无法通过 HITL 解锁
        if required_level == PermissionLevel.DENIED:
            self._record_audit(
                requester_id, tool_name, kwargs,
                required_level, "denied",
                matched_rule.description if matched_rule else "DENIED 级别操作",
            )
            raise PermissionDeniedException(
                f"[永久拒绝] 工具 '{tool_name}' 匹配到永久禁止规则，拒绝执行。\n"
                f"  原因：{matched_rule.description if matched_rule else '未知高危模式'}\n"
                "  此操作无法通过 HITL 授权解锁，请联系系统管理员。"
            )

        # Step 5：工具注册表查找
        if tool_name not in self._executors:
            self._record_audit(
                requester_id, tool_name, kwargs,
                required_level, "error",
                f"工具 '{tool_name}' 未在内核总线注册，可能是旁路攻击尝试",
            )
            logger.warning(
                "[潜在旁路攻击] 未注册工具 '%s' 被调用，申请方: %s",
                tool_name, requester_id,
            )
            raise ToolNotRegisteredException(
                f"[工具未注册] '{tool_name}' 未在内核总线注册。\n"
                "合法工具必须在进程启动阶段通过 register_executor() 注册。\n"
                "若你是开发者，请检查工具注册代码；"
                "若此调用来自沙盒，可能是越狱尝试，请立即告警。"
            )

        # Step 6：工具执行（Fail-Closed 封装）
        try:
            executor = self._executors[tool_name]
            result = executor(tool_name, kwargs)

            duration_ms = (time.monotonic() - start_time) * 1000
            self._record_audit(
                requester_id, tool_name, kwargs,
                required_level, "success",
            )
            logger.info(
                "[内核调用] 工具 '%s' 执行成功，耗时 %.1f ms，申请方: %s",
                tool_name, duration_ms, requester_id,
            )
            return result

        except (ApprovalRequiredException, PermissionDeniedException, KernelBusError):
            # 内核级异常向上透传，不重新封装
            raise
        except Exception as exc:
            # 所有其他异常：Fail-Closed 封装
            # 不暴露内部堆栈细节，防止错误信息泄漏系统内部结构
            self._record_audit(
                requester_id, tool_name, kwargs,
                required_level, "error",
                f"{type(exc).__name__}: {str(exc)[:200]}",
            )
            logger.error(
                "[内核错误] 工具 '%s' 执行异常（Fail-Closed）: %s",
                tool_name, exc,
            )
            raise KernelBusError(
                f"[Fail-Closed] 工具 '{tool_name}' 执行失败: {type(exc).__name__}。"
                "详细错误已记录到内核审计日志，拒绝向调用方泄漏内部堆栈。"
            ) from None

    # ------------------------------------------------------------------
    # HITL 审批令牌管理
    # ------------------------------------------------------------------

    def submit_approval(self, approval_token: str) -> None:
        """
        提交人工审批令牌（由 human_approval_prompter 在人类确认后调用）。

        令牌写入后，对应的 KERNEL 级别调用可在下次 call() 时携带令牌执行。
        令牌为一次性：使用后立即从集合中移除，防止重放攻击。
        """
        self._approved_tokens.add(approval_token)
        logger.info("[HITL 审批] 令牌 %s 已提交，等待对应工具调用核销。", approval_token[:8] + "...")

    def revoke_approval(self, approval_token: str) -> None:
        """撤销尚未使用的审批令牌（人类拒绝或超时后调用）。"""
        self._approved_tokens.discard(approval_token)
        logger.info("[HITL 撤销] 令牌 %s 已撤销。", approval_token[:8] + "...")

    # ------------------------------------------------------------------
    # 审计接口
    # ------------------------------------------------------------------

    @property
    def audit_log(self) -> list[AuditEntry]:
        """返回完整审计日志的只读副本。"""
        return list(self._audit_log)

    def audit_summary(self) -> str:
        """以人类可读格式输出审计统计摘要。"""
        total = len(self._audit_log)
        success = sum(1 for e in self._audit_log if e.outcome == "success")
        hitl = sum(1 for e in self._audit_log if e.outcome == "hitl_blocked")
        denied = sum(1 for e in self._audit_log if e.outcome == "denied")
        errors = sum(1 for e in self._audit_log if e.outcome == "error")
        return (
            f"[内核审计] 总调用={total} | 成功={success} | "
            f"HITL拦截={hitl} | 永久拒绝={denied} | 错误={errors}"
        )

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _record_audit(
        self,
        requester_id: str,
        tool_name: str,
        kwargs: dict[str, Any],
        level: PermissionLevel,
        outcome: str,
        error_detail: str = "",
    ) -> None:
        """记录一条审计日志条目（不可删除，不可修改）。"""
        # 参数摘要：只记录 key 名称与值的前 50 字符，防止密钥明文泄漏
        kwargs_summary = "; ".join(
            f"{k}={str(v)[:50]!r}" for k, v in kwargs.items()
        )
        entry = AuditEntry(
            timestamp=time.time(),
            requester_id=requester_id,
            tool_name=tool_name,
            kwargs_summary=kwargs_summary,
            permission_level=level,
            outcome=outcome,
            error_detail=error_detail,
        )
        self._audit_log.append(entry)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _is_valid_tool_name(name: str) -> bool:
    """
    验证工具名是否合法（只允许字母、数字、下划线）。

    防御目标：防止工具名被用于路径注入（如 "../../etc/passwd"）
    或命令注入（如 "echo; rm -rf /"）。
    """
    return bool(name) and all(c.isalnum() or c == "_" for c in name)


def _evaluate_permission(
    tool_name: str,
    kwargs: dict[str, Any],
) -> tuple[HitlRule | None, PermissionLevel]:
    """
    按 HITL 规则表评估工具调用所需的权限级别。

    匹配逻辑：
      1. 遍历 _HITL_RULES，从上到下，首次命中立即返回。
      2. 工具名以 rule.tool_name_prefix 开头（空前缀匹配所有工具名），
         且调用参数中任一值（转为字符串后）包含 dangerous_arg_keywords 中的任一关键词。
      3. 若无规则命中，返回 SAFE 级别（最小权限原则）。
    """
    # 将所有参数值转为字符串，用于关键词扫描
    all_arg_values = " ".join(str(v) for v in kwargs.values()).lower()

    for rule in _HITL_RULES:
        # 工具名前缀匹配（空前缀视为"匹配所有"）
        name_matches = (not rule.tool_name_prefix) or tool_name.startswith(rule.tool_name_prefix)
        if not name_matches:
            continue

        # 关键词扫描
        keyword_found = any(kw.lower() in all_arg_values for kw in rule.dangerous_arg_keywords)
        if keyword_found:
            return rule, rule.required_level

    # 无规则命中：默认 SAFE 级别（Fail-Safe，不是 Fail-Open）
    return None, PermissionLevel.SAFE


def _extract_affected_resources(kwargs: dict[str, Any]) -> list[str]:
    """从调用参数中提取受影响的资源标识，用于 HITL 异常的人类可读描述。"""
    resources: list[str] = []
    for k, v in kwargs.items():
        if isinstance(v, str) and len(v) < 200:
            resources.append(f"{k}={v}")
    return resources[:5]  # 最多返回 5 个，避免 HITL 提示过长


def _generate_approval_token(tool_name: str, requester_id: str) -> str:
    """
    生成 HITL 审批令牌。

    令牌由 tool_name + requester_id + 时间戳（精确到秒）的 SHA-256 哈希生成，
    确保每次拦截的令牌唯一且不可伪造（在令牌生命周期内）。

    生产环境建议：令牌应加入服务端密钥 HMAC，防止客户端伪造。
    """
    raw = f"{tool_name}:{requester_id}:{int(time.time())}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# 模块级全局内核总线单例
# ---------------------------------------------------------------------------

# 全局内核总线：整个进程共享唯一实例。
# 单例确保：
#   1. 所有工具执行器统一注册在同一个实例上，不存在"平行总线"逃逸路径。
#   2. 审计日志全局完整，不会因多实例而分散。
#   3. HITL 审批令牌的状态全局一致。
KERNEL_BUS = KernelApiBus()
