# = [端口 E: L1.5 领域推演引擎] =
# 路径: modules/02_bazi/bazi_unified_engine.py
# 系统灵魂插槽：承载全部 if/else 推演逻辑、权重叠加算法与结论汇总
# 禁止包含任何 I/O、网络请求或文件操作

from typing import Dict, List

from expert_rules.bazi_rules import (
    BAZI_TENSION_POLARITY,
    CLASH_PAIRS,
    FULL_COMBOS,
    GENERATE_CYCLE,
    CONTROL_CYCLE,
    HIDDEN_QUARKS,
    MATRIX_L1_CHONG,
    MATRIX_L1_HE,
    PUNISH_PAIRS,
    HARM_PAIRS,
    RESOURCE_CYCLE,
    STEM_COMBOS,
    STEM_CLASHES,
    THERMO_COLD,
    THERMO_WARM,
    TOMB_MAP,
    TUJIAN_EXPERT_RULES,
    V7_CLIMATE_RULES,
    V7_ROOT_QI_MATRIX,
    WX_RESTRICTS,
    YOLO_VETO_RULES,
    BRANCHES,
    STEMS,
)
from core_engine.bazi_math_core import (
    compute_element_mass,
    compute_strength_score,
    get_ten_god,
    get_void_branches,
)
from .bazi_v102_topology import (
    BaziClimateTopology,
    BaziInteractionTopology,
    BaziKinshipTopology,
    BaziNodeTopology,
    BaziPillarTopology,
    BaziStrengthTopology,
    BaziTujianTopology,
    BaziUnifiedTopology,
    BaziVoidTopology,
)

# ── 仓位权重常数（内联，避免循环导入）──────────────────────────
_POSITION_WEIGHTS: Dict[str, float] = {
    "月支": 9.0,
    "日支": 2.0,
    "时干": 2.0,
    "月干": 1.5,
    "时支": 1.5,
    "年干": 1.0,
    "年支": 1.0,
    "日干": 1.0,
}

_POS_TO_PILLAR: Dict[str, tuple] = {
    "年干": ("年", "stem"),
    "年支": ("年", "branch"),
    "月干": ("月", "stem"),
    "月支": ("月", "branch"),
    "日干": ("日", "stem"),
    "日支": ("日", "branch"),
    "时干": ("时", "stem"),
    "时支": ("时", "branch"),
}

ELEMENT_MAP_LOCAL: Dict[str, tuple] = {
    "甲": ("木", "阳"), "乙": ("木", "阴"),
    "寅": ("木", "阳"), "卯": ("木", "阴"),
    "丙": ("火", "阳"), "丁": ("火", "阴"),
    "巳": ("火", "阳"), "午": ("火", "阴"),
    "戊": ("土", "阳"), "己": ("土", "阴"),
    "辰": ("土", "阳"), "戌": ("土", "阳"),
    "丑": ("土", "阴"), "未": ("土", "阴"),
    "庚": ("金", "阳"), "辛": ("金", "阴"),
    "申": ("金", "阳"), "酉": ("金", "阴"),
    "壬": ("水", "阳"), "癸": ("水", "阴"),
    "亥": ("水", "阳"), "子": ("水", "阴"),
}


# ============================================================
# 内部辅助结构（轻量适配，替代原 FakeNode/FakeCluster）
# ============================================================

class _Node:
    __slots__ = ("char", "wuxing", "yinyang", "pos")

    def __init__(self, char: str, wuxing: str, yinyang: str, pos: str):
        self.char = char
        self.wuxing = wuxing
        self.yinyang = yinyang
        self.pos = pos


class _Pillar:
    __slots__ = ("name", "stem", "branch")

    def __init__(self, name: str):
        self.name = name
        self.stem: _Node | None = None
        self.branch: _Node | None = None


class _Cluster:
    """四柱集群内部表示——仅存储，不含推演逻辑"""

    def __init__(self):
        self.pillars: Dict[str, _Pillar] = {
            "年": _Pillar("年"),
            "月": _Pillar("月"),
            "日": _Pillar("日"),
            "时": _Pillar("时"),
        }
        self.day_master: _Node | None = None
        self.all_nodes: List[_Node] = []


# ============================================================
# 八字大一统推演引擎 V10
# ============================================================

class BaziUnifiedEngine:
    """
    L1.5 推演引擎：吞噬 BaziUnifiedTopology，输出完整推演特征向量。
    所有 if/else 判断集中于此，上游 Parser 与下游 Topology 保持纯净。
    """

    # ----------------------------------------------------------
    # 公共入口
    # ----------------------------------------------------------

    def infer(self, topology: BaziUnifiedTopology) -> dict:
        """
        主推演入口。
        接收已填充的拓扑实体，返回大一统特征 DNA 字典。
        """
        if not topology.is_input_valid:
            return {"error": True, "veto_reason": topology.veto_reason}

        cluster = self._build_cluster(topology)
        if cluster.day_master is None:
            return {"error": True, "veto_reason": "日干节点缺失，无法推演"}

        # 宏观张量
        macro = self._run_macro_tensor(topology, cluster)

        # 日主强弱
        strength = self._compute_strength(topology, cluster)
        topology.strength = strength

        # 微观探针向量
        micro = self._run_micro_probes(cluster)

        # 空亡
        void_info = self._compute_void(cluster)
        topology.void_info = void_info

        # 六亲星宫
        kinship = self._locate_kinship(cluster)
        topology.kinship = kinship

        # 图鉴专家
        tujian = self._run_tujian_expert(topology, cluster)
        topology.tujian = tujian

        return {**macro, **micro, **self._serialize_tujian(tujian)}

    # ----------------------------------------------------------
    # 集群构建
    # ----------------------------------------------------------

    def _build_cluster(self, topology: BaziUnifiedTopology) -> _Cluster:
        cluster = _Cluster()
        for node_topo in topology.nodes:
            elem, polar = ELEMENT_MAP_LOCAL.get(node_topo.char, ("", ""))
            node = _Node(node_topo.char, elem or node_topo.elem, polar or node_topo.polar, node_topo.pos)
            pillar_name, attr_name = _POS_TO_PILLAR.get(node_topo.pos, (None, None))
            if pillar_name:
                setattr(cluster.pillars[pillar_name], attr_name, node)
                cluster.all_nodes.append(node)
                if node_topo.pos == "日干":
                    cluster.day_master = node
        return cluster

    # ----------------------------------------------------------
    # V118 宏观张量
    # ----------------------------------------------------------

    def _run_macro_tensor(self, topology: BaziUnifiedTopology, cluster: _Cluster) -> dict:
        nodes_raw = [
            {"char": n.char, "pos": n.pos, "elem": n.wuxing}
            for n in cluster.all_nodes
        ]
        elem_mass = compute_element_mass(nodes_raw, _POSITION_WEIGHTS)
        topology.element_mass_vector = elem_mass

        dm = cluster.day_master
        dm_elem = dm.wuxing if dm else "木"
        month_b = cluster.pillars["月"].branch

        climate_override = ""
        is_frozen = False
        is_scorched = False
        if month_b:
            if month_b.char in V7_CLIMATE_RULES["冻结态"]["months"]:
                climate_override = V7_CLIMATE_RULES["冻结态"]["override_kernel"]
                is_frozen = True
            elif month_b.char in V7_CLIMATE_RULES["焦躁态"]["months"]:
                climate_override = V7_CLIMATE_RULES["焦躁态"]["override_kernel"]
                is_scorched = True

        topology.climate = BaziClimateTopology(
            is_frozen_state=is_frozen,
            is_scorched_state=is_scorched,
            climate_override_elem=climate_override,
            month_branch=month_b.char if month_b else "",
        )

        dm_char = dm.char if dm else "甲"
        branches = [n.char for n in cluster.all_nodes if n.pos.endswith("支")]
        valid_roots = V7_ROOT_QI_MATRIX.get(dm_char, [])
        has_root = any(b in valid_roots for b in branches)

        resource_elem = RESOURCE_CYCLE.get(dm_elem, "")
        output_elem = GENERATE_CYCLE.get(dm_elem, "")
        is_liquid = (
            elem_mass.get(resource_elem, 0.0) < 5.0
            and elem_mass.get(output_elem, 0.0) >= 15.0
        )

        disease_mass = max(elem_mass.values()) if elem_mass else 0.0

        return {
            "disease_mass": float(disease_mass),
            "is_liquid_state": 1.0 if is_liquid else 0.0,
            "has_root": 1.0 if has_root else 0.0,
            "is_climate_override": 1.0 if climate_override else 0.0,
        }

    # ----------------------------------------------------------
    # 日主强弱格局
    # ----------------------------------------------------------

    def _compute_strength(
        self, topology: BaziUnifiedTopology, cluster: _Cluster
    ) -> BaziStrengthTopology:
        dm = cluster.day_master
        if not dm:
            return BaziStrengthTopology(
                day_master_char="",
                day_master_elem="",
                day_master_polar="",
                strength_score=0.0,
                has_root=False,
                is_weak=True,
                is_liquid_state=False,
                kernel_elem="",
                pattern_label="未知",
            )

        nodes_raw = [{"char": n.char, "pos": n.pos, "elem": n.wuxing} for n in cluster.all_nodes]
        elem_mass = compute_element_mass(nodes_raw, _POSITION_WEIGHTS)
        score = compute_strength_score(elem_mass, dm.wuxing)

        branches = [n.char for n in cluster.all_nodes if n.pos.endswith("支")]
        has_root = any(b in V7_ROOT_QI_MATRIX.get(dm.char, []) for b in branches)

        resource_elem = RESOURCE_CYCLE.get(dm.wuxing, "")
        output_elem = GENERATE_CYCLE.get(dm.wuxing, "")
        is_liquid = (
            elem_mass.get(resource_elem, 0.0) < 5.0
            and elem_mass.get(output_elem, 0.0) >= 15.0
        )
        is_weak = score < 0.35

        # 调候核心用神覆盖
        kernel_elem = ""
        if topology.climate.climate_override_elem:
            kernel_elem = topology.climate.climate_override_elem
        elif is_weak:
            kernel_elem = resource_elem or dm.wuxing
        else:
            kernel_elem = CONTROL_CYCLE.get(dm.wuxing, "")

        return BaziStrengthTopology(
            day_master_char=dm.char,
            day_master_elem=dm.wuxing,
            day_master_polar=dm.yinyang,
            strength_score=score,
            has_root=has_root,
            is_weak=is_weak,
            is_liquid_state=is_liquid,
            kernel_elem=kernel_elem,
            pattern_label="普通格",
        )

    # ----------------------------------------------------------
    # 空亡计算
    # ----------------------------------------------------------

    def _compute_void(self, cluster: _Cluster) -> BaziVoidTopology:
        day_p = cluster.pillars.get("日")
        if not day_p or not day_p.stem or not day_p.branch:
            return BaziVoidTopology()

        void_1, void_2 = get_void_branches(day_p.stem.char, day_p.branch.char)
        void_list = [void_1, void_2]

        dm = cluster.day_master
        activated = []
        for p in cluster.pillars.values():
            if not p.branch or p.branch.char not in void_list:
                continue
            if dm:
                ten_god = get_ten_god(dm.wuxing, dm.yinyang, p.branch.wuxing, p.branch.yinyang)
                if "官" in ten_god or "杀" in ten_god:
                    activated.append(p.branch.char)

        return BaziVoidTopology(
            void_branch_1=void_1,
            void_branch_2=void_2,
            void_activated_chars=activated,
        )

    # ----------------------------------------------------------
    # 六亲星宫定位
    # ----------------------------------------------------------

    def _locate_kinship(self, cluster: _Cluster) -> BaziKinshipTopology:
        dm = cluster.day_master
        if not dm:
            return BaziKinshipTopology()

        father_chars: List[str] = []
        mother_chars: List[str] = []
        spouse_chars: List[str] = []

        for pillar_name in ["年", "月"]:
            p = cluster.pillars.get(pillar_name)
            if not p:
                continue
            for node in [p.stem, p.branch]:
                if not node:
                    continue
                rel = get_ten_god(dm.wuxing, dm.yinyang, node.wuxing, node.yinyang)
                if rel in ("正财", "偏财", "正官", "七杀"):
                    father_chars.append(node.char)
                elif rel in ("正印", "偏印", "食神", "伤官", "比肩", "劫财"):
                    mother_chars.append(node.char)

        for p in cluster.pillars.values():
            for node in [p.stem, p.branch]:
                if not node or node is dm:
                    continue
                rel = get_ten_god(dm.wuxing, dm.yinyang, node.wuxing, node.yinyang)
                if rel in ("正财", "偏财", "正官", "七杀"):
                    spouse_chars.append(f"{node.char}({rel})")

        return BaziKinshipTopology(
            father_chars=father_chars,
            mother_chars=mother_chars,
            spouse_chars=spouse_chars,
        )

    # ----------------------------------------------------------
    # 图鉴专家 (Amulet V2.0)
    # ----------------------------------------------------------

    def _run_tujian_expert(
        self, topology: BaziUnifiedTopology, cluster: _Cluster
    ) -> BaziTujianTopology:
        tujian_tags: List[str] = []
        tujian_strategies: List[str] = []
        high_entropy_clash = False
        toxic_attachment = False
        wealth_breaks_resource = False

        branch_list = [p.branch.char for p in cluster.pillars.values() if p.branch]
        clash_count = sum(
            1
            for i in range(len(branch_list))
            for j in range(i + 1, len(branch_list))
            if {branch_list[i], branch_list[j]} in CLASH_PAIRS
        )
        if clash_count >= 2:
            tujian_tags.append("图鉴_CLASS_高熵冲突系统")
            tujian_strategies.append(TUJIAN_EXPERT_RULES["GATE_HIGH_ENTROPY_CLASH"]["judgment"])
            high_entropy_clash = True

        dm = cluster.day_master
        if dm:
            for p in cluster.pillars.values():
                if not p.stem or p.stem is dm:
                    continue
                if {dm.char, p.stem.char} in STEM_COMBOS:
                    rel = get_ten_god(dm.wuxing, dm.yinyang, p.stem.wuxing, p.stem.yinyang)
                    if rel in ("七杀", "偏印", "劫财", "伤官"):
                        tujian_tags.append("图鉴_CLASS_日干参与贪合忌神")
                        tujian_strategies.append(
                            TUJIAN_EXPERT_RULES["GATE_TOXIC_ATTACHMENT"]["judgment"]
                        )
                        toxic_attachment = True
                        break

        kernel_wx = ""
        if topology.strength:
            kernel_wx = topology.strength.kernel_elem
        if kernel_wx == "火":
            tujian_tags.append("图鉴_CLASS_财星破印解局")
            tujian_strategies.append(
                TUJIAN_EXPERT_RULES["GATE_WEALTH_BREAKS_RESOURCE"]["judgment"]
            )
            wealth_breaks_resource = True

        return BaziTujianTopology(
            tujian_tags=tujian_tags,
            tujian_strategies=tujian_strategies,
            high_entropy_clash_alert=high_entropy_clash,
            toxic_attachment_alert=toxic_attachment,
            wealth_breaks_resource_alert=wealth_breaks_resource,
        )

    @staticmethod
    def _serialize_tujian(tujian: BaziTujianTopology) -> dict:
        return {
            "tujian_tags": tujian.tujian_tags,
            "tujian_strategies": tujian.tujian_strategies,
            "high_entropy_clash_alert": 1.0 if tujian.high_entropy_clash_alert else 0.0,
            "toxic_attachment_alert": 1.0 if tujian.toxic_attachment_alert else 0.0,
            "wealth_breaks_resource_alert": 1.0 if tujian.wealth_breaks_resource_alert else 0.0,
        }

    # ----------------------------------------------------------
    # V101–V13 微观探针全量展开（全部判断集中于此）
    # ----------------------------------------------------------

    def _run_micro_probes(self, cluster: _Cluster) -> dict:
        """
        执行全部微观探针，返回 float 化特征字典。
        所有规则逻辑仅在此处出现，不泄漏至 L1 层。
        """
        mv: Dict[str, float] = {}

        dm = cluster.day_master

        # [v101] structural overload collapse
        mv["structural_overload"] = 0.0
        if dm:
            support_count = sum(
                1
                for p in cluster.pillars.values()
                if p.branch
                and get_ten_god(dm.wuxing, dm.yinyang, p.branch.wuxing, p.branch.yinyang)
                in ("比肩", "劫财", "正印", "偏印")
            )
            if support_count == 0:
                day_b = cluster.pillars["日"].branch
                day_b_char = day_b.char if day_b else ""
                for p in cluster.pillars.values():
                    if not p.branch:
                        continue
                    rel = get_ten_god(dm.wuxing, dm.yinyang, p.branch.wuxing, p.branch.yinyang)
                    if "财" in rel or "杀" in rel:
                        ob = p.branch.char
                        if (
                            {day_b_char, ob} in FULL_COMBOS
                            or {day_b_char, ob} in CLASH_PAIRS
                            or (day_b_char in TOMB_MAP and ob in TOMB_MAP.get(day_b_char, []))
                        ):
                            mv["structural_overload"] = float(
                                BAZI_TENSION_POLARITY["v101_structural_overload"]
                            )
                            break

        # [v100] high entropy thermal death
        all_chars = [n.char for n in cluster.all_nodes]
        total = len(all_chars)
        warm_c = sum(1 for c in all_chars if c in THERMO_WARM)
        cold_c = sum(1 for c in all_chars if c in THERMO_COLD)
        macro_condensate = total > 0 and (warm_c / total > 0.75 or cold_c / total > 0.75)

        inner = [cluster.pillars["日"].branch, cluster.pillars["时"].branch]
        outer = [cluster.pillars["年"].branch, cluster.pillars["月"].branch]
        inner_chars = [b.char for b in inner if b]
        outer_chars = [b.char for b in outer if b]
        cross_predation = any(
            {ib, ob} in FULL_COMBOS
            or {ib, ob} in CLASH_PAIRS
            or (ib in TOMB_MAP and ob in TOMB_MAP.get(ib, []))
            or (ob in TOMB_MAP and ib in TOMB_MAP.get(ob, []))
            for ib in inner_chars
            for ob in outer_chars
        )
        mv["thermal_death"] = (
            float(BAZI_TENSION_POLARITY["v100_high_entropy_thermal_death"])
            if (not macro_condensate and not cross_predation)
            else 0.0
        )
        mv["macro_condensate"] = 1.0 if macro_condensate else 0.0
        mv["cross_domain_predation"] = 1.0 if cross_predation else 0.0

        # [v99] antimatter fission
        mv["antimatter_fission"] = 0.0
        if dm:
            day_b = cluster.pillars["日"].branch
            day_b_char = day_b.char if day_b else ""
            for name, p in cluster.pillars.items():
                if name == "日" or not p.branch:
                    continue
                if get_ten_god(dm.wuxing, dm.yinyang, p.branch.wuxing, p.branch.yinyang) == "七杀":
                    ob = p.branch.char
                    if (
                        {day_b_char, ob} in FULL_COMBOS
                        or {day_b_char, ob} in CLASH_PAIRS
                        or (day_b_char in TOMB_MAP and ob in TOMB_MAP.get(day_b_char, []))
                    ):
                        mv["antimatter_fission"] = float(
                            BAZI_TENSION_POLARITY["v99_antimatter_fission"]
                        )
                        break

        # [v98] holographic flesh smash
        holo_map = {
            "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午",
            "戊": "巳", "己": "午", "庚": "申", "辛": "酉",
            "壬": "亥", "癸": "子",
        }
        mv["flesh_smash"] = 0.0
        if dm:
            body_char = holo_map.get(dm.char, "")
            branches_objs = [p.branch for p in cluster.pillars.values() if p.branch]
            if body_char and any(b.char == body_char for b in branches_objs):
                body_wx = next((b.wuxing for b in branches_objs if b.char == body_char), None)
                if any(
                    b.char in ("丑", "辰", "未", "戌")
                    and GENERATE_CYCLE.get(b.wuxing) == body_wx
                    for b in branches_objs
                ):
                    mv["flesh_smash"] = float(BAZI_TENSION_POLARITY["v98_holographic_flesh_smash"])

        # [v101] holographic info capture
        mv["info_capture"] = 0.0
        if dm:
            for p in cluster.pillars.values():
                if not p.stem or p.stem is dm:
                    continue
                rel = get_ten_god(dm.wuxing, dm.yinyang, p.stem.wuxing, p.stem.yinyang)
                if "财" in rel or "官" in rel or "杀" in rel:
                    branch_of_stem_char = p.branch.char if p.branch else ""
                    is_rooted = p.stem.char in HIDDEN_QUARKS.get(branch_of_stem_char, [])
                    if not is_rooted and {dm.char, p.stem.char} in STEM_COMBOS:
                        mv["info_capture"] = 1.0
                        break

        # [v101] massive solid predation
        mv["massive_predation"] = 0.0
        if dm:
            support_count = sum(
                1
                for p in cluster.pillars.values()
                if p.branch
                and get_ten_god(dm.wuxing, dm.yinyang, p.branch.wuxing, p.branch.yinyang)
                in ("比肩", "劫财", "正印", "偏印")
            )
            if support_count >= 2:
                day_b = cluster.pillars["日"].branch
                day_b_char = day_b.char if day_b else ""
                for p in cluster.pillars.values():
                    if not p.branch:
                        continue
                    rel = get_ten_god(dm.wuxing, dm.yinyang, p.branch.wuxing, p.branch.yinyang)
                    if "财" in rel or "杀" in rel:
                        ob = p.branch.char
                        if (
                            {day_b_char, ob} in FULL_COMBOS
                            or {day_b_char, ob} in CLASH_PAIRS
                            or (day_b_char in TOMB_MAP and ob in TOMB_MAP.get(day_b_char, []))
                        ):
                            mv["massive_predation"] = 1.0
                            break

        # [v100] chain reaction matrix
        hb = cluster.pillars["时"].branch
        db = cluster.pillars["日"].branch
        mb = cluster.pillars["月"].branch
        yb = cluster.pillars["年"].branch

        def _acts(b1, b2) -> bool:
            if not b1 or not b2:
                return False
            c1, c2 = b1.char, b2.char
            return (
                {c1, c2} in FULL_COMBOS
                or {c1, c2} in CLASH_PAIRS
                or (c1 in TOMB_MAP and c2 in TOMB_MAP.get(c1, []))
            )

        mv["chain_reaction"] = 1.0 if (
            _acts(hb, db) and _acts(db, mb) and _acts(mb, yb)
        ) else 0.0

        # [v99] base work active
        mv["base_work_active"] = 0.0
        if db:
            for name, p in cluster.pillars.items():
                if name != "日" and p.branch:
                    ob = p.branch.char
                    dc = db.char
                    if (
                        {dc, ob} in FULL_COMBOS
                        or {dc, ob} in CLASH_PAIRS
                        or (dc in TOMB_MAP and ob in TOMB_MAP.get(dc, []))
                        or (ob in TOMB_MAP and dc in TOMB_MAP.get(ob, []))
                    ):
                        mv["base_work_active"] = 1.0
                        break

        # [v99] blackhole nesting
        branch_set = {p.branch.char for p in cluster.pillars.values() if p.branch}
        mv["blackhole_nesting"] = 1.0 if (
            ("辰" in branch_set and "未" in branch_set)
            or ("戌" in branch_set and "丑" in branch_set)
        ) else 0.0

        # [v99] dyson sphere topology
        yb_obj = cluster.pillars["年"].branch
        hb_obj = cluster.pillars["时"].branch
        db_obj = cluster.pillars["日"].branch
        mv["dyson_sphere"] = 0.0
        if yb_obj and hb_obj and db_obj:
            if (
                yb_obj.wuxing == hb_obj.wuxing == db_obj.wuxing
                and db_obj.char != yb_obj.char
            ):
                mv["dyson_sphere"] = 1.0

        # [v98] spatial density and proximity
        mv["spatial_density"] = 0.0
        if dm:
            output_wx = GENERATE_CYCLE.get(dm.wuxing, "")
            has_output = any(
                getattr(p.stem, "wuxing", None) == output_wx
                or getattr(p.branch, "wuxing", None) == output_wx
                for p in cluster.pillars.values()
            )
            has_gen_output = any(
                GENERATE_CYCLE.get(getattr(p.stem, "wuxing", None)) == output_wx
                for p in cluster.pillars.values()
            )
            has_ctrl_output = any(
                WX_RESTRICTS.get(getattr(p.branch, "wuxing", None)) == output_wx
                for p in cluster.pillars.values()
            )
            if has_output and has_gen_output and has_ctrl_output:
                mv["spatial_density"] = 1.0

        # [v98] dual protocol orbit
        mv["dual_protocol"] = 0.0
        wx_polar_map: Dict[str, set] = {}
        for p in cluster.pillars.values():
            s = p.stem
            if not s or s is dm:
                continue
            if s.wuxing not in wx_polar_map:
                wx_polar_map[s.wuxing] = set()
            wx_polar_map[s.wuxing].add(s.yinyang)
        if any(len(polars) >= 2 for polars in wx_polar_map.values()):
            mv["dual_protocol"] = 1.0

        # [v97] interference damping
        branch_chars = [p.branch.char for p in cluster.pillars.values() if p.branch]
        mv["interference_damping"] = 0.0
        for b1 in branch_chars:
            for b2 in branch_chars:
                if b1 == b2:
                    continue
                if {b1, b2} in CLASH_PAIRS:
                    if any({b1, ob} in FULL_COMBOS for ob in branch_chars if ob != b1) or \
                       any({b2, ob} in FULL_COMBOS for ob in branch_chars if ob != b2):
                        mv["interference_damping"] = 1.0

        # [v97] conditional harm breach
        mv["conditional_harm"] = 0.0
        pillar_list = list(cluster.pillars.values())
        for i in range(len(pillar_list)):
            for j in range(i + 1, len(pillar_list)):
                p1, p2 = pillar_list[i], pillar_list[j]
                if not p1.branch or not p2.branch or not p1.stem or not p2.stem:
                    continue
                if (
                    {p1.branch.char, p2.branch.char} in HARM_PAIRS
                    and {p1.stem.char, p2.stem.char} in STEM_COMBOS
                ):
                    mv["conditional_harm"] = 1.0

        # [v97] z-axis diode suppression
        mv["z_axis_suppression"] = 0.0
        for p in cluster.pillars.values():
            if p.stem and p.branch:
                if WX_RESTRICTS.get(p.stem.wuxing) == p.branch.wuxing:
                    mv["z_axis_suppression"] = 1.0
                    break

        # [v96] isotopic absolute strike
        mv["isotopic_strike"] = 0.0
        for p1 in cluster.pillars.values():
            for p2 in cluster.pillars.values():
                if p1 is p2:
                    continue
                s1, s2 = p1.stem, p2.stem
                if s1 and s2:
                    if (
                        WX_RESTRICTS.get(s1.wuxing) == s2.wuxing
                        and s1.yinyang == s2.yinyang
                        and {s1.char, s2.char} not in STEM_COMBOS
                    ):
                        mv["isotopic_strike"] = 1.0
                b1, b2 = p1.branch, p2.branch
                if b1 and b2:
                    if (
                        WX_RESTRICTS.get(b1.wuxing) == b2.wuxing
                        and b1.yinyang == b2.yinyang
                        and {b1.char, b2.char} not in FULL_COMBOS
                    ):
                        mv["isotopic_strike"] = 1.0

        # [v96] entangled convergence
        mv["entangled_convergence"] = 0.0
        for p1 in cluster.pillars.values():
            for p2 in cluster.pillars.values():
                if p1 is p2:
                    continue
                s1, s2 = p1.stem, p2.stem
                if s1 and s2:
                    if (
                        WX_RESTRICTS.get(s1.wuxing) == s2.wuxing
                        or WX_RESTRICTS.get(s2.wuxing) == s1.wuxing
                    ) and {s1.char, s2.char} in STEM_COMBOS:
                        mv["entangled_convergence"] = 1.0
                b1, b2 = p1.branch, p2.branch
                if b1 and b2:
                    if (
                        WX_RESTRICTS.get(b1.wuxing) == b2.wuxing
                        or WX_RESTRICTS.get(b2.wuxing) == b1.wuxing
                    ) and {b1.char, b2.char} in FULL_COMBOS:
                        mv["entangled_convergence"] = 1.0

        # [v95] distance insulation
        idx_map = {"年": 0, "月": 1, "日": 2, "时": 3}
        mv["distance_insulation"] = 0.0
        for p1_name, p1 in cluster.pillars.items():
            for p2_name, p2 in cluster.pillars.items():
                if p1_name == p2_name or not p1.branch or not p2.branch:
                    continue
                if abs(idx_map[p1_name] - idx_map[p2_name]) > 1:
                    if (
                        GENERATE_CYCLE.get(p1.branch.wuxing) == p2.branch.wuxing
                        or WX_RESTRICTS.get(p1.branch.wuxing) == p2.branch.wuxing
                    ):
                        mv["distance_insulation"] = 1.0

        # [v95] high energy activation
        mv["high_energy_act"] = 0.0
        if db:
            dc = db.char
            if (
                any({dc, ob} in FULL_COMBOS for ob in branch_chars if ob != dc)
                or any({dc, ob} in CLASH_PAIRS for ob in branch_chars if ob != dc)
                or any({dc, ob} in PUNISH_PAIRS for ob in branch_chars if ob != dc)
            ):
                mv["high_energy_act"] = 1.0

        # [v94] spatial density compression
        mv["density_compression"] = 0.0
        has_tu = any(n.wuxing == "土" for n in cluster.all_nodes)
        has_crashed_shui = any(
            n.wuxing == "水" and getattr(n, "state", "") == "CRASHED"
            for n in cluster.all_nodes
        )
        if has_tu and has_crashed_shui:
            mv["density_compression"] = 1.0

        # [v93] transient entanglement (high entropy)
        mv["transient_entangle"] = 0.0
        if dm:
            for p in cluster.pillars.values():
                if not p.stem or not p.branch:
                    continue
                rel_s = get_ten_god(dm.wuxing, dm.yinyang, p.stem.wuxing, p.stem.yinyang)
                if rel_s in ("偏财", "七杀"):
                    other_stems = [
                        op.stem.char for op in cluster.pillars.values()
                        if op.stem and op is not p
                    ]
                    if any({p.stem.char, os} in STEM_COMBOS for os in other_stems):
                        mv["transient_entangle"] = 1.0
                        break
                rel_b = get_ten_god(dm.wuxing, dm.yinyang, p.branch.wuxing, p.branch.yinyang)
                if rel_b in ("偏财", "七杀"):
                    other_branches = [
                        op.branch.char for op in cluster.pillars.values()
                        if op.branch and op is not p
                    ]
                    if any({p.branch.char, ob} in FULL_COMBOS for ob in other_branches):
                        mv["transient_entangle"] = 1.0
                        break

        # [v93] stable anchor (low entropy)
        mv["stable_anchor"] = 0.0
        if dm:
            for p in cluster.pillars.values():
                if not p.stem or not p.branch:
                    continue
                rel_s = get_ten_god(dm.wuxing, dm.yinyang, p.stem.wuxing, p.stem.yinyang)
                if rel_s in ("正财", "正官"):
                    other_stems = [
                        op.stem.char for op in cluster.pillars.values()
                        if op.stem and op is not p
                    ]
                    if any({p.stem.char, os} in STEM_COMBOS for os in other_stems):
                        mv["stable_anchor"] = 1.0
                        break

        # [v92] topological reversal (stem)
        mv["topo_reversal_stem"] = 0.0
        stems_chars = [p.stem.char for p in cluster.pillars.values() if p.stem]
        for s in stems_chars:
            if (
                any({s, os} in STEM_COMBOS for os in stems_chars if os != s)
                and any({s, os} in STEM_CLASHES for os in stems_chars if os != s)
            ):
                mv["topo_reversal_stem"] = 1.0
                break

        # [v92] topological reversal (branch)
        mv["topo_reversal_branch"] = 0.0
        for b in branch_chars:
            if (
                any({b, ob} in FULL_COMBOS for ob in branch_chars if ob != b)
                and any({b, ob} in CLASH_PAIRS for ob in branch_chars if ob != b)
            ):
                mv["topo_reversal_branch"] = 1.0
                break

        # [v91] authority void sublimation
        mv["authority_void"] = 0.0
        void_info = self._compute_void(cluster)
        void_list = [void_info.void_branch_1, void_info.void_branch_2]
        if dm and void_list[0]:
            for p in cluster.pillars.values():
                if not p.branch or p.branch.char not in void_list:
                    continue
                ten_god = get_ten_god(dm.wuxing, dm.yinyang, p.branch.wuxing, p.branch.yinyang)
                if "官" in ten_god or "杀" in ten_god:
                    mv["authority_void"] = 1.0
                    break

        # [v91] clone resource seizure
        mv["clone_seizure"] = 0.0
        if dm:
            clones = sum(
                1
                for n in cluster.all_nodes
                if n is not dm
                and get_ten_god(dm.wuxing, dm.yinyang, n.wuxing, n.yinyang) in ("比肩", "劫财")
            )
            resources = sum(
                1
                for n in cluster.all_nodes
                if n is not dm
                and "财" in get_ten_god(dm.wuxing, dm.yinyang, n.wuxing, n.yinyang)
            )
            if clones >= 2 and resources >= 1:
                mv["clone_seizure"] = 1.0

        # [v90] virtual calculation void
        mv["virtual_calc"] = 0.0
        if void_list[0]:
            for p in cluster.pillars.values():
                if p.branch and p.branch.char in void_list and p.branch.wuxing == "水":
                    mv["virtual_calc"] = 1.0
                    break

        # [v84] orbital drag
        mv["orbital_drag"] = 0.0
        if db:
            for name, p in cluster.pillars.items():
                if name != "日" and p.branch and {db.char, p.branch.char} in FULL_COMBOS:
                    mv["orbital_drag"] = 1.0
                    break

        # [v84] void singularity arch
        mv["void_arch"] = 0.0
        for pair in [{"亥", "未"}, {"寅", "戌"}, {"巳", "丑"}, {"申", "辰"}]:
            if pair.issubset(branch_set):
                mv["void_arch"] = 1.0
                break

        # [v83] subatomic penetration
        mv["subatomic_pen"] = 1.0 if (
            {"寅", "亥"}.issubset(branch_set) or {"辰", "酉"}.issubset(branch_set)
        ) else 0.0

        # [v83] quark confinement
        mv["quark_confinement"] = 0.0
        for pair in [{"子", "丑"}, {"辰", "酉"}, {"午", "未"}, {"卯", "戌"}]:
            if pair.issubset(branch_set):
                mv["quark_confinement"] = 1.0
                break

        # [v82] quark ascension
        mv["quark_ascension"] = 0.0
        for p in cluster.pillars.values():
            if not p.stem:
                continue
            stem_wx = p.stem.wuxing
            branch_wuxings = {
                bp.branch.wuxing for bp in cluster.pillars.values() if bp.branch
            }
            if stem_wx not in branch_wuxings:
                if any(
                    p.stem.char in HIDDEN_QUARKS.get(bp.branch.char, [])
                    for bp in cluster.pillars.values()
                    if bp.branch
                ):
                    mv["quark_ascension"] = 1.0
                    break

        # [v80] quantum tunneling ground
        mv["quantum_tunneling"] = 0.0
        branch_wx_set = {
            p.branch.wuxing for p in cluster.pillars.values() if p.branch
        }
        for p in cluster.pillars.values():
            if p.stem and p.stem.wuxing not in branch_wx_set:
                mv["quantum_tunneling"] = 1.0
                break

        # [v80] singularity siphon (三合局)
        mv["singularity_siphon"] = 0.0
        for trinity in [{"申", "子", "辰"}, {"亥", "卯", "未"}, {"寅", "午", "戌"}, {"巳", "酉", "丑"}]:
            if trinity.issubset(branch_set):
                mv["singularity_siphon"] = 1.0
                break

        # [v77] father evaporation
        mv["father_evaporation"] = 0.0
        if dm:
            father_wx = WX_RESTRICTS.get(dm.wuxing, "")
            if father_wx:
                stem_wx_set = {p.stem.wuxing for p in cluster.pillars.values() if p.stem}
                if father_wx not in stem_wx_set:
                    mv["father_evaporation"] = 1.0

        # [v77] terminal void decay
        mv["terminal_void"] = 0.0
        if void_list[0] and dm:
            time_b = cluster.pillars["时"].branch
            if time_b and time_b.char in void_list:
                if time_b.wuxing == GENERATE_CYCLE.get(dm.wuxing, ""):
                    mv["terminal_void"] = 1.0

        # [v73] containment singularity
        mv["containment_singularity"] = 0.0
        stored_map = {"辰": "水", "戌": "火", "丑": "金", "未": "木"}
        if dm:
            for p in cluster.pillars.values():
                if not p.branch:
                    continue
                stored = stored_map.get(p.branch.char, "")
                if stored:
                    if (
                        WX_RESTRICTS.get(stored) == dm.wuxing
                        or GENERATE_CYCLE.get(dm.wuxing) == stored
                    ):
                        mv["containment_singularity"] = 1.0
                        break

        # [v13] absolute weakness
        mv["absolute_weakness"] = 0.0
        if dm:
            has_root_any = any(
                get_ten_god(dm.wuxing, dm.yinyang, p.branch.wuxing, p.branch.yinyang)
                in ("比肩", "劫财", "正印", "偏印")
                for p in cluster.pillars.values()
                if p.branch
            )
            month_b = cluster.pillars["月"].branch
            if not has_root_any and month_b:
                month_rel = get_ten_god(dm.wuxing, dm.yinyang, month_b.wuxing, month_b.yinyang)
                if month_rel not in ("比肩", "劫财", "正印", "偏印"):
                    mv["absolute_weakness"] = 1.0

        return mv
