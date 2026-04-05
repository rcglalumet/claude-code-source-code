"""
core/mcp_tool_protocol.py
--------------------------
Alumet OS — MCP 工具协议层（防 Schema 爆炸与缓存穿透）

设计哲学（源自 Claude Code 微内核思想）：
  工具协议层是整个 Agentic 系统的"血管"。每一个工具的 Schema 都会被：
    1. 序列化后注入大模型的 System Prompt（消耗 Token 配额）
    2. 缓存在 LRU/Redis 中供热路径复用（缓存键由 Schema 内容哈希生成）

  因此，Schema 的体积与复杂度直接决定系统的安全边界：
    - Schema 越大 → Prompt 越长 → 每次请求成本线性上升
    - Schema 含巨型枚举 → 哈希碰撞概率上升 → 缓存穿透风险暴露
    - Schema 嵌套过深 → 大模型理解偏差 → 幻觉率升高

  本模块强制所有工具遵守"极简扁平化契约"。
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Schema 元数据：描述单个参数的扁平化规格
# ---------------------------------------------------------------------------

class ParameterSpec(BaseModel):
    """
    单个工具参数的极简描述。

    设计约束：
      - 类型只允许使用 JSON Schema 原生标量类型字符串
        （"string" | "integer" | "number" | "boolean" | "array" | "object"）
      - 【严禁】在此处内联枚举值列表（enum 字段）。
        原因：巨大枚举值会导致同一工具在不同调用场景下生成不同的 Schema 哈希，
        致使缓存键每次都不命中（缓存击穿 / Cache Stampede），大量请求同时穿透
        到后端重新序列化，形成雪崩效应。枚举校验应下沉到工具实现层运行时校验。
    """

    name: str = Field(..., description="参数名称，使用 snake_case")
    type: str = Field(..., description="JSON Schema 类型，仅限标量或容器类型")
    description: str = Field(..., description="简短的功能描述，不超过 80 字")
    required: bool = Field(default=True, description="是否为必填项")


class ToolSchema(BaseModel):
    """
    工具 Schema 的顶层包装。

    极简扁平化设计原则：
      1. 只描述"调用合约"，不描述"业务语义细节"。
         大模型不需要知道枚举值的全集，只需要知道参数的类型与意图。
      2. Schema 结构最多两层（tool → parameters），绝不递归嵌套。
      3. 总字符数建议控制在 512 字节以内（不含工具名与描述）。
    """

    name: str = Field(..., description="工具唯一标识，全局不重名")
    description: str = Field(..., description="工具功能的一句话摘要")
    parameters: list[ParameterSpec] = Field(default_factory=list)
    is_read_only: bool = Field(
        default=True,
        description="只读工具不修改任何系统状态，可安全并发调用；写操作工具须显式标注 False",
    )

    def fingerprint(self) -> str:
        """
        计算本 Schema 的稳定内容哈希（用于缓存键生成）。

        注意：只要 Schema 内容不变，哈希就不变，从而保证缓存命中率。
        这也是为什么我们禁止在 Schema 里嵌入动态枚举值的根本原因——
        枚举值一旦变动，哈希随之变动，缓存全部失效。
        """
        canonical = json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# BaseTool：所有 MCP 工具的抽象基类
# ---------------------------------------------------------------------------

class BaseTool(ABC):
    """
    Alumet OS MCP 工具抽象基类。

    强制约定：
      - 每个子类必须实现 get_schema()，且返回的 ToolSchema 必须遵守极简扁平化原则。
      - 每个子类必须实现 execute()，承载实际业务逻辑。
      - is_read_only 属性从 ToolSchema 中派生，子类无需单独声明，
        但可通过覆写 get_schema() 中的 is_read_only 字段来改变行为。

    安全语义：
      - is_read_only = True  → 工具只读取信息，不产生副作用，调度器可并行执行。
      - is_read_only = False → 工具具备写权限，调度器必须串行执行并记录审计日志。
    """

    # ------------------------------------------------------------------
    # 强制实现接口
    # ------------------------------------------------------------------

    @abstractmethod
    def get_schema(self) -> ToolSchema:
        """
        返回本工具的 Schema 描述。

        ⚠️  实现者必须严格遵守以下约束，违反者视为安全漏洞：
          1. parameters 列表中【绝对禁止】出现枚举值字段（如 Literal、enum）。
             原因：枚举值会使 Schema 体积随业务增长而膨胀，同时导致缓存键哈希
             在业务枚举更新时全量失效，引发缓存击穿（Cache Stampede），
             高并发下将压垮后端序列化服务。
          2. Schema 嵌套层级不超过两层。
          3. 参数描述字段不超过 80 个字符。
        """
        raise NotImplementedError

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """
        执行工具的核心业务逻辑。

        参数通过 **kwargs 传入，实现层负责运行时类型校验
        （包括枚举值合法性校验，下沉至此层，而非 Schema 层）。
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 从 Schema 派生的只读属性
    # ------------------------------------------------------------------

    @property
    def is_read_only(self) -> bool:
        """
        工具的只读性由 ToolSchema.is_read_only 字段决定。

        设计意图：将"安全属性声明"内聚在 Schema 中，
        避免 Schema 与实现层之间的状态不一致。
        """
        return self.get_schema().is_read_only

    @property
    def name(self) -> str:
        """工具名称快捷访问，直接代理到 Schema。"""
        return self.get_schema().name

    @property
    def schema_fingerprint(self) -> str:
        """返回本工具 Schema 的内容哈希，用于缓存键构造与变更检测。"""
        return self.get_schema().fingerprint()

    # ------------------------------------------------------------------
    # 自我校验：在工具注册时调用，提前暴露设计违规
    # ------------------------------------------------------------------

    def validate_schema_compliance(self) -> None:
        """
        在工具注册阶段执行 Schema 合规自检。

        检测项：
          - 参数描述是否超过 80 字符（可能导致 Prompt 膨胀）
          - Schema 总序列化体积是否超过安全阈值（512 字节）

        若发现违规，抛出 ValueError 阻断注册，实现"快速失败"原则。
        """
        schema = self.get_schema()

        for param in schema.parameters:
            if len(param.description) > 80:
                raise ValueError(
                    f"[Schema 违规] 工具 '{schema.name}' 的参数 '{param.name}' "
                    f"描述超过 80 字符（当前 {len(param.description)} 字符）。"
                    "请精简描述，防止 Prompt 膨胀。"
                )

        serialized = schema.model_dump_json()
        if len(serialized.encode()) > 512:
            raise ValueError(
                f"[Schema 违规] 工具 '{schema.name}' 的 Schema 序列化体积超过 512 字节 "
                f"（当前 {len(serialized.encode())} 字节）。"
                "请拆分工具或简化参数描述，防止缓存键爆炸与 Token 浪费。"
            )

    def __repr__(self) -> str:
        mode = "只读" if self.is_read_only else "写操作"
        return f"<Tool name={self.name!r} mode={mode} fingerprint={self.schema_fingerprint}>"


# ---------------------------------------------------------------------------
# 工具注册表：全局单例，管理所有已注册的 MCP 工具
# ---------------------------------------------------------------------------

class ToolRegistry:
    """
    MCP 工具全局注册表。

    职责：
      1. 维护工具名称到实例的映射。
      2. 在注册时强制执行 Schema 合规校验（快速失败）。
      3. 提供按只读性过滤的查询接口，供调度器区分并发/串行执行策略。
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        注册一个工具实例。

        注册流程：
          1. 触发 Schema 合规自检（validate_schema_compliance）。
          2. 检查工具名是否与已注册工具冲突。
          3. 写入内部映射表。

        快速失败原则：任何违规在注册阶段即抛出异常，而非在运行时暴露。
        """
        # 先执行 Schema 合规性校验，不合规直接阻断
        tool.validate_schema_compliance()

        tool_name = tool.name
        if tool_name in self._tools:
            raise ValueError(
                f"[注册冲突] 工具名 '{tool_name}' 已被注册。"
                "MCP 协议要求工具名全局唯一，请修改新工具的名称。"
            )
        self._tools[tool_name] = tool

    def get(self, name: str) -> BaseTool:
        """按名称获取工具，未找到时抛出 KeyError。"""
        if name not in self._tools:
            raise KeyError(f"[工具未找到] 名称 '{name}' 未在注册表中。")
        return self._tools[name]

    def list_read_only(self) -> list[BaseTool]:
        """返回所有只读工具，供调度器并行执行。"""
        return [t for t in self._tools.values() if t.is_read_only]

    def list_write(self) -> list[BaseTool]:
        """返回所有写操作工具，供调度器串行执行并记录审计。"""
        return [t for t in self._tools.values() if not t.is_read_only]

    def export_schemas(self) -> list[dict[str, Any]]:
        """
        导出所有已注册工具的 Schema 列表（用于注入大模型 System Prompt）。

        输出格式为极简 JSON 列表，确保注入 Prompt 后 Token 消耗最小化。
        """
        return [tool.get_schema().model_dump() for tool in self._tools.values()]


# ---------------------------------------------------------------------------
# 模块级全局注册表实例（单例）
# ---------------------------------------------------------------------------

# 全局注册表：整个进程共享唯一实例，所有工具在启动时向此注册
GLOBAL_TOOL_REGISTRY = ToolRegistry()
