# === [L2 大一统推演引擎] ===
# 路径: modules/02_bazi/bazi_unified_engine.py
# 整合 V118 宏观张量 + V101 微观探针 + Amulet V2.0 图鉴专家
# 输入：BaziFullCluster；输出：BaziTensionDNA（填充后注入 cluster）
# 禁止：LLM 调用、网络请求、Enum 罗列

from __future__ import annotations

from typing import List

from expert_rules.bazi_rules import (
    BAZI_TENSION_POLARITY, V7_CLIMATE_RULES, V7_ROOT_QI_MATRIX,
    RESOURCE_CYCLE, GENERATE_CYCLE, CONTROL_CYCLE,
    ELEMENT_MAP, HIDDEN_QUARKS, STEM_COMBOS, STEM_CLASHES,
    FULL_COMBOS, CLASH_PAIRS, PUNISH_PAIRS, HARM_PAIRS,
    TOMB_MAP, THERMO_WARM, THERMO_COLD, MATRIX_L1_CHONG, MATRIX_L1_HE,
    STEMS, BRANCHES,
)
from .bazi_v102_topology import (
    BaziFullCluster, BaziTensionDNA, BaziKinshipPointers,
)


# ==========================================
# 内部轻量节点与柱对象（替代 torch 依赖）
# ==========================================

class _Node:
    __slots__ = ("char", "wuxing", "yinyang", "state")

    def __init__(self, char: str, wuxing: str, yinyang: str):
        self.char = char
        self.wuxing = wuxing
        self.yinyang = yinyang
        self.state = "ACTIVE"


class _DayMaster(_Node):
    def get_relationship(self, other_wuxing: str | None, other_yinyang: str | None) -> str:
        if not other_wuxing:
            return "未知"
        same_yy = self.yinyang == other_yinyang
        if self.wuxing == other_wuxing:
            return "比肩" if same_yy else "劫财"
        if GENERATE_CYCLE.get(self.wuxing) == other_wuxing:
            return "食神" if same_yy else "伤官"
        if GENERATE_CYCLE.get(other_wuxing) == self.wuxing:
            return "偏印" if same_yy else "正印"
        if CONTROL_CYCLE.get(self.wuxing) == other_wuxing:
            return "偏财" if same_yy else "正财"
        if CONTROL_CYCLE.get(other_wuxing) == self.wuxing:
            return "七杀" if same_yy else "正官"
        return "未知"


class _Pillar:
    __slots__ = ("name", "stem", "branch")

    def __init__(self, name: str):
        self.name = name
        self.stem: _Node | None = None
        self.branch: _Node | None = None


class _Cluster:
    def __init__(self):
        self.pillars: dict[str, _Pillar] = {
            "年": _Pillar("年"), "月": _Pillar("月"),
            "日": _Pillar("日"), "时": _Pillar("时"),
        }
        self.day_master: _DayMaster | None = None
        self.all_nodes: list[_Node] = []

    def get_all_interaction_tags(self) -> set[str]:
        tags: set[str] = set()
        branches = [p.branch.char for p in self.pillars.values() if p.branch]
        for i in range(len(branches)):
            for j in range(i + 1, len(branches)):
                pair = {branches[i], branches[j]}
                if pair in MATRIX_L1_CHONG:
                    tags.add(f"TAG_地支相冲_{branches[i]}{branches[j]}")
                if pair in MATRIX_L1_HE:
                    tags.add(f"TAG_地支相合_{branches[i]}{branches[j]}")
        return tags


_POS_TO_PILLAR: dict[str, tuple[str, str]] = {
    "年干": ("年", "stem"), "年支": ("年", "branch"),
    "月干": ("月", "stem"), "月支": ("月", "branch"),
    "日干": ("日", "stem"), "日支": ("日", "branch"),
    "时干": ("时", "stem"), "时支": ("时", "branch"),
}

_HOLO_MAP: dict[str, str] = {
    "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午",
    "戊": "巳", "己": "午", "庚": "申", "辛": "酉",
    "壬": "亥", "癸": "子",
}


def _build_cluster_from_topology(cluster: BaziFullCluster) -> _Cluster:
    """将 BaziFullCluster 拓扑降维为引擎内部轻量 Cluster。"""
    c = _Cluster()
    for node in cluster.nodes:
        pillar_name, attr_name = _POS_TO_PILLAR.get(node.pos, (None, None))
        if not pillar_name:
            continue
        if node.pos == "日干":
            n_obj = _DayMaster(node.char, node.element, node.polarity)
            c.day_master = n_obj
        else:
            n_obj = _Node(node.char, node.element, node.polarity)
        setattr(c.pillars[pillar_name], attr_name, n_obj)
        c.all_nodes.append(n_obj)
    return c


# ==========================================
# 探针函数集（所有 rule_vXXX 方法提取为模块级函数）
# ==========================================

def _p_branch(cluster: _Cluster, name: str) -> _Node | None:
    return getattr(cluster.pillars.get(name, _Pillar(name)), "branch", None)


def _p_stem(cluster: _Cluster, name: str) -> _Node | None:
    return getattr(cluster.pillars.get(name, _Pillar(name)), "stem", None)


def rule_v101_holographic_info_capture(cluster: _Cluster) -> float:
    dm = cluster.day_master
    if not dm:
        return 0.0
    for p in cluster.pillars.values():
        if not p.stem or p.stem is dm:
            continue
        rel = dm.get_relationship(p.stem.wuxing, p.stem.yinyang)
        if "财" in rel or "官" in rel or "杀" in rel:
            branch_char = p.branch.char if p.branch else ""
            is_solid = (
                p.stem.char in HIDDEN_QUARKS.get(branch_char, [])
                or (p.branch and p.stem.wuxing == p.branch.wuxing)
            )
            if not is_solid and {dm.char, p.stem.char} in STEM_COMBOS:
                return 1.0
    return 0.0


def rule_v101_structural_overload_collapse(cluster: _Cluster) -> float:
    dm = cluster.day_master
    if not dm:
        return 0.0
    support_count = sum(
        1 for p in cluster.pillars.values()
        if p.branch and dm.get_relationship(p.branch.wuxing, p.branch.yinyang) in ["比肩", "劫财", "正印", "偏印"]
    )
    if support_count > 0:
        return 0.0
    db = _p_branch(cluster, "日")
    day_b_char = db.char if db else ""
    for p in cluster.pillars.values():
        if not p.branch:
            continue
        rel = dm.get_relationship(p.branch.wuxing, p.branch.yinyang)
        if "财" in rel or "杀" in rel:
            ob = p.branch.char
            if (
                {day_b_char, ob} in FULL_COMBOS
                or {day_b_char, ob} in CLASH_PAIRS
                or (day_b_char in TOMB_MAP and ob in TOMB_MAP.get(day_b_char, []))
            ):
                return 1.0
    return 0.0


def rule_v101_massive_solid_predation(cluster: _Cluster) -> float:
    dm = cluster.day_master
    if not dm:
        return 0.0
    support_count = sum(
        1 for p in cluster.pillars.values()
        if p.branch and dm.get_relationship(p.branch.wuxing, p.branch.yinyang) in ["比肩", "劫财", "正印", "偏印"]
    )
    if support_count < 2:
        return 0.0
    db = _p_branch(cluster, "日")
    day_b_char = db.char if db else ""
    for p in cluster.pillars.values():
        if not p.branch:
            continue
        rel = dm.get_relationship(p.branch.wuxing, p.branch.yinyang)
        if "财" in rel or "杀" in rel:
            ob = p.branch.char
            if (
                {day_b_char, ob} in FULL_COMBOS
                or {day_b_char, ob} in CLASH_PAIRS
                or (day_b_char in TOMB_MAP and ob in TOMB_MAP.get(day_b_char, []))
            ):
                return 1.0
    return 0.0


def rule_v100_macro_condensate(cluster: _Cluster) -> float:
    all_chars = [n.char for n in cluster.all_nodes]
    total = len(all_chars)
    if total == 0:
        return 0.0
    warm = sum(1 for c in all_chars if c in THERMO_WARM)
    cold = sum(1 for c in all_chars if c in THERMO_COLD)
    if warm / total > 0.75 or cold / total > 0.75:
        return 1.0
    return 0.0


def rule_v100_cross_domain_predation(cluster: _Cluster) -> float:
    inner = [
        (_p_branch(cluster, "日") or _Node("", "", "")).char,
        (_p_branch(cluster, "时") or _Node("", "", "")).char,
    ]
    outer = [
        (_p_branch(cluster, "年") or _Node("", "", "")).char,
        (_p_branch(cluster, "月") or _Node("", "", "")).char,
    ]
    for ib in inner:
        for ob in outer:
            if not ib or not ob:
                continue
            if (
                {ib, ob} in FULL_COMBOS
                or {ib, ob} in CLASH_PAIRS
                or (ib in TOMB_MAP and ob in TOMB_MAP.get(ib, []))
                or (ob in TOMB_MAP and ib in TOMB_MAP.get(ob, []))
            ):
                return 1.0
    return 0.0


def rule_v100_high_entropy_thermal_death(cluster: _Cluster) -> float:
    if rule_v100_macro_condensate(cluster) == 0.0 and rule_v100_cross_domain_predation(cluster) == 0.0:
        return 1.0
    return 0.0


def rule_v100_chain_reaction_matrix(cluster: _Cluster) -> float:
    hb = (_p_branch(cluster, "时") or _Node("", "", "")).char
    db = (_p_branch(cluster, "日") or _Node("", "", "")).char
    mb = (_p_branch(cluster, "月") or _Node("", "", "")).char
    yb = (_p_branch(cluster, "年") or _Node("", "", "")).char

    def acts(b1: str, b2: str) -> bool:
        if not b1 or not b2:
            return False
        return (
            {b1, b2} in FULL_COMBOS
            or {b1, b2} in CLASH_PAIRS
            or (b1 in TOMB_MAP and b2 in TOMB_MAP.get(b1, []))
        )
    if acts(hb, db) and acts(db, mb) and acts(mb, yb):
        return 1.0
    return 0.0


def rule_v99_base_work_active(cluster: _Cluster) -> float:
    db_node = _p_branch(cluster, "日")
    if not db_node:
        return 0.0
    db = db_node.char
    for name, p in cluster.pillars.items():
        if name != "日" and p.branch:
            ob = p.branch.char
            if (
                {db, ob} in FULL_COMBOS
                or {db, ob} in CLASH_PAIRS
                or (db in TOMB_MAP and ob in TOMB_MAP.get(db, []))
                or (ob in TOMB_MAP and db in TOMB_MAP.get(ob, []))
            ):
                return 1.0
    return 0.0


def rule_v99_antimatter_fission(cluster: _Cluster) -> float:
    dm = cluster.day_master
    db_node = _p_branch(cluster, "日")
    if not dm or not db_node:
        return 0.0
    db = db_node.char
    for name, p in cluster.pillars.items():
        if name != "日" and p.branch and dm.get_relationship(p.branch.wuxing, p.branch.yinyang) == "七杀":
            ob = p.branch.char
            if (
                {db, ob} in FULL_COMBOS
                or {db, ob} in CLASH_PAIRS
                or (db in TOMB_MAP and ob in TOMB_MAP.get(db, []))
            ):
                return 1.0
    return 0.0


def rule_v99_blackhole_nesting(cluster: _Cluster) -> float:
    branches = {p.branch.char for p in cluster.pillars.values() if p.branch}
    if ("辰" in branches and "未" in branches) or ("戌" in branches and "丑" in branches):
        return 1.0
    return 0.0


def rule_v99_dyson_sphere_topology(cluster: _Cluster) -> float:
    yb = _p_branch(cluster, "年")
    hb = _p_branch(cluster, "时")
    db = _p_branch(cluster, "日")
    if not yb or not hb or not db:
        return 0.0
    if yb.wuxing == hb.wuxing == db.wuxing and db.char != yb.char:
        return 1.0
    return 0.0


def rule_v98_holographic_flesh_smash(cluster: _Cluster) -> float:
    dm = cluster.day_master
    if not dm:
        return 0.0
    body_char = _HOLO_MAP.get(dm.char)
    if not body_char:
        return 0.0
    branches = [p.branch for p in cluster.pillars.values() if p.branch]
    if not any(b.char == body_char for b in branches):
        return 0.0
    body_wx = next((b.wuxing for b in branches if b.char == body_char), None)
    for b in branches:
        if b.char in ["丑", "辰", "未", "戌"] and GENERATE_CYCLE.get(b.wuxing) == body_wx:
            return 1.0
    return 0.0


def rule_v98_spatial_density_and_proximity(cluster: _Cluster) -> float:
    dm = cluster.day_master
    output_wx = GENERATE_CYCLE.get(dm.wuxing) if dm else None
    if not output_wx:
        return 0.0
    has_output = any(
        getattr(p.stem, "wuxing", None) == output_wx or getattr(p.branch, "wuxing", None) == output_wx
        for p in cluster.pillars.values()
    )
    has_resource_to_output = any(
        GENERATE_CYCLE.get(getattr(p.stem, "wuxing", None)) == output_wx
        for p in cluster.pillars.values()
    )
    has_control_of_output = any(
        CONTROL_CYCLE.get(getattr(p.branch, "wuxing", None)) == output_wx
        for p in cluster.pillars.values()
    )
    if has_output and has_resource_to_output and has_control_of_output:
        return 1.0
    return 0.0


def rule_v98_dual_protocol_orbit(cluster: _Cluster) -> float:
    wx_polar_map: dict[str, set[str]] = {}
    dm = cluster.day_master
    for p in cluster.pillars.values():
        s = p.stem
        if not s or s is dm:
            continue
        wx_polar_map.setdefault(s.wuxing, set()).add(s.yinyang)
    for polars in wx_polar_map.values():
        if len(polars) >= 2:
            return 1.0
    return 0.0


def rule_v97_interference_damping(cluster: _Cluster) -> float:
    branches = [p.branch.char for p in cluster.pillars.values() if p.branch]
    for b1 in branches:
        for b2 in branches:
            if not b1 or not b2 or b1 == b2:
                continue
            if {b1, b2} in CLASH_PAIRS:
                if any({b1, ob} in FULL_COMBOS for ob in branches if ob and ob != b1):
                    return 1.0
                if any({b2, ob} in FULL_COMBOS for ob in branches if ob and ob != b2):
                    return 1.0
    return 0.0


def rule_v97_conditional_harm_breach(cluster: _Cluster) -> float:
    pillars = list(cluster.pillars.values())
    for i in range(len(pillars)):
        for j in range(i + 1, len(pillars)):
            p1, p2 = pillars[i], pillars[j]
            if not p1.branch or not p2.branch or not p1.stem or not p2.stem:
                continue
            if {p1.branch.char, p2.branch.char} in HARM_PAIRS and {p1.stem.char, p2.stem.char} in STEM_COMBOS:
                return 1.0
    return 0.0


def rule_v97_z_axis_diode_suppression(cluster: _Cluster) -> float:
    for p in cluster.pillars.values():
        if not p.stem or not p.branch:
            continue
        if CONTROL_CYCLE.get(p.stem.wuxing) == p.branch.wuxing:
            return 1.0
    return 0.0


def rule_v96_isotopic_absolute_strike(cluster: _Cluster) -> float:
    pvals = list(cluster.pillars.values())
    for i, p1 in enumerate(pvals):
        for p2 in pvals[i + 1:]:
            if not p1.stem or not p2.stem or not p1.branch or not p2.branch:
                continue
            s1, s2 = p1.stem, p2.stem
            if (
                CONTROL_CYCLE.get(s1.wuxing) == s2.wuxing
                and s1.yinyang == s2.yinyang
                and {s1.char, s2.char} not in STEM_COMBOS
            ):
                return 1.0
            b1, b2 = p1.branch, p2.branch
            if (
                CONTROL_CYCLE.get(b1.wuxing) == b2.wuxing
                and b1.yinyang == b2.yinyang
                and {b1.char, b2.char} not in FULL_COMBOS
            ):
                return 1.0
    return 0.0


def rule_v96_entangled_convergence(cluster: _Cluster) -> float:
    pvals = list(cluster.pillars.values())
    for i, p1 in enumerate(pvals):
        for p2 in pvals[i + 1:]:
            if not p1.stem or not p2.stem or not p1.branch or not p2.branch:
                continue
            s1, s2 = p1.stem, p2.stem
            if (
                CONTROL_CYCLE.get(s1.wuxing) == s2.wuxing
                or CONTROL_CYCLE.get(s2.wuxing) == s1.wuxing
            ) and {s1.char, s2.char} in STEM_COMBOS:
                return 1.0
            b1, b2 = p1.branch, p2.branch
            if (
                CONTROL_CYCLE.get(b1.wuxing) == b2.wuxing
                or CONTROL_CYCLE.get(b2.wuxing) == b1.wuxing
            ) and {b1.char, b2.char} in FULL_COMBOS:
                return 1.0
    return 0.0


def rule_v95_distance_insulation(cluster: _Cluster) -> float:
    idx_map = {"年": 0, "月": 1, "日": 2, "时": 3}
    items = list(cluster.pillars.items())
    for i, (n1, p1) in enumerate(items):
        for n2, p2 in items[i + 1:]:
            if not p1.branch or not p2.branch:
                continue
            if abs(idx_map.get(n1, 0) - idx_map.get(n2, 0)) > 1:
                if (
                    GENERATE_CYCLE.get(p1.branch.wuxing) == p2.branch.wuxing
                    or CONTROL_CYCLE.get(p1.branch.wuxing) == p2.branch.wuxing
                ):
                    return 1.0
    return 0.0


def rule_v95_high_energy_activation(cluster: _Cluster) -> float:
    db_node = _p_branch(cluster, "日")
    if not db_node:
        return 0.0
    db = db_node.char
    branches = [p.branch.char for p in cluster.pillars.values() if p.branch and p.branch.char != db]
    for ob in branches:
        if {db, ob} in FULL_COMBOS or {db, ob} in CLASH_PAIRS or {db, ob} in PUNISH_PAIRS:
            return 1.0
    return 0.0


def rule_v94_spatial_density_compression(cluster: _Cluster) -> float:
    has_earth = any(n.wuxing == "土" for n in cluster.all_nodes)
    has_crashed_water = any(
        n.wuxing == "水" and n.state == "CRASHED" for n in cluster.all_nodes
    )
    if has_earth and has_crashed_water:
        return 1.0
    return 0.0


def rule_v93_high_entropy_transient_entanglement(cluster: _Cluster) -> float:
    dm = cluster.day_master
    if not dm:
        return 0.0
    pvals = list(cluster.pillars.values())
    for p in pvals:
        if p.stem and dm.get_relationship(p.stem.wuxing, p.stem.yinyang) in ["偏财", "七杀"]:
            if any(
                {p.stem.char, os.stem.char} in STEM_COMBOS
                for os in pvals if os is not p and os.stem
            ):
                return 1.0
        if p.branch and dm.get_relationship(p.branch.wuxing, p.branch.yinyang) in ["偏财", "七杀"]:
            if any(
                {p.branch.char, ob.branch.char} in FULL_COMBOS
                for ob in pvals if ob is not p and ob.branch
            ):
                return 1.0
    return 0.0


def rule_v93_low_entropy_stable_anchor(cluster: _Cluster) -> float:
    dm = cluster.day_master
    if not dm:
        return 0.0
    pvals = list(cluster.pillars.values())
    for p in pvals:
        if p.stem and dm.get_relationship(p.stem.wuxing, p.stem.yinyang) in ["正财", "正官"]:
            if any(
                {p.stem.char, os.stem.char} in STEM_COMBOS
                for os in pvals if os is not p and os.stem
            ):
                return 1.0
        if p.branch and dm.get_relationship(p.branch.wuxing, p.branch.yinyang) in ["正财", "正官"]:
            if any(
                {p.branch.char, ob.branch.char} in FULL_COMBOS
                for ob in pvals if ob is not p and ob.branch
            ):
                return 1.0
    return 0.0


def rule_v92_topological_reversal_stem(cluster: _Cluster) -> float:
    stems = [p.stem.char for p in cluster.pillars.values() if p.stem]
    for s in stems:
        has_combo = any({s, os} in STEM_COMBOS for os in stems if os and os != s)
        has_clash = any({s, os} in STEM_CLASHES for os in stems if os and os != s)
        if has_combo and has_clash:
            return 1.0
    return 0.0


def rule_v92_topological_reversal_branch(cluster: _Cluster) -> float:
    branches = [p.branch.char for p in cluster.pillars.values() if p.branch]
    for b in branches:
        has_combo = any({b, ob} in FULL_COMBOS for ob in branches if ob and ob != b)
        has_clash = any({b, ob} in CLASH_PAIRS for ob in branches if ob and ob != b)
        if has_combo and has_clash:
            return 1.0
    return 0.0


def rule_v91_authority_void_sublimation(cluster: _Cluster) -> float:
    dm = cluster.day_master
    if not dm:
        return 0.0
    try:
        day_p = cluster.pillars.get("日")
        if not day_p or not day_p.branch or not day_p.stem:
            return 0.0
        offset = (BRANCHES.index(day_p.branch.char) - STEMS.index(day_p.stem.char)) % 12
        void_1 = BRANCHES[(BRANCHES.index(day_p.branch.char) - (STEMS.index(day_p.stem.char) % 10) + 10) % 12]
        void_2 = BRANCHES[(BRANCHES.index(day_p.branch.char) - (STEMS.index(day_p.stem.char) % 10) + 11) % 12]
        xun_branch_start = (BRANCHES.index(day_p.branch.char) - STEMS.index(day_p.stem.char) % 10) % 12
        void_1 = BRANCHES[(xun_branch_start + 10) % 12]
        void_2 = BRANCHES[(xun_branch_start + 11) % 12]
        for p in cluster.pillars.values():
            if not p.branch:
                continue
            if p.branch.char in [void_1, void_2]:
                rel = dm.get_relationship(p.branch.wuxing, p.branch.yinyang)
                if "官" in rel or "杀" in rel:
                    return 1.0
    except Exception:
        pass
    return 0.0


def rule_v91_clone_resource_seizure(cluster: _Cluster) -> float:
    dm = cluster.day_master
    if not dm:
        return 0.0
    clones = sum(
        1 for n in cluster.all_nodes
        if n is not dm and dm.get_relationship(n.wuxing, n.yinyang) in ["比肩", "劫财"]
    )
    resources = sum(
        1 for n in cluster.all_nodes
        if n is not dm and "财" in dm.get_relationship(n.wuxing, n.yinyang)
    )
    if clones >= 2 and resources >= 1:
        return 1.0
    return 0.0


def rule_v90_virtual_calculation_void(cluster: _Cluster) -> float:
    try:
        day_p = cluster.pillars.get("日")
        if not day_p or not day_p.branch or not day_p.stem:
            return 0.0
        xun_branch_start = (BRANCHES.index(day_p.branch.char) - STEMS.index(day_p.stem.char) % 10) % 12
        void_1 = BRANCHES[(xun_branch_start + 10) % 12]
        void_2 = BRANCHES[(xun_branch_start + 11) % 12]
        for p in cluster.pillars.values():
            if p.branch and p.branch.char in [void_1, void_2] and p.branch.wuxing == "水":
                return 1.0
    except Exception:
        pass
    return 0.0


def rule_v84_orbital_drag(cluster: _Cluster) -> float:
    db_node = _p_branch(cluster, "日")
    if not db_node:
        return 0.0
    db = db_node.char
    for name, p in cluster.pillars.items():
        if name != "日" and p.branch and {db, p.branch.char} in FULL_COMBOS:
            return 1.0
    return 0.0


def rule_v84_void_singularity_arch(cluster: _Cluster) -> float:
    branches = {p.branch.char for p in cluster.pillars.values() if p.branch}
    for pair in [{"亥", "未"}, {"寅", "戌"}, {"巳", "丑"}, {"申", "辰"}]:
        if pair.issubset(branches):
            return 1.0
    return 0.0


def rule_v83_subatomic_penetration(cluster: _Cluster) -> float:
    branches = {p.branch.char for p in cluster.pillars.values() if p.branch}
    if {"寅", "亥"}.issubset(branches) or {"辰", "酉"}.issubset(branches):
        return 1.0
    return 0.0


def rule_v83_quark_confinement(cluster: _Cluster) -> float:
    branches = {p.branch.char for p in cluster.pillars.values() if p.branch}
    for pair in [{"子", "丑"}, {"辰", "酉"}, {"午", "未"}, {"卯", "戌"}]:
        if pair.issubset(branches):
            return 1.0
    return 0.0


def rule_v82_quark_ascension(cluster: _Cluster) -> float:
    for p in cluster.pillars.values():
        if not p.stem:
            continue
        stem_char = p.stem.char
        stem_wx = p.stem.wuxing
        has_same_wx_branch = any(
            bp.branch and bp.branch.wuxing == stem_wx
            for bp in cluster.pillars.values()
        )
        if not has_same_wx_branch:
            hidden_in_any = any(
                stem_char in HIDDEN_QUARKS.get(bp.branch.char, [])
                for bp in cluster.pillars.values() if bp.branch
            )
            if hidden_in_any:
                return 1.0
    return 0.0


def rule_v80_quantum_tunneling_ground(cluster: _Cluster) -> float:
    for p in cluster.pillars.values():
        if not p.stem:
            continue
        if not any(
            bp.branch and bp.branch.wuxing == p.stem.wuxing
            for bp in cluster.pillars.values()
        ):
            return 1.0
    return 0.0


def rule_v80_singularity_siphon(cluster: _Cluster) -> float:
    branches = {p.branch.char for p in cluster.pillars.values() if p.branch}
    for trinity in [{"申", "子", "辰"}, {"亥", "卯", "未"}, {"寅", "午", "戌"}, {"巳", "酉", "丑"}]:
        if trinity.issubset(branches):
            return 1.0
    return 0.0


def rule_v77_father_evaporation(cluster: _Cluster) -> float:
    dm = cluster.day_master
    if not dm:
        return 0.0
    father_wx = CONTROL_CYCLE.get(dm.wuxing)
    if not father_wx:
        return 0.0
    if not any(p.stem and p.stem.wuxing == father_wx for p in cluster.pillars.values()):
        return 1.0
    return 0.0


def rule_v77_terminal_void_decay(cluster: _Cluster) -> float:
    try:
        day_p = cluster.pillars.get("日")
        if not day_p or not day_p.branch or not day_p.stem:
            return 0.0
        xun_branch_start = (BRANCHES.index(day_p.branch.char) - STEMS.index(day_p.stem.char) % 10) % 12
        void_1 = BRANCHES[(xun_branch_start + 10) % 12]
        void_2 = BRANCHES[(xun_branch_start + 11) % 12]
        dm = cluster.day_master
        hour_b = _p_branch(cluster, "时")
        if not hour_b or not dm:
            return 0.0
        if hour_b.char in [void_1, void_2] and hour_b.wuxing == GENERATE_CYCLE.get(dm.wuxing):
            return 1.0
    except Exception:
        pass
    return 0.0


def rule_v73_containment_singularity(cluster: _Cluster) -> float:
    _tomb_stored = {"辰": "水", "戌": "火", "丑": "金", "未": "木"}
    dm = cluster.day_master
    if not dm:
        return 0.0
    for p in cluster.pillars.values():
        if not p.branch:
            continue
        stored = _tomb_stored.get(p.branch.char)
        if stored and (
            CONTROL_CYCLE.get(stored) == dm.wuxing
            or GENERATE_CYCLE.get(dm.wuxing) == stored
        ):
            return 1.0
    return 0.0


def rule_v13_absolute_weakness(cluster: _Cluster) -> float:
    dm = cluster.day_master
    if not dm:
        return 0.0
    has_root = any(
        p.branch and dm.get_relationship(p.branch.wuxing, p.branch.yinyang) in ["比肩", "劫财", "正印", "偏印"]
        and p.branch.state != "CRISP_METAL"
        for p in cluster.pillars.values()
    )
    mb = _p_branch(cluster, "月")
    if not has_root and mb and dm.get_relationship(mb.wuxing, mb.yinyang) not in ["比肩", "劫财", "正印", "偏印"]:
        return 1.0
    return 0.0


# ==========================================
# 宏观张量执行器
# ==========================================

def execute_v118_macro_tensor(cluster_topo: BaziFullCluster) -> dict[str, float]:
    """V118 宏观张量：总质量、相变、调候。"""
    sp = cluster_topo.strength_profile
    climate = cluster_topo.climate
    return {
        "disease_mass": float(sp.disease_mass),
        "is_liquid_state": 1.0 if sp.is_liquid_state else 0.0,
        "has_root": 1.0 if sp.has_root else 0.0,
        "is_climate_override": 1.0 if climate.is_climate_override_active else 0.0,
    }


# ==========================================
# 图鉴专家覆写（Amulet V2.0 第7漏斗）
# ==========================================

def execute_amulet_tujian_expert(c: _Cluster, kernel_elem: str) -> dict:
    expert_vector: dict = {
        "high_entropy_clash_alert": 0.0,
        "toxic_attachment_alert": 0.0,
        "wealth_breaks_resource_alert": 0.0,
        "tujian_tags": [],
    }
    tags = c.get_all_interaction_tags()
    tujian_tags: list[str] = []
    strategy: list[str] = []

    clash_count = sum(1 for tag in tags if "相冲" in tag)
    if clash_count >= 2:
        tujian_tags.append("图鉴_CLASS_高熵冲局系统")
        strategy.append("执行『动中求财』策略。")
        expert_vector["high_entropy_clash_alert"] = 1.0

    if "TAG_日干参与合绊" in tags:
        tujian_tags.append("图鉴_CLASS_身弱强合或贪合忌神")
        expert_vector["toxic_attachment_alert"] = 1.0

    if kernel_elem == "火":
        tujian_tags.append("图鉴_CLASS_财星破印解局")
        expert_vector["wealth_breaks_resource_alert"] = 1.0

    expert_vector["tujian_tags"] = tujian_tags
    return expert_vector


# ==========================================
# 主入口
# ==========================================

def run_unified_engine(cluster_topo: BaziFullCluster) -> BaziFullCluster:
    """
    主推演入口：接收 BaziFullCluster，执行所有探针，
    将 BaziTensionDNA 填充后写回 cluster.tension_dna。
    """
    if not cluster_topo.is_input_valid:
        return cluster_topo

    c = _build_cluster_from_topology(cluster_topo)

    macro = execute_v118_macro_tensor(cluster_topo)

    polarity_const = BAZI_TENSION_POLARITY

    micro: dict[str, float] = {}
    if rule_v101_structural_overload_collapse(c) == 1.0:
        micro["structural_overload"] = float(polarity_const["v101_structural_overload"])
    if rule_v100_high_entropy_thermal_death(c) == 1.0:
        micro["thermal_death"] = float(polarity_const["v100_high_entropy_thermal_death"])
    if rule_v98_holographic_flesh_smash(c) == 1.0:
        micro["flesh_smash"] = float(polarity_const["v98_holographic_flesh_smash"])
    if rule_v99_antimatter_fission(c) == 1.0:
        micro["antimatter_fission"] = float(polarity_const["v99_antimatter_fission"])

    micro["info_capture"] = float(rule_v101_holographic_info_capture(c))
    micro["massive_predation"] = float(rule_v101_massive_solid_predation(c))
    micro["macro_condensate"] = float(rule_v100_macro_condensate(c))
    micro["cross_domain_predation"] = float(rule_v100_cross_domain_predation(c))
    micro["chain_reaction"] = float(rule_v100_chain_reaction_matrix(c))
    micro["base_work_active"] = float(rule_v99_base_work_active(c))
    micro["blackhole_nesting"] = float(rule_v99_blackhole_nesting(c))
    micro["dyson_sphere"] = float(rule_v99_dyson_sphere_topology(c))
    micro["spatial_density"] = float(rule_v98_spatial_density_and_proximity(c))
    micro["dual_protocol"] = float(rule_v98_dual_protocol_orbit(c))
    micro["interference_damping"] = float(rule_v97_interference_damping(c))
    micro["conditional_harm"] = float(rule_v97_conditional_harm_breach(c))
    micro["z_axis_suppression"] = float(rule_v97_z_axis_diode_suppression(c))
    micro["isotopic_strike"] = float(rule_v96_isotopic_absolute_strike(c))
    micro["entangled_convergence"] = float(rule_v96_entangled_convergence(c))
    micro["distance_insulation"] = float(rule_v95_distance_insulation(c))
    micro["high_energy_act"] = float(rule_v95_high_energy_activation(c))
    micro["density_compression"] = float(rule_v94_spatial_density_compression(c))
    micro["transient_entangle"] = float(rule_v93_high_entropy_transient_entanglement(c))
    micro["stable_anchor"] = float(rule_v93_low_entropy_stable_anchor(c))
    micro["topo_reversal_stem"] = float(rule_v92_topological_reversal_stem(c))
    micro["topo_reversal_branch"] = float(rule_v92_topological_reversal_branch(c))
    micro["authority_void"] = float(rule_v91_authority_void_sublimation(c))
    micro["clone_seizure"] = float(rule_v91_clone_resource_seizure(c))
    micro["virtual_calc"] = float(rule_v90_virtual_calculation_void(c))
    micro["orbital_drag"] = float(rule_v84_orbital_drag(c))
    micro["void_arch"] = float(rule_v84_void_singularity_arch(c))
    micro["subatomic_pen"] = float(rule_v83_subatomic_penetration(c))
    micro["quark_confinement"] = float(rule_v83_quark_confinement(c))
    micro["quark_ascension"] = float(rule_v82_quark_ascension(c))
    micro["quantum_tunneling"] = float(rule_v80_quantum_tunneling_ground(c))
    micro["singularity_siphon"] = float(rule_v80_singularity_siphon(c))
    micro["father_evaporation"] = float(rule_v77_father_evaporation(c))
    micro["terminal_void"] = float(rule_v77_terminal_void_decay(c))
    micro["containment_singularity"] = float(rule_v73_containment_singularity(c))
    micro["absolute_weakness"] = float(rule_v13_absolute_weakness(c))

    kernel_elem = cluster_topo.strength_profile.kernel_element
    tujian = execute_amulet_tujian_expert(c, kernel_elem)

    kinship_raw = cluster_topo.interaction_tags
    kinship = BaziKinshipPointers(
        father_chars=[],
        mother_chars=[],
        spouse_descriptors=[],
        is_oppressed=False,
        is_wealth_scattered=False,
        is_resource_blocked=False,
    )

    dna = BaziTensionDNA(
        **macro,
        **{k: v for k, v in micro.items() if isinstance(v, float)},
        high_entropy_clash_alert=float(tujian.get("high_entropy_clash_alert", 0.0)),
        toxic_attachment_alert=float(tujian.get("toxic_attachment_alert", 0.0)),
        wealth_breaks_resource_alert=float(tujian.get("wealth_breaks_resource_alert", 0.0)),
        tujian_tags=tujian.get("tujian_tags", []),
        kinship_pointers=kinship,
    )

    cluster_topo.tension_dna = dna
    return cluster_topo
