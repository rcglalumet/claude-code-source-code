# -*- coding: utf-8 -*-
# = [端口 E: L1.5 领域推演引擎] =
# 路径: modules/01_xiangshu/xiangshu_unified_engine.py
# @Layer: [L1.5] 象数派统一推演引擎（系统灵魂插槽，V11 适配版）
# @Description:
#   承载所有复杂的 if/else 推演逻辑、权重叠加算法与结论汇总。
#   输入：XiangShuGraph（含 11 维分析维度 + engine_topology）
#   探针碰撞来源扩展为双轨道：
#     轨道 A：engine_topology 节点 properties（原有倒排索引）
#     轨道 B：11 维派生标量字段（直接触发映射表）
#   所有 L5 规则通过 O(1) 倒排索引或静态映射表命中，零 RAG，零向量检索。

import logging
from typing import Any, Dict, List, Set

from expert_rules.xiangshu_rules import (
    CAT_ANCESTRY,
    CAT_CAREER,
    CAT_HEALTH,
    CAT_PERSONALITY,
    CAT_RELATION,
    GLOBAL_BOUNDARY,
    INTERACTION_RULES,
    XIANGSHU_GENOMES,
    XIANGSHU_WEIGHTS,
    YOLO_VETO_RULES,
)
from core_engine.xiangshu_math_core import accumulate_tensor
from xiangshu_v102_topology import (
    XiangShuFinding,
    XiangShuGraph,
    XiangShuReport,
)

logger = logging.getLogger("L1_5_XiangShu_Engine_V11")

# ==============================================================================
# [系统启动] 预编译全息倒排索引 (Keyword -> Set[Rule_IDs])
# 来源：XIANGSHU_GENOMES 中每个基因座的 keywords 列表
# ==============================================================================
_GLOBAL_INVERTED_INDEX: Dict[str, Set[str]] = {}
for _rule_id, _genome in XIANGSHU_GENOMES.items():
    for _kw in _genome.get("keywords", []):
        _kw_lower = _kw.lower()
        if _kw_lower not in _GLOBAL_INVERTED_INDEX:
            _GLOBAL_INVERTED_INDEX[_kw_lower] = set()
        _GLOBAL_INVERTED_INDEX[_kw_lower].add(_rule_id)

logger.info(
    "[L1.5 V11 引擎] 倒排索引编译完成，共映射 %d 个独立微观特征关键词",
    len(_GLOBAL_INVERTED_INDEX),
)

# ==============================================================================
# [系统启动] 预处理 YOLO 拦截关键词（O(1) frozenset）
# ==============================================================================
_YOLO_TRIGGER_SETS: List[Dict[str, Any]] = []
for _veto_id, _veto_rule in YOLO_VETO_RULES.items():
    raw_kws = _veto_rule.get("trigger_keywords", "")
    kw_set = frozenset(k.strip().lower() for k in raw_kws.split(",") if k.strip())
    _YOLO_TRIGGER_SETS.append({
        "veto_id": _veto_id,
        "kw_set": kw_set,
        "action": _veto_rule.get("action", "BLOCK_AND_RETURN"),
        "reason": _veto_rule.get("reason", ""),
    })

# ==============================================================================
# [轨道 B] 11 维派生标量 -> 规则 ID 静态触发映射表
# 格式：[(dim_accessor_fn, trigger_condition_fn, Set[rule_id], dim_label)]
# accessor_fn: graph -> 标量值
# trigger_fn:  标量值 -> bool（True 则触发对应规则集）
# 全部为 O(1) 纯函数，零推演，零 LLM。
# ==============================================================================
_DIM_TRIGGER_MAP: List[Dict[str, Any]] = [
    # --- Dim-01 格式塔 ---
    {
        "dim": "gestalt_mimicry.has_mirror_split",
        "accessor": lambda g: g.gestalt_mimicry.has_mirror_split,
        "condition": lambda v: v is True,
        "rules": {"T068", "T101"},
    },
    {
        "dim": "gestalt_mimicry.has_organ_gestalt",
        "accessor": lambda g: g.gestalt_mimicry.has_organ_gestalt,
        "condition": lambda v: v is True,
        "rules": {"T056", "T080"},
    },
    {
        "dim": "gestalt_mimicry.enclosure_type",
        "accessor": lambda g: g.gestalt_mimicry.enclosure_type,
        "condition": lambda v: v in ("full_wrap", "dual_bag"),
        "rules": {"T046", "T057"},
    },
    # --- Dim-02 截断 ---
    {
        "dim": "truncation.has_double_end_truncation",
        "accessor": lambda g: g.truncation.has_double_end_truncation,
        "condition": lambda v: v is True,
        "rules": {"T016"},
    },
    {
        "dim": "truncation.has_double_end_truncation",
        "accessor": lambda g: g.truncation.has_double_end_truncation,
        "condition": lambda v: v is False,
        "rules": {"T041"},
    },
    {
        "dim": "truncation.top_lighting_intensity",
        "accessor": lambda g: g.truncation.top_lighting_intensity,
        "condition": lambda v: v in ("strong", "extreme"),
        "rules": {"T012", "T095"},
    },
    # --- Dim-03 表面老化 ---
    {
        "dim": "surface_aging.peeling_severity",
        "accessor": lambda g: g.surface_aging.peeling_severity,
        "condition": lambda v: v in ("moderate", "severe", "necrotic"),
        "rules": {"T020", "T103"},
    },
    {
        "dim": "surface_aging.macro_symmetry_score",
        "accessor": lambda g: g.surface_aging.macro_symmetry_score,
        "condition": lambda v: isinstance(v, float) and v >= 0.9,
        "rules": {"T057"},
    },
    {
        "dim": "surface_aging.micro_roughness_present",
        "accessor": lambda g: g.surface_aging.micro_roughness_present,
        "condition": lambda v: v is True,
        "rules": {"T049"},
    },
    # --- Dim-04 阵列方向 ---
    {
        "dim": "array_orientation.has_orthogonal_cross",
        "accessor": lambda g: g.array_orientation.has_orthogonal_cross,
        "condition": lambda v: v is True,
        "rules": {"T052", "T068"},
    },
    {
        "dim": "array_orientation.protrusion_direction",
        "accessor": lambda g: g.array_orientation.protrusion_direction,
        "condition": lambda v: v in ("both", "up", "down", "radial"),
        "rules": {"T041", "T037"},
    },
    {
        "dim": "array_orientation.protrusion_sharpness",
        "accessor": lambda g: g.array_orientation.protrusion_sharpness,
        "condition": lambda v: v in ("needle", "blade"),
        "rules": {"T015", "T041"},
    },
    # --- Dim-05 物理倾斜 ---
    {
        "dim": "physical_tilt.tilt_degrees",
        "accessor": lambda g: abs(g.physical_tilt.tilt_degrees),
        "condition": lambda v: v >= 5.0,
        "rules": {"T062"},
    },
    {
        "dim": "physical_tilt.is_vertically_anchored",
        "accessor": lambda g: g.physical_tilt.is_vertically_anchored,
        "condition": lambda v: v is True,
        "rules": {"T013"},
    },
    {
        "dim": "physical_tilt.facet_exposure_type",
        "accessor": lambda g: g.physical_tilt.facet_exposure_type,
        "condition": lambda v: v in ("full_frontal", "all_sides"),
        "rules": {"T095", "T085"},
    },
    # --- Dim-06 高低差 ---
    {
        "dim": "asymmetric_height.left_right_height_delta",
        "accessor": lambda g: g.asymmetric_height.left_right_height_delta,
        "condition": lambda v: isinstance(v, float) and v >= 0.2,
        "rules": {"T059"},
    },
    {
        "dim": "asymmetric_height.has_central_fracture",
        "accessor": lambda g: g.asymmetric_height.has_central_fracture,
        "condition": lambda v: v is True,
        "rules": {"T092", "T016"},
    },
    # --- Dim-07 流体密度 ---
    {
        "dim": "fluid_density.solid_density_level",
        "accessor": lambda g: g.fluid_density.solid_density_level,
        "condition": lambda v: v in ("high", "extreme"),
        "rules": {"T054"},
    },
    {
        "dim": "fluid_density.mirror_density_level",
        "accessor": lambda g: g.fluid_density.mirror_density_level,
        "condition": lambda v: v == "zero",
        "rules": {"T013"},
    },
    {
        "dim": "fluid_density.cross_palace_blocked",
        "accessor": lambda g: g.fluid_density.cross_palace_blocked,
        "condition": lambda v: v is True,
        "rules": {"T076", "T027"},
    },
    {
        "dim": "fluid_density.photon_projection_active",
        "accessor": lambda g: g.fluid_density.photon_projection_active,
        "condition": lambda v: v is True,
        "rules": {"T024"},
    },
    # --- Dim-08 颗粒物理 ---
    {
        "dim": "granular_physics.primary_medium_hardness",
        "accessor": lambda g: g.granular_physics.primary_medium_hardness,
        "condition": lambda v: v in ("hard", "ultra_hard", "crystalline"),
        "rules": {"T046"},
    },
    {
        "dim": "granular_physics.secondary_medium_hardness",
        "accessor": lambda g: g.granular_physics.secondary_medium_hardness,
        "condition": lambda v: v in ("ultra_soft", "soft"),
        "rules": {"T019"},
    },
    {
        "dim": "granular_physics.edge_sharpness_level",
        "accessor": lambda g: g.granular_physics.edge_sharpness_level,
        "condition": lambda v: v == "surgical",
        "rules": {"T015", "T041"},
    },
    # --- Dim-09 角落挤压 ---
    {
        "dim": "corner_jamming.corner_pressure_type",
        "accessor": lambda g: g.corner_jamming.corner_pressure_type,
        "condition": lambda v: v == "full_escape",
        "rules": {"T057"},
    },
    {
        "dim": "corner_jamming.corner_pressure_type",
        "accessor": lambda g: g.corner_jamming.corner_pressure_type,
        "condition": lambda v: v == "severe",
        "rules": {"T043"},
    },
    {
        "dim": "corner_jamming.is_fluid_frozen",
        "accessor": lambda g: g.corner_jamming.is_fluid_frozen,
        "condition": lambda v: v is True,
        "rules": {"T013", "T007"},
    },
    {
        "dim": "corner_jamming.fluid_turbulence_score",
        "accessor": lambda g: g.corner_jamming.fluid_turbulence_score,
        "condition": lambda v: isinstance(v, float) and v >= 0.8,
        "rules": {"T075", "T029"},
    },
    # --- Dim-10 流体浸染 ---
    {
        "dim": "fluid_soaking_3d.soaking_coverage_ratio",
        "accessor": lambda g: g.fluid_soaking_3d.soaking_coverage_ratio,
        "condition": lambda v: isinstance(v, float) and v >= 0.7,
        "rules": {"T007", "T060"},
    },
    {
        "dim": "fluid_soaking_3d.dimension_fold_present",
        "accessor": lambda g: g.fluid_soaking_3d.dimension_fold_present,
        "condition": lambda v: v is True,
        "rules": {"T101", "T054"},
    },
    # --- Dim-11 色形味穿刺 ---
    {
        "dim": "color_shape_piercing.upward_piercing",
        "accessor": lambda g: g.color_shape_piercing.upward_piercing,
        "condition": lambda v: v is True,
        "rules": {"T041", "T037"},
    },
    {
        "dim": "color_shape_piercing.downward_piercing",
        "accessor": lambda g: g.color_shape_piercing.downward_piercing,
        "condition": lambda v: v is True,
        "rules": {"T060", "T015"},
    },
    {
        "dim": "color_shape_piercing.wuxing_collision_count",
        "accessor": lambda g: g.color_shape_piercing.wuxing_collision_count,
        "condition": lambda v: isinstance(v, int) and v >= 2,
        "rules": {"T021", "T029"},
    },
    # --- 图谱级元字段 ---
    {
        "dim": "is_inverted",
        "accessor": lambda g: g.is_inverted,
        "condition": lambda v: v is True,
        "rules": {"T101"},
    },
    {
        "dim": "crop_slant_degrees",
        "accessor": lambda g: abs(g.crop_slant_degrees),
        "condition": lambda v: v >= 5.0,
        "rules": {"T062"},
    },
]


# ==============================================================================
# [内部] 轨道 A：engine_topology 节点属性文本 -> 倒排索引碰撞
# ==============================================================================
def _collect_topology_props_text(graph: XiangShuGraph) -> str:
    """
    将图谱中所有非背景节点的 label/concept/properties 拼接为大文本串。
    """
    parts: List[str] = []
    for node in graph.nodes.values():
        if node.is_background:
            continue
        parts.append(node.concept.lower())
        parts.append(node.palace.lower())
        parts.extend(p.lower() for p in node.properties)
    return " ".join(parts)


def _get_triggered_rules_from_topology(props_text: str) -> Set[str]:
    """轨道 A O(1) 碰撞，100% 召回，不截断。"""
    triggered: Set[str] = set()
    for kw, rule_ids in _GLOBAL_INVERTED_INDEX.items():
        if kw in props_text:
            triggered.update(rule_ids)
    return triggered


# ==============================================================================
# [内部] 轨道 B：11 维派生标量 -> 静态触发映射
# ==============================================================================
def _get_triggered_rules_from_dims(graph: XiangShuGraph) -> Dict[str, Set[str]]:
    """
    遍历 _DIM_TRIGGER_MAP，对每个触发条目检查派生标量是否满足条件。
    返回 {rule_id: Set[dim_label]}，记录每条规则由哪些维度触发。
    """
    rule_to_dims: Dict[str, Set[str]] = {}
    for entry in _DIM_TRIGGER_MAP:
        try:
            value = entry["accessor"](graph)
            if entry["condition"](value):
                for rid in entry["rules"]:
                    if rid not in rule_to_dims:
                        rule_to_dims[rid] = set()
                    rule_to_dims[rid].add(entry["dim"])
        except Exception as exc:
            logger.debug("[DimTrigger] %s 访问失败: %s", entry["dim"], exc)
    return rule_to_dims


# ==============================================================================
# [内部] YOLO 拦截检测
# ==============================================================================
def _yolo_check(props_text: str) -> Dict[str, Any]:
    for entry in _YOLO_TRIGGER_SETS:
        for kw in entry["kw_set"]:
            if kw in props_text:
                return {"vetoed": True, "reason": entry["reason"]}
    return {"vetoed": False, "reason": ""}


# ==============================================================================
# [内部] 从 INTERACTION_RULES 取物理参数（O(1)）
# ==============================================================================
def _get_interaction_params(rule_key: str) -> Dict[str, float]:
    if rule_key in INTERACTION_RULES:
        entry = INTERACTION_RULES[rule_key]
        return {
            "mass_impact": float(entry.get("mass_impact", 0.0)),
            "tension_increment": float(entry.get("tension_increment", 0.0)),
        }
    return {"mass_impact": 0.0, "tension_increment": 0.0}


# ==============================================================================
# [内部] 精准落点：在 engine_topology 节点中定位触发节点
# ==============================================================================
def _find_triggering_nodes(graph: XiangShuGraph, keywords: List[str]) -> List[str]:
    matched_ids: List[str] = []
    for nid, node in graph.nodes.items():
        if node.is_background:
            continue
        node_text = (node.concept + " " + node.palace + " " + " ".join(node.properties)).lower()
        if any(kw.lower() in node_text for kw in keywords):
            matched_ids.append(nid)
    return matched_ids


# ==============================================================================
# [内部] 构建单条 XiangShuFinding
# ==============================================================================
def _build_finding(
    rule_id: str,
    genome: Dict[str, Any],
    triggered_node_ids: List[str],
    triggered_dim: str = "",
) -> XiangShuFinding:
    distilled = XIANGSHU_WEIGHTS.get(rule_id, {})
    base_weight = float(distilled.get("base_weight", genome.get("base_weight", 0.0)))
    wuxing = str(genome.get("wuxing", "EARTH")).upper()
    return XiangShuFinding(
        rule_id=rule_id,
        category=genome.get("category", ""),
        wuxing=wuxing,
        tensor_weight=base_weight,
        reasoning=genome.get("reasoning", ""),
        summary=genome.get("summary", ""),
        triggered_node_ids=triggered_node_ids,
        triggered_dim=triggered_dim,
    )


# ==============================================================================
# [内部] 五大宏观领域命中计数
# ==============================================================================
def _count_by_category(findings: List[XiangShuFinding]) -> Dict[str, int]:
    counts: Dict[str, int] = {
        CAT_PERSONALITY: 0,
        CAT_CAREER: 0,
        CAT_RELATION: 0,
        CAT_HEALTH: 0,
        CAT_ANCESTRY: 0,
    }
    for f in findings:
        if f.category in counts:
            counts[f.category] += 1
    return counts


# ==============================================================================
# [公开接口] 主推演函数
# ==============================================================================
def run_xiangshu_engine(graph: XiangShuGraph) -> XiangShuReport:
    """
    [L1.5 V11 主推演接口]
    输入: XiangShuGraph（由 V11 Parser 产出，含 11 维分析维度）
    输出: XiangShuReport（完整推演报告）

    推演流程：
    1. 收集 engine_topology 节点属性文本（轨道 A）
    2. YOLO 拦截检测
    3. 轨道 A：倒排索引 O(1) 碰撞
    4. 轨道 B：11 维派生标量静态触发映射
    5. 合并双轨道命中规则集合（去重）
    6. 遍历命中规则，构建 XiangShuFinding 列表
    7. 张量累加（物理叠加权重 / tension / mass / entropy）
    8. 按 tensor_weight 降序排列，汇总成 XiangShuReport
    """
    # Step 1: 轨道 A 属性文本
    props_text = _collect_topology_props_text(graph)

    # Step 2: YOLO 拦截
    yolo_result = _yolo_check(props_text)
    if yolo_result["vetoed"]:
        logger.warning("[L1.5 YOLO] 拦截命中: %s", yolo_result["reason"])
        return XiangShuReport(
            image_id=graph.image_id,
            is_vetoed=True,
            veto_reason=yolo_result["reason"],
        )

    # Step 3: 轨道 A 倒排碰撞
    track_a_rules: Set[str] = _get_triggered_rules_from_topology(props_text)

    # Step 4: 轨道 B 维度触发
    track_b_rule_to_dims: Dict[str, Set[str]] = _get_triggered_rules_from_dims(graph)

    # Step 5: 合并去重
    all_rule_ids: Set[str] = track_a_rules | set(track_b_rule_to_dims.keys())

    # Step 6: 构建 findings
    findings: List[XiangShuFinding] = []
    activated_weights: List[float] = []
    tension_increments: List[float] = []
    mass_impacts: List[float] = []
    seen_rule_ids: Set[str] = set()

    for rule_id in all_rule_ids:
        if rule_id in seen_rule_ids:
            continue
        seen_rule_ids.add(rule_id)

        genome = XIANGSHU_GENOMES.get(rule_id)
        if genome is None:
            continue

        keywords = genome.get("keywords", [])
        triggering_nodes = _find_triggering_nodes(graph, keywords)

        # 记录触发维度（轨道 B 有记录则优先，否则标注轨道 A）
        dim_label = ""
        if rule_id in track_b_rule_to_dims:
            dim_label = " | ".join(sorted(track_b_rule_to_dims[rule_id]))
        elif rule_id in track_a_rules:
            dim_label = "engine_topology.properties"

        finding = _build_finding(rule_id, genome, triggering_nodes, dim_label)
        findings.append(finding)

        activated_weights.append(finding.tensor_weight)
        interaction = _get_interaction_params(rule_id)
        tension_increments.append(interaction["tension_increment"])
        mass_impacts.append(interaction["mass_impact"])

    # Step 7: 张量累加
    tensor_summary = accumulate_tensor(
        activated_weights=activated_weights,
        tension_increments=tension_increments,
        mass_impacts=mass_impacts,
        global_max_tension=GLOBAL_BOUNDARY["max_tension"],
        global_min_mass=GLOBAL_BOUNDARY["min_mass"],
    )

    # Step 8: 排序 + 五大领域统计
    findings.sort(key=lambda f: f.tensor_weight, reverse=True)
    category_counts = _count_by_category(findings)

    report = XiangShuReport(
        image_id=graph.image_id,
        findings=findings,
        personality_hit_count=category_counts[CAT_PERSONALITY],
        career_hit_count=category_counts[CAT_CAREER],
        relation_hit_count=category_counts[CAT_RELATION],
        health_hit_count=category_counts[CAT_HEALTH],
        ancestry_hit_count=category_counts[CAT_ANCESTRY],
        total_weight=tensor_summary["total_weight"],
        tension=tensor_summary["tension"],
        mass=tensor_summary["mass"],
        entropy=tensor_summary["entropy"],
        is_vetoed=False,
        veto_reason="",
        graph_snapshot=graph.model_dump(),
    )

    logger.info(
        "[L1.5 V11 引擎] image_id=%s 命中规则=%d (A=%d B=%d) 总权重=%.2f tension=%.2f",
        graph.image_id, len(findings),
        len(track_a_rules), len(track_b_rule_to_dims),
        report.total_weight, report.tension,
    )
    return report
