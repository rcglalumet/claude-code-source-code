"""
agentic_workflow/working_memory_context.py
-------------------------------------------
Alumet OS — 动态热数据容器与跨会话记忆（Agent 工作记忆区）

核心使命：贯彻"极致的缓存护城河"哲学，为 Agent 提供有界、可压缩、
跨会话持久化的工作记忆区。

设计背景：
  Agent 在执行任务时需要维护两类记忆：

  记忆类型 M1 —— 短期工作记忆（对话历史）：
    当前任务的完整对话上下文。容量有限，随轮次增长，
    必须受到物理红线约束，超限时强制唤醒压缩器。

  记忆类型 M2 —— 长期核心记忆（用户偏好与核心指令）：
    跨会话的持久化信息，如用户偏好、常用配置、核心约束指令。
    这是 Claude Code MEMORY.md 哲学的 Python 实现：
    将高度提纯的"人类意图"写入磁盘，确保系统重启后不失忆。

物理红线：
  工作记忆张量（对话历史）总字节数不得超过 WORKING_MEMORY_LIMIT_BYTES（25KB）。
  每次装载新消息时，先追加，后检测，超限则立即同步调用 ContextAutoCompactor
  进行内存折叠，确保在任何时刻向 LLM 网关发出的上下文都在安全水位以内。

联动机制：
  WorkingMemoryContext ─── (超限时) ──→ ContextAutoCompactor.compact_if_needed()
                       ←── (返回压缩后消息列表) ─────────────────────────────┘

跨会话持久化（MEMORY.md 哲学映射）：
  写入：将核心记忆提纯为 JSON 存入 data_center/system_hot_memory.json
  读取：初始化时自动加载，将持久化记忆注入 system prompt 前缀
  格式：结构化 JSON，支持版本号、更新时间戳、记忆条目分类
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agentic_workflow.context_auto_compactor import (
    ContextAutoCompactor,
    CompactionReport,
    GLOBAL_COMPACTOR,
    _measure_bytes,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 物理红线常量
# ---------------------------------------------------------------------------

# 工作记忆张量总容量上限：25KB
# 与 ContextAutoCompactor.HARD_LIMIT_BYTES 保持一致，二者共享同一物理约束。
# 此处独立声明，使工作记忆容器可以在无压缩器依赖的场景下独立部署。
WORKING_MEMORY_LIMIT_BYTES: int = 25 * 1024  # 25 KB

# 触发主动压缩的警戒水位（物理红线的 80%）
# 在达到硬上限之前的缓冲区，避免每条消息都恰好卡在边界触发压缩
COMPACTION_TRIGGER_THRESHOLD: float = 0.80

# 持久化热记忆文件的默认路径
DEFAULT_HOT_MEMORY_PATH: Path = Path("data_center/system_hot_memory.json")

# 单条热记忆条目的最大字符数（防止单条记忆膨胀）
HOT_MEMORY_ENTRY_MAX_CHARS: int = 500

# 热记忆最大条目数（防止无限累积）
HOT_MEMORY_MAX_ENTRIES: int = 50


# ---------------------------------------------------------------------------
# 热记忆条目数据结构
# ---------------------------------------------------------------------------

@dataclass
class HotMemoryEntry:
    """
    单条持久化热记忆条目。

    分类设计：
      preference  → 用户行为偏好（如"偏好简洁回答"、"代码风格：PEP8"）
      constraint  → 核心约束指令（如"绝不输出不安全内容"、"任务超时阈值 30s"）
      context     → 跨会话上下文（如"当前项目：Alumet OS"、"用户角色：架构师"）
      fact        → 关键事实记忆（如"数据库连接串已在 .env 中配置"）
    """

    key: str                    # 记忆键（全局唯一标识）
    value: str                  # 记忆值（已提纯的高密度信息）
    category: str               # 分类：preference | constraint | context | fact
    created_at: float           # 创建时间戳
    updated_at: float           # 最后更新时间戳
    importance: int = 5         # 重要性评分 1~10，用于 L4 实体压缩时的优先级排序

    def to_prompt_fragment(self) -> str:
        """将本条记忆格式化为可注入 system prompt 的文本片段。"""
        return f"[{self.category.upper()}] {self.key}: {self.value}"


# ---------------------------------------------------------------------------
# 热记忆持久化存储
# ---------------------------------------------------------------------------

@dataclass
class HotMemoryStore:
    """
    热记忆持久化存储结构（映射至 data_center/system_hot_memory.json）。

    版本字段用于未来的格式迁移（不同版本的加载逻辑可按 schema_version 分支处理）。
    """

    schema_version: int = 1
    last_updated: float = field(default_factory=time.time)
    entries: dict[str, HotMemoryEntry] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 写入的字典。"""
        return {
            "schema_version": self.schema_version,
            "last_updated": self.last_updated,
            "entries": {
                k: asdict(v) for k, v in self.entries.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HotMemoryStore":
        """从 JSON 反序列化，支持向前兼容（未知字段忽略）。"""
        entries_raw = data.get("entries", {})
        entries = {}
        for k, v in entries_raw.items():
            try:
                entries[k] = HotMemoryEntry(**{
                    fld: v[fld]
                    for fld in HotMemoryEntry.__dataclass_fields__
                    if fld in v
                })
            except (TypeError, KeyError) as e:
                logger.warning("[热记忆] 条目 '%s' 反序列化失败，已跳过: %s", k, e)
        return cls(
            schema_version=data.get("schema_version", 1),
            last_updated=data.get("last_updated", time.time()),
            entries=entries,
        )


# ---------------------------------------------------------------------------
# Agent 工作记忆上下文（核心类）
# ---------------------------------------------------------------------------

class WorkingMemoryContext:
    """
    Alumet OS Agent 工作记忆上下文。

    职责：
      1. 维护当前任务的对话历史（短期工作记忆），受 25KB 物理红线约束。
      2. 超限时自动联动 ContextAutoCompactor 进行内存折叠。
      3. 管理跨会话持久化热记忆（长期核心记忆），启动时加载、关闭时写入。
      4. 提供将热记忆注入 system prompt 的接口，确保 Agent 跨会话不失忆。

    生命周期：
      1. 调用 initialize() 加载热记忆文件（或创建新文件）。
      2. 通过 append_message() / append_tool_result() 追加消息。
         每次追加后自动执行阈值检测，超限则压缩。
      3. 通过 get_messages_for_llm() 获取注入热记忆 system 前缀后的完整上下文。
      4. 通过 upsert_hot_memory() 更新热记忆条目。
      5. 调用 flush_hot_memory() 将热记忆持久化到磁盘。
    """

    def __init__(
        self,
        compactor: ContextAutoCompactor | None = None,
        hot_memory_path: Path = DEFAULT_HOT_MEMORY_PATH,
        limit_bytes: int = WORKING_MEMORY_LIMIT_BYTES,
        trigger_threshold: float = COMPACTION_TRIGGER_THRESHOLD,
    ) -> None:
        """
        Args:
            compactor:         压缩器实例（依赖注入，默认使用全局压缩器）。
            hot_memory_path:   热记忆 JSON 文件路径。
            limit_bytes:       物理红线（字节数上限）。
            trigger_threshold: 主动压缩触发水位（占物理红线的比例）。
        """
        self._compactor = compactor or GLOBAL_COMPACTOR
        self._hot_memory_path = hot_memory_path
        self._limit = limit_bytes
        self._trigger_bytes = int(limit_bytes * trigger_threshold)

        # 短期工作记忆：对话历史列表
        self._messages: list[dict[str, Any]] = []

        # 长期核心记忆：持久化热记忆存储
        self._hot_store = HotMemoryStore()

        # 压缩历史记录（供监控与调试）
        self._compaction_history: list[CompactionReport] = []

        # 热记忆脏标记：True 表示内存中有未持久化的修改
        self._hot_memory_dirty: bool = False

    # ------------------------------------------------------------------
    # 初始化：加载热记忆
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """
        初始化工作记忆上下文，从磁盘加载热记忆。

        此方法必须在使用工作记忆前调用（或在构造后立即调用）。
        若热记忆文件不存在，创建空存储并写入初始文件。
        若文件损坏（JSON 解析失败），使用空存储并记录 WARNING，
        不抛出异常（宁可空白启动，也不阻断 Agent 初始化）。
        """
        path = self._hot_memory_path

        if path.exists():
            try:
                raw = path.read_text(encoding="utf-8")
                data = json.loads(raw)
                self._hot_store = HotMemoryStore.from_dict(data)
                logger.info(
                    "[热记忆] 已从 %s 加载 %d 条记忆条目。",
                    path,
                    len(self._hot_store.entries),
                )
            except (json.JSONDecodeError, OSError, ValueError) as e:
                logger.warning(
                    "[热记忆] 文件 %s 加载失败（%s），使用空记忆启动。"
                    "Agent 本次无长期记忆，但运行不受影响。",
                    path,
                    e,
                )
                self._hot_store = HotMemoryStore()
        else:
            logger.info("[热记忆] 文件 %s 不存在，初始化空记忆存储。", path)
            self._hot_store = HotMemoryStore()
            # 创建目录与初始文件，确保后续 flush 不会因目录不存在而失败
            self._ensure_directory()
            self._write_hot_memory_file()

    # ------------------------------------------------------------------
    # 短期工作记忆操作
    # ------------------------------------------------------------------

    def append_message(self, message: dict[str, Any]) -> CompactionReport | None:
        """
        追加一条消息到工作记忆，并执行阈值检测。

        若追加后超过警戒水位（物理红线的 80%），立即同步触发压缩器。
        压缩在追加之后、返回调用方之前完成，确保调用方拿到的始终是合规的上下文。

        Args:
            message: 符合 {role, content} 格式的消息字典。

        Returns:
            若触发了压缩，返回 CompactionReport；否则返回 None。
        """
        self._messages.append(message)
        return self._check_and_compact()

    def append_tool_result(
        self,
        tool_name: str,
        result: Any,
        success: bool = True,
    ) -> CompactionReport | None:
        """
        追加工具执行结果到工作记忆。

        工具结果以 role="tool" 的消息格式追加，便于大模型区分工具输出与用户输入。
        工具结果通常是 JSON，体积可能较大，追加后必须强制检测压缩触发。

        Args:
            tool_name: 工具名称（用于结果标注）。
            result:    工具执行结果（任意可序列化对象）。
            success:   工具是否执行成功。

        Returns:
            若触发了压缩，返回 CompactionReport；否则返回 None。
        """
        try:
            content = json.dumps(
                {"tool": tool_name, "success": success, "result": result},
                ensure_ascii=False,
            )
        except (TypeError, ValueError):
            # 若 result 不可序列化，降级为字符串表示
            content = json.dumps(
                {"tool": tool_name, "success": success, "result": str(result)},
                ensure_ascii=False,
            )

        tool_msg: dict[str, Any] = {"role": "tool", "content": content}
        self._messages.append(tool_msg)

        logger.debug(
            "[工作记忆] 追加工具结果: tool=%s, success=%s, 当前消息数=%d",
            tool_name, success, len(self._messages),
        )

        return self._check_and_compact()

    def clear_session(self) -> None:
        """
        清空当前会话的短期工作记忆（不影响长期热记忆）。

        用于：
          - 任务完成后重置工作记忆，开始新任务
          - 熔断降级后重置上下文
          - 单元测试的初始化清理
        """
        count = len(self._messages)
        self._messages.clear()
        logger.info("[工作记忆] 会话记忆已清空（共清除 %d 条消息）。", count)

    # ------------------------------------------------------------------
    # 获取注入热记忆后的完整上下文（供 LLM 调用使用）
    # ------------------------------------------------------------------

    def get_messages_for_llm(self) -> list[dict[str, Any]]:
        """
        获取注入热记忆 system 前缀后的完整上下文列表。

        输出格式：
          [热记忆 system 消息（若有）] + [当前会话消息列表]

        热记忆注入设计（MEMORY.md 哲学）：
          将所有持久化热记忆条目格式化为一条 system 消息，
          作为对话历史的最前缀注入。大模型每次调用时都能看到
          跨会话的用户偏好与核心约束，实现"重启不失忆"效果。

          注入顺序：constraint（最优先）> preference > context > fact
          这确保核心约束指令在 system prompt 中排在最前面。
        """
        hot_prefix = self._build_hot_memory_prefix()

        if hot_prefix:
            prefix_msg: dict[str, Any] = {
                "role": "system",
                "content": hot_prefix,
            }
            return [prefix_msg] + list(self._messages)
        return list(self._messages)

    # ------------------------------------------------------------------
    # 热记忆（长期持久化记忆）操作
    # ------------------------------------------------------------------

    def upsert_hot_memory(
        self,
        key: str,
        value: str,
        category: str = "context",
        importance: int = 5,
    ) -> None:
        """
        插入或更新一条热记忆条目，标记脏位。

        Args:
            key:        记忆键（全局唯一，相同 key 则覆盖）。
            value:      记忆值（将被提纯写入，最大 500 字符）。
            category:   分类：preference | constraint | context | fact。
            importance: 重要性 1~10，越高越在压缩时优先保留。
        """
        # 截断过长的记忆值，防止单条记忆膨胀
        if len(value) > HOT_MEMORY_ENTRY_MAX_CHARS:
            value = value[: HOT_MEMORY_ENTRY_MAX_CHARS] + "…[已截断]"
            logger.warning("[热记忆] 条目 '%s' 超过最大长度，已截断至 %d 字符。", key, HOT_MEMORY_ENTRY_MAX_CHARS)

        # 热记忆总条目数上限，超过时按重要性淘汰最低分条目
        if len(self._hot_store.entries) >= HOT_MEMORY_MAX_ENTRIES and key not in self._hot_store.entries:
            self._evict_lowest_importance()

        now = time.time()
        if key in self._hot_store.entries:
            existing = self._hot_store.entries[key]
            self._hot_store.entries[key] = HotMemoryEntry(
                key=key, value=value, category=category,
                created_at=existing.created_at, updated_at=now, importance=importance,
            )
            logger.debug("[热记忆] 更新条目: key=%s", key)
        else:
            self._hot_store.entries[key] = HotMemoryEntry(
                key=key, value=value, category=category,
                created_at=now, updated_at=now, importance=importance,
            )
            logger.debug("[热记忆] 新增条目: key=%s", key)

        self._hot_store.last_updated = now
        self._hot_memory_dirty = True

    def delete_hot_memory(self, key: str) -> bool:
        """
        删除一条热记忆条目。

        Returns:
            True 表示成功删除，False 表示 key 不存在。
        """
        if key in self._hot_store.entries:
            del self._hot_store.entries[key]
            self._hot_store.last_updated = time.time()
            self._hot_memory_dirty = True
            logger.info("[热记忆] 条目 '%s' 已删除。", key)
            return True
        return False

    def flush_hot_memory(self) -> None:
        """
        将热记忆强制持久化到磁盘（写入 system_hot_memory.json）。

        调用时机：
          - Agent 任务完成时（确保本次会话的记忆提炼被写入）
          - 进程退出前（atexit hook）
          - 用户触发"保存记忆"指令时

        若脏标记为 False（无未持久化的修改），跳过写入以减少 I/O。
        """
        if not self._hot_memory_dirty:
            logger.debug("[热记忆] 无待写入变更，跳过 flush。")
            return

        self._ensure_directory()
        self._write_hot_memory_file()
        self._hot_memory_dirty = False
        logger.info(
            "[热记忆] 已持久化 %d 条记忆到 %s。",
            len(self._hot_store.entries),
            self._hot_memory_path,
        )

    # ------------------------------------------------------------------
    # 状态查询接口
    # ------------------------------------------------------------------

    @property
    def current_bytes(self) -> int:
        """当前工作记忆的字节数（不含热记忆前缀）。"""
        return _measure_bytes(self._messages)

    @property
    def utilization(self) -> float:
        """工作记忆利用率：当前字节数 / 物理上限，0.0~1.0+。"""
        return self.current_bytes / self._limit

    @property
    def message_count(self) -> int:
        """当前工作记忆中的消息条数。"""
        return len(self._messages)

    @property
    def hot_memory_count(self) -> int:
        """当前热记忆条目数。"""
        return len(self._hot_store.entries)

    def memory_status(self) -> str:
        """人类可读的记忆状态摘要，用于日志与监控。"""
        return (
            f"[工作记忆状态] "
            f"短期={self.current_bytes}B/{self._limit}B "
            f"({self.utilization:.1%}) | "
            f"消息数={self.message_count} | "
            f"热记忆条目={self.hot_memory_count} | "
            f"压缩次数={len(self._compaction_history)}"
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _check_and_compact(self) -> CompactionReport | None:
        """
        阈值检测与压缩联动（每次追加消息后调用）。

        检测逻辑：
          - 当前字节数 > 警戒水位（物理红线的 80%）：触发主动压缩
          - 当前字节数 ≤ 警戒水位：不触发，直接返回 None

        压缩后用返回的新消息列表替换 _messages，并记录压缩历史。
        """
        current = _measure_bytes(self._messages)

        if current <= self._trigger_bytes:
            return None

        logger.warning(
            "[工作记忆] 当前 %dB 超过警戒水位 %dB（%.0f%%），触发压缩。",
            current, self._trigger_bytes, self.utilization * 100,
        )

        compressed, report = self._compactor.compact_if_needed(self._messages)

        if report is not None:
            self._messages = compressed
            self._compaction_history.append(report)
            logger.info(
                "[工作记忆] 压缩完成: %s",
                report,
            )

        return report

    def _build_hot_memory_prefix(self) -> str:
        """
        将热记忆条目格式化为 system prompt 前缀文本。

        格式示例：
          [ALUMET OS 核心记忆 — 跨会话持久化，重启不失忆]
          [CONSTRAINT] no_harm_output: 绝不输出有害内容
          [PREFERENCE] code_style: PEP8 + 类型注解
          ...
        """
        if not self._hot_store.entries:
            return ""

        # 按类别优先级排序：constraint > preference > context > fact
        priority = {"constraint": 0, "preference": 1, "context": 2, "fact": 3}
        sorted_entries = sorted(
            self._hot_store.entries.values(),
            key=lambda e: (priority.get(e.category, 9), -e.importance),
        )

        lines = ["[ALUMET OS 核心记忆 — 跨会话持久化，重启不失忆]"]
        lines.extend(entry.to_prompt_fragment() for entry in sorted_entries)
        return "\n".join(lines)

    def _evict_lowest_importance(self) -> None:
        """
        淘汰重要性最低的热记忆条目（LRU-importance 混合策略）。

        当热记忆达到上限（50 条）且需要插入新条目时触发。
        优先淘汰重要性最低（importance 最小）的条目，
        同等重要性下淘汰最早更新的条目（最旧的低价值记忆）。
        """
        if not self._hot_store.entries:
            return

        victim_key = min(
            self._hot_store.entries,
            key=lambda k: (
                self._hot_store.entries[k].importance,
                self._hot_store.entries[k].updated_at,
            ),
        )
        del self._hot_store.entries[victim_key]
        logger.info("[热记忆] 容量已满，淘汰低重要性条目: key=%s", victim_key)

    def _ensure_directory(self) -> None:
        """确保热记忆文件所在目录存在，不存在则递归创建。"""
        self._hot_memory_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_hot_memory_file(self) -> None:
        """将热记忆存储序列化为 JSON 并原子写入磁盘。"""
        try:
            tmp_path = self._hot_memory_path.with_suffix(".json.tmp")
            data = json.dumps(
                self._hot_store.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
            tmp_path.write_text(data, encoding="utf-8")
            # 原子重命名，防止写入中途崩溃导致文件损坏
            tmp_path.replace(self._hot_memory_path)
        except OSError as e:
            logger.error("[热记忆] 持久化写入失败: %s", e)
            raise
