# = [端口 P: L1 降维 Parser] =
# 路径: modules/02_bazi/bazi_ephemeris_parser.py
# 纯净解析工具：将外部原始请求降维为 BaziUnifiedTopology
# 绝对禁止包含推演断语 / if/else 业务判断 / LLM 调用

from typing import List

from expert_rules.bazi_rules import (
    ELEMENT_MAP,
    POS_MAP,
    YOLO_VETO_RULES,
    MATRIX_L1_CHONG,
    MATRIX_L1_HE,
    FULL_COMBOS,
    CLASH_PAIRS,
    PUNISH_PAIRS,
    HARM_PAIRS,
    STEM_COMBOS,
    STEM_CLASHES,
    TOMB_MAP,
    BRANCHES,
    STEMS,
)
from .bazi_v102_topology import (
    BaziInteractionTopology,
    BaziNodeTopology,
    BaziPillarTopology,
    BaziUnifiedTopology,
)


_POS_TO_PILLAR = {
    "年干": ("年", "stem"),
    "年支": ("年", "branch"),
    "月干": ("月", "stem"),
    "月支": ("月", "branch"),
    "日干": ("日", "stem"),
    "日支": ("日", "branch"),
    "时干": ("时", "stem"),
    "时支": ("时", "branch"),
}

_POSITION_WEIGHTS = {
    "月支": 9.0,
    "日支": 2.0,
    "时干": 2.0,
    "月干": 1.5,
    "时支": 1.5,
    "年干": 1.0,
    "年支": 1.0,
    "日干": 1.0,
}

_PILLAR_ORDER = ["年", "月", "日", "时"]


class BaziEphemerisParser:
    """
    L1 降维 Parser（无推演逻辑）.

    职责:
    1. YOLO 拦截：关键词黑名单 + 结构完整性校验
    2. 标签解析：'位置_字符' -> BaziNodeTopology
    3. 四柱组装：-> BaziPillarTopology 列表
    4. 互动枚举：六合/相冲/刑/害/天干合冲 -> BaziInteractionTopology 列表
    5. 打包输出：-> BaziUnifiedTopology（交付 Engine 推演）
    """

    def parse(self, raw_input: str) -> BaziUnifiedTopology:
        """
        主入口.
        raw_input 格式: 以空格或逗号分隔的 '位置_字符' 标签串.
        示例: "年干_甲 年支_子 月干_丙 月支_寅 日干_戊 日支_辰 时干_庚 时支_申"
        """
        tags = self._tokenize(raw_input)

        veto_result = self._run_yolo_check(raw_input, tags)
        if veto_result:
            return BaziUnifiedTopology(
                raw_input_tags=tags,
                is_input_valid=False,
                veto_reason=veto_result,
            )

        nodes = self._parse_nodes(tags)
        pillars = self._build_pillars(nodes)
        interactions = self._enumerate_interactions(nodes)

        return BaziUnifiedTopology(
            raw_input_tags=tags,
            nodes=nodes,
            pillars=pillars,
            interactions=interactions,
            is_input_valid=True,
        )

    # ----------------------------------------------------------
    # 1. 标记化
    # ----------------------------------------------------------

    @staticmethod
    def _tokenize(raw_input: str) -> List[str]:
        import re
        return [t.strip() for t in re.split(r"[,，\s]+", raw_input) if t.strip()]

    # ----------------------------------------------------------
    # 2. YOLO 拦截（纯字符串匹配，无推演）
    # ----------------------------------------------------------

    @staticmethod
    def _run_yolo_check(raw_input: str, tags: List[str]) -> str:
        for rule_id, rule in YOLO_VETO_RULES.items():
            for kw in rule.get("trigger_keywords", []):
                if kw in raw_input:
                    return rule["reason"]
            if rule.get("structural_check") == "node_count < 8":
                valid_tag_count = sum(
                    1 for t in tags
                    if "_" in t
                    and t.split("_")[0] in _POS_TO_PILLAR
                    and t.split("_")[1] in ELEMENT_MAP
                )
                if valid_tag_count < 8:
                    return rule["reason"]
        return ""

    # ----------------------------------------------------------
    # 3. 节点解析
    # ----------------------------------------------------------

    @staticmethod
    def _parse_nodes(tags: List[str]) -> List[BaziNodeTopology]:
        nodes: List[BaziNodeTopology] = []
        for tag in tags:
            if "_" not in tag:
                continue
            pos, char = tag.split("_", 1)
            if pos not in _POS_TO_PILLAR or char not in ELEMENT_MAP:
                continue
            elem, polar = ELEMENT_MAP[char]
            is_stem = (pos.endswith("干"))
            is_month_branch = (pos == "月支")
            base_mass = _POSITION_WEIGHTS.get(pos, 1.0)
            nodes.append(BaziNodeTopology(
                char=char,
                pos=pos,
                elem=elem,
                polar=polar,
                is_stem=is_stem,
                is_month_branch=is_month_branch,
                mass=float(base_mass),
            ))
        return nodes

    # ----------------------------------------------------------
    # 4. 四柱组装
    # ----------------------------------------------------------

    @staticmethod
    def _build_pillars(nodes: List[BaziNodeTopology]) -> List[BaziPillarTopology]:
        pillar_dict: dict = {name: {"stem": None, "branch": None} for name in _PILLAR_ORDER}
        for node in nodes:
            pillar_name, attr_name = _POS_TO_PILLAR.get(node.pos, (None, None))
            if pillar_name:
                pillar_dict[pillar_name][attr_name] = node

        pillars: List[BaziPillarTopology] = []
        for name in _PILLAR_ORDER:
            s = pillar_dict[name]["stem"]
            b = pillar_dict[name]["branch"]
            pillars.append(BaziPillarTopology(
                name=name,
                stem_char=s.char if s else "",
                branch_char=b.char if b else "",
                stem_elem=s.elem if s else "",
                branch_elem=b.elem if b else "",
                stem_ten_god="",
                branch_ten_god="",
            ))
        return pillars

    # ----------------------------------------------------------
    # 5. 互动枚举（O(n²) 穷举，无推演）
    # ----------------------------------------------------------

    @staticmethod
    def _enumerate_interactions(nodes: List[BaziNodeTopology]) -> List[BaziInteractionTopology]:
        interactions: List[BaziInteractionTopology] = []

        stems = [(n.char, n.pos) for n in nodes if n.is_stem]
        branches = [(n.char, n.pos) for n in nodes if not n.is_stem]

        # 天干合/冲
        for i in range(len(stems)):
            for j in range(i + 1, len(stems)):
                s1_char, s1_pos = stems[i]
                s2_char, s2_pos = stems[j]
                pair = {s1_char, s2_char}
                if pair in STEM_COMBOS:
                    interactions.append(BaziInteractionTopology(
                        interaction_type="天干相合",
                        char_a=s1_char, char_b=s2_char,
                        pos_a=s1_pos, pos_b=s2_pos,
                    ))
                if pair in STEM_CLASHES:
                    interactions.append(BaziInteractionTopology(
                        interaction_type="天干相冲",
                        char_a=s1_char, char_b=s2_char,
                        pos_a=s1_pos, pos_b=s2_pos,
                    ))

        # 地支六合/三合半合/相冲/刑/害/入墓
        branch_set = {c for c, _ in branches}
        for i in range(len(branches)):
            for j in range(i + 1, len(branches)):
                b1_char, b1_pos = branches[i]
                b2_char, b2_pos = branches[j]
                pair = {b1_char, b2_char}

                if pair in MATRIX_L1_HE:
                    interactions.append(BaziInteractionTopology(
                        interaction_type="地支六合",
                        char_a=b1_char, char_b=b2_char,
                        pos_a=b1_pos, pos_b=b2_pos,
                    ))
                if pair in MATRIX_L1_CHONG:
                    interactions.append(BaziInteractionTopology(
                        interaction_type="地支相冲",
                        char_a=b1_char, char_b=b2_char,
                        pos_a=b1_pos, pos_b=b2_pos,
                    ))
                if pair in FULL_COMBOS:
                    interactions.append(BaziInteractionTopology(
                        interaction_type="地支三合/六合",
                        char_a=b1_char, char_b=b2_char,
                        pos_a=b1_pos, pos_b=b2_pos,
                    ))
                if pair in PUNISH_PAIRS:
                    interactions.append(BaziInteractionTopology(
                        interaction_type="地支刑",
                        char_a=b1_char, char_b=b2_char,
                        pos_a=b1_pos, pos_b=b2_pos,
                    ))
                if pair in HARM_PAIRS:
                    interactions.append(BaziInteractionTopology(
                        interaction_type="地支害",
                        char_a=b1_char, char_b=b2_char,
                        pos_a=b1_pos, pos_b=b2_pos,
                    ))

                # 入墓
                if b2_char in TOMB_MAP and b1_char in TOMB_MAP.get(b2_char, []):
                    interactions.append(BaziInteractionTopology(
                        interaction_type="入墓",
                        char_a=b1_char, char_b=b2_char,
                        pos_a=b1_pos, pos_b=b2_pos,
                    ))
                if b1_char in TOMB_MAP and b2_char in TOMB_MAP.get(b1_char, []):
                    interactions.append(BaziInteractionTopology(
                        interaction_type="入墓",
                        char_a=b2_char, char_b=b1_char,
                        pos_a=b2_pos, pos_b=b1_pos,
                    ))

        return interactions
