# -*- coding: utf-8 -*-
# = [端口 M: L0 核心代数算法] =
# 路径: core_engine/xiangshu_math_core.py
# @Layer: 🔢 [L0] 象数派纯 CPU 代数引擎 (轨道 B3 专属)
# @Description: 纯数学公式与张量叠加算法。
#               零 I/O，零网络，零 LLM 调用。
#               所有函数仅接收基础标量/列表，返回基础标量/字典。

from typing import Dict, List, Tuple


# ==============================================================================
# [B3-001] 五行生克权重调制矩阵（O(1) 静态查表）
# 键: (施力五行, 受力五行) -> 倍率修正系数
# ==============================================================================
WUXING_INTERACTION_MATRIX: Dict[Tuple[str, str], float] = {
    # 相生（顺生：+0.3 增益）
    ("WOOD",  "FIRE"):  1.3,
    ("FIRE",  "EARTH"): 1.3,
    ("EARTH", "METAL"): 1.3,
    ("METAL", "WATER"): 1.3,
    ("WATER", "WOOD"):  1.3,
    # 相克（逆克：-0.4 衰减）
    ("WOOD",  "EARTH"): 0.6,
    ("EARTH", "WATER"): 0.6,
    ("WATER", "FIRE"):  0.6,
    ("FIRE",  "METAL"): 0.6,
    ("METAL", "WOOD"):  0.6,
    # 同行（比和：±0，维持原值）
    ("WOOD",  "WOOD"):  1.0,
    ("FIRE",  "FIRE"):  1.0,
    ("EARTH", "EARTH"): 1.0,
    ("METAL", "METAL"): 1.0,
    ("WATER", "WATER"): 1.0,
}


def wuxing_modulate(base_weight: float, source_wuxing: str, target_wuxing: str) -> float:
    """
    [B3-001] 五行调制：根据两宫五行的生克关系，对 base_weight 进行物理系数修正。
    返回修正后的张量权重（float）。
    """
    key = (source_wuxing.upper(), target_wuxing.upper())
    coeff = WUXING_INTERACTION_MATRIX.get(key, 1.0)
    return round(base_weight * coeff, 4)


# ==============================================================================
# [B3-002] 张量累加引擎：多规则命中时的物理叠加算法
# 规则：tension 与 mass 按物理向量叠加，entropy 为熵积分
# ==============================================================================
def accumulate_tensor(
    activated_weights: List[float],
    tension_increments: List[float],
    mass_impacts: List[float],
    global_max_tension: float = 25.0,
    global_min_mass: float = -15.0,
) -> Dict[str, float]:
    """
    [B3-002] 物理张量累加。
    - activated_weights: 所有命中规则的 base_weight 列表
    - tension_increments: 各规则对应的 tension_increment 列表
    - mass_impacts:       各规则对应的 mass_impact 列表
    - 返回: {"total_weight": float, "tension": float, "mass": float, "entropy": float}
    """
    total_weight = sum(activated_weights)
    raw_tension = sum(tension_increments)
    raw_mass = sum(mass_impacts)

    # 边界钳制（防爆协议）
    tension = min(raw_tension, global_max_tension)
    mass = max(raw_mass, global_min_mass)

    # 熵值 = 命中规则数量 / 最大可能规则数（归一化至 [0, 1]）
    max_possible = 103  # 当前 XIANGSHU_GENOMES 总基因座数
    rule_count = len(activated_weights)
    entropy = round(min(rule_count / max(max_possible, 1), 1.0), 4)

    return {
        "total_weight": round(total_weight, 4),
        "tension": round(tension, 4),
        "mass": round(mass, 4),
        "entropy": entropy,
        "rule_hit_count": rule_count,
    }


# ==============================================================================
# [B3-003] 宫位九宫格坐标映射（3×3 线性化索引）
# 标准洛书九宫：1=西北, 2=北, 3=东北, 4=西, 5=中, 6=东, 7=西南, 8=南, 9=东南
# 像素归一化坐标 (x_norm, y_norm) ∈ [0,1] -> 九宫 index (1-9)
# ==============================================================================
def pixel_to_palace_index(x_norm: float, y_norm: float) -> int:
    """
    [B3-003] 将归一化像素坐标映射到九宫格 index (1-9)。
    x_norm ∈ [0,1]：0=左, 1=右
    y_norm ∈ [0,1]：0=上, 1=下
    """
    col = min(int(x_norm * 3), 2)  # 0,1,2 -> 左,中,右
    row = min(int(y_norm * 3), 2)  # 0,1,2 -> 上,中,下
    return row * 3 + col + 1       # 1-9 线性化


# ==============================================================================
# [B3-004] 张量权重归一化（Softmax 变体，防除零）
# ==============================================================================
def normalize_weights(weights: List[float]) -> List[float]:
    """
    [B3-004] 对一组权重进行 Min-Max 归一化至 [0, 1]。
    若所有权重相等（或列表为空），返回等权列表。
    """
    if not weights:
        return []
    w_min = min(weights)
    w_max = max(weights)
    span = w_max - w_min
    if span == 0.0:
        n = len(weights)
        return [round(1.0 / n, 6)] * n
    return [round((w - w_min) / span, 6) for w in weights]


# ==============================================================================
# [B3-005] MCTS 蒸馏分数计算（夜间权重更新的输入接口）
# 公式: score = base_weight * (1 + feedback_positive_rate) - entropy_penalty
# ==============================================================================
def mcts_distill_score(
    base_weight: float,
    feedback_positive_rate: float,
    entropy: float,
    entropy_tolerance: float = 0.85,
) -> float:
    """
    [B3-005] 计算 MCTS 蒸馏得分。
    - feedback_positive_rate: 用户正反馈率 ∈ [0, 1]
    - entropy: 当前图谱熵值 ∈ [0, 1]
    - entropy_penalty 当 entropy > entropy_tolerance 时启动惩罚
    返回 float 蒸馏得分（越高越优先保留）。
    """
    entropy_penalty = max(0.0, entropy - entropy_tolerance) * base_weight * 0.5
    score = base_weight * (1.0 + feedback_positive_rate) - entropy_penalty
    return round(score, 4)


# ==============================================================================
# [B3-006] 关系强度线性映射（ominous/auspicious/neutral -> [-1, 0, 1]）
# ==============================================================================
RELATION_SCORE_MAP: Dict[str, float] = {
    "DIVIDES":   -1.0,
    "CROSSES":   -0.9,
    "OPPRESSES": -0.8,
    "MISSING":   -0.7,
    "BLOCKS":    -0.6,
    "NONE":       0.0,
    "PULLS":      0.1,
    "SUPPORTS":   0.8,
    "POINTS_TO":  1.0,
}


def relation_to_score(relation_type: str) -> float:
    """
    [B3-006] 将图谱边关系类型字符串映射为 [-1, 1] 区间的数值分数（O(1) 查表）。
    """
    return RELATION_SCORE_MAP.get(relation_type.upper(), 0.0)
