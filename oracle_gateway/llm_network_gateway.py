"""
oracle_gateway/llm_network_gateway.py
---------------------------------------
Alumet OS — 全局 LLM 网络层与 413 应急压缩钩子

核心使命：
  封装对所有大模型后端（DeepSeek / Claude / Gemini / OpenAI 兼容接口）
  的 HTTP / SDK 调用，提供统一的防御性网络接口。

  本模块是系统与"外部神经网络"之间的唯一通信管道，
  承担以下三项核心防线职责：

  防线 1 —— 指数退避重试（Exponential Backoff）：
    面对瞬时网络抖动、服务端限流（429）、临时不可用（503）等
    可恢复性错误，自动执行指数退避重试（最多 N 次），
    对上层调用方完全透明——调用方看不到临时故障，只看到最终结果。

  防线 2 —— ContextOverflowSignal 响应式压缩钩子：
    捕获 HTTP 413 Payload Too Large 或 API 语义错误
    context_length_exceeded / max_tokens 超限时，
    【绝对禁止崩溃】——抛出特定的 ContextOverflowSignal 异常，
    通知上层主控循环（avatar_os_ignition.py）去触发五级压缩器
    进行紧急折叠，然后静默重试，实现"服务永不因上下文溢出而中断"。

  防线 3 —— 后端健康管理（Circuit Breaker 熔断）：
    追踪每个后端的连续失败次数，超过阈值时暂时将该后端标记为
    "熔断状态"，自动切换到备用后端（Fallback），
    防止对已知故障后端的无效重试消耗算力预算。

设计哲学：
  外部 LLM API 是系统中最不可靠的组件——它们会限流、超时、
  返回乱码、突然涨价、改变响应格式。
  一个成熟的 Agentic 系统必须将"LLM API 不可靠"视为常态，
  而非异常，并在架构层面内建对应的韧性机制。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 指数退避重试参数
# ---------------------------------------------------------------------------

# 最大重试次数（首次尝试不计入，总请求次数 = 1 + MAX_RETRIES）
MAX_RETRIES: int = 4

# 初始退避基础时间（秒）：第 k 次重试等待 BASE_BACKOFF * 2^k 秒
BASE_BACKOFF_SECONDS: float = 1.0

# 最大单次退避时间（秒），防止退避时间无限增长
MAX_BACKOFF_SECONDS: float = 32.0

# 退避抖动因子：在退避时间上叠加随机扰动，防止"惊群效应"
# 实际等待时间 = backoff * (1 + jitter * random(-1, 1))
BACKOFF_JITTER: float = 0.2

# 可重试的 HTTP 状态码
RETRYABLE_HTTP_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# 触发 ContextOverflowSignal 的 HTTP 状态码
CONTEXT_OVERFLOW_HTTP_CODES: frozenset[int] = frozenset({413})

# 触发 ContextOverflowSignal 的 API 错误类型关键词
CONTEXT_OVERFLOW_ERROR_KEYWORDS: tuple[str, ...] = (
    "context_length_exceeded",
    "max_tokens",
    "context window",
    "too many tokens",
    "prompt is too long",
    "input too long",
    "context_window_exceeded",
    "maximum context length",
    "token limit",
)

# ---------------------------------------------------------------------------
# 熔断器参数
# ---------------------------------------------------------------------------

# 连续失败多少次后触发熔断
CIRCUIT_BREAKER_THRESHOLD: int = 5

# 熔断状态持续时间（秒），超过后自动尝试恢复（半开状态）
CIRCUIT_BREAKER_RESET_SECONDS: float = 60.0


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------

class GatewayError(Exception):
    """网关基础异常，所有网关相关异常的父类。"""


class ContextOverflowSignal(GatewayError):
    """
    上下文溢出信号异常（响应式应急压缩钩子的触发器）。

    当 LLM API 返回 413 / context_length_exceeded 时抛出此异常。
    上层主控循环（avatar_os_ignition.py）捕获此信号后：
      1. 调用 ContextAutoCompactor.emergency_compact() 紧急折叠
      2. 用压缩后的消息列表重新发起请求
      3. 对最终用户完全透明（不显示任何错误）

    携带信息：
      - backend_name：触发溢出的后端名称（便于切换后端重试）
      - overflow_type：溢出类型（http_413 / api_error / token_limit）
      - retry_after_compact：建议是否压缩后重试
    """

    def __init__(
        self,
        message: str,
        backend_name: str,
        overflow_type: str = "unknown",
        retry_after_compact: bool = True,
    ) -> None:
        super().__init__(message)
        self.backend_name = backend_name
        self.overflow_type = overflow_type
        self.retry_after_compact = retry_after_compact


class AllBackendsFailedError(GatewayError):
    """所有后端均已失败或熔断，无法完成请求。"""


class BackendCircuitOpenError(GatewayError):
    """指定后端处于熔断状态，请求被拒绝。"""


# ---------------------------------------------------------------------------
# 后端配置与状态
# ---------------------------------------------------------------------------

class BackendStatus(Enum):
    """后端健康状态（Circuit Breaker 状态机）。"""
    HEALTHY   = "healthy"    # 正常
    HALF_OPEN = "half_open"  # 熔断后的探测状态（允许一次试探请求）
    OPEN      = "open"       # 熔断中（拒绝所有请求）


@dataclass
class LLMBackendConfig:
    """
    单个 LLM 后端的配置描述。

    支持所有 OpenAI 兼容接口（DeepSeek、本地 Ollama、Azure OpenAI 等），
    以及通过 api_type 标识的原生接口（claude、gemini）。
    """

    name: str                              # 后端唯一名称（如 "deepseek", "claude"）
    api_base: str                          # API 基础 URL
    api_key: str = ""                      # API 密钥（从环境变量注入，不硬编码）
    model: str = "gpt-4o"                  # 模型名称
    api_type: str = "openai_compat"        # 接口类型：openai_compat | claude | gemini
    timeout_seconds: float = 60.0          # 单次请求超时（秒）
    max_tokens: int = 4096                 # 最大输出 Token 数
    temperature: float = 0.7               # 采样温度
    priority: int = 0                      # 优先级（越低越优先，用于后端选择）


@dataclass
class BackendRuntimeState:
    """后端运行时动态状态（熔断器状态）。"""

    consecutive_failures: int = 0          # 连续失败次数
    status: BackendStatus = BackendStatus.HEALTHY
    last_failure_time: float = 0.0
    total_requests: int = 0
    total_failures: int = 0
    total_context_overflows: int = 0


# ---------------------------------------------------------------------------
# LLM 网关请求/响应数据结构
# ---------------------------------------------------------------------------

@dataclass
class GatewayRequest:
    """标准化网关请求，屏蔽不同后端的接口差异。"""

    messages: list[dict[str, Any]]         # 标准 OpenAI 格式消息列表
    stream: bool = False                   # 是否流式输出（当前实现为非流式）
    extra_params: dict[str, Any] = field(default_factory=dict)  # 后端特定参数扩展


@dataclass
class GatewayResponse:
    """标准化网关响应。"""

    content: str                           # 大模型输出的文本内容
    backend_name: str                      # 实际使用的后端名称
    model: str                             # 实际使用的模型名称
    usage: dict[str, int] = field(default_factory=dict)  # Token 使用量
    raw_response: dict[str, Any] = field(default_factory=dict)  # 原始响应体
    latency_ms: float = 0.0               # 端到端延迟（毫秒）


# ---------------------------------------------------------------------------
# LLM 网络网关主体
# ---------------------------------------------------------------------------

class LLMNetworkGateway:
    """
    Alumet OS 全局 LLM 网络网关。

    职责：
      1. 管理多个 LLM 后端的配置与健康状态
      2. 执行指数退避重试（对上层透明）
      3. 检测 413 / context_length_exceeded 并抛出 ContextOverflowSignal
      4. 维护 Circuit Breaker 状态机，自动切换故障后端
      5. 提供统一的 send() 接口，屏蔽后端差异

    推荐使用方式（avatar_os_ignition.py 中的主控循环）：
      try:
          response = await gateway.send(request)
      except ContextOverflowSignal as sig:
          # 触发五级压缩器紧急折叠
          messages, _ = compactor.emergency_compact(messages)
          request.messages = messages
          response = await gateway.send(request)  # 压缩后重试
    """

    def __init__(
        self,
        backends: list[LLMBackendConfig] | None = None,
        max_retries: int = MAX_RETRIES,
        base_backoff: float = BASE_BACKOFF_SECONDS,
        circuit_threshold: int = CIRCUIT_BREAKER_THRESHOLD,
        circuit_reset: float = CIRCUIT_BREAKER_RESET_SECONDS,
    ) -> None:
        """
        Args:
            backends:          LLM 后端配置列表（按 priority 排序后使用）。
                               若为 None，使用默认的 DeepSeek 本地兼容配置。
            max_retries:       最大重试次数（不含首次尝试）。
            base_backoff:      指数退避基础时间（秒）。
            circuit_threshold: 连续失败触发熔断的次数阈值。
            circuit_reset:     熔断状态自动重置的等待时间（秒）。
        """
        if backends is None:
            # 默认单后端配置（供开发环境快速启动使用）
            backends = [
                LLMBackendConfig(
                    name="default",
                    api_base="http://localhost:11434/v1",  # Ollama 默认端口
                    model="deepseek-r1:8b",
                    api_type="openai_compat",
                )
            ]

        # 按优先级排序（priority 越小越优先）
        self._backends: list[LLMBackendConfig] = sorted(backends, key=lambda b: b.priority)
        self._states: dict[str, BackendRuntimeState] = {
            b.name: BackendRuntimeState() for b in self._backends
        }
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        self._circuit_threshold = circuit_threshold
        self._circuit_reset = circuit_reset

    # ------------------------------------------------------------------
    # 核心公开接口
    # ------------------------------------------------------------------

    async def send(self, request: GatewayRequest) -> GatewayResponse:
        """
        向可用后端发送请求，内建指数退避重试与熔断切换。

        调用流程：
          1. 按优先级遍历后端，跳过熔断中的后端
          2. 对选定后端执行带重试的请求（_send_with_retry）
          3. 捕获 ContextOverflowSignal 直接向上透传（不重试，交给调用方压缩后处理）
          4. 若所有后端均失败，抛出 AllBackendsFailedError

        Args:
            request: 标准化网关请求。

        Returns:
            GatewayResponse，携带大模型输出内容与元数据。

        Raises:
            ContextOverflowSignal: 上下文溢出，需要调用方压缩后重试。
            AllBackendsFailedError: 所有后端均失败或熔断。
        """
        last_error: Exception | None = None

        for backend in self._backends:
            state = self._states[backend.name]

            # 检查熔断状态
            if not self._is_backend_available(backend.name):
                logger.warning("[网关] 后端 '%s' 处于熔断状态，跳过。", backend.name)
                continue

            try:
                response = await self._send_with_retry(backend, state, request)
                # 成功：重置熔断器
                self._on_success(backend.name)
                return response

            except ContextOverflowSignal:
                # 上下文溢出信号：直接向上透传，不重试其他后端
                # （其他后端也会有同样的溢出，应先压缩再重试同一后端）
                state.total_context_overflows += 1
                raise

            except GatewayError as e:
                last_error = e
                logger.error(
                    "[网关] 后端 '%s' 最终失败: %s，尝试下一个后端。",
                    backend.name, e,
                )
                continue

        raise AllBackendsFailedError(
            f"所有 {len(self._backends)} 个 LLM 后端均已失败或熔断。"
            f"最后一个错误: {last_error}"
        )

    async def send_with_overflow_recovery(
        self,
        request: GatewayRequest,
        compact_fn: Any,  # Callable[[list], tuple[list, Any]]
        max_compact_attempts: int = 2,
    ) -> GatewayResponse:
        """
        带自动压缩恢复的发送接口（便捷封装）。

        封装了"捕获 ContextOverflowSignal → 调用压缩器 → 重试"的完整流程，
        供调用方在无需关心压缩细节时直接使用。

        Args:
            request:              标准化请求。
            compact_fn:           压缩函数，签名: (messages) → (compressed_messages, report)
                                  通常传入 compactor.emergency_compact。
            max_compact_attempts: 最多触发几次压缩重试（防止死循环）。

        Returns:
            GatewayResponse

        Raises:
            AllBackendsFailedError:  所有后端均失败。
            GatewayError:            压缩后仍然溢出。
        """
        for attempt in range(max_compact_attempts + 1):
            try:
                return await self.send(request)
            except ContextOverflowSignal as sig:
                if attempt >= max_compact_attempts:
                    logger.error(
                        "[网关] 已达最大压缩重试次数 %d，无法恢复上下文溢出。",
                        max_compact_attempts,
                    )
                    raise

                logger.warning(
                    "[网关] 捕获 ContextOverflowSignal（第 %d/%d 次），"
                    "触发应急压缩后重试。后端=%s",
                    attempt + 1, max_compact_attempts, sig.backend_name,
                )

                # 调用外部压缩函数（通常是 ContextAutoCompactor.emergency_compact）
                compressed_messages, compact_report = compact_fn(request.messages)
                request = GatewayRequest(
                    messages=compressed_messages,
                    stream=request.stream,
                    extra_params=request.extra_params,
                )
                logger.info(
                    "[网关] 压缩完成，压缩后消息数=%d，重试请求...",
                    len(compressed_messages),
                )

        # 理论上不可达（循环结束前一定 return 或 raise）
        raise GatewayError("send_with_overflow_recovery: 意外退出循环")

    # ------------------------------------------------------------------
    # 带重试的单后端请求
    # ------------------------------------------------------------------

    async def _send_with_retry(
        self,
        backend: LLMBackendConfig,
        state: BackendRuntimeState,
        request: GatewayRequest,
    ) -> GatewayResponse:
        """
        对单个后端执行指数退避重试请求。

        重试策略：
          - 可重试错误（429/5xx/网络超时）：指数退避后重试
          - ContextOverflowSignal（413/context_length_exceeded）：
            立即向上透传，不重试（等待压缩后由调用方重试）
          - 不可重试错误（400/401/403）：立即失败，不重试

        指数退避公式：
          wait = min(BASE_BACKOFF * 2^attempt, MAX_BACKOFF) * (1 + jitter)
          jitter ∈ [-BACKOFF_JITTER, +BACKOFF_JITTER]

        Args:
            backend: 后端配置。
            state:   后端运行时状态（用于熔断器更新）。
            request: 标准化请求。

        Returns:
            GatewayResponse

        Raises:
            ContextOverflowSignal: 上下文溢出（不在此层重试）。
            GatewayError:          所有重试均失败后抛出。
        """
        state.total_requests += 1
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                # 计算本次退避时间（指数退避 + 抖动）
                wait = self._compute_backoff(attempt)
                logger.info(
                    "[网关] 后端 '%s' 第 %d/%d 次重试，等待 %.2fs...",
                    backend.name, attempt, self._max_retries, wait,
                )
                await asyncio.sleep(wait)

            try:
                start = time.monotonic()
                response = await self._dispatch_request(backend, request)
                latency_ms = (time.monotonic() - start) * 1000
                response.latency_ms = latency_ms
                response.backend_name = backend.name

                logger.info(
                    "[网关] 后端 '%s' 请求成功，延迟=%.0fms，输出长度=%d字符",
                    backend.name, latency_ms, len(response.content),
                )
                return response

            except ContextOverflowSignal:
                # 上下文溢出：不在重试层处理，直接透传给上层
                self._on_failure(backend.name)
                raise

            except _RetryableError as e:
                # 可重试错误：记录并继续下一次重试
                last_error = e
                self._on_failure(backend.name)
                logger.warning(
                    "[网关] 后端 '%s' 可重试错误（第 %d/%d 次）: %s",
                    backend.name, attempt + 1, self._max_retries + 1, e,
                )
                continue

            except GatewayError as e:
                # 不可重试错误（如 401 认证失败）：立即终止重试
                self._on_failure(backend.name)
                raise

        # 所有重试均失败
        raise GatewayError(
            f"后端 '{backend.name}' 在 {self._max_retries + 1} 次尝试后最终失败: {last_error}"
        )

    def _compute_backoff(self, attempt: int) -> float:
        """
        计算第 attempt 次重试的退避等待时间（秒）。

        公式：wait = min(base * 2^attempt, max_backoff) * uniform(1-j, 1+j)
        其中 j = BACKOFF_JITTER（默认 0.2）

        抖动的目的：
          多个 Agent 实例同时重试时，若退避时间完全相同，
          它们会在同一时刻向服务端发起请求，造成"惊群效应"（Thundering Herd）。
          叠加随机抖动使各实例的重试时间错开，避免流量尖峰。
        """
        import random
        base_wait = min(self._base_backoff * (2 ** attempt), MAX_BACKOFF_SECONDS)
        jitter = 1.0 + BACKOFF_JITTER * random.uniform(-1.0, 1.0)
        return base_wait * jitter

    # ------------------------------------------------------------------
    # 后端请求分发（适配不同 API 格式）
    # ------------------------------------------------------------------

    async def _dispatch_request(
        self,
        backend: LLMBackendConfig,
        request: GatewayRequest,
    ) -> GatewayResponse:
        """
        根据 backend.api_type 将请求分发到对应的适配器。

        当前支持：
          openai_compat → OpenAI 兼容接口（DeepSeek、Ollama、Azure 等）
          claude        → Anthropic Claude 原生接口（预留，结构完整）
          gemini        → Google Gemini 原生接口（预留，结构完整）

        设计原则：
          所有适配器最终都调用 _http_post()，这是唯一真实发出网络请求的函数。
          不同适配器只负责构造不同格式的请求体与解析不同格式的响应体。
        """
        if backend.api_type == "openai_compat":
            return await self._call_openai_compat(backend, request)
        elif backend.api_type == "claude":
            return await self._call_claude(backend, request)
        elif backend.api_type == "gemini":
            return await self._call_gemini(backend, request)
        else:
            raise GatewayError(f"不支持的 api_type: '{backend.api_type}'")

    async def _call_openai_compat(
        self,
        backend: LLMBackendConfig,
        request: GatewayRequest,
    ) -> GatewayResponse:
        """
        OpenAI 兼容接口适配器（兼容 DeepSeek / Ollama / Azure / 本地模型）。

        请求格式：标准 OpenAI Chat Completions API
        错误格式：OpenAI 错误响应体（含 error.code / error.message）
        """
        url = f"{backend.api_base.rstrip('/')}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if backend.api_key:
            headers["Authorization"] = f"Bearer {backend.api_key}"

        body: dict[str, Any] = {
            "model": backend.model,
            "messages": request.messages,
            "max_tokens": backend.max_tokens,
            "temperature": backend.temperature,
            **request.extra_params,
        }

        raw = await self._http_post(url, headers, body, backend.timeout_seconds, backend.name)

        # 解析响应
        try:
            content = raw["choices"][0]["message"]["content"]
            usage = raw.get("usage", {})
            return GatewayResponse(
                content=content,
                backend_name=backend.name,
                model=raw.get("model", backend.model),
                usage=usage,
                raw_response=raw,
            )
        except (KeyError, IndexError, TypeError) as e:
            raise GatewayError(
                f"后端 '{backend.name}' 响应格式解析失败: {e}，原始响应: {str(raw)[:200]}"
            )

    async def _call_claude(
        self,
        backend: LLMBackendConfig,
        request: GatewayRequest,
    ) -> GatewayResponse:
        """
        Anthropic Claude 原生接口适配器（预留扩展位）。

        Claude 的消息格式与 OpenAI 基本兼容，但 system 消息需要单独传递。
        此处提供结构完整的实现框架，具体参数可按 Anthropic API 文档调整。
        """
        url = f"{backend.api_base.rstrip('/')}/messages"
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": backend.api_key,
        }

        # 分离 system 消息（Claude API 单独传递 system 字段）
        system_content = ""
        user_messages = []
        for msg in request.messages:
            if msg.get("role") == "system":
                system_content += msg.get("content", "") + "\n"
            else:
                user_messages.append(msg)

        body: dict[str, Any] = {
            "model": backend.model,
            "max_tokens": backend.max_tokens,
            "messages": user_messages,
            **request.extra_params,
        }
        if system_content.strip():
            body["system"] = system_content.strip()

        raw = await self._http_post(url, headers, body, backend.timeout_seconds, backend.name)

        try:
            content = raw["content"][0]["text"]
            usage = {
                "prompt_tokens": raw.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": raw.get("usage", {}).get("output_tokens", 0),
            }
            return GatewayResponse(
                content=content,
                backend_name=backend.name,
                model=raw.get("model", backend.model),
                usage=usage,
                raw_response=raw,
            )
        except (KeyError, IndexError, TypeError) as e:
            raise GatewayError(f"Claude 响应解析失败: {e}")

    async def _call_gemini(
        self,
        backend: LLMBackendConfig,
        request: GatewayRequest,
    ) -> GatewayResponse:
        """
        Google Gemini 原生接口适配器（预留扩展位）。

        Gemini 使用 generateContent 端点，消息格式与 OpenAI 不同（role="model"）。
        """
        url = (
            f"{backend.api_base.rstrip('/')}/models/{backend.model}"
            f":generateContent?key={backend.api_key}"
        )
        headers = {"Content-Type": "application/json"}

        # 将 OpenAI 格式消息转换为 Gemini 格式
        gemini_parts = []
        for msg in request.messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            gemini_parts.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}],
            })

        body: dict[str, Any] = {
            "contents": gemini_parts,
            "generationConfig": {
                "maxOutputTokens": backend.max_tokens,
                "temperature": backend.temperature,
            },
            **request.extra_params,
        }

        raw = await self._http_post(url, headers, body, backend.timeout_seconds, backend.name)

        try:
            content = raw["candidates"][0]["content"]["parts"][0]["text"]
            return GatewayResponse(
                content=content,
                backend_name=backend.name,
                model=backend.model,
                raw_response=raw,
            )
        except (KeyError, IndexError, TypeError) as e:
            raise GatewayError(f"Gemini 响应解析失败: {e}")

    # ------------------------------------------------------------------
    # 底层 HTTP 请求（单次，不含重试逻辑）
    # ------------------------------------------------------------------

    async def _http_post(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout: float,
        backend_name: str,
    ) -> dict[str, Any]:
        """
        执行单次 HTTP POST 请求，解析 JSON 响应。

        使用 asyncio.to_thread 将同步的 urllib 请求放入线程池，
        避免阻塞 asyncio 事件循环。

        生产环境升级建议：
          替换为 aiohttp.ClientSession 或 httpx.AsyncClient，
          获得真正的异步 I/O，消除线程池的上下文切换开销。
          当前使用 urllib 是为了保持零外部依赖（stdlib only）。

        错误分类：
          - HTTP 413：抛出 ContextOverflowSignal
          - HTTP 429/5xx：抛出 _RetryableError（触发重试）
          - HTTP 400/401/403/404：抛出 GatewayError（不重试）
          - 响应体含 context overflow 关键词：抛出 ContextOverflowSignal
          - 网络超时：抛出 _RetryableError
        """
        raw_body = json.dumps(body, ensure_ascii=False).encode("utf-8")

        def _do_request() -> tuple[int, bytes]:
            """同步执行 HTTP 请求（在线程池中运行）。"""
            req = urllib.request.Request(url, data=raw_body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status, resp.read()
            except urllib.error.HTTPError as e:
                return e.code, e.read()
            except urllib.error.URLError as e:
                raise _NetworkError(f"网络连接失败: {e.reason}") from e

        try:
            status_code, response_body = await asyncio.to_thread(_do_request)
        except _NetworkError as e:
            raise _RetryableError(f"网络超时或连接失败: {e}") from e
        except Exception as e:
            raise _RetryableError(f"HTTP 请求意外失败: {e}") from e

        # 解析响应体
        try:
            response_data: dict[str, Any] = json.loads(response_body.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, ValueError):
            response_data = {"_raw": response_body.decode("utf-8", errors="replace")[:500]}

        # 错误分类处理
        if status_code in CONTEXT_OVERFLOW_HTTP_CODES:
            # HTTP 413：上下文溢出（Payload Too Large）
            raise ContextOverflowSignal(
                message=f"后端 '{backend_name}' 返回 HTTP 413 Payload Too Large",
                backend_name=backend_name,
                overflow_type="http_413",
            )

        if status_code in RETRYABLE_HTTP_CODES:
            # 可重试错误（限流/服务临时不可用）
            retry_after = _extract_retry_after(response_data)
            raise _RetryableError(
                f"HTTP {status_code}（可重试），backend={backend_name}"
                + (f"，Retry-After={retry_after}s" if retry_after else "")
            )

        if status_code >= 400:
            # 检查响应体是否含上下文溢出语义错误
            error_msg = _extract_error_message(response_data).lower()
            if any(kw in error_msg for kw in CONTEXT_OVERFLOW_ERROR_KEYWORDS):
                raise ContextOverflowSignal(
                    message=f"后端 '{backend_name}' 报告上下文溢出: {error_msg[:100]}",
                    backend_name=backend_name,
                    overflow_type="api_error",
                )
            # 其他 4xx 错误（认证失败、参数错误等）：不重试
            raise GatewayError(
                f"后端 '{backend_name}' 返回 HTTP {status_code}: {error_msg[:200]}"
            )

        return response_data

    # ------------------------------------------------------------------
    # 熔断器状态机
    # ------------------------------------------------------------------

    def _is_backend_available(self, name: str) -> bool:
        """
        检查后端是否可用（未处于熔断状态）。

        半开状态（HALF_OPEN）：熔断重置时间到期后，允许一次试探请求。
        若试探成功，转为 HEALTHY；若失败，重新开始熔断计时。
        """
        state = self._states[name]
        if state.status == BackendStatus.HEALTHY:
            return True
        if state.status == BackendStatus.OPEN:
            # 检查是否超过熔断重置时间
            if time.time() - state.last_failure_time >= self._circuit_reset:
                state.status = BackendStatus.HALF_OPEN
                logger.info("[熔断器] 后端 '%s' 进入半开状态，允许试探请求。", name)
                return True
            return False
        # HALF_OPEN：允许
        return True

    def _on_success(self, name: str) -> None:
        """请求成功：重置熔断器状态。"""
        state = self._states[name]
        if state.status != BackendStatus.HEALTHY:
            logger.info("[熔断器] 后端 '%s' 恢复健康，熔断器关闭。", name)
        state.consecutive_failures = 0
        state.status = BackendStatus.HEALTHY

    def _on_failure(self, name: str) -> None:
        """请求失败：更新连续失败计数，必要时触发熔断。"""
        state = self._states[name]
        state.consecutive_failures += 1
        state.total_failures += 1
        state.last_failure_time = time.time()

        if (state.consecutive_failures >= self._circuit_threshold
                and state.status == BackendStatus.HEALTHY):
            state.status = BackendStatus.OPEN
            logger.error(
                "[熔断器] 后端 '%s' 连续失败 %d 次，触发熔断！"
                "将在 %.0fs 后自动进入半开状态。",
                name, state.consecutive_failures, self._circuit_reset,
            )

    # ------------------------------------------------------------------
    # 状态查询接口
    # ------------------------------------------------------------------

    def health_report(self) -> str:
        """返回所有后端的健康状态摘要。"""
        lines = ["[LLM 网关健康报告]"]
        for backend in self._backends:
            state = self._states[backend.name]
            lines.append(
                f"  {backend.name}: {state.status.value} | "
                f"请求={state.total_requests} | 失败={state.total_failures} | "
                f"溢出={state.total_context_overflows} | "
                f"连续失败={state.consecutive_failures}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 内部异常（不对外暴露）
# ---------------------------------------------------------------------------

class _RetryableError(Exception):
    """可重试错误（仅在 _send_with_retry 内部使用）。"""


class _NetworkError(Exception):
    """底层网络错误（由 urllib 抛出后包装为 _RetryableError）。"""


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _extract_error_message(response: dict[str, Any]) -> str:
    """从各种 API 错误响应格式中提取错误消息字符串。"""
    # OpenAI 格式
    if "error" in response:
        err = response["error"]
        if isinstance(err, dict):
            return err.get("message", str(err))
        return str(err)
    # 通用格式
    for key in ("message", "detail", "msg", "_raw"):
        if key in response:
            return str(response[key])
    return str(response)[:200]


def _extract_retry_after(response: dict[str, Any]) -> float | None:
    """从响应体中提取 Retry-After 时间（秒），若无则返回 None。"""
    for key in ("retry_after", "retryAfter", "retry-after"):
        val = response.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return None


# ---------------------------------------------------------------------------
# 模块级全局网关单例
# ---------------------------------------------------------------------------

# 全局网关：系统所有 LLM 调用经由此实例发出，共享后端健康状态与熔断器。
# 实例化时传入空 backends 列表，由 avatar_os_ignition.py 在启动时注入后端配置。
GLOBAL_GATEWAY: LLMNetworkGateway | None = None


def initialize_gateway(backends: list[LLMBackendConfig]) -> LLMNetworkGateway:
    """
    初始化全局网关单例（在系统点火时调用一次）。

    Args:
        backends: 完整的后端配置列表（从环境变量或配置文件读取）。

    Returns:
        初始化完成的 LLMNetworkGateway 实例。
    """
    global GLOBAL_GATEWAY
    GLOBAL_GATEWAY = LLMNetworkGateway(backends=backends)
    logger.info(
        "[网关] 全局网关初始化完成，后端数=%d: %s",
        len(backends),
        [b.name for b in backends],
    )
    return GLOBAL_GATEWAY
