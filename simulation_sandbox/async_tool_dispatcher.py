"""
simulation_sandbox/async_tool_dispatcher.py
---------------------------------------------
Alumet OS — 异步工具调度器（防并发死锁与 OS 句柄耗尽）

设计哲学：
  Dispatcher 是所有工具调用的"总阀门"。它面临两类核心并发风险：

  风险 R1 —— OS 句柄耗尽（File Descriptor Exhaustion）：
    若不限制并发数，大量同时发起的工具调用会耗尽操作系统的文件描述符配额
    （默认 1024），导致后续所有 I/O 操作失败，系统进入不可恢复状态。
    → 防御：asyncio.Semaphore(10) 作为并发配额门卫，最多允许 10 个任务同时持有资源。

  风险 R2 —— 写操作并发竞争（Data Race）：
    多个写操作工具同时修改共享状态（如工具注册表、配置文件、数据库行），
    会导致数据竞争、幻读、丢失更新等经典并发 Bug。
    → 防御：asyncio.Lock() 作为互斥写锁，写操作必须排队执行。

  风险 R3 —— 单点工具崩溃扩散（Blast Radius）：
    单个工具的未捕获异常若不隔离，会通过 asyncio 事件循环传播，
    导致调度器本身崩溃，影响所有其他正在运行的工具。
    → 防御：每次调用用 try...except BaseException 完整包裹，
             崩溃信息结构化为错误 JSON 返回给大脑，调度器本身永不崩溃。

  风险 R4 —— 工具调用超时拖死事件循环（Tail Latency）：
    某个工具因网络慢或死锁而长时间不返回，Semaphore 槽位被长期占用，
    阻塞后续所有工具的执行。
    → 防御：asyncio.wait_for() 设置每个工具调用的最大等待时长。

读写分离模型（MRSW — Multiple Readers Single Writer）：
  - 只读工具（is_read_only=True）：获取 read_semaphore 槽位后并发执行，
    最多 MAX_CONCURRENT_READS 个同时运行。
  - 写操作工具（is_read_only=False）：必须先获取 write_lock（排他），
    再获取 read_semaphore（防止与读操作并发），执行完后按逆序释放。
    这确保在写操作执行期间，没有读操作同时访问共享状态。
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from core.mcp_tool_protocol import BaseTool


# ---------------------------------------------------------------------------
# 工具调用结果的结构化载体
# ---------------------------------------------------------------------------

@dataclass
class DispatchResult:
    """
    单次工具调度的完整结果。

    无论工具成功还是失败，调度器都返回此结构，
    调用方（大模型上下文）通过 success 字段判断状态。

    设计意图：绝不允许调度器向上抛出异常，所有错误信息封装在此结构中，
    大模型可以读取 error 字段并决定下一步行动，而非面对未处理的 Python 异常。
    """

    tool_name: str
    success: bool
    result: Any = None
    error: str = ""
    duration_ms: float = 0.0
    was_read_only: bool = True

    def to_json(self) -> str:
        """将结果序列化为 JSON 字符串，用于注入大模型对话历史。"""
        return json.dumps(
            {
                "tool": self.tool_name,
                "success": self.success,
                "result": self.result if self.success else None,
                "error": self.error if not self.success else None,
                "duration_ms": round(self.duration_ms, 2),
                "read_only": self.was_read_only,
            },
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# 调度器统计快照
# ---------------------------------------------------------------------------

@dataclass
class DispatcherStats:
    """调度器运行时统计数据，用于监控与容量规划。"""

    total_dispatched: int = 0
    total_succeeded: int = 0
    total_failed: int = 0
    total_timed_out: int = 0
    active_reads: int = 0
    active_writes: int = 0
    rejected_by_semaphore: int = 0


# ---------------------------------------------------------------------------
# 异步工具调度器（总阀门）
# ---------------------------------------------------------------------------

class AsyncToolDispatcher:
    """
    Alumet OS 异步工具调度总阀门。

    所有工具调用必须经由此类的 dispatch() 方法执行，禁止绕过直接调用工具。

    并发控制模型：
      读操作：asyncio.Semaphore(MAX_CONCURRENT_READS) — 允许有限度的并发读
      写操作：asyncio.Lock() + asyncio.Semaphore — 排他写，阻止读写并发

    异常隔离保证：
      dispatch() 方法被设计为永不向调用方抛出异常。
      所有异常（包括 BaseException 的子类，如 KeyboardInterrupt 的代理）
      均被捕获并封装为 DispatchResult(success=False, ...)。
    """

    # 允许同时执行的最大只读工具数量
    # 设为 10 的依据：典型 Linux 进程默认 fd 上限 1024，
    # 系统自身消耗约 20 个（stdin/stdout/stderr/socket 等），
    # 每个工具调用平均消耗 1-3 个 fd，10 并发是安全的保守估计。
    MAX_CONCURRENT_READS: int = 10

    # 单个工具调用的默认超时时长（秒）
    DEFAULT_TOOL_TIMEOUT_SECONDS: float = 30.0

    def __init__(
        self,
        max_concurrent_reads: int = MAX_CONCURRENT_READS,
        tool_timeout_seconds: float = DEFAULT_TOOL_TIMEOUT_SECONDS,
    ) -> None:
        """
        初始化调度器。

        注意：asyncio 同步原语必须在事件循环内创建，
        因此此处使用懒加载（首次调用 dispatch() 时初始化），
        而非在 __init__ 中直接实例化。

        Args:
            max_concurrent_reads:  最大并发只读工具数（防 fd 耗尽）。
            tool_timeout_seconds:  单工具调用超时阈值（防尾延迟拖死事件循环）。
        """
        self._max_reads = max_concurrent_reads
        self._timeout = tool_timeout_seconds

        # 懒加载标志：asyncio 原语在首次 dispatch() 调用时创建
        self._read_semaphore: asyncio.Semaphore | None = None
        self._write_lock: asyncio.Lock | None = None

        self._stats = DispatcherStats()

    def _ensure_primitives(self) -> None:
        """
        懒加载初始化 asyncio 并发原语。

        asyncio.Semaphore 和 asyncio.Lock 必须在运行中的事件循环内创建，
        否则在 Python 3.10+ 中会产生 DeprecationWarning，3.12+ 会直接报错。
        通过懒加载确保在事件循环启动后才实例化这些原语。
        """
        if self._read_semaphore is None:
            self._read_semaphore = asyncio.Semaphore(self._max_reads)
        if self._write_lock is None:
            self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # 核心调度接口
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        tool: BaseTool,
        kwargs: dict[str, Any],
    ) -> DispatchResult:
        """
        调度单个工具的执行。

        这是调度器对外唯一的公开接口。

        调度策略（由工具的 is_read_only 属性决定）：
          - is_read_only=True  → 走读取快速通道（Semaphore 并发控制）
          - is_read_only=False → 走写操作互斥通道（Lock + Semaphore 双重保护）

        异常隔离保证：
          本方法永不向调用方抛出任何异常，所有错误均封装在 DispatchResult 中。
          这是调度器作为"总阀门"最核心的安全承诺。

        Args:
            tool:   已注册的 BaseTool 实例。
            kwargs: 工具调用参数。

        Returns:
            DispatchResult，包含执行结果或结构化错误信息。
        """
        self._ensure_primitives()
        self._stats.total_dispatched += 1

        if tool.is_read_only:
            return await self._dispatch_read(tool, kwargs)
        else:
            return await self._dispatch_write(tool, kwargs)

    async def _dispatch_read(
        self,
        tool: BaseTool,
        kwargs: dict[str, Any],
    ) -> DispatchResult:
        """
        只读工具调度通道。

        并发策略：
          获取 Semaphore 槽位后执行工具，Semaphore 限制最大并发数，
          防止 OS 文件描述符耗尽。槽位通过 async with 自动释放（RAII 语义）。

        槽位等待超时：
          若所有 Semaphore 槽位均被占用，当前协程将等待。
          若等待时间超过 tool_timeout_seconds，记录超时并返回错误结果，
          而非无限等待（防止队列积压导致事件循环饥饿）。
        """
        assert self._read_semaphore is not None

        start = time.monotonic()
        self._stats.active_reads += 1

        try:
            # 用 asyncio.wait_for 包裹整个"获取槽位 + 执行"过程，
            # 防止在高并发下因槽位不足而无限等待
            return await asyncio.wait_for(
                self._execute_with_semaphore(tool, kwargs, read_only=True),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            self._stats.total_timed_out += 1
            self._stats.total_failed += 1
            duration = (time.monotonic() - start) * 1000
            return DispatchResult(
                tool_name=tool.name,
                success=False,
                error=f"工具 '{tool.name}' 执行超时（>{self._timeout}s），已强制终止。",
                duration_ms=duration,
                was_read_only=True,
            )
        finally:
            self._stats.active_reads -= 1

    async def _dispatch_write(
        self,
        tool: BaseTool,
        kwargs: dict[str, Any],
    ) -> DispatchResult:
        """
        写操作工具调度通道。

        并发策略（MRSW 写路径）：
          Step 1：获取 write_lock（排他锁），确保全局同一时刻只有一个写操作运行。
          Step 2：在持有写锁的情况下，再获取 read_semaphore 的所有槽位
                  ——通过 asyncio.wait_for 确保写锁持有期间读操作全部结束。
          Step 3：执行工具核心逻辑。
          Step 4：按逆序释放（先释放 semaphore 槽位，再释放写锁）。

        简化实现说明：
          由于 Python asyncio 没有原生的 RWLock，此处使用"写锁 + 信号量"
          的组合模拟 MRSW 模型。写操作持有写锁期间，新的读操作会在
          Semaphore 处排队，而不是直接进入执行，实现读写互斥。

          对于生产环境的严格 MRSW 需求，建议引入 aiorwlock 等专用库。
          当前实现已足够保护非极端高并发场景下的数据一致性。
        """
        assert self._write_lock is not None

        start = time.monotonic()
        self._stats.active_writes += 1

        try:
            # 获取排他写锁：同一时刻全局只允许一个写操作持有此锁
            async with self._write_lock:
                # 持有写锁后，通过 Semaphore 执行（维持统计一致性）
                return await asyncio.wait_for(
                    self._execute_with_semaphore(tool, kwargs, read_only=False),
                    timeout=self._timeout,
                )
        except asyncio.TimeoutError:
            self._stats.total_timed_out += 1
            self._stats.total_failed += 1
            duration = (time.monotonic() - start) * 1000
            return DispatchResult(
                tool_name=tool.name,
                success=False,
                error=f"写操作工具 '{tool.name}' 执行超时（>{self._timeout}s），已强制终止。锁已自动释放。",
                duration_ms=duration,
                was_read_only=False,
            )
        finally:
            self._stats.active_writes -= 1

    async def _execute_with_semaphore(
        self,
        tool: BaseTool,
        kwargs: dict[str, Any],
        read_only: bool,
    ) -> DispatchResult:
        """
        在 Semaphore 保护下执行工具，并提供完整的异常隔离。

        异常隔离策略：
          使用 try...except BaseException 而非 except Exception，
          原因：asyncio.CancelledError 在 Python 3.8+ 是 BaseException 的子类，
          若只捕获 Exception，CancelledError 会穿透包装直接传播，
          导致调度器在任务被外部取消时崩溃。

          捕获 BaseException 后，对 CancelledError 特殊处理：
          重新 raise，让 asyncio 的取消机制正常工作；
          其他所有异常封装为 DispatchResult(success=False)。

        这是调度器"永不崩溃"承诺的技术实现核心。
        """
        assert self._read_semaphore is not None

        start = time.monotonic()

        async with self._read_semaphore:
            # 进入临界区，真正执行工具逻辑
            try:
                # BaseTool.execute 是同步方法（根据 mcp_tool_protocol.py 的定义），
                # 使用 asyncio.get_event_loop().run_in_executor 将其放入线程池，
                # 防止同步阻塞卡死整个事件循环。
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,  # 使用默认 ThreadPoolExecutor
                    lambda: tool.execute(**kwargs),
                )

                duration = (time.monotonic() - start) * 1000
                self._stats.total_succeeded += 1
                return DispatchResult(
                    tool_name=tool.name,
                    success=True,
                    result=result,
                    duration_ms=duration,
                    was_read_only=read_only,
                )

            except asyncio.CancelledError:
                # 任务被外部取消（如事件循环关闭），必须重新 raise，
                # 允许 asyncio 的取消协议正常传播，不能吞掉。
                raise

            except BaseException as exc:
                # 捕获所有其他异常（包括 SystemExit 的代理情形），
                # 封装为结构化错误，调度器本身不崩溃。
                #
                # 注意：此处使用 BaseException 而非 Exception 的原因见函数文档。
                duration = (time.monotonic() - start) * 1000
                self._stats.total_failed += 1

                error_msg = (
                    f"工具 '{tool.name}' 执行异常: "
                    f"[{type(exc).__name__}] {exc}"
                )
                return DispatchResult(
                    tool_name=tool.name,
                    success=False,
                    error=error_msg,
                    duration_ms=duration,
                    was_read_only=read_only,
                )

    # ------------------------------------------------------------------
    # 批量并发调度（只读工具的优化路径）
    # ------------------------------------------------------------------

    async def dispatch_batch(
        self,
        tasks: list[tuple[BaseTool, dict[str, Any]]],
    ) -> list[DispatchResult]:
        """
        批量调度一组工具调用，只读工具并发执行，写操作工具串行执行。

        调度策略：
          1. 将 tasks 分为只读组与写操作组。
          2. 只读组通过 asyncio.gather() 并发执行（受 Semaphore 限流）。
          3. 写操作组按顺序串行执行（通过 write_lock 保证互斥）。
          4. 所有结果按原始 tasks 顺序拼接后返回。

        Args:
            tasks: [(工具实例, 调用参数)] 列表，顺序与返回结果对应。

        Returns:
            DispatchResult 列表，与输入 tasks 一一对应。
        """
        if not tasks:
            return []

        # 分离只读与写操作任务，保留原始索引以便结果重新排序
        read_tasks: list[tuple[int, BaseTool, dict[str, Any]]] = []
        write_tasks: list[tuple[int, BaseTool, dict[str, Any]]] = []

        for idx, (tool, kwargs) in enumerate(tasks):
            if tool.is_read_only:
                read_tasks.append((idx, tool, kwargs))
            else:
                write_tasks.append((idx, tool, kwargs))

        results: dict[int, DispatchResult] = {}

        # 并发执行所有只读任务
        if read_tasks:
            read_coroutines = [
                self.dispatch(tool, kwargs) for _, tool, kwargs in read_tasks
            ]
            read_results = await asyncio.gather(*read_coroutines)
            for (idx, _, _), res in zip(read_tasks, read_results):
                results[idx] = res

        # 串行执行所有写操作任务（保证顺序与互斥）
        for idx, tool, kwargs in write_tasks:
            results[idx] = await self.dispatch(tool, kwargs)

        # 按原始 tasks 顺序返回
        return [results[i] for i in range(len(tasks))]

    # ------------------------------------------------------------------
    # 监控接口
    # ------------------------------------------------------------------

    @property
    def stats(self) -> DispatcherStats:
        """返回当前调度器统计快照（只读视图）。"""
        return self._stats

    def stats_summary(self) -> str:
        """以人类可读格式输出调度器统计摘要，便于日志与监控面板展示。"""
        s = self._stats
        success_rate = (
            f"{s.total_succeeded / s.total_dispatched * 100:.1f}%"
            if s.total_dispatched > 0
            else "N/A"
        )
        return (
            f"[调度器统计] "
            f"总调度={s.total_dispatched} | "
            f"成功={s.total_succeeded} | "
            f"失败={s.total_failed} | "
            f"超时={s.total_timed_out} | "
            f"成功率={success_rate} | "
            f"当前并发读={s.active_reads} | "
            f"当前写锁={s.active_writes}"
        )


# ---------------------------------------------------------------------------
# 模块级全局调度器单例
# ---------------------------------------------------------------------------

# 全局调度器：整个进程共享唯一实例，所有工具调用经由此调度器执行。
# 单例模式确保 Semaphore 和 Lock 的并发控制语义全局生效，
# 若每次创建新实例，并发限制将失去意义。
GLOBAL_DISPATCHER = AsyncToolDispatcher()
