# === [L1 降维 Parser] ===
# 路径: modules/02_bazi/bazi_ephemeris_parser.py
# 纯净工具层 — 解析外部请求，无 LLM 调用，无复杂 if/else 断语
# 唯一职责：将原始输入映射为 BaziFullCluster 拓扑实体

from __future__ import annotations

from expert_rules.bazi_rules import (
    STEMS, BRANCHES, ELEMENT_MAP, POS_MAP, POSITION_WEIGHTS,
    GENERATE_CYCLE, CONTROL_CYCLE, RESOURCE_CYCLE,
    FULL_COMBOS, HALF_COMBOS, CLASH_PAIRS, PUNISH_PAIRS,
    HARM_PAIRS, STEM_COMBOS, STEM_CLASHES,
    MATRIX_L1_CHONG, MATRIX_L1_HE,
    V7_CLIMATE_RULES, YOLO_VETO_RULES,
    V7_ROOT_QI_MATRIX,
)
from core_engine.bazi_math_core import (
    compute_kongwang,
    compute_ten_gods,
    compute_root_strength,
    compute_element_mass_vector,
    compute_thermo_ratio,
    find_dominant_element,
)
from .bazi_v102_topology import (
    BaziInputRequest,
    BaziCharNode,
    BaziPillar,
    BaziClimate,
    BaziStrengthProfile,
    BaziInteractionTags,
    BaziKinshipPointers,
    BaziFullCluster,
)

# ==========================================
# 干支排盘静态查表 (O(1))
# ==========================================

_STEM_10_TABLE: dict[int, str] = {i: s for i, s in enumerate(STEMS)}
_BRANCH_12_TABLE: dict[int, str] = {i: b for i, b in enumerate(BRANCHES)}

_YEAR_OFFSET = 4

_PILLAR_NAMES = ["年", "月", "日", "时"]
_PILLAR_INDICES = {"年": 0, "月": 1, "日": 2, "时": 3}

# 月支固定查表（月支索引=月份-1，偏移寅月起）
_MONTH_BRANCH_TABLE: dict[int, str] = {
    1: '寅', 2: '卯', 3: '辰', 4: '巳', 5: '午', 6: '未',
    7: '申', 8: '酉', 9: '戌', 10: '亥', 11: '子', 12: '丑',
}

# 时支固定查表（以2小时为单位，23-1点为子时）
_HOUR_BRANCH_TABLE: dict[int, str] = {
    0: '子', 1: '子',
    2: '丑', 3: '丑',
    4: '寅', 5: '寅',
    6: '卯', 7: '卯',
    8: '辰', 9: '辰',
    10: '巳', 11: '巳',
    12: '午', 13: '午',
    14: '未', 15: '未',
    16: '申', 17: '申',
    18: '酉', 19: '酉',
    20: '戌', 21: '戌',
    22: '亥', 23: '亥',
}

# 月干起点查表：年干→正月天干索引
_MONTH_STEM_START: dict[str, int] = {
    '甲': 2, '己': 2,
    '乙': 4, '庚': 4,
    '丙': 6, '辛': 6,
    '丁': 8, '壬': 8,
    '戊': 0, '癸': 0,
}

# 时干起点查表：日干→子时天干索引
_HOUR_STEM_START: dict[str, int] = {
    '甲': 0, '己': 0,
    '乙': 2, '庚': 2,
    '丙': 4, '辛': 4,
    '丁': 6, '壬': 6,
    '戊': 8, '癸': 8,
}


def _validate_input(req: BaziInputRequest) -> tuple[bool, str]:
    """YOLO 拦截校验，纯字典查表，返回 (is_valid, reason)。"""
    rules = YOLO_VETO_RULES

    veto_004 = rules.get("VETO_004", {})
    if req.birth_year < 1900 or req.birth_year > 2100:
        return False, veto_004.get("reason", "年份越界")

    veto_005 = rules.get("VETO_005", {})
    if not (1 <= req.birth_month <= 12):
        return False, veto_005.get("reason", "月份不合法")
    if not (1 <= req.birth_day <= 31):
        return False, veto_005.get("reason", "日期不合法")
    if not (0 <= req.birth_hour <= 23):
        return False, veto_005.get("reason", "小时不合法")

    return True, ""


def _compute_year_pillar(year: int) -> tuple[str, str]:
    """年柱：(年干, 年支)，基准为甲子年=4。"""
    stem_idx = (year - _YEAR_OFFSET) % 10
    branch_idx = (year - _YEAR_OFFSET) % 12
    return _STEM_10_TABLE[stem_idx], _BRANCH_12_TABLE[branch_idx]


def _compute_month_pillar(year_stem: str, month: int) -> tuple[str, str]:
    """月柱：月支由月份固定查表，月干由年干推算。"""
    month_branch = _MONTH_BRANCH_TABLE[month]
    branch_idx = BRANCHES.index(month_branch)
    stem_start = _MONTH_STEM_START.get(year_stem, 0)
    # 正月(寅月)=index 2，每月+1
    month_offset = (branch_idx - 2) % 12
    stem_idx = (stem_start + month_offset) % 10
    return _STEM_10_TABLE[stem_idx], month_branch


def _compute_day_pillar(year: int, month: int, day: int) -> tuple[str, str]:
    """
    日柱：使用万年历公式（基于儒略日数）计算。
    基准：1900-01-01 为甲戌日（甲=0，戌=10）。
    """
    _MONTH_DAYS_OFFSET = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    day_of_year = _MONTH_DAYS_OFFSET[month - 1] + day
    if is_leap and month > 2:
        day_of_year += 1

    total_days_from_base = (year - 1900) * 365 + (year - 1900) // 4 - (year - 1900) // 100 + (year - 1900) // 400 + day_of_year - 1

    stem_idx = (total_days_from_base + 0) % 10
    branch_idx = (total_days_from_base + 10) % 12
    return _STEM_10_TABLE[stem_idx], _BRANCH_12_TABLE[branch_idx]


def _compute_hour_pillar(day_stem: str, hour: int) -> tuple[str, str]:
    """时柱：时支由小时固定查表，时干由日干推算。"""
    hour_branch = _HOUR_BRANCH_TABLE[hour]
    branch_idx = BRANCHES.index(hour_branch)
    stem_start = _HOUR_STEM_START.get(day_stem, 0)
    stem_idx = (stem_start + branch_idx) % 10
    return _STEM_10_TABLE[stem_idx], hour_branch


def _build_char_node(
    char: str, pos: str, kongwang_list: list[str],
    dm_element: str, dm_polarity: str
) -> BaziCharNode:
    """将单个字符 + 坐标映射为 BaziCharNode。"""
    elem, polarity = ELEMENT_MAP.get(char, ("未知", "未知"))
    is_stem = pos.endswith("干")
    is_month_branch = (pos == "月支")
    base_mass = 5.0 if is_stem else 10.0
    mass = base_mass * 2.0 if is_month_branch else base_mass
    weight = POSITION_WEIGHTS.get(pos, 1.0)
    ten_god = compute_ten_gods(dm_element, dm_polarity, elem, polarity)

    return BaziCharNode(
        char=char,
        pos=pos,
        element=elem,
        polarity=polarity,
        is_stem=is_stem,
        is_month_branch=is_month_branch,
        mass=mass,
        position_weight=weight,
        is_in_kongwang=(char in kongwang_list),
        ten_god=ten_god,
    )


def _build_interaction_tags(pillars_map: dict[str, tuple[str, str]]) -> BaziInteractionTags:
    """检测所有干支互动关系，纯字典集合查表，无推演断语。"""
    branch_chars = [pillars_map[n][1] for n in _PILLAR_NAMES]
    stem_chars = [pillars_map[n][0] for n in _PILLAR_NAMES]

    clash_tags, combo_tags, half_combo_tags = [], [], []
    trinity_tags, punish_tags, harm_tags = [], [], []
    stem_combo_tags, stem_clash_tags = [], []
    clash_count = 0

    for i in range(len(branch_chars)):
        for j in range(i + 1, len(branch_chars)):
            b1, b2 = branch_chars[i], branch_chars[j]
            pair = {b1, b2}
            if pair in CLASH_PAIRS:
                clash_tags.append(f"TAG_地支相冲_{b1}{b2}")
                clash_count += 1
            if pair in FULL_COMBOS:
                combo_tags.append(f"TAG_地支六合_{b1}{b2}")
            if pair in HALF_COMBOS:
                half_combo_tags.append(f"TAG_地支半合_{b1}{b2}")
            if pair in PUNISH_PAIRS:
                punish_tags.append(f"TAG_地支相刑_{b1}{b2}")
            if pair in HARM_PAIRS:
                harm_tags.append(f"TAG_地支相害_{b1}{b2}")

    trinity_sets = [
        {'申', '子', '辰'}, {'亥', '卯', '未'},
        {'寅', '午', '戌'}, {'巳', '酉', '丑'},
    ]
    branch_set = set(branch_chars)
    for trinity in trinity_sets:
        if trinity.issubset(branch_set):
            label = "".join(sorted(trinity))
            trinity_tags.append(f"TAG_地支三合_{label}")

    for i in range(len(stem_chars)):
        for j in range(i + 1, len(stem_chars)):
            s1, s2 = stem_chars[i], stem_chars[j]
            pair = {s1, s2}
            if pair in STEM_COMBOS:
                stem_combo_tags.append(f"TAG_天干合_{s1}{s2}")
            if pair in STEM_CLASHES:
                stem_clash_tags.append(f"TAG_天干冲_{s1}{s2}")

    return BaziInteractionTags(
        clash_tags=clash_tags,
        combo_tags=combo_tags,
        half_combo_tags=half_combo_tags,
        trinity_tags=trinity_tags,
        punish_tags=punish_tags,
        harm_tags=harm_tags,
        stem_combo_tags=stem_combo_tags,
        stem_clash_tags=stem_clash_tags,
        total_clash_count=clash_count,
    )


def _build_climate(month_branch: str) -> BaziClimate:
    """气候状态查表。"""
    for state, rule in V7_CLIMATE_RULES.items():
        if month_branch in rule['months']:
            return BaziClimate(
                month_branch=month_branch,
                climate_state=state,
                override_kernel=rule['override_kernel'],
                is_climate_override_active=True,
            )
    return BaziClimate(
        month_branch=month_branch,
        climate_state="中性",
        override_kernel="",
        is_climate_override_active=False,
    )


def _build_kinship(
    pillars_map: dict[str, tuple[str, str]],
    dm_element: str, dm_polarity: str,
) -> BaziKinshipPointers:
    """亲缘指针：按十神关系映射至父/母/配偶信息宫。"""
    father_chars, mother_chars, spouse_descriptors = [], [], []
    official_kill_count = 0
    wealth_count = 0
    resource_count = 0

    for pillar_name in _PILLAR_NAMES:
        stem_char, branch_char = pillars_map[pillar_name]
        for char in [stem_char, branch_char]:
            if not char:
                continue
            elem, polarity = ELEMENT_MAP.get(char, ("未知", "未知"))
            ten_god = compute_ten_gods(dm_element, dm_polarity, elem, polarity)

            if pillar_name in ["年", "月"]:
                if ten_god in ["正财", "偏财", "正官", "七杀"]:
                    father_chars.append(char)
                elif ten_god in ["正印", "偏印", "食神", "伤官", "比肩", "劫财"]:
                    mother_chars.append(char)

            if ten_god in ["正财", "偏财", "正官", "七杀"]:
                spouse_descriptors.append(f"{char}({ten_god})")

            if ten_god in ["正官", "七杀"]:
                official_kill_count += 1
            if ten_god in ["正财", "偏财"]:
                wealth_count += 1
            if ten_god in ["正印", "偏印"]:
                resource_count += 1

    is_oppressed = official_kill_count >= 2
    is_wealth_scattered = wealth_count >= 1
    is_resource_blocked = wealth_count >= 1 and resource_count >= 1

    return BaziKinshipPointers(
        father_chars=father_chars,
        mother_chars=mother_chars,
        spouse_descriptors=spouse_descriptors,
        is_oppressed=is_oppressed,
        is_wealth_scattered=is_wealth_scattered,
        is_resource_blocked=is_resource_blocked,
    )


def parse_bazi_request(req: BaziInputRequest) -> BaziFullCluster:
    """
    主解析入口：BaziInputRequest → BaziFullCluster。
    纯查表，无 LLM 调用，无网络请求，O(1) 主路径。
    """
    is_valid, veto_reason = _validate_input(req)

    year_stem, year_branch = _compute_year_pillar(req.birth_year)
    month_stem, month_branch = _compute_month_pillar(year_stem, req.birth_month)
    day_stem, day_branch = _compute_day_pillar(req.birth_year, req.birth_month, req.birth_day)
    hour_stem, hour_branch = _compute_hour_pillar(day_stem, req.birth_hour)

    pillars_map: dict[str, tuple[str, str]] = {
        "年": (year_stem, year_branch),
        "月": (month_stem, month_branch),
        "日": (day_stem, day_branch),
        "时": (hour_stem, hour_branch),
    }

    kongwang_list = compute_kongwang(day_stem, day_branch)

    dm_element, dm_polarity = ELEMENT_MAP.get(day_stem, ("木", "阳"))

    pos_order = [
        ("年干", year_stem), ("年支", year_branch),
        ("月干", month_stem), ("月支", month_branch),
        ("日干", day_stem), ("日支", day_branch),
        ("时干", hour_stem), ("时支", hour_branch),
    ]
    nodes = [
        _build_char_node(char, pos, kongwang_list, dm_element, dm_polarity)
        for pos, char in pos_order
    ]

    pillar_list = []
    for idx, name in enumerate(_PILLAR_NAMES):
        stem_char, branch_char = pillars_map[name]
        stem_node = next((n for n in nodes if n.pos == f"{name}干"), None)
        branch_node = next((n for n in nodes if n.pos == f"{name}支"), None)
        pillar_list.append(BaziPillar(
            pillar_name=name,
            stem=stem_node,
            branch=branch_node,
            pillar_index=idx,
        ))

    all_branches = [pillars_map[n][1] for n in _PILLAR_NAMES]
    all_chars = [char for _, char in pos_order]
    node_dicts = [
        {"char": n.char, "elem": n.element, "pos": n.pos, "mass": n.mass}
        for n in nodes
    ]

    mass_vector = compute_element_mass_vector(node_dicts)
    thermo = compute_thermo_ratio(all_chars)
    dominant_elem = find_dominant_element(mass_vector)
    root_strength = compute_root_strength(day_stem, all_branches)

    dm_resource_elem = RESOURCE_CYCLE.get(dm_element, "水")
    dm_output_elem = GENERATE_CYCLE.get(dm_element, "火")
    is_liquid_state = (
        mass_vector.get(dm_resource_elem, 0.0) < 5.0
        and mass_vector.get(dm_output_elem, 0.0) >= 15.0
    )

    climate = _build_climate(month_branch)
    kernel_element = climate.override_kernel if climate.is_climate_override_active else dm_element

    strength_profile = BaziStrengthProfile(
        day_master_char=day_stem,
        day_master_element=dm_element,
        day_master_polarity=dm_polarity,
        has_root=(root_strength > 0.0),
        root_branches=[b for b in all_branches if b in V7_ROOT_QI_MATRIX.get(day_stem, [])],
        root_strength_score=root_strength,
        dominant_element=dominant_elem,
        disease_mass=mass_vector.get(dominant_elem, 0.0),
        is_liquid_state=is_liquid_state,
        warm_ratio=thermo["warm_ratio"],
        cold_ratio=thermo["cold_ratio"],
        pattern_label="普通格",
        kernel_element=kernel_element,
    )

    interaction_tags = _build_interaction_tags(pillars_map)
    kinship = _build_kinship(pillars_map, dm_element, dm_polarity)

    return BaziFullCluster(
        input_request=req,
        pillars=pillar_list,
        nodes=nodes,
        kongwang_branches=kongwang_list,
        climate=climate,
        strength_profile=strength_profile,
        interaction_tags=interaction_tags,
        tension_dna=None,
        is_input_valid=is_valid,
        veto_reason=veto_reason,
    )
