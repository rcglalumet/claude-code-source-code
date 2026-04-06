# = [端口 M: L0 核心代数算法] =
# 路径: core_engine/bazi_math_core.py
# 【轨道 B3 专属】: 纯 CPU 代数——无 I/O，无网络，无副作用

from typing import Tuple

from expert_rules.bazi_rules import STEMS, BRANCHES, ELEMENT_MAP, GENERATE_CYCLE, CONTROL_CYCLE


# ==========================================
# 天干地支序数映射 (O(1) 模运算基础)
# ==========================================

STEM_INDEX: dict[str, int] = {s: i for i, s in enumerate(STEMS)}
BRANCH_INDEX: dict[str, int] = {b: i for i, b in enumerate(BRANCHES)}


def compute_jiazi_index(stem: str, branch: str) -> int:
    """
    计算干支六十甲子序号 (0-59).
    六十甲子 = 天干 5 轮 × 12 地支，满足:
        stem_idx % 2 == branch_idx % 2  (阴阳同性)
    返回值范围 [0, 59]，超出则返回 -1 表示非法配对。
    """
    si = STEM_INDEX.get(stem, -1)
    bi = BRANCH_INDEX.get(branch, -1)
    if si == -1 or bi == -1:
        return -1
    if si % 2 != bi % 2:
        return -1
    return (si * 6 + bi * 5) % 60


def get_void_branches(day_stem: str, day_branch: str) -> Tuple[str, str]:
    """
    计算日柱空亡地支 (旬空).
    旬空算法: 当前旬起点为日干甲子序号减去 (序号 % 10)，
    旬末尾两支即为空亡。
    """
    si = STEM_INDEX.get(day_stem, -1)
    bi = BRANCH_INDEX.get(day_branch, -1)
    if si == -1 or bi == -1:
        return ("", "")
    offset = (bi - si) % 12
    void_1 = BRANCHES[(10 + offset) % 12]
    void_2 = BRANCHES[(11 + offset) % 12]
    return (void_1, void_2)


def compute_element_mass(
    nodes: list[dict],
    position_weights: dict[str, float],
) -> dict[str, float]:
    """
    按仓位权重累加五行质量张量.
    nodes: [{"char": "甲", "pos": "月干", "elem": "木", ...}, ...]
    返回: {"木": 12.0, "火": 5.0, ...}
    """
    mass: dict[str, float] = {"木": 0.0, "火": 0.0, "土": 0.0, "金": 0.0, "水": 0.0}
    for node in nodes:
        elem = node.get("elem", "")
        pos = node.get("pos", "")
        if elem in mass:
            mass[elem] += position_weights.get(pos, 1.0)
    return mass


def get_ten_god(
    day_master_elem: str,
    day_master_polar: str,
    target_elem: str,
    target_polar: str,
) -> str:
    """
    计算十神关系 (纯代数，无分支外判).
    基于生克关系矩阵与阴阳同性判断返回十神名称字符串。
    """
    if not target_elem:
        return "未知"
    is_same_polar = (day_master_polar == target_polar)

    if day_master_elem == target_elem:
        return "比肩" if is_same_polar else "劫财"

    if GENERATE_CYCLE.get(day_master_elem) == target_elem:
        return "食神" if is_same_polar else "伤官"

    if GENERATE_CYCLE.get(target_elem) == day_master_elem:
        return "偏印" if is_same_polar else "正印"

    if CONTROL_CYCLE.get(day_master_elem) == target_elem:
        return "偏财" if is_same_polar else "正财"

    if CONTROL_CYCLE.get(target_elem) == day_master_elem:
        return "七杀" if is_same_polar else "正官"

    return "未知"


def compute_strength_score(
    element_mass: dict[str, float],
    day_master_elem: str,
) -> float:
    """
    计算日主强度分 (归一化标量).
    强度 = (日主同行质量 + 印星质量) / 总质量
    返回值域 [0.0, 1.0]。
    """
    total = sum(element_mass.values())
    if total == 0.0:
        return 0.0

    resource_elem_map = {v: k for k, v in GENERATE_CYCLE.items()}
    resource_elem = resource_elem_map.get(day_master_elem, "")

    support_mass = element_mass.get(day_master_elem, 0.0)
    if resource_elem:
        support_mass += element_mass.get(resource_elem, 0.0)

    return round(support_mass / total, 4)


def identify_wuxing_from_char(char: str) -> Tuple[str, str]:
    """
    O(1) 字典查表：汉字 -> (五行, 阴阳).
    未识别字符返回 ("", "").
    """
    return ELEMENT_MAP.get(char, ("", ""))
