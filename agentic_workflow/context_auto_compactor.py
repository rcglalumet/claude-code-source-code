"""
agentic_workflow/context_auto_compactor.py
--------------------------------------------
Alumet OS — 五级压缩器与防失忆折叠器

核心使命：贯彻"极致的缓存护城河"哲学，捍卫 Token 配额边界。

设计背景：
  大模型的上下文窗口是有限的稀缺资源。随着 Agentic 循环的推进，对话历史
  持续累积，最终面临三种死亡模式：

  死亡模式 D1 —— 静默截断（Silent Truncation）：
    LLM API 在超过 context_length 时，从最早的消息开始静默丢弃，
    导致大模型"失忆"——它完全不知道早期的决策与约束，开始输出幻觉。

  死亡模式 D2 —— 413 Payload Too Large：
    部分 LLM 网关（如企业内网代理）在请求体超过物理大小限制时，
    直接返回 HTTP 413，整个 Agent 任务崩溃。

  死亡模式 D3 —— Token 成本爆炸：
    未压缩的上下文每轮都完整发送，Token 消耗随轮数线性增长，
    长任务的成本曲线呈指数级上升。

防御策略：五级压缩漏斗（从轻到重，按需触发）：
  L1 — 剔除 LLM 内部 Thinking（通常对下游决策无用，纯粹消耗 Token）
  L2 — 截断过长的 Tool JSON 返回值（超出阈值的尾部截断并打标记）
  L3 — 摘要早期对话轮次（保留语义核心，折叠冗余细节）
  L4 — 提取核心实体张量（只保留 key=value 形式的关键实体）
  L5 — 极简暴力截断（最后防线，强制保留最新的 N 条消息）

双触发机制：
  主动触发：每轮 Agentic 循环前调用 compact_if_needed()，超过 25KB 阈值则启动
  应急触发：LLM 网关遭遇 413 时调用 emergency_compact()，无情折叠直至安全
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 物理红线常量
# ---------------------------------------------------------------------------

# 跨门派短期记忆张量总容量上限：25KB（UTF-8 编码字节数）
# 物理意义：超过此阈值，消息体在传输到 LLM 网关前必须被压缩，
# 绝不允许以超标状态发出任何请求。
HARD_LIMIT_BYTES: int = 25 * 1024  # 25 KB

# L2 单条 Tool 返回值的最大字节数（超出部分截断）
L2_TOOL_RESULT_MAX_BYTES: int = 512

# L3 摘要折叠保留的最近轮数（早于此轮数的消息进入摘要折叠）
L3_RECENT_TURNS_TO_KEEP: int = 4

# L5 暴力截断保留的最近消息条数（最后防线）
L5_KEEP_LAST_N_MESSAGES: int = 6


# ---------------------------------------------------------------------------
# 压缩结果元数据
# ---------------------------------------------------------------------------

@dataclass
class CompactionReport:
    """
    单次压缩操作的完整元数据报告。

    用途：
      1. 告知调用方本次压缩的效果（压缩率），便于监控与容量规划。
      2. 记录触发的最深压缩级别，用于判断上下文是否已严重退化。
      3. 若最深级别达到 L5（暴力截断），应触发人工告警，
         因为这意味着 Agent 任务的历史信息已发生不可逆丢失。
    """

    original_bytes: int
    compressed_bytes: int
    deepest_level_triggered: int  # 1~5，触发的最深压缩级别
    messages_before: int
    messages_after: int
    emergency_triggered: bool = False

    @property
    def compression_ratio(self) -> float:
        """压缩率：0.0 表示无压缩，1.0 表示完全清空。"""
        if self.original_bytes == 0:
            return 0.0
        return 1.0 - self.compressed_bytes / self.original_bytes

    def __str__(self) -> str:
        mode = "【应急】" if self.emergency_triggered else "【主动】"
        return (
            f"{mode}压缩报告 | "
            f"级别=L{self.deepest_level_triggered} | "
            f"{self.original_bytes}B → {self.compressed_bytes}B | "
            f"压缩率={self.compression_ratio:.1%} | "
            f"消息数={self.messages_before} → {self.messages_after}"
        )


# ---------------------------------------------------------------------------
# 五级压缩漏斗实现
# ---------------------------------------------------------------------------

class ContextAutoCompactor:
    """
    Alumet OS 上下文自动压缩器（五级压缩漏斗）。

    调用约定：
      - compact_if_needed(messages)：主动检查，超阈值则按需触发 L1~L5。
      - emergency_compact(messages)：应急折叠，无论当前大小，强制触发完整漏斗
                                     直至压缩到安全水位以下。
      - 两个方法均返回压缩后的消息列表与 CompactionReport。
      - 原始 messages 列表不会被修改（返回新列表）。
    """

    def __init__(
        self,
        hard_limit_bytes: int = HARD_LIMIT_BYTES,
        l2_tool_max_bytes: int = L2_TOOL_RESULT_MAX_BYTES,
        l3_recent_turns: int = L3_RECENT_TURNS_TO_KEEP,
        l5_keep_last_n: int = L5_KEEP_LAST_N_MESSAGES,
    ) -> None:
        self._limit = hard_limit_bytes
        self._l2_max = l2_tool_max_bytes
        self._l3_recent = l3_recent_turns
        self._l5_keep = l5_keep_last_n

    # ------------------------------------------------------------------
    # 主动触发接口：每轮 Agent 循环前调用
    # ------------------------------------------------------------------

    def compact_if_needed(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], CompactionReport | None]:
        """
        主动阈值检查：若消息体总字节数超过 HARD_LIMIT_BYTES，触发压缩漏斗。

        若当前大小未超标，直接返回原列表与 None（无需压缩，零开销）。

        Args:
            messages: 当前对话历史列表（只读，不会被修改）。

        Returns:
            (压缩后消息列表, CompactionReport 或 None)
        """
        current_bytes = _measure_bytes(messages)

        if current_bytes <= self._limit:
            # 未超标，快速返回，不执行任何压缩操作
            return messages, None

        logger.warning(
            "[主动压缩] 上下文已达 %d 字节，超过 %d 字节上限，启动五级压缩漏斗。",
            current_bytes,
            self._limit,
        )

        compressed, report = self._run_funnel(
            messages=messages,
            original_bytes=current_bytes,
            emergency=False,
        )
        logger.info("%s", report)
        return compressed, report

    # ------------------------------------------------------------------
    # 应急触发接口：LLM 网关 413 时调用的 Hook
    # ------------------------------------------------------------------

    def emergency_compact(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], CompactionReport]:
        """
        应急折叠 Hook：供 LLM 网关遭遇 413 Payload Too Large 时调用。

        与主动压缩的区别：
          - 不检查阈值，无论当前大小立即触发完整漏斗（L1→L5）。
          - 目标水位更激进：压缩至 HARD_LIMIT_BYTES 的 60%（留足余量）。
          - 若完整漏斗后仍超标，强制 L5 暴力截断到绝对安全线。
          - CompactionReport.emergency_triggered 标记为 True，
            触发上层监控告警（L5 意味着历史信息不可逆丢失）。

        Args:
            messages: 当前对话历史列表。

        Returns:
            (压缩后消息列表, CompactionReport)，此方法保证返回 CompactionReport。
        """
        original_bytes = _measure_bytes(messages)

        logger.error(
            "[应急压缩] 接收到 413 应急信号，当前上下文 %d 字节，立即执行无情折叠。",
            original_bytes,
        )

        compressed, report = self._run_funnel(
            messages=messages,
            original_bytes=original_bytes,
            emergency=True,
            # 应急目标水位：60% 的限额，为下一轮消息预留充足空间
            target_bytes=int(self._limit * 0.6),
        )

        logger.error("[应急压缩完成] %s", report)

        if report.deepest_level_triggered >= 5:
            logger.critical(
                "[L5 告警] 应急压缩触发了 L5 暴力截断！早期对话历史已不可逆丢失。"
                "请人工介入评估 Agent 任务是否需要重置。"
            )

        return compressed, report

    # ------------------------------------------------------------------
    # 五级压缩漏斗（内部实现）
    # ------------------------------------------------------------------

    def _run_funnel(
        self,
        messages: list[dict[str, Any]],
        original_bytes: int,
        emergency: bool,
        target_bytes: int | None = None,
    ) -> tuple[list[dict[str, Any]], CompactionReport]:
        """
        按 L1→L5 顺序依次施压，每级压缩后检查是否已达到目标水位。
        一旦达标，立即停止，不触发更深级别（最小化信息损失）。

        设计哲学：
          越浅的级别（L1/L2）信息损失越小，越深的级别（L4/L5）信息损失越大。
          因此漏斗从 L1 开始尝试，尽可能在浅层解决问题，
          只有在浅层不足以达标时才继续向下渗透。
        """
        target = target_bytes if target_bytes is not None else self._limit
        msgs_before = len(messages)
        current = list(messages)
        deepest = 0

        # --- L1：剔除 LLM 内部 Thinking 字段 ---
        # thinking 字段是大模型的"内心独白"，对下游决策通常无实质贡献，
        # 却可能占据数百至数千 Token。在压缩场景下首先清除。
        current = self._l1_strip_thinking(current)
        deepest = 1
        if _measure_bytes(current) <= target:
            return current, _make_report(original_bytes, current, deepest, msgs_before, emergency)

        # --- L2：截断过长的 Tool JSON 返回值 ---
        # 工具返回值（尤其是搜索/数据库查询结果）可能包含大量原始数据。
        # 大模型通常只需要前几百字节的关键信息，其余为冗余噪音。
        current = self._l2_truncate_tool_results(current)
        deepest = 2
        if _measure_bytes(current) <= target:
            return current, _make_report(original_bytes, current, deepest, msgs_before, emergency)

        # --- L3：摘要早期对话轮次 ---
        # 保留最近 L3_RECENT_TURNS_TO_KEEP 轮消息的完整内容，
        # 将早期消息折叠为语义摘要（保留"发生了什么"，丢弃"具体怎么说的"）。
        current = self._l3_summarize_early_turns(current)
        deepest = 3
        if _measure_bytes(current) <= target:
            return current, _make_report(original_bytes, current, deepest, msgs_before, emergency)

        # --- L4：提取核心实体张量 ---
        # 从所有消息中提取 key=value 形式的关键实体信息，
        # 将整个历史压缩为一条结构化的"实体记忆"消息。
        # 此级别会丢失对话的叙事结构，只保留关键事实。
        current = self._l4_extract_entity_tensor(current)
        deepest = 4
        if _measure_bytes(current) <= target:
            return current, _make_report(original_bytes, current, deepest, msgs_before, emergency)

        # --- L5：极简暴力截断（最后防线）---
        # 直接保留最新的 L5_KEEP_LAST_N_MESSAGES 条消息，丢弃其余一切。
        # 这是破坏性最强的操作，意味着 Agent 的长期记忆被清空。
        # 触发此级别必须记录 CRITICAL 日志并触发人工告警。
        current = self._l5_hard_truncate(current)
        deepest = 5
        logger.critical(
            "[L5 暴力截断] 上下文压缩已达最后防线！"
            "仅保留最新 %d 条消息，历史信息不可逆丢失。",
            self._l5_keep,
        )
        return current, _make_report(original_bytes, current, deepest, msgs_before, emergency)

    # ------------------------------------------------------------------
    # 各级压缩实现
    # ------------------------------------------------------------------

    def _l1_strip_thinking(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        L1：剔除 LLM 内部 Thinking 字段。

        大模型（如 Claude extended thinking）在响应中包含 thinking 字段，
        记录其推理过程。这些内容对已完成的决策无任何附加价值，
        却可能消耗数百到数千 Token。在压缩场景下优先清除，
        且不会导致任何语义信息的实质性丢失。
        """
        result = []
        for msg in messages:
            if isinstance(msg.get("thinking"), str):
                # 创建消息副本并移除 thinking 字段
                cleaned = {k: v for k, v in msg.items() if k != "thinking"}
                result.append(cleaned)
            else:
                result.append(msg)
        return result

    def _l2_truncate_tool_results(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        L2：截断过长的 Tool JSON 返回值。

        工具角色（role="tool"）的消息内容通常是原始 JSON，
        可能包含数据库查询结果、搜索列表、API 完整响应等大体积数据。
        大模型在后续决策中通常只需要前 512 字节的关键信息。

        截断策略：
          - 保留前 L2_TOOL_RESULT_MAX_BYTES 字节的内容。
          - 在截断处追加 "[...已截断，原始长度: {n} 字节]" 标记，
            让大模型知晓数据被截断而非完整，避免产生"数据完整"的幻觉。
        """
        result = []
        for msg in messages:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if isinstance(content, str):
                    encoded = content.encode("utf-8")
                    if len(encoded) > self._l2_max:
                        truncated = encoded[: self._l2_max].decode("utf-8", errors="ignore")
                        marker = f" [...已截断，原始长度: {len(encoded)} 字节]"
                        msg = {**msg, "content": truncated + marker}
            result.append(msg)
        return result

    def _l3_summarize_early_turns(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        L3：摘要折叠早期对话轮次。

        保留最近 L3_RECENT_TURNS_TO_KEEP 条消息的完整内容，
        将更早的消息替换为一条结构化摘要消息：
          - 统计各角色的消息数量
          - 提取每条消息 content 字段的前 80 字符作为关键词索引
          - 将摘要注入为 role="system" 的历史摘要消息

        语义保真度说明：
          L3 会丢失早期对话的具体措辞，但保留了"事件序列"的结构性记忆。
          这对大多数 Agentic 任务已足够——大模型知道"发生了什么"，
          即使不知道"具体怎么说的"。
        """
        if len(messages) <= self._l3_recent:
            return messages

        # system 消息（通常在最前面）必须完整保留，不参与折叠
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # 将非 system 消息分为"早期"（待折叠）和"近期"（完整保留）
        cutoff = max(0, len(non_system) - self._l3_recent)
        early = non_system[:cutoff]
        recent = non_system[cutoff:]

        if not early:
            return messages

        # 构造摘要条目列表
        summary_entries: list[str] = []
        for idx, msg in enumerate(early):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                snippet = content[:80].replace("\n", " ")
            else:
                snippet = str(content)[:80]
            summary_entries.append(f"  [{idx + 1}] {role}: {snippet}…")

        summary_content = (
            f"[L3 历史摘要] 以下 {len(early)} 条早期消息已折叠（保留语义核心）：\n"
            + "\n".join(summary_entries)
            + f"\n[摘要结束，近期 {len(recent)} 条消息完整保留]"
        )

        summary_msg: dict[str, Any] = {
            "role": "system",
            "content": summary_content,
        }

        return system_msgs + [summary_msg] + recent

    def _l4_extract_entity_tensor(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        L4：提取核心实体张量。

        从所有非 system 消息中扫描并提取 key=value 形式的关键实体信息
        （如 task_id、file_path、database_url、error_code 等），
        将整个对话历史压缩为一条"实体记忆"消息，丢弃叙事结构。

        提取规则（轻量级启发式，无需 NLP 模型）：
          - JSON 对象中的顶层 key: primitive_value 对
          - 形如 key=value 的字符串模式

        设计权衡：
          L4 会丢失对话的因果逻辑（"为什么这样做"），
          只保留关键事实（"什么是什么"）。
          这对需要回溯推理的任务有较大影响，
          因此仅在 L1~L3 均无法达标时才触发。
        """
        system_msgs = [m for m in messages if m.get("role") == "system"]

        entities: dict[str, str] = {}

        for msg in messages:
            if msg.get("role") == "system":
                continue
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue

            # 尝试解析 JSON 并提取顶层基础类型字段
            stripped = content.strip()
            if stripped.startswith("{"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            if isinstance(v, (str, int, float, bool)) and k not in entities:
                                entities[k] = str(v)[:100]
                except (json.JSONDecodeError, ValueError):
                    pass

            # 提取 key=value 模式（启发式扫描，最多提取 20 个实体）
            if len(entities) < 20:
                for part in content.split():
                    if "=" in part and not part.startswith("=") and not part.endswith("="):
                        k, _, v = part.partition("=")
                        k = k.strip().strip('"\'')
                        v = v.strip().strip('"\'')
                        if k and v and len(k) < 50 and k not in entities:
                            entities[k] = v[:100]

        if not entities:
            # 若无法提取实体，至少保留 system 消息 + 最新一条消息
            last = [m for m in messages if m.get("role") != "system"][-1:]
            return system_msgs + last

        entity_lines = "\n".join(f"  {k}: {v}" for k, v in entities.items())
        entity_msg: dict[str, Any] = {
            "role": "system",
            "content": (
                f"[L4 实体张量] 以下为从对话历史中提取的核心实体（共 {len(entities)} 个）：\n"
                f"{entity_lines}\n"
                "[注意：原始对话叙事已因极限压缩而丢失，仅保留关键事实实体。]"
            ),
        }
        return system_msgs + [entity_msg]

    def _l5_hard_truncate(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        L5：极简暴力截断（最后防线）。

        保留所有 system 消息（保持基础约束不丢失）
        + 最新的 L5_KEEP_LAST_N_MESSAGES 条非 system 消息。
        其余历史全部丢弃。

        ⚠️  此操作不可逆，历史信息将永久丢失。
        触发此级别必须在调用方层面记录 CRITICAL 日志并发送人工告警通知。
        """
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        truncation_notice: dict[str, Any] = {
            "role": "system",
            "content": (
                f"[L5 截断告警] 上下文已超出物理容量极限，"
                f"已丢弃 {max(0, len(non_system) - self._l5_keep)} 条历史消息，"
                f"仅保留最新 {self._l5_keep} 条。Agent 任务记忆已部分丢失，"
                "请优先完成当前子任务，避免依赖早期上下文。"
            ),
        }

        kept = non_system[-self._l5_keep :] if len(non_system) > self._l5_keep else non_system

        return system_msgs + [truncation_notice] + kept


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _measure_bytes(messages: list[dict[str, Any]]) -> int:
    """计算消息列表序列化后的 UTF-8 字节数（用于压缩触发判断）。"""
    return len(json.dumps(messages, ensure_ascii=False).encode("utf-8"))


def _make_report(
    original_bytes: int,
    compressed: list[dict[str, Any]],
    deepest: int,
    msgs_before: int,
    emergency: bool,
) -> CompactionReport:
    return CompactionReport(
        original_bytes=original_bytes,
        compressed_bytes=_measure_bytes(compressed),
        deepest_level_triggered=deepest,
        messages_before=msgs_before,
        messages_after=len(compressed),
        emergency_triggered=emergency,
    )


# ---------------------------------------------------------------------------
# 模块级全局压缩器单例
# ---------------------------------------------------------------------------

# 全局压缩器：整个进程共享唯一实例，所有 Agent 会话的上下文经由此压缩。
# 单例确保压缩参数（阈值、各级配置）全局一致，便于统一调参与监控。
GLOBAL_COMPACTOR = ContextAutoCompactor()
