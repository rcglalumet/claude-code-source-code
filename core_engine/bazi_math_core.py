# === [L0 核心代数算法] ===
# 路径: core_engine/bazi_math_core.py
# 轨道 B3 专属：纯 CPU 代数，禁止网络调用，禁止 LLM 调用
# 包含：天干地支序号换算、60甲子推演、空亡计算、通根强度计算

from expert_rules.bazi_rules import (
    STEMS, BRANCHES, ELEMENT_MAP, GENERATE_CYCLE,
    CONTROL_CYCLE, RESOURCE_CYCLE, HIDDEN_QUARKS, V7_ROOT_QI_MATRIX,
    POSITION_WEIGHTS,
)

# 60甲子循环索引
JIAZI_CYCLE = [
    (STEMS[i % 10], BRANCHES[i % 12]) for i in range(60)
]

STEM_INDEX: dict[str, int] = {s: i for i, s in enumerate(STEMS)}
BRANCH_INDEX: dict[str, int] = {b: i for i, b in enumerate(BRANCHES)}


def stem_branch_to_jiazi_index(stem: str, branch: str) -> int:
    """天干地支 → 60甲子序号 [0, 59]"""
    s_idx = STEM_INDEX[stem]
    b_idx = BRANCH_INDEX[branch]
    for n in range(60):
        if n % 10 == s_idx and n % 12 == b_idx:
            return n
    return -1


def jiazi_index_to_stem_branch(index: int) -> tuple[str, str]:
    """60甲子序号 → (天干, 地支)"""
    index = index % 60
    return JIAZI_CYCLE[index]


def compute_kongwang(day_stem: str, day_branch: str) -> list[str]:
    """
    计算日柱空亡地支（旬空）。
    每旬10天干配12地支，末尾剩余2支为空亡。
    公式：旬首 = 60甲子序号 // 10 * 10，空亡 = 旬首第10、11支。
    """
    jiazi_idx = stem_branch_to_jiazi_index(day_stem, day_branch)
    if jiazi_idx < 0:
        return []
    xun_start = (jiazi_idx // 10) * 10
    void_1 = BRANCHES[(xun_start // 10 * 10 + 10) % 12]
    void_2 = BRANCHES[(xun_start // 10 * 10 + 11) % 12]
    xun_branch_start = BRANCH_INDEX[JIAZI_CYCLE[xun_start][1]]
    void_1 = BRANCHES[(xun_branch_start + 10) % 12]
    void_2 = BRANCHES[(xun_branch_start + 11) % 12]
    return [void_1, void_2]


def compute_ten_gods(
    dm_element: str, dm_polarity: str, target_element: str, target_polarity: str
) -> str:
    """
    根据日主与目标的五行阴阳关系推算十神。
    返回：比肩/劫财/食神/伤官/偏财/正财/七杀/正官/偏印/正印
    """
    if not dm_element or not target_element:
        return "未知"

    same_polarity = (dm_polarity == target_polarity)

    if dm_element == target_element:
        return "比肩" if same_polarity else "劫财"

    if GENERATE_CYCLE.get(dm_element) == target_element:
        return "食神" if same_polarity else "伤官"

    if GENERATE_CYCLE.get(target_element) == dm_element:
        return "偏印" if same_polarity else "正印"

    if CONTROL_CYCLE.get(dm_element) == target_element:
        return "偏财" if same_polarity else "正财"

    if CONTROL_CYCLE.get(target_element) == dm_element:
        return "七杀" if same_polarity else "正官"

    return "未知"


def compute_root_strength(dm_char: str, all_branches: list[str]) -> float:
    """
    计算日主通根强度（0.0 ~ 1.0）。
    按照 POSITION_WEIGHTS 中的月支权重最高原则，返回归一化分数。
    """
    valid_roots = V7_ROOT_QI_MATRIX.get(dm_char, [])
    if not valid_roots:
        return 0.0
    matched = sum(1 for b in all_branches if b in valid_roots)
    return min(1.0, matched / max(len(valid_roots), 1))


def compute_element_mass_vector(
    nodes: list[dict],
) -> dict[str, float]:
    """
    统计命局五行质量向量。
    nodes: [{"char": str, "elem": str, "pos": str, "mass": float}]
    返回: {"木": float, "火": float, "土": float, "金": float, "水": float}
    """
    mass: dict[str, float] = {"木": 0.0, "火": 0.0, "土": 0.0, "金": 0.0, "水": 0.0}
    for node in nodes:
        elem = node.get("elem", "")
        node_mass = node.get("mass", 10.0)
        if elem in mass:
            mass[elem] += node_mass
    return mass


def compute_position_weighted_mass(
    nodes: list[dict],
) -> dict[str, float]:
    """
    按坐标权重加权后的五行质量向量（用于强弱判断）。
    """
    mass: dict[str, float] = {"木": 0.0, "火": 0.0, "土": 0.0, "金": 0.0, "水": 0.0}
    for node in nodes:
        elem = node.get("elem", "")
        pos = node.get("pos", "")
        base_mass = node.get("mass", 10.0)
        weight = POSITION_WEIGHTS.get(pos, 1.0)
        if elem in mass:
            mass[elem] += base_mass * weight
    return mass


def find_dominant_element(mass_vector: dict[str, float]) -> str:
    """返回五行质量向量中最重的元素。"""
    return max(mass_vector, key=mass_vector.get)


def compute_thermo_ratio(all_chars: list[str]) -> dict[str, float]:
    """
    计算命局寒暖比例。
    返回: {"warm_ratio": float, "cold_ratio": float}
    """
    from expert_rules.bazi_rules import THERMO_WARM, THERMO_COLD

    total = len(all_chars)
    if total == 0:
        return {"warm_ratio": 0.0, "cold_ratio": 0.0}

    warm = sum(1 for c in all_chars if c in THERMO_WARM)
    cold = sum(1 for c in all_chars if c in THERMO_COLD)
    return {
        "warm_ratio": round(warm / total, 4),
        "cold_ratio": round(cold / total, 4),
    }


def encode_node_mass(pos: str, is_month_branch: bool) -> float:
    """
    根据坐标编码计算节点基础质量。
    天干基础 5.0，地支基础 10.0，月支翻倍。
    """
    _, col = pos.split("支") if "支" in pos else (None, None)
    is_stem = pos.endswith("干")
    base = 5.0 if is_stem else 10.0
    return base * 2.0 if is_month_branch else base
