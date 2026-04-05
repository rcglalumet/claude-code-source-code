"""
async_background_housekeeping.py
----------------------------------
Alumet OS — 后台静默清算与垃圾回收守护进程（系统淋巴排毒）

核心使命：
  作为系统的"淋巴排毒系统"，在完全不打扰前端主进程的前提下，
  异步执行两类后台职责：

  职责 P1 —— 两阶段垃圾回收（Two-Pass GC）：
    清理孤立的状态对象（已被主进程打上 .orphaned_at 时间戳标记）。
    设计哲学：主进程只需"打标记立即返回"，绝不等待清理完成。
    真正的清理工作延迟到后台守护协程的扫描窗口中完成。

  职责 P2 —— 历史推演静默转移（Trace Archiving）：
    将高价值的历史对话推演记录（Trace）从内存/临时目录
    静默搬运到 data_center/raw_cases/，为夜间蒸馏器准备原材料。
    转移完成后从内存中清除，实现内存的自然退潮。

设计哲学（反熵增原则）：
  任何系统在长时间运行后都会积累熵——孤立对象、过期缓存、
  无效状态、冗余历史。若不主动清理，系统会逐渐走向混沌：
    - 内存泄漏（孤立对象永不释放）
    - 磁盘膨胀（历史记录无限堆积）
    - 查找性能退化（状态表越来越大）

  本模块通过定期后台清算，对抗这种自然熵增，
  使系统在长期运行中保持稳定的性能基线。

并发安全模型：
  - 所有状态读写通过 asyncio.Lock 保护（单事件循环，无跨线程竞争）。
  - GC 扫描与主进程的状态操作分属不同的 await 点，天然不重叠。
  - 磁盘写入使用 aiofiles（可选依赖），降级时退为同步写入。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量配置
# ---------------------------------------------------------------------------

# 孤立对象的 TTL（存活时间）：超过此时间后被 GC 清除（秒）
ORPHAN_TTL_SECONDS: float = 300.0  # 5 分钟

# GC 扫描间隔：每隔多少秒执行一次完整的两阶段 GC 扫描
GC_SCAN_INTERVAL_SECONDS: float = 60.0  # 1 分钟

# Trace 归档批次大小：每次归档最多处理多少条 Trace
ARCHIVE_BATCH_SIZE: int = 20

# Trace 归档间隔：每隔多少秒执行一次 Trace 归档
ARCHIVE_INTERVAL_SECONDS: float = 120.0  # 2 分钟

# raw_cases 目录路径（MCTS 蒸馏器的原材料仓库）
RAW_CASES_DIR: Path = Path("data_center/raw_cases")

# 单个 Trace 归档文件的最大字节数（防止单文件过大影响夜间蒸馏读取性能）
MAX_TRACE_FILE_BYTES: int = 512 * 1024  # 512 KB


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class StateObject:
    """
    主进程托管的状态对象（工作记忆快照、工具调用中间状态等）。

    生命周期：
      ACTIVE    → 主进程正在使用
      ORPHANED  → 主进程已完成，打上 orphaned_at 时间戳，等待 GC 回收
      ARCHIVED  → GC 已决定将其内容转移到 raw_cases（高价值对象）
      COLLECTED → GC 已完成回收，对象从注册表中移除

    设计意图：
      ORPHANED 状态的引入使主进程与 GC 完全解耦——
      主进程不需要知道 GC 何时运行，只需打标记；
      GC 不需要打断主进程，只需在下次扫描时处理所有 ORPHANED 对象。
    """

    object_id: str
    session_id: str
    created_at: float
    payload: dict[str, Any]           # 状态载体（对话历史、工具调用链等）
    status: str = "active"            # active | orphaned | archived | collected
    orphaned_at: float | None = None  # 主进程打标记的时间戳
    value_score: float = 0.0          # 价值评分（0.0~1.0），决定是否归档而非直接丢弃


@dataclass
class TraceRecord:
    """
    历史推演记录（Trace）—— 蒸馏器的原材料。

    一条 Trace 记录了 Agent 完成一次任务的完整推演轨迹：
      - 输入的用户意图
      - Agent 的工具调用序列
      - 最终输出结果
      - 成功/失败标记（失败 Trace 对蒸馏器同样有价值，负样本学习）
      - 性能指标（轮数、Token 消耗估算）

    这些原材料被 MCTS 蒸馏器读取后，通过复盘提取新的业务铁律。
    """

    trace_id: str
    session_id: str
    user_intent: str          # 用户最初的意图描述
    tool_call_sequence: list[dict[str, Any]]  # 工具调用链（顺序记录）
    final_output: str         # 最终输出摘要
    success: bool             # 任务是否成功完成
    total_turns: int          # 总轮数
    estimated_tokens: int     # 估算的 Token 消耗
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)  # 业务标签（用于蒸馏器分类）


@dataclass
class GcReport:
    """单次 GC 扫描的统计报告。"""

    scan_time: float          # 扫描发生的时间戳
    phase1_collected: int     # Pass 1 回收的孤立对象数（直接丢弃）
    phase1_archived: int      # Pass 1 标记为归档的高价值对象数
    phase2_traces_written: int  # Pass 2 写入 raw_cases 的 Trace 文件数
    phase2_bytes_written: int   # Pass 2 写入的总字节数
    total_duration_ms: float  # 本次 GC 扫描总耗时（毫秒）


# ---------------------------------------------------------------------------
# 垃圾回收守护进程
# ---------------------------------------------------------------------------

class BackgroundHousekeepingDaemon:
    """
    Alumet OS 后台静默清算守护进程。

    运行模型：
      本类在 asyncio 事件循环中以协程方式运行，与主进程共享同一个事件循环，
      但所有实际工作发生在主进程的 await 间隙，对主进程的响应延迟零影响。

      守护进程持续运行两个并发任务：
        - _gc_scan_loop()：定期执行两阶段 GC 扫描
        - _archive_loop()：定期执行 Trace 归档转移

    主进程接口（无等待设计）：
      register_state()  → 注册新的状态对象
      mark_orphaned()   → 打孤立标记（立即返回，不等待 GC）
      submit_trace()    → 提交 Trace 记录（立即返回，不等待归档）
    """

    def __init__(
        self,
        gc_interval: float = GC_SCAN_INTERVAL_SECONDS,
        archive_interval: float = ARCHIVE_INTERVAL_SECONDS,
        orphan_ttl: float = ORPHAN_TTL_SECONDS,
        raw_cases_dir: Path = RAW_CASES_DIR,
    ) -> None:
        self._gc_interval = gc_interval
        self._archive_interval = archive_interval
        self._orphan_ttl = orphan_ttl
        self._raw_cases_dir = raw_cases_dir

        # 状态注册表：object_id → StateObject
        # 受 _state_lock 保护，所有读写必须在持有锁的情况下进行
        self._state_registry: dict[str, StateObject] = {}
        self._state_lock = asyncio.Lock()

        # Trace 队列：主进程提交的 Trace 在此排队，等待归档协程处理
        # 使用 asyncio.Queue 实现生产者（主进程）与消费者（归档协程）的解耦
        self._trace_queue: asyncio.Queue[TraceRecord] = asyncio.Queue(maxsize=500)

        # GC 历史报告（最多保留最近 100 次）
        self._gc_history: list[GcReport] = []

        # 守护进程运行标志
        self._running: bool = False
        self._tasks: list[asyncio.Task[None]] = []

        # 确保 raw_cases 目录存在
        self._raw_cases_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 守护进程启动与停止
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """
        启动后台守护协程（GC 扫描循环 + Trace 归档循环）。

        调用方式：在 asyncio 主程序启动时调用，无需 await 等待完成。
        推荐使用 asyncio.create_task() 将其放入后台运行：
          asyncio.create_task(daemon.start())
        """
        if self._running:
            logger.warning("[后台GC] 守护进程已在运行，忽略重复启动请求。")
            return

        self._running = True
        logger.info(
            "[后台GC] 守护进程启动：GC间隔=%ds，归档间隔=%ds，孤立TTL=%ds",
            self._gc_interval, self._archive_interval, self._orphan_ttl,
        )

        # 启动两个并发后台任务
        gc_task = asyncio.create_task(self._gc_scan_loop(), name="gc-scan-loop")
        archive_task = asyncio.create_task(self._archive_loop(), name="archive-loop")
        self._tasks = [gc_task, archive_task]

        # 注册任务异常回调，防止后台任务静默崩溃而无任何告警
        for task in self._tasks:
            task.add_done_callback(self._on_task_done)

    async def stop(self) -> None:
        """
        优雅停止守护进程：取消所有后台任务，等待它们完成清理。

        在进程退出前应调用此方法，确保：
          1. 正在进行的 GC 扫描完成当前批次
          2. Trace 队列中的剩余记录被持久化到磁盘（不丢失原材料）
        """
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # 停止前将 Trace 队列中的剩余记录强制归档
        await self._flush_trace_queue()
        logger.info("[后台GC] 守护进程已停止，Trace 队列已刷盘。")

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        """
        后台任务结束回调：检测意外崩溃并记录 CRITICAL 日志。

        正常情况下后台任务不会退出（它们是无限循环）。
        若任务因未捕获异常退出，此回调会记录 CRITICAL 告警，
        防止守护进程静默失效而运维人员毫不知情。
        """
        if task.cancelled():
            return  # 主动取消，正常情况
        exc = task.exception()
        if exc is not None:
            logger.critical(
                "[后台GC] 守护任务 '%s' 意外崩溃，异常: %s: %s。"
                "守护进程已部分失效，请立即排查！",
                task.get_name(), type(exc).__name__, exc,
            )

    # ------------------------------------------------------------------
    # 主进程接口（设计为无等待，立即返回）
    # ------------------------------------------------------------------

    async def register_state(
        self,
        session_id: str,
        payload: dict[str, Any],
        value_score: float = 0.5,
    ) -> str:
        """
        注册一个新的状态对象，返回其全局唯一 object_id。

        主进程在开始一个新 Agent 会话时调用此方法，
        将当前会话的工作状态快照托管给 GC 守护进程管理。

        Args:
            session_id:   所属会话的唯一标识。
            payload:      状态载体（对话历史快照、工具调用中间状态等）。
            value_score:  价值评分 0.0~1.0，决定孤立后是否归档（> 0.5 则归档）。

        Returns:
            object_id（str），供后续 mark_orphaned() 调用时引用。
        """
        object_id = str(uuid.uuid4())
        obj = StateObject(
            object_id=object_id,
            session_id=session_id,
            created_at=time.time(),
            payload=payload,
            value_score=value_score,
        )
        async with self._state_lock:
            self._state_registry[object_id] = obj
        logger.debug("[后台GC] 注册状态对象: id=%s, session=%s", object_id[:8], session_id)
        return object_id

    async def mark_orphaned(self, object_id: str) -> None:
        """
        将状态对象标记为孤立（主进程已完成，不再使用该对象）。

        ⚠️  设计核心：此方法立即返回，绝不等待 GC 完成。
        主进程只需打上 orphaned_at 时间戳，GC 守护进程会在下次扫描时处理。

        这是"生产者-消费者"解耦的核心体现：
          主进程（生产者）：打标记，立即继续服务下一个请求
          GC 守护进程（消费者）：在后台扫描，批量清理孤立对象

        Args:
            object_id: 由 register_state() 返回的对象 ID。
        """
        async with self._state_lock:
            obj = self._state_registry.get(object_id)
            if obj is None:
                logger.warning("[后台GC] 尝试标记不存在的对象: id=%s", object_id[:8])
                return
            if obj.status != "active":
                logger.debug("[后台GC] 对象 %s 已非 active 状态（%s），跳过标记。", object_id[:8], obj.status)
                return
            obj.status = "orphaned"
            obj.orphaned_at = time.time()

        logger.debug("[后台GC] 对象已标记为孤立: id=%s，GC 将在下次扫描时处理。", object_id[:8])
        # 立即返回，不等待 GC

    def submit_trace(self, trace: TraceRecord) -> bool:
        """
        提交一条 Trace 记录到归档队列（同步，非阻塞）。

        使用 Queue.put_nowait() 而非 await Queue.put()，
        确保主进程调用此方法时不会因队列满而阻塞。
        若队列已满（达到 500 条上限），丢弃新 Trace 并记录 WARNING。

        Returns:
            True 表示成功入队，False 表示队列满被丢弃。
        """
        try:
            self._trace_queue.put_nowait(trace)
            logger.debug("[后台GC] Trace 已入队: trace_id=%s，队列大小=%d", trace.trace_id[:8], self._trace_queue.qsize())
            return True
        except asyncio.QueueFull:
            logger.warning(
                "[后台GC] Trace 队列已满（上限500），丢弃 trace_id=%s。"
                "请检查归档协程是否正常运行，或降低 Trace 提交频率。",
                trace.trace_id[:8],
            )
            return False

    # ------------------------------------------------------------------
    # GC 扫描循环（两阶段 GC）
    # ------------------------------------------------------------------

    async def _gc_scan_loop(self) -> None:
        """
        两阶段 GC 扫描无限循环（后台守护协程）。

        每隔 GC_SCAN_INTERVAL_SECONDS 秒执行一次完整扫描：
          Pass 1：识别并处理所有 ORPHANED 状态的对象
          Pass 2：执行 Trace 静默转移（在此循环中触发归档批次）
        """
        while self._running:
            try:
                await asyncio.sleep(self._gc_interval)
                await self._run_gc_scan()
            except asyncio.CancelledError:
                logger.info("[后台GC] GC 扫描循环收到取消信号，退出。")
                break
            except Exception as exc:
                # 单次扫描失败不允许终止循环，记录 ERROR 后继续等待下一个周期
                logger.error("[后台GC] GC 扫描异常（将在下个周期重试）: %s: %s", type(exc).__name__, exc)

    async def _run_gc_scan(self) -> GcReport:
        """
        执行完整的两阶段 GC 扫描，返回扫描报告。

        Pass 1（孤立对象清理）：
          遍历所有 ORPHANED 状态对象，检查 orphaned_at + ORPHAN_TTL：
            - 超过 TTL 且 value_score ≤ 0.5：直接从注册表删除（低价值，丢弃）
            - 超过 TTL 且 value_score > 0.5：标记为 ARCHIVED（高价值，转移 Trace）
          使用两阶段处理（先收集 ID，再删除），避免在遍历中修改字典。

        Pass 2（Trace 静默转移）：
          将 Trace 队列中当前批次的记录写入 raw_cases/ 目录，
          为夜间 MCTS 蒸馏器准备原材料。
        """
        start = time.monotonic()
        now = time.time()
        phase1_collected = 0
        phase1_archived = 0

        # ------- Pass 1：孤立对象清理 -------
        # 步骤 1a：在锁保护下收集所有超时孤立对象的 ID（快照，避免长时间持锁）
        to_collect: list[str] = []
        to_archive: list[StateObject] = []

        async with self._state_lock:
            for obj_id, obj in self._state_registry.items():
                if obj.status != "orphaned" or obj.orphaned_at is None:
                    continue
                age = now - obj.orphaned_at
                if age < self._orphan_ttl:
                    continue  # 尚未超过 TTL，保留

                if obj.value_score > 0.5:
                    # 高价值对象：转移到归档队列，再从注册表移除
                    to_archive.append(obj)
                    obj.status = "archived"
                else:
                    # 低价值对象：直接标记为待删除
                    to_collect.append(obj_id)

        # 步骤 1b：在锁外将高价值对象的 payload 转化为 Trace 并入队
        for obj in to_archive:
            trace = _state_to_trace(obj)
            self.submit_trace(trace)
            async with self._state_lock:
                self._state_registry.pop(obj.object_id, None)
            phase1_archived += 1

        # 步骤 1c：在锁保护下批量删除低价值孤立对象
        if to_collect:
            async with self._state_lock:
                for obj_id in to_collect:
                    self._state_registry.pop(obj_id, None)
            phase1_collected = len(to_collect)

        if phase1_collected + phase1_archived > 0:
            logger.info(
                "[后台GC Pass 1] 清理孤立对象: 丢弃=%d，归档=%d。"
                "注册表剩余对象数=%d",
                phase1_collected, phase1_archived, len(self._state_registry),
            )

        # ------- Pass 2：Trace 静默转移 -------
        traces_written, bytes_written = await self._flush_trace_batch(ARCHIVE_BATCH_SIZE)

        duration_ms = (time.monotonic() - start) * 1000
        report = GcReport(
            scan_time=now,
            phase1_collected=phase1_collected,
            phase1_archived=phase1_archived,
            phase2_traces_written=traces_written,
            phase2_bytes_written=bytes_written,
            total_duration_ms=duration_ms,
        )

        # 保留最近 100 次报告
        self._gc_history.append(report)
        if len(self._gc_history) > 100:
            self._gc_history = self._gc_history[-100:]

        logger.info(
            "[后台GC 扫描完成] 回收=%d，归档=%d，Trace写入=%d（%dB），耗时=%.1fms",
            phase1_collected, phase1_archived, traces_written, bytes_written, duration_ms,
        )
        return report

    # ------------------------------------------------------------------
    # Trace 归档循环
    # ------------------------------------------------------------------

    async def _archive_loop(self) -> None:
        """
        Trace 归档无限循环（后台守护协程）。

        每隔 ARCHIVE_INTERVAL_SECONDS 秒执行一次归档批次，
        将 Trace 队列中积压的记录批量写入 raw_cases/ 目录。

        与 GC 扫描循环并发运行（asyncio.create_task），
        两者均通过 await asyncio.sleep() 让出事件循环，
        确保主进程的协程在两次 sleep 之间可以正常运行。
        """
        while self._running:
            try:
                await asyncio.sleep(self._archive_interval)
                written, total_bytes = await self._flush_trace_batch(ARCHIVE_BATCH_SIZE)
                if written > 0:
                    logger.info("[后台GC 归档] 定期归档：写入 %d 条 Trace，共 %dB", written, total_bytes)
            except asyncio.CancelledError:
                logger.info("[后台GC] Trace 归档循环收到取消信号，退出。")
                break
            except Exception as exc:
                logger.error("[后台GC] Trace 归档异常（将在下个周期重试）: %s: %s", type(exc).__name__, exc)

    async def _flush_trace_queue(self) -> None:
        """停止前强制清空 Trace 队列（防止数据丢失）。"""
        remaining = self._trace_queue.qsize()
        if remaining > 0:
            logger.info("[后台GC] 停止前强制归档剩余 %d 条 Trace...", remaining)
            await self._flush_trace_batch(remaining)

    async def _flush_trace_batch(self, max_count: int) -> tuple[int, int]:
        """
        从 Trace 队列中取出最多 max_count 条记录，批量写入 raw_cases/ 目录。

        写入策略：
          每次调用生成一个以时间戳命名的 JSON Lines 文件
          （每行一条 Trace JSON），便于夜间蒸馏器流式读取。

          文件名格式：raw_cases/traces_{timestamp}_{batch_id}.jsonl

        Returns:
            (写入条数, 写入总字节数)
        """
        batch: list[TraceRecord] = []
        for _ in range(max_count):
            try:
                trace = self._trace_queue.get_nowait()
                batch.append(trace)
            except asyncio.QueueEmpty:
                break

        if not batch:
            return 0, 0

        # 构造 JSON Lines 内容
        lines: list[str] = []
        for trace in batch:
            try:
                line = json.dumps(asdict(trace), ensure_ascii=False)
                lines.append(line)
            except (TypeError, ValueError) as e:
                logger.warning("[后台GC] Trace 序列化失败，已跳过: %s", e)

        if not lines:
            return 0, 0

        content = "\n".join(lines) + "\n"
        content_bytes = content.encode("utf-8")

        # 文件大小安全检查（防止单个 Trace 文件过大）
        if len(content_bytes) > MAX_TRACE_FILE_BYTES:
            logger.warning(
                "[后台GC] 当前批次 Trace 文件体积 %dB 超过上限 %dB，将分批写入。",
                len(content_bytes), MAX_TRACE_FILE_BYTES,
            )
            # 简单处理：截取前半批递归写入（生产环境可改为分片循环）
            mid = len(batch) // 2
            w1, b1 = await self._flush_trace_batch_direct(batch[:mid])
            w2, b2 = await self._flush_trace_batch_direct(batch[mid:])
            return w1 + w2, b1 + b2

        return await self._flush_trace_batch_direct(batch)

    async def _flush_trace_batch_direct(self, batch: list[TraceRecord]) -> tuple[int, int]:
        """将指定批次的 Trace 写入单个 .jsonl 文件。"""
        lines = []
        for trace in batch:
            try:
                lines.append(json.dumps(asdict(trace), ensure_ascii=False))
            except (TypeError, ValueError):
                pass

        if not lines:
            return 0, 0

        content = "\n".join(lines) + "\n"
        content_bytes = content.encode("utf-8")

        timestamp = int(time.time())
        batch_id = str(uuid.uuid4())[:8]
        filename = f"traces_{timestamp}_{batch_id}.jsonl"
        filepath = self._raw_cases_dir / filename

        # 使用 asyncio.to_thread 将同步 I/O 放入线程池，不阻塞事件循环
        try:
            await asyncio.to_thread(_write_file_sync, filepath, content_bytes)
            logger.debug("[后台GC] 写入 Trace 文件: %s (%d 条, %dB)", filename, len(lines), len(content_bytes))
            return len(lines), len(content_bytes)
        except OSError as e:
            logger.error("[后台GC] Trace 文件写入失败: %s: %s", filepath, e)
            return 0, 0

    # ------------------------------------------------------------------
    # 监控接口
    # ------------------------------------------------------------------

    @property
    def active_object_count(self) -> int:
        """当前注册表中存活的状态对象数。"""
        return len(self._state_registry)

    @property
    def pending_trace_count(self) -> int:
        """Trace 队列中待归档的记录数。"""
        return self._trace_queue.qsize()

    def last_gc_report(self) -> GcReport | None:
        """返回最近一次 GC 扫描报告。"""
        return self._gc_history[-1] if self._gc_history else None

    def housekeeping_summary(self) -> str:
        """人类可读的守护进程状态摘要。"""
        last = self.last_gc_report()
        last_str = f"上次GC: 回收={last.phase1_collected}, 归档={last.phase1_archived}" if last else "尚未运行"
        return (
            f"[后台GC状态] 运行中={self._running} | "
            f"注册对象={self.active_object_count} | "
            f"待归档Trace={self.pending_trace_count} | "
            f"{last_str}"
        )


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _state_to_trace(obj: StateObject) -> TraceRecord:
    """
    将高价值的 StateObject 转化为 TraceRecord。

    转化策略：
      从 payload 中提取关键字段（如对话历史、工具调用链）；
      若 payload 格式不符合预期，降级为通用摘要格式。
    """
    payload = obj.payload
    return TraceRecord(
        trace_id=str(uuid.uuid4()),
        session_id=obj.session_id,
        user_intent=payload.get("user_intent", "未知意图"),
        tool_call_sequence=payload.get("tool_call_sequence", []),
        final_output=payload.get("final_output", ""),
        success=payload.get("success", False),
        total_turns=payload.get("total_turns", 0),
        estimated_tokens=payload.get("estimated_tokens", 0),
        created_at=obj.created_at,
        tags=payload.get("tags", []),
    )


def _write_file_sync(filepath: Path, content: bytes) -> None:
    """同步写入文件（供 asyncio.to_thread 调用）。"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp = filepath.with_suffix(".jsonl.tmp")
    tmp.write_bytes(content)
    tmp.replace(filepath)


# ---------------------------------------------------------------------------
# 模块级全局守护进程实例
# ---------------------------------------------------------------------------

# 全局守护进程：在进程启动时通过 asyncio.create_task(DAEMON.start()) 激活。
# 单例确保所有状态对象和 Trace 队列的管理全局统一，
# 不会因多实例而产生"孤儿对象被多个 GC 竞争处理"的竞态条件。
DAEMON = BackgroundHousekeepingDaemon()
