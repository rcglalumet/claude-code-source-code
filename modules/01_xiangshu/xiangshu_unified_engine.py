# -*- coding: utf-8 -*-
# = [端口 E: L1.5 领域推演引擎] =
# 路径: modules/01_xiangshu/xiangshu_unified_engine.py
# @Layer: ⚙️ [L1.5] 象数派统一推演引擎（系统灵魂插槽）
# @Description: 承载所有复杂的 if/else 推演逻辑、权重叠加算法与结论汇总。
#               所有 L5 规则通过 O(1) 倒排索引命中，零向量检索，零 RAG。
#               L1 Parser 的输出（XiangShuGraph）在此被炼金为 XiangShuReport。

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
from core_engine.xiangshu_math_core import accumulate_tensor, wuxing_modulate
from xiangshu_v102_topology import (
    XiangShuFinding,
    XiangShuGraph,
    XiangShuReport,
)

logger = logging.getLogger("L1_5_XiangShu_Engine")

# ==============================================================================
# [系统启动] 预编译全息倒排索引 (Keyword -> Set[Rule_IDs])
# O(1) 碰撞，100% 召回，绝无截断
# ==============================================================================
_GLOBAL_INVERTED_INDEX: Dict[str, Set[str]] = {}
for _rule_id, _genome in XIANGSHU_GENOMES.items():
    for _kw in _genome.get("keywords", []):
        _kw_lower = _kw.lower()
        if _kw_lower not in _GLOBAL_INVERTED_INDEX:
            _GLOBAL_INVERTED_INDEX[_kw_lower] = set()
        _GLOBAL_INVERTED_INDEX[_kw_lower].add(_rule_id)

logger.info(
    "🚀 [L1.5 引擎] 倒排索引编译完成，共映射 %d 个独立微观特征关键词",
    len(_GLOBAL_INVERTED_INDEX),
)

# ==============================================================================
# [YOLO] 预处理：将触发关键词扁平化为集合（O(1) 查找）
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
# [内部] 全息探针召回（所有图谱节点属性 vs 倒排索引的 O(1) 碰撞）
# ==============================================================================
def _collect_all_props_text(graph: XiangShuGraph) -> str:
    """
    将图谱中所有非背景节点的属性，拼接为一个大文本串，供倒排索引碰撞。
    """
    parts = []
    for node in graph.nodes.values():
        if node.is_background:
            continue
        parts.append(node.label.lower())
        parts.extend(p.lower() for p in node.properties)
    return " ".join(parts)


def _get_triggered_rule_ids(all_props_text: str) -> Set[str]:
    """
    对 all_props_text 进行 O(1) 倒排碰撞，返回被触发的规则 ID 集合。
    100% 召回，不截断。
    """
    triggered: Set[str] = set()
    for kw, rule_ids in _GLOBAL_INVERTED_INDEX.items():
        if kw in all_props_text:
            triggered.update(rule_ids)
    return triggered


def _find_triggering_nodes(
    graph: XiangShuGraph, keywords: List[str]
) -> List[str]:
    """
    精准落点定位：找出图谱中实际含有 keywords 中任意关键词的节点 ID。
    """
    matched_ids = []
    for nid, node in graph.nodes.items():
        if node.is_background:
            continue
        node_text = (node.label + " " + " ".join(node.properties)).lower()
        if any(kw.lower() in node_text for kw in keywords):
            matched_ids.append(nid)
    return matched_ids


# ==============================================================================
# [内部] YOLO 拦截检测
# ==============================================================================
def _yolo_check(all_props_text: str) -> Dict[str, Any]:
    """
    检查图谱属性文本是否命中 YOLO_VETO_RULES 中的拦截关键词。
    返回 {"vetoed": bool, "reason": str}。
    """
    for entry in _YOLO_TRIGGER_SETS:
        for kw in entry["kw_set"]:
            if kw in all_props_text:
                return {"vetoed": True, "reason": entry["reason"]}
    return {"vetoed": False, "reason": ""}


# ==============================================================================
# [内部] 五行调制权重：用 INTERACTION_RULES 中的 mass_impact / tension_increment
# ==============================================================================
def _get_interaction_params(rule_key: str) -> Dict[str, float]:
    """
    从 INTERACTION_RULES 中查找对应规则的物理参数（O(1)）。
    若未找到，返回零向量占位。
    """
    default = {"mass_impact": 0.0, "tension_increment": 0.0}
    # INTERACTION_RULES key 为短名如 "Sharp_Angle_Sha"，尝试全量匹配
    if rule_key in INTERACTION_RULES:
        entry = INTERACTION_RULES[rule_key]
        return {
            "mass_impact": float(entry.get("mass_impact", 0.0)),
            "tension_increment": float(entry.get("tension_increment", 0.0)),
        }
    return default


# ==============================================================================
# [内部] 构建单条 XiangShuFinding
# ==============================================================================
def _build_finding(
    rule_id: str,
    genome: Dict[str, Any],
    triggered_node_ids: List[str],
) -> XiangShuFinding:
    """
    根据命中的基因座与触发节点，构建一条推演结论。
    权重取 XIANGSHU_WEIGHTS 中的蒸馏覆写值（若存在），否则取 genome 原始值。
    """
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
    [L1.5 主推演接口]
    输入: XiangShuGraph（由 L1 Parser 产出）
    输出: XiangShuReport（完整推演报告）

    推演流程：
    1. 收集全图属性文本
    2. YOLO 拦截检测
    3. 倒排索引 O(1) 碰撞，获取命中规则 ID 集合
    4. 遍历命中规则，构建 XiangShuFinding 列表
    5. 张量累加（物理叠加权重 / tension / mass / entropy）
    6. 按 tensor_weight 降序排列，汇总成 XiangShuReport
    """
    # Step 1: 提取全图属性文本
    all_props_text = _collect_all_props_text(graph)

    # Step 2: YOLO 拦截
    yolo_result = _yolo_check(all_props_text)
    if yolo_result["vetoed"]:
        logger.warning("[L1.5 YOLO] 拦截命中: %s", yolo_result["reason"])
        return XiangShuReport(
            image_id=graph.image_id,
            is_vetoed=True,
            veto_reason=yolo_result["reason"],
        )

    # Step 3: 倒排索引碰撞，获取命中规则集合
    triggered_rule_ids = _get_triggered_rule_ids(all_props_text)

    # 特殊补丁：T101（倒置）和 T062（裁切倾斜）通过拓扑字段直接触发
    if graph.is_inverted:
        triggered_rule_ids.add("T101")
    if abs(graph.crop_slant_degrees) >= 5.0:
        triggered_rule_ids.add("T062")

    # Step 4: 遍历命中规则，构建 findings
    findings: List[XiangShuFinding] = []
    activated_weights: List[float] = []
    tension_increments: List[float] = []
    mass_impacts: List[float] = []

    for rule_id in triggered_rule_ids:
        genome = XIANGSHU_GENOMES.get(rule_id)
        if genome is None:
            continue

        # 精准落点：找出触发节点
        keywords = genome.get("keywords", [])
        triggering_nodes = _find_triggering_nodes(graph, keywords)

        finding = _build_finding(rule_id, genome, triggering_nodes)
        findings.append(finding)

        # 收集物理张量参数
        activated_weights.append(finding.tensor_weight)
        interaction = _get_interaction_params(rule_id)
        tension_increments.append(interaction["tension_increment"])
        mass_impacts.append(interaction["mass_impact"])

    # Step 5: 张量累加
    tensor_summary = accumulate_tensor(
        activated_weights=activated_weights,
        tension_increments=tension_increments,
        mass_impacts=mass_impacts,
        global_max_tension=GLOBAL_BOUNDARY["max_tension"],
        global_min_mass=GLOBAL_BOUNDARY["min_mass"],
    )

    # Step 6: 排序 + 五大领域统计
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
        "[L1.5 引擎] image_id=%s 命中规则=%d 总权重=%.2f tension=%.2f",
        graph.image_id, len(findings), report.total_weight, report.tension,
    )
    return report
