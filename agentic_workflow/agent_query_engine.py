"""
agentic_workflow/agent_query_engine.py
----------------------------------------
Alumet OS — Agent 查询引擎（防幻觉死锁与无限空转）

设计哲学（源自 Claude Code 微内核思想）：
  大模型是"概率性黑盒"——它在任何时刻都可能输出格式违规的内容。
  一个工业级 Agentic 引擎必须将这一不确定性视为"一等公民"，
  并从架构层面内建以下三道防线：

  防线 1 —— 契约强制（Pydantic 严格反序列化）：
    每次大模型返回结果，必须经过 Pydantic 严格模式反序列化校验。
    不合格的输出不会"悄悄污染"系统状态，而是立即抛出 ValidationError。

  防线 2 —— 纠偏回注（错误信息塞回上下文）：
    捕获 ValidationError 后，【绝对禁止退出进程或静默忽略】。
    必须将结构化的错误描述追加到对话历史，让大模型"看到自己的错误"，
    并在下一轮循环中重新尝试。

  防线 3 —— 熔断降级（Strike Counter）：
    连续 N 次（默认 3 次）反序列化失败后，不再重试，直接 break 跳出循环，
    执行 Fail-Closed 降级策略（返回安全默认值，触发告警），
    防止无效对话无限空转消耗 Token 与算力。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from pydantic import BaseModel, ValidationError, field_validator

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)


# ---------------------------------------------------------------------------
# 大模型响应的 Pydantic 强类型契约
# ---------------------------------------------------------------------------

class ToolCall(BaseModel):
    """
    单次工具调用的结构化描述。

    字段全部为强类型，Pydantic 在严格模式下不允许任何隐式类型转换，
    确保大模型输出的每一个字段都符合精确的类型预期。
    """

    tool_name: str
    arguments: dict[str, Any]

    @field_validator("tool_name")
    @classmethod
    def tool_name_must_not_be_empty(cls, v: str) -> str:
        """工具名不允许为空字符串，防止大模型输出空名称导致工具查找崩溃。"""
        if not v.strip():
            raise ValueError("tool_name 不能为空字符串")
        return v.strip()


class AgentResponse(BaseModel):
    """
    大模型单轮输出的顶层契约。

    设计意图：
      - 使用严格的 model_config 拒绝所有未声明字段（extra="forbid"），
        防止大模型在响应中"塞入"未知字段污染下游。
      - finish_reason 枚举值由运行时业务层校验，而非在此处内联枚举，
        遵循 MCP 协议层的"防缓存击穿"原则（即使在应用层也保持一致性）。

    ⚠️  关于 finish_reason 枚举校验的说明：
      此处故意不使用 Literal["stop", "tool_call", ...] 或 enum 约束，
      原因与 ToolSchema 设计一致：
        枚举值列表可能随大模型 API 版本迭代而扩展，
        若内联在 Schema/Model 中，每次 API 升级都会触发全量缓存失效与
        大量告警。枚举校验下沉到 run_event_loop 的业务逻辑层处理。
    """

    model_config = {"extra": "forbid", "strict": True}

    thinking: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str = "stop"
    content: str | None = None


# ---------------------------------------------------------------------------
# 降级结果：Fail-Closed 策略的载体
# ---------------------------------------------------------------------------

class FailClosedResult(BaseModel):
    """
    熔断后的 Fail-Closed 降级结果。

    Fail-Closed（关闭失败）语义：
      当系统无法确认大模型输出的合法性时，宁可拒绝服务、返回空结果，
      也不允许将不确定的输出流入下游，避免幻觉污染核心数据。
    """

    success: bool = False
    reason: str = "连续反序列化失败，熔断降级，拒绝本次 Agent 任务"
    partial_history: list[dict[str, str]] = []


# ---------------------------------------------------------------------------
# 大模型调用适配器类型别名（依赖注入，便于测试替换）
# ---------------------------------------------------------------------------

# LLMCaller: 接收对话历史列表，返回大模型的原始 JSON 字符串
LLMCaller = Callable[[list[dict[str, str]]], str]

# ToolExecutor: 接收工具调用对象，返回工具执行结果（任意可序列化对象）
ToolExecutor = Callable[[ToolCall], Any]


# ---------------------------------------------------------------------------
# Agent 查询引擎核心实现
# ---------------------------------------------------------------------------

class AgentQueryEngine:
    """
    Alumet OS Agent 查询引擎。

    核心能力：
      - 驱动"大模型 → 工具调用 → 结果回注"的 Agentic 循环。
      - 内建三道防线，杜绝幻觉死锁与无限空转（见模块文档）。
      - 通过依赖注入隔离大模型 API 与工具执行层，便于单元测试。
    """

    # 连续反序列化失败的熔断阈值，超过此值立即跳出循环执行降级
    MAX_CONSECUTIVE_FAILURES: int = 3

    # 单次 Agentic 循环的最大轮数（防止合法工具调用链过长导致空转）
    MAX_TURNS: int = 20

    def __init__(
        self,
        llm_caller: LLMCaller,
        tool_executor: ToolExecutor,
        max_consecutive_failures: int = MAX_CONSECUTIVE_FAILURES,
        max_turns: int = MAX_TURNS,
    ) -> None:
        """
        初始化引擎。

        Args:
            llm_caller:               大模型调用适配器，接收对话历史返回原始 JSON 字符串。
            tool_executor:            工具执行适配器，接收 ToolCall 返回执行结果。
            max_consecutive_failures: 熔断阈值，连续失败超过此次数触发 Fail-Closed。
            max_turns:                最大循环轮数，防止合法场景下的超长工具链空转。
        """
        self._llm_caller = llm_caller
        self._tool_executor = tool_executor
        self._max_failures = max_consecutive_failures
        self._max_turns = max_turns

    def run_event_loop(
        self,
        initial_messages: list[dict[str, str]],
    ) -> AgentResponse | FailClosedResult:
        """
        启动 Agent 事件循环，驱动完整的 Agentic 推理过程。

        循环终止条件（任一满足即退出）：
          1. 大模型返回 finish_reason == "stop"（任务自然完成）。
          2. 连续反序列化失败次数达到熔断阈值（Fail-Closed 降级）。
          3. 循环轮数超过 max_turns（防无限空转保护）。

        Args:
            initial_messages: 初始对话历史（包含 system prompt 与用户消息）。

        Returns:
            成功完成时返回最后一个合法的 AgentResponse；
            熔断降级时返回 FailClosedResult。
        """
        # 深拷贝对话历史，避免修改调用方传入的原始列表
        history: list[dict[str, str]] = list(initial_messages)

        # 连续反序列化失败计数器（strike counter）
        # 每次成功反序列化后重置为 0，只统计"连续"失败
        strike_counter: int = 0

        # 保存最后一次成功解析的响应，供熔断后的降级结果携带
        last_valid_response: AgentResponse | None = None

        turn: int = 0

        logger.info("Agent 事件循环启动，最大轮数=%d，熔断阈值=%d", self._max_turns, self._max_failures)

        # ---------------------------------------------------------------
        # 核心事件循环：while True + 明确的 break 条件
        # ---------------------------------------------------------------
        while True:
            turn += 1

            # 防无限空转：超过最大轮数直接中断
            if turn > self._max_turns:
                logger.warning(
                    "[防空转] 已执行 %d 轮，超过最大限制 %d 轮，强制终止循环。",
                    turn - 1,
                    self._max_turns,
                )
                break

            logger.info("——— 第 %d 轮 Agent 循环开始 ———", turn)

            # -----------------------------------------------------------
            # Step 1：调用大模型，获取原始 JSON 字符串
            # -----------------------------------------------------------
            try:
                raw_output: str = self._llm_caller(history)
                logger.debug("大模型原始输出（第 %d 轮）:\n%s", turn, raw_output)
            except Exception as call_err:
                # 大模型 API 调用失败（网络超时、限流等），不计入 strike，
                # 但记录错误后跳出循环，由上层重试策略决定是否重新发起任务
                logger.error("[API 调用失败] 第 %d 轮大模型调用异常: %s", turn, call_err)
                break

            # -----------------------------------------------------------
            # Step 2：Pydantic 严格反序列化校验
            #
            # ⚠️  防线 1 + 防线 2 的实现核心：
            #   - ValidationError：大模型输出不符合 AgentResponse 契约
            #     → 绝对禁止退出进程，必须捕获并将错误回注对话历史
            #   - json.JSONDecodeError：大模型输出根本不是合法 JSON
            #     → 同等处理，错误信息同样回注
            # -----------------------------------------------------------
            try:
                parsed_data = json.loads(raw_output)
                agent_response = AgentResponse.model_validate(parsed_data, strict=True)

            except (json.JSONDecodeError, ValidationError) as parse_err:
                # -------------------------------------------------------
                # 防线 2：错误信息塞回给大模型，让其"看到自己的违规"
                #
                # 设计原则：
                #   错误提示必须结构化、可操作，而非泛泛的"请重试"。
                #   大模型需要知道：它违反了哪个字段的哪条规则，
                #   才能在下一轮输出时有针对性地修正。
                # -------------------------------------------------------
                strike_counter += 1

                error_type = "JSON 解析失败" if isinstance(parse_err, json.JSONDecodeError) else "Schema 校验失败"
                error_detail = str(parse_err)

                correction_message = (
                    f"[系统纠偏指令 — 第 {strike_counter} 次违规]\n"
                    f"错误类型：{error_type}\n"
                    f"错误详情：{error_detail}\n\n"
                    "你违反了 JSON 契约。请立即修正并重试，注意：\n"
                    "  1. 输出必须是合法的 JSON 对象，不包含任何代码块标记（如 ```json）。\n"
                    "  2. 字段名和类型必须严格符合以下契约：\n"
                    "     { \"thinking\": string|null, \"tool_calls\": [...] | null, "
                    "\"finish_reason\": string, \"content\": string|null }\n"
                    "  3. 不允许出现契约中未声明的额外字段。\n"
                    f"当前已连续违规 {strike_counter} 次，"
                    f"超过 {self._max_failures} 次将触发熔断降级，任务将被终止。"
                )

                logger.warning(
                    "[反序列化失败] 第 %d 轮，连续失败第 %d 次（熔断阈值 %d）\n错误: %s",
                    turn,
                    strike_counter,
                    self._max_failures,
                    error_detail,
                )

                # 将大模型的"违规输出"与纠偏指令一并追加到历史，供下轮使用
                history.append({"role": "assistant", "content": raw_output})
                history.append({"role": "user", "content": correction_message})

                # -------------------------------------------------------
                # 防线 3：熔断检查
                # 连续失败达到阈值 → break 跳出，执行 Fail-Closed 降级
                # -------------------------------------------------------
                if strike_counter >= self._max_failures:
                    logger.error(
                        "[熔断触发] 连续反序列化失败已达 %d 次，触发 Fail-Closed 降级，终止本次 Agent 任务。",
                        strike_counter,
                    )
                    # Fail-Closed：宁可拒绝服务，也不允许不确定的输出流入下游
                    return FailClosedResult(
                        success=False,
                        reason=(
                            f"连续 {strike_counter} 次 JSON 契约违规，"
                            "熔断降级，拒绝本次 Agent 任务以保护系统状态完整性。"
                        ),
                        partial_history=history,
                    )

                # 未达熔断阈值，继续循环让大模型重试
                continue

            # -----------------------------------------------------------
            # 反序列化成功：重置 strike_counter，记录合法响应
            # -----------------------------------------------------------
            strike_counter = 0
            last_valid_response = agent_response

            logger.info(
                "[解析成功] 第 %d 轮，finish_reason=%r，tool_calls=%s",
                turn,
                agent_response.finish_reason,
                "有" if agent_response.tool_calls else "无",
            )

            # -----------------------------------------------------------
            # Step 3：判断循环终止条件（自然完成）
            # -----------------------------------------------------------
            if agent_response.finish_reason == "stop":
                logger.info("[任务完成] 大模型返回 finish_reason=stop，循环正常终止。")
                break

            # -----------------------------------------------------------
            # Step 4：执行工具调用，将结果回注对话历史
            # -----------------------------------------------------------
            if agent_response.tool_calls:
                tool_results: list[dict[str, Any]] = []

                for tool_call in agent_response.tool_calls:
                    logger.info("[工具调用] 执行工具 '%s'，参数: %s", tool_call.tool_name, tool_call.arguments)
                    try:
                        result = self._tool_executor(tool_call)
                        tool_results.append(
                            {
                                "tool_name": tool_call.tool_name,
                                "status": "success",
                                "result": result,
                            }
                        )
                        logger.info("[工具完成] 工具 '%s' 执行成功。", tool_call.tool_name)
                    except Exception as tool_err:
                        # 工具执行失败不触发 strike，但错误信息必须回注，
                        # 让大模型在下轮决策时感知到工具执行状态
                        tool_results.append(
                            {
                                "tool_name": tool_call.tool_name,
                                "status": "error",
                                "error": str(tool_err),
                            }
                        )
                        logger.warning("[工具错误] 工具 '%s' 执行异常: %s", tool_call.tool_name, tool_err)

                # 将大模型的工具调用意图与工具执行结果分别追加到历史
                history.append(
                    {
                        "role": "assistant",
                        "content": raw_output,
                    }
                )
                history.append(
                    {
                        "role": "tool",
                        "content": json.dumps(tool_results, ensure_ascii=False),
                    }
                )
            else:
                # finish_reason 非 stop 但也没有 tool_calls，
                # 属于大模型语义模糊状态，追加 assistant 消息后继续循环
                history.append({"role": "assistant", "content": raw_output})
                logger.debug("[无工具调用] 第 %d 轮大模型未请求任何工具，继续循环。", turn)

        # ---------------------------------------------------------------
        # 循环结束后的返回处理
        # ---------------------------------------------------------------
        if last_valid_response is not None:
            return last_valid_response

        # 从未成功解析过任何响应（例如第一轮就 API 调用失败）
        return FailClosedResult(
            success=False,
            reason="Agent 事件循环未能获得任何合法响应，任务终止。",
            partial_history=history,
        )


# ---------------------------------------------------------------------------
# 工厂函数：快速构建引擎实例（便于依赖注入与测试）
# ---------------------------------------------------------------------------

def create_agent_engine(
    llm_caller: LLMCaller,
    tool_executor: ToolExecutor,
    max_consecutive_failures: int = AgentQueryEngine.MAX_CONSECUTIVE_FAILURES,
    max_turns: int = AgentQueryEngine.MAX_TURNS,
) -> AgentQueryEngine:
    """
    工厂函数：构造并返回一个配置好的 AgentQueryEngine 实例。

    Args:
        llm_caller:               大模型调用适配器。
        tool_executor:            工具执行适配器。
        max_consecutive_failures: 熔断阈值（默认 3 次）。
        max_turns:                最大循环轮数（默认 20 轮）。

    Returns:
        配置完毕的 AgentQueryEngine 实例，可直接调用 run_event_loop。
    """
    return AgentQueryEngine(
        llm_caller=llm_caller,
        tool_executor=tool_executor,
        max_consecutive_failures=max_consecutive_failures,
        max_turns=max_turns,
    )
