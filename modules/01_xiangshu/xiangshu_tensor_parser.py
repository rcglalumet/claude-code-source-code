# -*- coding: utf-8 -*-
# = [端口 P: L1 降维 Parser] =
# 路径: modules/01_xiangshu/xiangshu_tensor_parser.py
# @Layer: [L1] 象数派降维 Parser（绝对 Dumb Tool）
# @Description:
#   将 VLM 上游的 11 维象数载荷 JSON 反序列化为 XiangShuGraph。
#   核心原则：直接利用 Pydantic model_validate 进行反序列化，禁止一切猜测逻辑。
#   Parser 唯一允许的操作：
#     1. JSON key 的静态别名映射（alias）
#     2. palace 字符串 -> palace_index 的 O(1) 静态查表
#     3. relation_type -> relation_score 的 O(1) 静态查表
#     4. 白名单背景节点的 O(1) frozenset 过滤
#   严禁：if/else 推演断语、LLM 调用、语义猜测、任何业务判断。

import logging
from typing import Any, Dict, List

from xiangshu_v102_topology import (
    ArrayOrientationDim,
    AsymmetricHeightDim,
    ColorShapePiercingDim,
    CornerJammingDim,
    FluidDensityDim,
    FluidSoaking3DDim,
    GestaltMimicryDim,
    GranularPhysicsDim,
    PhysicalTiltDim,
    SurfaceAgingDim,
    TruncationDim,
    XiangShuEdge,
    XiangShuGraph,
    XiangShuNode,
)
from expert_rules.xiangshu_rules import XIANGSHU_WHITELIST_KEYWORDS
from core_engine.xiangshu_math_core import relation_to_score

logger = logging.getLogger("L1_XiangShu_Parser_V11")

# ==============================================================================
# [静态常数] 白名单关键词集合（O(1) 查找）
# ==============================================================================
_WHITELIST_SET: frozenset = frozenset(kw.lower() for kw in XIANGSHU_WHITELIST_KEYWORDS)

# ==============================================================================
# [静态常数] 文王八卦宫位名 -> 洛书九宫格 index 映射（O(1) 查表）
# 布局依据：洛书标准数字宫位
# ==============================================================================
_PALACE_TO_INDEX: Dict[str, int] = {
    "GEN":    1,   # 艮（东北）-> 左上
    "KAN":    2,   # 坎（北）  -> 上中
    "XUN":    3,   # 巽（东南）-> 右上
    "ZHEN":   4,   # 震（东）  -> 左中
    "CENTER": 5,   # 中宫      -> 正中
    "DUI":    6,   # 兑（西）  -> 右中
    "KUN":    7,   # 坤（西南）-> 左下
    "LI":     8,   # 离（南）  -> 下中
    "QIAN":   9,   # 乾（西北）-> 右下
}

# ==============================================================================
# [静态常数] engine_topology.edges[] 中 JSON key "source_id" 别名映射
# VLM 产出的边字段名可能为 source_id 或 source，统一为 source_id
# ==============================================================================
_EDGE_KEY_ALIASES: Dict[str, str] = {
    "source":    "source_id",
    "target":    "target_id",
    "relation":  "relation_type",
}


# ==============================================================================
# [内部工具] 节点原始数据规范化（仅做 key 映射 + 类型转换，零推演）
# ==============================================================================
def _normalize_node_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    将原始节点字典规范化为 XiangShuNode.model_validate 可直接消费的格式。
    仅处理：字段别名（id -> node_id via alias）、palace_index 查表、
    is_background 白名单过滤。
    """
    normalized = dict(raw)

    # palace -> palace_index（O(1) 查表）
    palace_raw = str(normalized.get("palace", "CENTER")).upper()
    normalized["palace_index"] = _PALACE_TO_INDEX.get(palace_raw, 5)
    normalized["palace"] = palace_raw

    # 白名单背景检测（O(1) frozenset 查找）
    label = str(normalized.get("concept", normalized.get("label", ""))).lower()
    props: List[str] = normalized.get("properties", [])
    normalized["is_background"] = (
        label in _WHITELIST_SET
        or any(p.lower() in _WHITELIST_SET for p in props)
    )
    normalized["is_primary_subject"] = False

    # Pydantic alias 要求：XiangShuNode 用 alias="id"，model_validate 时传 "id"
    # 确保 "id" 字段存在（VLM 可能用 "id" 或 "node_id"）
    if "id" not in normalized and "node_id" in normalized:
        normalized["id"] = normalized["node_id"]

    return normalized


# ==============================================================================
# [内部工具] 边原始数据规范化（仅做 key 映射 + relation_score 查表，零推演）
# ==============================================================================
def _normalize_edge_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    将原始边字典规范化为 XiangShuEdge.model_validate 可直接消费的格式。
    仅处理：字段别名映射、relation_score O(1) 查表。
    """
    normalized: Dict[str, Any] = {}
    for k, v in raw.items():
        canonical_key = _EDGE_KEY_ALIASES.get(k, k)
        normalized[canonical_key] = v

    # relation_score O(1) 查表
    relation_type = str(normalized.get("relation_type", "NONE")).upper()
    normalized["relation_type"] = relation_type
    normalized["relation_score"] = relation_to_score(relation_type)
    normalized.setdefault("context", "")

    return normalized


# ==============================================================================
# [对外接口] 主解析函数：VLM 11 维 Payload -> XiangShuGraph
# 核心：直接调用 model_validate，禁止一切推演猜测。
# ==============================================================================
def parse_vlm_payload(raw_payload: Dict[str, Any]) -> XiangShuGraph:
    """
    [绝对 Dumb Tool] 将 VLM 11 维象数载荷 JSON 反序列化为 XiangShuGraph。

    预期 raw_payload 顶层结构：
    {
        "gestalt_mimicry_and_text_decomposition": { ... },
        "truncation_and_interior_mapping":         { ... },
        "surface_aging_and_neatness":              { ... },
        "array_orientation_and_protrusion":        { ... },
        "physical_tilt_and_exposed_facet":         { ... },
        "asymmetrical_height_disparity":           { ... },
        "fluid_density_matching_and_migration":    { ... },
        "granular_physics_and_edge_sharpness":     { ... },
        "corner_jamming_and_turbulence":           { ... },
        "fluid_soaking_and_3d_stacking":           { ... },
        "color_shape_taste_and_piercing":          { ... },
        "engine_topology": {
            "nodes": [ {"id": ..., "palace": ..., "properties": [...]} ],
            "edges": [ {"source_id": ..., "target_id": ..., "relation": ...} ]
        }
    }
    """
    # --- [1] 11 维度 model_validate（直接反序列化，零猜测）---
    gestalt_mimicry = GestaltMimicryDim.model_validate(
        raw_payload.get("gestalt_mimicry_and_text_decomposition", {})
    )
    truncation = TruncationDim.model_validate(
        raw_payload.get("truncation_and_interior_mapping", {})
    )
    surface_aging = SurfaceAgingDim.model_validate(
        raw_payload.get("surface_aging_and_neatness", {})
    )
    array_orientation = ArrayOrientationDim.model_validate(
        raw_payload.get("array_orientation_and_protrusion", {})
    )
    physical_tilt = PhysicalTiltDim.model_validate(
        raw_payload.get("physical_tilt_and_exposed_facet", {})
    )
    asymmetric_height = AsymmetricHeightDim.model_validate(
        raw_payload.get("asymmetrical_height_disparity", {})
    )
    fluid_density = FluidDensityDim.model_validate(
        raw_payload.get("fluid_density_matching_and_migration", {})
    )
    granular_physics = GranularPhysicsDim.model_validate(
        raw_payload.get("granular_physics_and_edge_sharpness", {})
    )
    corner_jamming = CornerJammingDim.model_validate(
        raw_payload.get("corner_jamming_and_turbulence", {})
    )
    fluid_soaking_3d = FluidSoaking3DDim.model_validate(
        raw_payload.get("fluid_soaking_and_3d_stacking", {})
    )
    color_shape_piercing = ColorShapePiercingDim.model_validate(
        raw_payload.get("color_shape_taste_and_piercing", {})
    )

    # --- [2] engine_topology: nodes + edges ---
    topology_raw = raw_payload.get("engine_topology", {})

    raw_nodes_list: List[Dict[str, Any]] = topology_raw.get("nodes", [])
    nodes: Dict[str, XiangShuNode] = {}
    primary_subject_id = ""
    for rn in raw_nodes_list:
        if not isinstance(rn, dict):
            continue
        normalized = _normalize_node_dict(rn)
        node = XiangShuNode.model_validate(normalized)
        nodes[node.node_id] = node

    raw_edges_list: List[Dict[str, Any]] = topology_raw.get("edges", [])
    edges: List[XiangShuEdge] = []
    for re in raw_edges_list:
        if not isinstance(re, dict):
            continue
        normalized_edge = _normalize_edge_dict(re)
        edges.append(XiangShuEdge.model_validate(normalized_edge))

    # --- [3] 元数据直接透传（tilt_degrees -> crop_slant_degrees）---
    tilt_degrees = physical_tilt.tilt_degrees
    is_inverted = fluid_soaking_3d.dimension_fold_present

    image_id = str(raw_payload.get("image_id", "unknown"))
    avatar_category = str(raw_payload.get("avatar_category", "misc_landscape"))

    graph = XiangShuGraph(
        image_id=image_id,
        gestalt_mimicry=gestalt_mimicry,
        truncation=truncation,
        surface_aging=surface_aging,
        array_orientation=array_orientation,
        physical_tilt=physical_tilt,
        asymmetric_height=asymmetric_height,
        fluid_density=fluid_density,
        granular_physics=granular_physics,
        corner_jamming=corner_jamming,
        fluid_soaking_3d=fluid_soaking_3d,
        color_shape_piercing=color_shape_piercing,
        nodes=nodes,
        edges=edges,
        primary_subject_id=primary_subject_id,
        avatar_category=avatar_category,
        is_inverted=is_inverted,
        crop_slant_degrees=tilt_degrees,
    )

    logger.debug(
        "[Parser V11] image_id=%s nodes=%d edges=%d",
        image_id, len(nodes), len(edges),
    )
    return graph
