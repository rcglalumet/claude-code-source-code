# -*- coding: utf-8 -*-
# = [端口 T: L1 拓扑实体] =
# 路径: modules/01_xiangshu/xiangshu_v102_topology.py
# @Layer: 🗺️ [L1] 象数派拓扑实体 (V10.2 Pydantic 纯净版)
# @Description: 所有字段均为基础标量 (str, int, float, bool)。
#               严禁使用 Enum / Literal 罗列庞大选项（防缓存击穿）。
#               所有中文语义已强行映射为冰冷的英文标量字段。

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==============================================================================
# [L1] 图谱节点实体（VLM 解析后的单个视觉对象）
# ==============================================================================
class XiangShuNode(BaseModel):
    node_id: str = Field(description="节点唯一 ID，格式如 \"N001\"")
    label: str = Field(description="VLM 识别的英文标签，如 \"person\", \"shadow\", \"fence\"")
    palace_index: int = Field(
        default=5,
        description="所在九宫格宫位 index，1-9，洛书布局（1=左上,5=中心,9=右下）",
    )
    x_norm: float = Field(
        default=0.5,
        description="节点中心点归一化横坐标 [0, 1]，0=最左",
    )
    y_norm: float = Field(
        default=0.5,
        description="节点中心点归一化纵坐标 [0, 1]，0=最上",
    )
    properties: List[str] = Field(
        default_factory=list,
        description="VLM 提取的属性标签列表，如 [\"blurry\", \"back_of_head\", \"iron_fences\"]",
    )
    is_primary_subject: bool = Field(
        default=False,
        description="是否为画面主体（寻主算法判定）",
    )
    is_background: bool = Field(
        default=False,
        description="是否为背景白名单节点（天空/草地等），白名单节点跳过推演",
    )


# ==============================================================================
# [L1] 图谱边实体（节点间的空间关系）
# ==============================================================================
class XiangShuEdge(BaseModel):
    source_id: str = Field(description="源节点 ID")
    target_id: str = Field(description="目标节点 ID")
    relation_type: str = Field(
        default="NONE",
        description=(
            "边关系类型字符串，可选值（不强制枚举）："
            "DIVIDES / CROSSES / MISSING / OPPRESSES / BLOCKS / "
            "POINTS_TO / SUPPORTS / PULLS / NONE"
        ),
    )
    relation_score: float = Field(
        default=0.0,
        description="关系量化分数 [-1.0, 1.0]，由 relation_to_score() 映射",
    )


# ==============================================================================
# [L1] VLM 图谱实体（Parser 输出的完整结构化数据）
# ==============================================================================
class XiangShuGraph(BaseModel):
    image_id: str = Field(description="图片唯一 ID")
    nodes: Dict[str, XiangShuNode] = Field(
        default_factory=dict,
        description="节点字典，key 为 node_id",
    )
    edges: List[XiangShuEdge] = Field(
        default_factory=list,
        description="节点间关系边列表",
    )
    primary_subject_id: str = Field(
        default="",
        description="寻主算法确定的主体节点 ID",
    )
    avatar_category: str = Field(
        default="real_photo",
        description=(
            "头像分类字符串，如 \"real_photo\" / \"anime_manga\" / "
            "\"misc_landscape\" / \"isolated_object\" / \"group_photo\""
        ),
    )
    has_multiple_subjects: bool = Field(
        default=False,
        description="画面中是否存在多个并列主体（影响 T087 等规则触发）",
    )
    is_inverted: bool = Field(
        default=False,
        description="画面是否存在物理倒置元素（T101 规则触发条件）",
    )
    crop_slant_degrees: float = Field(
        default=0.0,
        description="裁切倾斜角度（度），0 表示无倾斜，正值向右倾，负值向左倾（T062 触发阈值 ≥ 5.0）",
    )


# ==============================================================================
# [L1] 单条推演结论实体（引擎 L1.5 输出的原子断语）
# ==============================================================================
class XiangShuFinding(BaseModel):
    rule_id: str = Field(description="命中的规则 ID，如 \"T015\"")
    category: str = Field(description="五大宏观领域之一，如 \"⛰️ 事业与财富\"")
    wuxing: str = Field(description="五行归属字符串，如 \"METAL\"")
    tensor_weight: float = Field(description="本条断语的张量权重（float）")
    reasoning: str = Field(description="物理逻辑推演文本")
    summary: str = Field(description="一针见血的断语结论文本")
    triggered_node_ids: List[str] = Field(
        default_factory=list,
        description="触发本条规则的节点 ID 列表",
    )


# ==============================================================================
# [L1] 象数分析最终报告实体（所有推演结论的汇总）
# ==============================================================================
class XiangShuReport(BaseModel):
    image_id: str = Field(description="原始图片 ID")
    findings: List[XiangShuFinding] = Field(
        default_factory=list,
        description="所有命中规则的推演结论列表，已按 tensor_weight 降序排列",
    )

    # 五大宏观领域分类命中数
    personality_hit_count: int = Field(
        default=0, description="\"🪞 性格与潜意识\" 领域命中条数"
    )
    career_hit_count: int = Field(
        default=0, description="\"⛰️ 事业与财富\" 领域命中条数"
    )
    relation_hit_count: int = Field(
        default=0, description="\"🔗 人际与情感\" 领域命中条数"
    )
    health_hit_count: int = Field(
        default=0, description="\"⚔️ 健康与疾厄\" 领域命中条数"
    )
    ancestry_hit_count: int = Field(
        default=0, description="\"🌳 祖荫与本命\" 领域命中条数"
    )

    # 张量物理汇总
    total_weight: float = Field(default=0.0, description="所有命中规则的权重总和")
    tension: float = Field(default=0.0, description="张力（越高越凶险），上限 25.0")
    mass: float = Field(default=0.0, description="质量场（越负越虚耗），下限 -15.0")
    entropy: float = Field(default=0.0, description="图谱复杂度熵值 [0, 1]")

    # YOLO 拦截标志
    is_vetoed: bool = Field(default=False, description="是否被 YOLO 拦截规则阻断")
    veto_reason: str = Field(default="", description="拦截原因说明（is_vetoed=True 时填写）")

    # 原始图谱快照（供 L2 汇聚层引用）
    graph_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        description="原始 XiangShuGraph 的序列化快照（.model_dump()），供上层引用",
    )
