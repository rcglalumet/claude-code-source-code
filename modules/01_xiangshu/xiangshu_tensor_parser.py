# -*- coding: utf-8 -*-
# = [端口 P: L1 降维 Parser] =
# 路径: modules/01_xiangshu/xiangshu_tensor_parser.py
# @Layer: 🔌 [L1] 象数派降维 Parser（Dumb Tool）
# @Description: 解析外部原始请求，将非结构化输入映射为 XiangShuGraph 拓扑实体。
#               绝对禁止包含 if/else 推演断语或 LLM 调用。
#               所有逻辑仅限于：字段提取、类型转换、白名单过滤、宫位坐标映射。

import logging
from typing import Any, Dict, List

from xiangshu_v102_topology import (
    XiangShuEdge,
    XiangShuGraph,
    XiangShuNode,
)
from expert_rules.xiangshu_rules import XIANGSHU_WHITELIST_KEYWORDS
from core_engine.xiangshu_math_core import pixel_to_palace_index, relation_to_score

logger = logging.getLogger("L1_XiangShu_Parser")

# ==============================================================================
# 白名单关键词集合（O(1) 查找）
# ==============================================================================
_WHITELIST_SET = frozenset(kw.lower() for kw in XIANGSHU_WHITELIST_KEYWORDS)

# 画像分类标签静态映射表（口语 -> 英文标量，O(1) 查表）
_AVATAR_CATEGORY_MAP: Dict[str, str] = {
    "真人":        "real_photo",
    "real":        "real_photo",
    "photo":       "real_photo",
    "动漫":        "anime_manga",
    "anime":       "anime_manga",
    "manga":       "anime_manga",
    "漫画":        "anime_manga",
    "风景":        "misc_landscape",
    "landscape":   "misc_landscape",
    "孤物":        "isolated_object",
    "isolated":    "isolated_object",
    "object":      "isolated_object",
    "group":       "group_photo",
    "合照":        "group_photo",
    "多人":        "group_photo",
}


def _map_avatar_category(raw: str) -> str:
    """将口语分类字符串映射为英文标量（O(1) 查表，fallback 为 'real_photo'）。"""
    return _AVATAR_CATEGORY_MAP.get(raw.strip().lower(), "real_photo")


def _is_background_node(label: str, properties: List[str]) -> bool:
    """判断节点是否属于白名单背景节点（O(1) 集合查找）。"""
    if label.lower() in _WHITELIST_SET:
        return True
    return any(p.lower() in _WHITELIST_SET for p in properties)


def _extract_properties(raw_props: Any) -> List[str]:
    """从各类原始格式中安全提取属性列表（纯工具函数，无推演）。"""
    if isinstance(raw_props, list):
        return [str(p) for p in raw_props if p]
    if isinstance(raw_props, str):
        return [p.strip() for p in raw_props.split(",") if p.strip()]
    if isinstance(raw_props, dict):
        return [str(v) for v in raw_props.values() if v]
    return []


def _parse_node(node_id: str, raw_node: Dict[str, Any]) -> XiangShuNode:
    """
    将单个原始节点字典解析为 XiangShuNode。
    严禁推演，仅做字段提取与类型转换。
    """
    label = str(raw_node.get("label", raw_node.get("type", "unknown")))
    x_norm = float(raw_node.get("x_norm", raw_node.get("x", 0.5)))
    y_norm = float(raw_node.get("y_norm", raw_node.get("y", 0.5)))
    x_norm = max(0.0, min(1.0, x_norm))
    y_norm = max(0.0, min(1.0, y_norm))
    palace_index = pixel_to_palace_index(x_norm, y_norm)

    raw_props = raw_node.get("properties", raw_node.get("attributes", []))
    properties = _extract_properties(raw_props)

    is_primary = bool(raw_node.get("is_primary_subject", False))
    is_bg = _is_background_node(label, properties)

    return XiangShuNode(
        node_id=node_id,
        label=label,
        palace_index=palace_index,
        x_norm=x_norm,
        y_norm=y_norm,
        properties=properties,
        is_primary_subject=is_primary,
        is_background=is_bg,
    )


def _parse_edge(raw_edge: Dict[str, Any]) -> XiangShuEdge:
    """
    将单个原始边字典解析为 XiangShuEdge。
    relation_type 通过 O(1) 查表映射为量化分数，无推演。
    """
    source_id = str(raw_edge.get("source", raw_edge.get("from", "")))
    target_id = str(raw_edge.get("target", raw_edge.get("to", "")))
    relation_type = str(raw_edge.get("relation", raw_edge.get("type", "NONE"))).upper()
    score = relation_to_score(relation_type)

    return XiangShuEdge(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        relation_score=score,
    )


def parse_vlm_payload(raw_payload: Dict[str, Any]) -> XiangShuGraph:
    """
    [对外接口] 将 VLM 上游的原始 JSON Payload 解析为 XiangShuGraph。

    期望的 raw_payload 结构（字段名允许多种口语变体）：
    {
        "image_id": "img_001",
        "nodes": {
            "N001": {"label": "person", "x_norm": 0.5, "y_norm": 0.5,
                     "properties": ["back_of_head", "blurry"], "is_primary_subject": true},
            ...
        },
        "edges": [
            {"source": "N001", "target": "N002", "relation": "DIVIDES"},
            ...
        ],
        "avatar_category": "real_photo",
        "crop_slant_degrees": 0.0
    }
    """
    image_id = str(raw_payload.get("image_id", "unknown"))

    # 节点解析
    raw_nodes = raw_payload.get("nodes", {})
    if isinstance(raw_nodes, list):
        raw_nodes = {str(i): n for i, n in enumerate(raw_nodes)}

    nodes: Dict[str, XiangShuNode] = {}
    primary_subject_id = ""
    for nid, rn in raw_nodes.items():
        if not isinstance(rn, dict):
            continue
        node = _parse_node(nid, rn)
        nodes[nid] = node
        if node.is_primary_subject and not primary_subject_id:
            primary_subject_id = nid

    # 边解析
    raw_edges = raw_payload.get("edges", [])
    edges: List[XiangShuEdge] = []
    for re in raw_edges:
        if isinstance(re, dict):
            edges.append(_parse_edge(re))

    # 元信息解析
    avatar_category = _map_avatar_category(
        str(raw_payload.get("avatar_category", "real"))
    )
    has_multiple = bool(raw_payload.get("has_multiple_subjects", False))
    is_inverted = bool(raw_payload.get("is_inverted", False))
    crop_slant = float(raw_payload.get("crop_slant_degrees", 0.0))

    graph = XiangShuGraph(
        image_id=image_id,
        nodes=nodes,
        edges=edges,
        primary_subject_id=primary_subject_id,
        avatar_category=avatar_category,
        has_multiple_subjects=has_multiple,
        is_inverted=is_inverted,
        crop_slant_degrees=crop_slant,
    )

    logger.debug(
        "[Parser] image_id=%s nodes=%d edges=%d primary=%s",
        image_id, len(nodes), len(edges), primary_subject_id,
    )
    return graph
