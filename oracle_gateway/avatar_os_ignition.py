"""
oracle_gateway/avatar_os_ignition.py
--------------------------------------
Alumet OS — 系统全局点火与 CLI/TUI 主矩阵

核心使命：
  这是整个 Alumet OS 的 __main__ 绝对入口。

  职责一：依赖注入组装（Dependency Injection Wiring）
    将所有已编写的引擎、沙盒、调度器、记忆体按正确的依赖顺序实例化并连接：
      LLMNetworkGateway（网络层）
      → ContextAutoCompactor（压缩器）
      → WorkingMemoryContext（工作记忆，注入压缩器）
      → KernelApiBus（内核总线，注册所有工具执行器）
      → AsyncToolDispatcher（异步调度器）
      → AgentQueryEngine（Agent 引擎，注入网关与调度器）
      → YoloVetoClassifier（前置过滤器）
      → BackgroundHousekeepingDaemon（后台 GC，异步启动）

  职责二：主控事件循环（Main Agent Loop）
    驱动"用户输入 → YOLO 过滤 → Agent 推理 → HITL 拦截 → 输出"的完整闭环。

  职责三：HITL（Human-In-The-Loop）人工防线
    捕获从 KernelApiBus 向上透传的 ApprovalRequiredException，
    在终端打印红色告警，将进程挂起等待人类 [Y/N] 授权。
    Y → 提交审批令牌，重试操作；N → 记录拒绝，安全降级。

  职责四：earlyInput 缓冲池
    在 Agent 推理期间（大模型"思考"期间），用户可能会继续键入字符。
    若不处理，这些字符会在 Agent 完成后被立即发送，造成终端输入错乱。
    earlyInput 缓冲池通过非阻塞读取捕获这些提前键入的字符，
    在 Agent 完成输出后优先展示，并询问用户是否以此作为下一轮输入。

  职责五：ContextOverflowSignal 应急处理
    捕获 LLMNetworkGateway 抛出的 ContextOverflowSignal，
    调用 ContextAutoCompactor.emergency_compact() 紧急折叠，
    然后静默重试，对用户完全透明。

ANSI 颜色约定（终端输出）：
  红色   → HITL 高危告警、系统错误
  黄色   → 警告、YOLO 拦截通知
  绿色   → Agent 成功输出、系统就绪
  青色   → Agent 思考过程（thinking 字段）
  白色   → 普通系统消息
  重置   → 恢复默认颜色
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import termios
import tty
from dataclasses import dataclass, field
from typing import Any

# 系统内部模块导入
from agentic_workflow.agent_query_engine import (
    AgentQueryEngine,
    AgentResponse,
    FailClosedResult,
)
from agentic_workflow.context_auto_compactor import ContextAutoCompactor
from agentic_workflow.working_memory_context import WorkingMemoryContext
from agentic_workflow.yolo_veto_classifier import YoloVetoClassifier, VetoResult
from async_background_housekeeping import BackgroundHousekeepingDaemon, TraceRecord
from core_engine.kernel_api_bus import (
    KernelApiBus,
    ApprovalRequiredException,
    PermissionDeniedException,
)
from oracle_gateway.llm_network_gateway import (
    LLMNetworkGateway,
    LLMBackendConfig,
    GatewayRequest,
    GatewayResponse,
    ContextOverflowSignal,
    AllBackendsFailedError,
    initialize_gateway,
)
from simulation_sandbox.async_tool_dispatcher import AsyncToolDispatcher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ANSI 终端颜色常量
# ---------------------------------------------------------------------------

class Color:
    """ANSI 转义码颜色常量（仅在 TTY 终端中启用，防止管道输出乱码）。"""

    _ENABLED = sys.stdout.isatty()

    RED     = "\033[91m"  if _ENABLED else ""
    YELLOW  = "\033[93m"  if _ENABLED else ""
    GREEN   = "\033[92m"  if _ENABLED else ""
    CYAN    = "\033[96m"  if _ENABLED else ""
    BLUE    = "\033[94m"  if _ENABLED else ""
    MAGENTA = "\033[95m"  if _ENABLED else ""
    BOLD    = "\033[1m"   if _ENABLED else ""
    DIM     = "\033[2m"   if _ENABLED else ""
    RESET   = "\033[0m"   if _ENABLED else ""

    @classmethod
    def fmt(cls, text: str, *codes: str) -> str:
        """将文本用指定颜色代码包裹（自动在末尾追加 RESET）。"""
        prefix = "".join(codes)
        return f"{prefix}{text}{cls.RESET}" if prefix else text


# ---------------------------------------------------------------------------
# earlyInput 缓冲池
# ---------------------------------------------------------------------------

class EarlyInputBuffer:
    """
    Agent 推理期间的提前输入缓冲池。

    问题背景：
      当 Agent 正在调用 LLM（可能需要数秒至数十秒）时，
      用户可能会继续向终端键入字符（impatient typing）。
      这些字符若未被捕获，将在 Agent 输出后被立即发送给 stdin，
      造成：
        - 意外触发下一轮对话（用户未来得及看完 Agent 的回答）
        - 终端光标位置错乱（字符插入到提示符之前）
        - readline 历史记录混乱

    解决方案：earlyInput 缓冲池
      在 Agent 推理开始时，通过非阻塞读取监听 stdin，
      将用户键入的字符暂存到缓冲池。
      Agent 输出完成后：
        1. 若缓冲池非空，展示捕获的字符："检测到提前输入: [xxx]"
        2. 询问用户是否以此作为下一轮输入（Y/N）
        3. Y → 直接使用，跳过新一轮的输入提示
        4. N → 丢弃，等待正常输入

    实现方式：
      使用 asyncio 的非阻塞 stdin 读取，在 Agent 推理协程并发运行期间
      监听 stdin 的 readable 事件，字符到来时追加到缓冲区。
      仅在 Unix-like 系统上有效（依赖 termios/tty 原始模式）。
    """

    def __init__(self) -> None:
        self._buffer: list[str] = []
        self._collecting: bool = False
        self._task: asyncio.Task[None] | None = None
        self._is_unix = hasattr(termios, "tcgetattr")

    def start_collecting(self) -> None:
        """在 Agent 推理开始时调用，启动后台键盘监听任务。"""
        if not self._is_unix or not sys.stdin.isatty():
            return  # 非 TTY 环境（如 pytest、管道）跳过
        self._buffer.clear()
        self._collecting = True
        self._task = asyncio.create_task(self._collect_loop(), name="early-input-collector")

    def stop_collecting(self) -> str:
        """
        在 Agent 推理完成后调用，停止监听并返回捕获的字符串。

        Returns:
            缓冲池中的完整字符串（可能为空）。
        """
        self._collecting = False
        if self._task and not self._task.done():
            self._task.cancel()
        return "".join(self._buffer)

    async def _collect_loop(self) -> None:
        """
        后台键盘监听协程（仅在 Unix 系统中运行）。

        工作原理：
          将 stdin 切换为"原始模式"（raw mode），
          在此模式下每个按键会立即产生字节而无需等待回车。
          非阻塞读取：通过 asyncio.get_event_loop().add_reader() 注册回调，
          当 stdin 可读时将字节追加到缓冲池。

        安全恢复：
          无论如何，退出时必须恢复 stdin 的原始终端设置（tcsetattr），
          否则终端会陷入原始模式导致后续输入异常。
        """
        loop = asyncio.get_event_loop()
        fd = sys.stdin.fileno()

        try:
            old_settings = termios.tcgetattr(fd)
        except termios.error:
            return  # 非真实终端，跳过

        try:
            tty.setraw(fd)

            future: asyncio.Future[None] = loop.create_future()

            def _on_readable() -> None:
                if not self._collecting:
                    loop.remove_reader(fd)
                    if not future.done():
                        future.set_result(None)
                    return
                try:
                    ch = sys.stdin.read(1)
                    if ch and ch not in ("\r", "\n", "\x03", "\x04"):
                        # 过滤回车、换行、Ctrl-C、Ctrl-D
                        self._buffer.append(ch)
                except Exception:
                    pass

            loop.add_reader(fd, _on_readable)

            while self._collecting:
                await asyncio.sleep(0.05)

            loop.remove_reader(fd)

        except asyncio.CancelledError:
            pass
        finally:
            # 无论如何恢复终端设置，防止终端进入异常状态
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 系统组件容器（依赖注入 Wiring 的结果）
# ---------------------------------------------------------------------------

@dataclass
class AlumOsComponents:
    """
    Alumet OS 全量组件容器。

    所有组件在 _bootstrap_components() 中完成实例化与连接，
    之后通过此容器统一传递给主控循环，避免全局变量。
    """

    gateway: LLMNetworkGateway
    compactor: ContextAutoCompactor
    memory: WorkingMemoryContext
    kernel_bus: KernelApiBus
    dispatcher: AsyncToolDispatcher
    veto: YoloVetoClassifier
    gc_daemon: BackgroundHousekeepingDaemon
    early_input: EarlyInputBuffer = field(default_factory=EarlyInputBuffer)


# ---------------------------------------------------------------------------
# HITL 人工防线
# ---------------------------------------------------------------------------

class HitlInterceptor:
    """
    Human-In-The-Loop 终端拦截器。

    当 KernelApiBus 向上透传 ApprovalRequiredException 时，
    此类负责：
      1. 在终端打印醒目的红色告警（操作描述、风险等级、受影响资源）
      2. 将进程挂起，等待人类输入 [Y/N]
      3. Y → 调用 kernel_bus.submit_approval(token) 并返回 True
      4. N → 记录拒绝，返回 False
    """

    def __init__(self, kernel_bus: KernelApiBus) -> None:
        self._bus = kernel_bus

    async def intercept(self, exc: ApprovalRequiredException) -> bool:
        """
        执行 HITL 拦截流程。

        此方法会挂起 asyncio 事件循环中的主控协程，
        通过 asyncio.to_thread 将阻塞的 input() 调用移到线程池，
        防止事件循环因等待人类输入而完全冻结。

        Returns:
            True  → 人类授权通过，调用方可重试操作
            False → 人类拒绝，调用方应执行安全降级
        """
        self._print_alert(exc)

        try:
            # 将阻塞的 input() 放入线程池，不冻结事件循环
            answer = await asyncio.to_thread(
                self._prompt_human,
                f"{Color.BOLD}{Color.RED}  ► 请输入授权决策 [{Color.GREEN}Y{Color.RED}/{Color.RED}N{Color.RED}]:{Color.RESET} ",
            )
        except (EOFError, KeyboardInterrupt):
            # 非交互环境（如管道输入）或用户 Ctrl-C：默认拒绝
            print(f"\n{Color.fmt('  [自动拒绝] 非交互环境或中断，执行 Fail-Closed 降级。', Color.YELLOW)}")
            return False

        approved = answer.strip().upper() in ("Y", "YES", "是", "确认")

        if approved:
            self._bus.submit_approval(exc.approval_token)
            print(Color.fmt(
                f"  ✅ 已授权。令牌 [{exc.approval_token[:8]}...] 已提交内核总线，重新执行操作...",
                Color.GREEN,
            ))
        else:
            print(Color.fmt(
                f"  ❌ 已拒绝。操作将被取消，系统保持当前安全状态。",
                Color.YELLOW,
            ))

        return approved

    def _print_alert(self, exc: ApprovalRequiredException) -> None:
        """在终端打印醒目的 HITL 红色告警框。"""
        border = Color.fmt("═" * 60, Color.RED, Color.BOLD)
        print(f"\n{border}")
        print(Color.fmt("  ⚠️  高危操作拦截 —— 需要人工授权", Color.RED, Color.BOLD))
        print(border)
        print(Color.fmt(f"  工具名称：{exc.tool_name}", Color.RED))
        print(Color.fmt(f"  风险等级：{exc.risk_level.name}", Color.RED, Color.BOLD))
        print(Color.fmt(f"  操作描述：{exc.operation}", Color.YELLOW))
        print(Color.fmt(f"  申请方：  {exc.requester_id}", Color.DIM))
        if exc.affected_resources:
            print(Color.fmt(f"  受影响资源：", Color.YELLOW))
            for res in exc.affected_resources[:5]:
                print(Color.fmt(f"    • {res}", Color.YELLOW))
        print(Color.fmt(f"  审批令牌：{exc.approval_token[:16]}...", Color.DIM))
        print(border)

    @staticmethod
    def _prompt_human(prompt: str) -> str:
        """同步阻塞式等待人类输入（在线程池中运行）。"""
        return input(prompt)


# ---------------------------------------------------------------------------
# 系统点火函数（依赖注入 Wiring）
# ---------------------------------------------------------------------------

def _bootstrap_components(config: dict[str, Any]) -> AlumOsComponents:
    """
    系统点火：按依赖顺序实例化并连接所有组件。

    依赖关系图（从底层到顶层）：
      LLMBackendConfig ──────────────┐
      ContextAutoCompactor ──────────┤
      WorkingMemoryContext ──────────┤ ──→ AlumOsComponents
      KernelApiBus (+ executors) ────┤
      AsyncToolDispatcher ───────────┤
      YoloVetoClassifier ────────────┤
      BackgroundHousekeepingDaemon ──┘

    Args:
        config: 系统配置字典（从环境变量或配置文件读取）。

    Returns:
        完整组装好的 AlumOsComponents 实例。
    """
    logger.info("[点火] 开始依赖注入组装...")

    # 1. LLM 网络层
    backends = _build_backends_from_config(config)
    gateway = initialize_gateway(backends)
    logger.info("[点火] LLM 网络网关就绪，后端数=%d", len(backends))

    # 2. 压缩器（五级漏斗）
    compactor = ContextAutoCompactor()
    logger.info("[点火] 五级压缩器就绪")

    # 3. 工作记忆（注入压缩器）
    from pathlib import Path
    hot_memory_path = Path(config.get("hot_memory_path", "data_center/system_hot_memory.json"))
    memory = WorkingMemoryContext(compactor=compactor, hot_memory_path=hot_memory_path)
    memory.initialize()
    logger.info("[点火] 工作记忆就绪，热记忆条目=%d", memory.hot_memory_count)

    # 4. 内核 API 总线（注册工具执行器）
    kernel_bus = KernelApiBus()
    _register_builtin_tools(kernel_bus, config)
    logger.info("[点火] 内核总线就绪")

    # 5. 异步工具调度器
    dispatcher = AsyncToolDispatcher()
    logger.info("[点火] 异步调度器就绪")

    # 6. YOLO 前置过滤器
    extra_kws = config.get("extra_dangerous_keywords", [])
    veto = YoloVetoClassifier(extra_dangerous_keywords=extra_kws if extra_kws else None)
    logger.info("[点火] YOLO 过滤器就绪")

    # 7. 后台 GC 守护进程
    from pathlib import Path as P
    raw_cases_dir = P(config.get("raw_cases_dir", "data_center/raw_cases"))
    gc_daemon = BackgroundHousekeepingDaemon(raw_cases_dir=raw_cases_dir)
    logger.info("[点火] 后台 GC 守护进程已配置（将在事件循环启动后激活）")

    logger.info("[点火] ✅ 所有组件装配完成")
    return AlumOsComponents(
        gateway=gateway,
        compactor=compactor,
        memory=memory,
        kernel_bus=kernel_bus,
        dispatcher=dispatcher,
        veto=veto,
        gc_daemon=gc_daemon,
    )


def _build_backends_from_config(config: dict[str, Any]) -> list[LLMBackendConfig]:
    """
    从配置字典（通常来源于环境变量）构建后端配置列表。

    优先级：DeepSeek(0) > Claude(1) > Gemini(2) > 本地 Ollama(99)
    """
    backends: list[LLMBackendConfig] = []

    # DeepSeek（首选：高性价比）
    if os.environ.get("DEEPSEEK_API_KEY") or config.get("deepseek_api_key"):
        backends.append(LLMBackendConfig(
            name="deepseek",
            api_base="https://api.deepseek.com/v1",
            api_key=os.environ.get("DEEPSEEK_API_KEY", config.get("deepseek_api_key", "")),
            model=config.get("deepseek_model", "deepseek-chat"),
            api_type="openai_compat",
            priority=0,
        ))

    # Claude（备选：推理能力强）
    if os.environ.get("ANTHROPIC_API_KEY") or config.get("anthropic_api_key"):
        backends.append(LLMBackendConfig(
            name="claude",
            api_base="https://api.anthropic.com/v1",
            api_key=os.environ.get("ANTHROPIC_API_KEY", config.get("anthropic_api_key", "")),
            model=config.get("claude_model", "claude-3-5-sonnet-20241022"),
            api_type="claude",
            priority=1,
        ))

    # Gemini（第三备选）
    if os.environ.get("GEMINI_API_KEY") or config.get("gemini_api_key"):
        backends.append(LLMBackendConfig(
            name="gemini",
            api_base="https://generativelanguage.googleapis.com/v1beta",
            api_key=os.environ.get("GEMINI_API_KEY", config.get("gemini_api_key", "")),
            model=config.get("gemini_model", "gemini-2.0-flash"),
            api_type="gemini",
            priority=2,
        ))

    # 本地 Ollama（最后兜底，不需要 API Key）
    if not backends or config.get("enable_local_fallback", True):
        backends.append(LLMBackendConfig(
            name="local_ollama",
            api_base=config.get("ollama_base", "http://localhost:11434/v1"),
            model=config.get("ollama_model", "deepseek-r1:8b"),
            api_type="openai_compat",
            priority=99,
        ))

    return backends


def _register_builtin_tools(bus: KernelApiBus, config: dict[str, Any]) -> None:
    """
    向内核总线注册内置工具执行器。

    实际系统中，每个工具对应一个 BaseTool 实现。
    此处注册若干代表性工具，展示注册模式：
      - 只读工具（echo、file_read）：SAFE 级别
      - 写操作工具（file_write）：TRUSTED 级别，受内核路由规则约束
    """
    def echo_executor(name: str, kwargs: dict) -> str:
        return str(kwargs.get("text", ""))

    def file_read_executor(name: str, kwargs: dict) -> str:
        """安全的文件读取（仅允许读 data_center/ 下的文件）。"""
        from pathlib import Path
        path_str = kwargs.get("path", "")
        safe_base = Path("data_center").resolve()
        target = (safe_base / path_str).resolve()
        # 路径安全检查：防止路径穿越
        if not str(target).startswith(str(safe_base)):
            raise PermissionError(f"路径 '{path_str}' 超出允许范围")
        if not target.exists():
            return f"[文件不存在: {path_str}]"
        return target.read_text(encoding="utf-8", errors="replace")[:4096]

    bus.register_executor("echo", echo_executor)
    bus.register_executor("file_read", file_read_executor)
    logger.info("[点火] 内置工具已注册: echo, file_read")


# ---------------------------------------------------------------------------
# Agent 推理适配器（连接 AgentQueryEngine 与 LLMNetworkGateway）
# ---------------------------------------------------------------------------

def _build_llm_caller(
    gateway: LLMNetworkGateway,
    compactor: ContextAutoCompactor,
) -> Any:
    """
    构造 AgentQueryEngine 使用的 llm_caller 函数。

    此函数是网关与引擎之间的适配器：
      - AgentQueryEngine 期望 llm_caller(history: list) → str（原始 JSON 字符串）
      - LLMNetworkGateway 提供 async send(request) → GatewayResponse

    适配器内部处理 ContextOverflowSignal：
      捕获后调用 emergency_compact，静默重试一次。
      若重试后仍溢出，向上透传异常让主控循环处理。
    """
    async def _async_llm_caller(history: list[dict]) -> str:
        request = GatewayRequest(messages=history)

        try:
            response = await gateway.send_with_overflow_recovery(
                request,
                compact_fn=compactor.emergency_compact,
                max_compact_attempts=2,
            )
            return response.content
        except AllBackendsFailedError as e:
            # 所有后端失败：返回 JSON 格式的错误，让引擎的纠偏机制处理
            import json
            return json.dumps({
                "thinking": None,
                "tool_calls": None,
                "finish_reason": "stop",
                "content": f"[系统错误] LLM 网关所有后端均失败: {e}",
            })

    def _sync_wrapper(history: list[dict]) -> str:
        """
        AgentQueryEngine 调用的同步包装器。

        在已有事件循环中，使用 asyncio.run_coroutine_threadsafe 或
        直接在 async 上下文中 await。

        设计选择：
          由于 avatar_os_ignition 本身在 asyncio 中运行，
          此适配器直接返回协程对象，由 run_event_loop 外部 await。
          这要求 AgentQueryEngine 的 llm_caller 协议支持协程，
          实际调用在 _run_agent_turn() 中由 await 发起。
        """
        # 协程对象在异步上下文中被 await 使用
        return _async_llm_caller(history)  # type: ignore[return-value]

    return _async_llm_caller


# ---------------------------------------------------------------------------
# 单轮 Agent 推理（带 HITL 拦截）
# ---------------------------------------------------------------------------

async def _run_agent_turn(
    user_input: str,
    components: AlumOsComponents,
    hitl: HitlInterceptor,
    config: dict[str, Any],
) -> str:
    """
    执行单轮 Agent 推理，返回最终输出文本。

    流程：
      1. 追加用户输入到工作记忆
      2. 构造 llm_caller（连接网关与引擎）
      3. 启动 earlyInput 缓冲池收集
      4. 调用 AgentQueryEngine.run_event_loop()
      5. 停止 earlyInput 收集
      6. 处理结果（FailClosedResult → 降级消息）
      7. 追加 assistant 输出到工作记忆
      8. 返回输出文本

    HITL 拦截：
      ApprovalRequiredException 在此层被捕获，交给 HitlInterceptor 处理。
      若人类授权，携带 approval_token 重试；否则返回拒绝消息。
    """
    # 1. 追加用户输入
    components.memory.append_message({"role": "user", "content": user_input})

    # 2. 获取完整上下文（含热记忆前缀）
    messages = components.memory.get_messages_for_llm()

    # 3. 构造异步 llm_caller
    llm_caller = _build_llm_caller(components.gateway, components.compactor)

    # 工具执行器（通过内核总线路由）
    async def tool_executor_async(tool_call: Any) -> Any:
        try:
            return components.kernel_bus.call(
                tool_name=tool_call.tool_name,
                kwargs=tool_call.arguments,
                requester_id="agent_query_engine",
            )
        except ApprovalRequiredException as exc:
            # HITL 拦截：挂起等待人类授权
            approved = await hitl.intercept(exc)
            if approved:
                # 人类授权：携带令牌重试
                return components.kernel_bus.call(
                    tool_name=tool_call.tool_name,
                    kwargs=tool_call.arguments,
                    requester_id="agent_query_engine",
                    approval_token=exc.approval_token,
                )
            else:
                return {"error": "操作已被人类拒绝，安全降级。"}

    # 构建同步工具执行器（AgentQueryEngine 期望同步接口）
    def sync_tool_executor(tool_call: Any) -> Any:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(tool_executor_async(tool_call))

    # 4. 启动 earlyInput 收集
    components.early_input.start_collecting()

    # 5. 调用 AgentQueryEngine
    try:
        # 构造兼容 AgentQueryEngine 的同步 llm_caller
        def sync_llm_caller(history: list[dict]) -> str:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(llm_caller(history))

        from agentic_workflow.agent_query_engine import AgentQueryEngine
        engine = AgentQueryEngine(
            llm_caller=sync_llm_caller,
            tool_executor=sync_tool_executor,
            max_consecutive_failures=3,
            max_turns=config.get("max_agent_turns", 20),
        )
        result = engine.run_event_loop(messages)
    finally:
        # 6. 停止 earlyInput 收集（无论成功失败都要停止）
        early_chars = components.early_input.stop_collecting()

    # 7. 处理结果
    if isinstance(result, FailClosedResult):
        output_text = (
            f"[系统降级] {result.reason}\n"
            "系统已触发 Fail-Closed 保护，当前任务无法完成。"
            "请稍后重试或简化您的请求。"
        )
    else:
        output_text = result.content or "[Agent 未返回内容]"

    # 8. 追加 assistant 输出到工作记忆
    components.memory.append_message({"role": "assistant", "content": output_text})

    # 9. 处理 earlyInput 缓冲（若有提前输入则展示）
    if early_chars.strip():
        print(Color.fmt(
            f"\n[提前输入缓冲] 检测到 Agent 思考期间的输入: {early_chars!r}",
            Color.DIM,
        ))

    return output_text


# ---------------------------------------------------------------------------
# 主控事件循环（CLI 主矩阵）
# ---------------------------------------------------------------------------

async def main_loop(config: dict[str, Any] | None = None) -> None:
    """
    Alumet OS 主控事件循环（CLI 交互模式）。

    这是系统的"大脑皮层"——驱动完整的用户交互闭环：
      用户输入 → YOLO 过滤 → Agent 推理 → HITL 拦截 → 输出 → 循环

    退出条件：
      - 用户输入 "exit" / "quit" / Ctrl-D (EOF)
      - 用户输入 Ctrl-C（KeyboardInterrupt）
      - 连续 N 次 Agent 失败（可配置）
    """
    if config is None:
        config = {}

    # 点火：组装所有组件
    print(Color.fmt("⚡ Alumet OS 正在点火...", Color.CYAN, Color.BOLD))
    try:
        components = _bootstrap_components(config)
    except Exception as e:
        print(Color.fmt(f"✖ 点火失败: {e}", Color.RED, Color.BOLD))
        raise

    hitl = HitlInterceptor(components.kernel_bus)

    # 启动后台 GC 守护进程
    await components.gc_daemon.start()

    # 打印欢迎横幅
    _print_banner(components)

    consecutive_failures = 0
    max_failures = config.get("max_consecutive_agent_failures", 5)

    try:
        while True:
            # 展示记忆状态（调试模式）
            if config.get("debug_memory"):
                print(Color.fmt(f"\n{components.memory.memory_status()}", Color.DIM))

            # 读取用户输入
            try:
                user_input = await asyncio.to_thread(
                    _read_user_input,
                    Color.fmt("你 ► ", Color.GREEN, Color.BOLD),
                )
            except (EOFError, KeyboardInterrupt):
                print(Color.fmt("\n\n正在优雅退出，保存记忆...", Color.CYAN))
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # 内置命令处理
            if user_input.lower() in ("exit", "quit", "bye", "再见"):
                print(Color.fmt("再见！记忆已保存。", Color.GREEN))
                break
            if user_input.lower() == "/status":
                _print_status(components)
                continue
            if user_input.lower() == "/clear":
                components.memory.clear_session()
                print(Color.fmt("会话记忆已清空。", Color.YELLOW))
                continue
            if user_input.lower() == "/memory":
                _print_hot_memory(components)
                continue

            # YOLO 前置过滤（非对称算力防线）
            veto_result: VetoResult = components.veto.evaluate(user_input)
            if veto_result.vetoed:
                print(Color.fmt(
                    f"\n{Color.YELLOW}[拦截] {veto_result.rejection_message}{Color.RESET}",
                    Color.YELLOW,
                ))
                continue

            # Agent 推理
            print(Color.fmt("\n⏳ Agent 正在推理...", Color.DIM))
            try:
                output = await _run_agent_turn(user_input, components, hitl, config)
                consecutive_failures = 0
                print(f"\n{Color.fmt('Alumet ►', Color.CYAN, Color.BOLD)} {output}\n")

            except PermissionDeniedException as e:
                # 永久拒绝操作（DENIED 级别）
                print(Color.fmt(f"\n[永久拒绝] {e}", Color.RED))
                consecutive_failures += 1

            except Exception as e:
                consecutive_failures += 1
                logger.error("[主控] 推理异常（第 %d/%d 次）: %s", consecutive_failures, max_failures, e)
                print(Color.fmt(f"\n[系统错误] {type(e).__name__}: {e}", Color.RED))

                if consecutive_failures >= max_failures:
                    print(Color.fmt(
                        f"\n连续失败 {consecutive_failures} 次，系统触发 Fail-Closed 保护，退出主控循环。",
                        Color.RED, Color.BOLD,
                    ))
                    break

    finally:
        # 优雅退出：持久化热记忆，停止后台守护进程
        print(Color.fmt("\n正在保存热记忆...", Color.DIM))
        components.memory.flush_hot_memory()
        await components.gc_daemon.stop()
        print(Color.fmt("✅ Alumet OS 已安全关闭。", Color.GREEN))


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _read_user_input(prompt: str) -> str:
    """同步阻塞读取用户输入（在 asyncio.to_thread 中运行）。"""
    return input(prompt)


def _print_banner(components: AlumOsComponents) -> None:
    """打印系统启动横幅。"""
    print(Color.fmt("""
╔══════════════════════════════════════════════════════╗
║          A l u m e t   O S   v 0 . 1 . 0            ║
║     微内核 · 五级压缩 · MCTS蒸馏 · HITL防线         ║
╚══════════════════════════════════════════════════════╝""", Color.CYAN, Color.BOLD))
    print(Color.fmt(
        f"  后端数: {len(components.gateway._backends)} | "
        f"热记忆: {components.memory.hot_memory_count} 条 | "
        f"输入 /status 查看系统状态\n",
        Color.DIM,
    ))


def _print_status(components: AlumOsComponents) -> None:
    """打印系统运行状态摘要。"""
    print(Color.fmt("\n=== 系统状态 ===", Color.CYAN, Color.BOLD))
    print(components.memory.memory_status())
    print(components.gateway.health_report())
    print(components.veto.stats_summary())
    print(components.gc_daemon.housekeeping_summary())
    print()


def _print_hot_memory(components: AlumOsComponents) -> None:
    """打印当前热记忆内容。"""
    entries = components.memory._hot_store.entries
    if not entries:
        print(Color.fmt("  [热记忆为空]", Color.DIM))
        return
    print(Color.fmt(f"\n=== 热记忆（{len(entries)} 条）===", Color.CYAN, Color.BOLD))
    for key, entry in entries.items():
        print(Color.fmt(
            f"  [{entry.category.upper()}] {key}: {entry.value[:80]}",
            Color.DIM,
        ))
    print()


# ---------------------------------------------------------------------------
# 系统入口
# ---------------------------------------------------------------------------

def _load_config() -> dict[str, Any]:
    """
    从环境变量加载系统配置。

    所有敏感配置（API Key）必须通过环境变量注入，
    绝不允许硬编码在代码中或提交到版本控制系统。
    """
    return {
        "hot_memory_path": os.environ.get("ALUMET_HOT_MEMORY_PATH", "data_center/system_hot_memory.json"),
        "raw_cases_dir": os.environ.get("ALUMET_RAW_CASES_DIR", "data_center/raw_cases"),
        "max_agent_turns": int(os.environ.get("ALUMET_MAX_TURNS", "20")),
        "max_consecutive_agent_failures": int(os.environ.get("ALUMET_MAX_FAILURES", "5")),
        "debug_memory": os.environ.get("ALUMET_DEBUG_MEMORY", "").lower() == "true",
        "enable_local_fallback": os.environ.get("ALUMET_LOCAL_FALLBACK", "true").lower() == "true",
        "ollama_base": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "deepseek-r1:8b"),
    }


def run() -> None:
    """
    同步入口函数（供 __main__ 和 CLI 脚本调用）。

    通过 asyncio.run() 启动主控事件循环，
    确保所有 asyncio 资源（任务、队列、锁）在退出时正确清理。
    """
    logging.basicConfig(
        level=logging.INFO if not os.environ.get("ALUMET_DEBUG") else logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        stream=sys.stderr,  # 日志输出到 stderr，不干扰 stdout 的用户界面
    )

    config = _load_config()
    try:
        asyncio.run(main_loop(config))
    except KeyboardInterrupt:
        print(Color.fmt("\n已收到中断信号，Alumet OS 退出。", Color.YELLOW))
    except Exception as e:
        print(Color.fmt(f"\n致命错误: {e}", Color.RED, Color.BOLD))
        logger.exception("主控循环意外崩溃")
        sys.exit(1)


if __name__ == "__main__":
    run()
