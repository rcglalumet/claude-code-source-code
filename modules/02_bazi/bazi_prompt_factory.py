# = [端口 F: L1 表现层 Prompt 工厂] =
# 路径: modules/02_bazi/bazi_prompt_factory.py
# 所有给 LLM 的指令模板与输出文本模板集中管理
# 无推演逻辑，无 I/O，无网络调用

from typing import Dict, List

from expert_rules.bazi_rules import WUXING_MAPPING, CHEMISTRY_DICT


# ==========================================
# 系统级 Prompt 模板
# ==========================================

SYSTEM_PROMPT_BAZI_ANALYST = """\
你是一位精通中国传统命理的八字分析专家，同时具备现代心理学与职业规划知识。
你的任务是依据用户的八字特征向量，给出务实、具体、有洞察力的分析报告。

【铁律】
- 只基于传入的特征向量数据进行分析，禁止自行推演八字关系。
- 输出语言应当温暖、专业，避免恐吓性断语。
- 对于负面特征，必须同时给出对应的化解策略。
- 所有建议须落地可执行，避免空洞玄学套语。
"""

SYSTEM_PROMPT_BRIEF_READING = """\
你是八字简读助手。根据输入的关键特征，输出不超过300字的核心提示。
直接切入最重要的1-2个命盘特征，给出一针见血的断语与行动建议。
"""


# ==========================================
# 用户侧 Prompt 模板（按功能分类）
# ==========================================

def build_full_report_prompt(
    day_master_char: str,
    day_master_elem: str,
    strength_score: float,
    is_weak: bool,
    kernel_elem: str,
    climate_override_elem: str,
    element_mass_vector: Dict[str, float],
    tujian_tags: List[str],
    tujian_strategies: List[str],
    kinship_info: Dict[str, List[str]],
    tension_features: Dict[str, float],
) -> str:
    """生成完整八字分析报告的 Prompt（交付 LLM 渲染）"""
    chemistry = CHEMISTRY_DICT.get(day_master_char, {})
    kernel_desc = chemistry.get("desc", "")
    kernel_industry = WUXING_MAPPING.get(kernel_elem, {}).get("industry", "")
    kernel_geo = WUXING_MAPPING.get(kernel_elem, {}).get("geo", "")

    strength_label = "偏弱，需要补强" if is_weak else "偏旺，需要疏泄"
    mass_lines = "\n".join(
        f"  - {elem}: {mass:.1f}分" for elem, mass in element_mass_vector.items()
    )
    tag_lines = "\n".join(f"  - {tag}" for tag in tujian_tags) or "  - 无特殊图鉴标签"
    strategy_lines = "\n".join(f"  - {s}" for s in tujian_strategies) or "  - 常规均衡发展"
    kinship_father = "、".join(kinship_info.get("father_chars", [])) or "暂无"
    kinship_mother = "、".join(kinship_info.get("mother_chars", [])) or "暂无"
    kinship_spouse = "、".join(kinship_info.get("spouse_chars", [])) or "暂无"

    high_features = [k for k, v in tension_features.items() if isinstance(v, float) and v > 0.5]
    feature_lines = "\n".join(f"  - {f}" for f in high_features) or "  - 无显著张力特征"

    climate_note = f"调候急需【{climate_override_elem}】" if climate_override_elem else "气候中和，调候正常"

    return f"""\
【八字分析任务】

▌ 日主信息
日主：{day_master_char}（{day_master_elem}）
强弱：{strength_label}（强度得分 {strength_score:.2f}）
核心用神：{kernel_elem}
调候说明：{climate_note}
用神特性：{kernel_desc}
适合方向：{kernel_industry}（{kernel_geo}）

▌ 五行质量分布
{mass_lines}

▌ 图鉴专家标签
{tag_lines}

▌ 推荐策略
{strategy_lines}

▌ 六亲星宫
  - 父星代表字：{kinship_father}
  - 母星代表字：{kinship_mother}
  - 配偶星代表字：{kinship_spouse}

▌ 激活张力特征
{feature_lines}

请结合以上信息，撰写一份完整的八字命盘分析报告，涵盖：
1. 命局整体格局与日主特质（2-3句）
2. 事业与财富方向（结合用神五行与行业映射）
3. 人际关系特质（结合六亲星宫与贪合特征）
4. 健康注意事项（结合调候与偏枯情况）
5. 核心人生策略（结合图鉴策略，落地可执行）
"""


def build_brief_reading_prompt(
    day_master_char: str,
    day_master_elem: str,
    is_weak: bool,
    kernel_elem: str,
    tujian_tags: List[str],
    top_strategy: str,
) -> str:
    """生成简读版（300字内）Prompt"""
    strength_label = "身弱" if is_weak else "身旺"
    tag_summary = "、".join(tujian_tags[:2]) if tujian_tags else "无特殊标签"

    return f"""\
【八字快读任务】

日主 {day_master_char}（{day_master_elem}，{strength_label}），核心用神为【{kernel_elem}】。
图鉴标签：{tag_summary}
核心策略：{top_strategy or '常规均衡发展'}

请用不超过300字，给出一针见血的核心断语与最重要的1条行动建议。
"""


def build_yolo_rejection_prompt(veto_reason: str) -> str:
    """YOLO 拦截后的友好反馈 Prompt"""
    return f"""\
【输入校验失败】

系统检测到输入数据存在以下问题：
{veto_reason}

请确认八字格式为：年干_X 年支_X 月干_X 月支_X 日干_X 日支_X 时干_X 时支_X
其中 X 为合法的天干（甲乙丙丁戊己庚辛壬癸）或地支（子丑寅卯辰巳午未申酉戌亥）。
"""


def build_void_branch_prompt(
    void_branch_1: str,
    void_branch_2: str,
    void_activated_chars: List[str],
) -> str:
    """空亡信息 Prompt 片段"""
    activated = "、".join(void_activated_chars) if void_activated_chars else "无"
    return f"""\
▌ 空亡（旬空）信息
本命旬空地支：【{void_branch_1}】【{void_branch_2}】
落空重要十神字：{activated}
（空亡字代表的人事物，往往缘浅或有缺憾，需特别留意。）
"""


# ==========================================
# Prompt 拼装器（供 L2 层调用）
# ==========================================

class BaziPromptFactory:
    """
    静态工厂类：根据推演特征向量组装对应的 Prompt 字符串。
    不持有状态，不执行推演，不做 I/O。
    """

    @staticmethod
    def get_system_prompt(mode: str = "full") -> str:
        """
        mode: 'full' = 完整报告模式；'brief' = 简读模式
        """
        if mode == "brief":
            return SYSTEM_PROMPT_BRIEF_READING
        return SYSTEM_PROMPT_BAZI_ANALYST

    @staticmethod
    def build_user_prompt(dna: dict, mode: str = "full") -> str:
        """
        dna: BaziUnifiedEngine.infer() 的返回字典
        mode: 'full' | 'brief'
        """
        if dna.get("error"):
            return build_yolo_rejection_prompt(dna.get("veto_reason", "未知错误"))

        day_master_char = dna.get("day_master_char", "")
        day_master_elem = dna.get("day_master_elem", "")
        strength_score = float(dna.get("strength_score", 0.0))
        is_weak = bool(dna.get("is_weak", True))
        kernel_elem = dna.get("kernel_elem", "")
        climate_override = dna.get("climate_override_elem", "")
        element_mass = dna.get("element_mass_vector", {})
        tujian_tags = dna.get("tujian_tags", [])
        tujian_strategies = dna.get("tujian_strategies", [])
        kinship = {
            "father_chars": dna.get("kinship_father_chars", []),
            "mother_chars": dna.get("kinship_mother_chars", []),
            "spouse_chars": dna.get("kinship_spouse_chars", []),
        }
        tension_features = {
            k: v for k, v in dna.items()
            if isinstance(v, float) and k not in (
                "disease_mass", "strength_score", "is_liquid_state",
                "has_root", "is_climate_override",
            )
        }

        if mode == "brief":
            top_strategy = tujian_strategies[0] if tujian_strategies else ""
            return build_brief_reading_prompt(
                day_master_char=day_master_char,
                day_master_elem=day_master_elem,
                is_weak=is_weak,
                kernel_elem=kernel_elem,
                tujian_tags=tujian_tags,
                top_strategy=top_strategy,
            )

        return build_full_report_prompt(
            day_master_char=day_master_char,
            day_master_elem=day_master_elem,
            strength_score=strength_score,
            is_weak=is_weak,
            kernel_elem=kernel_elem,
            climate_override_elem=climate_override,
            element_mass_vector=element_mass,
            tujian_tags=tujian_tags,
            tujian_strategies=tujian_strategies,
            kinship_info=kinship,
            tension_features=tension_features,
        )
