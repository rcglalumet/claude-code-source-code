# === [L1 表现层 Prompt 工厂] ===
# 路径: modules/02_bazi/bazi_prompt_factory.py
# 职责：将所有给 LLM 的指令文本与输出格式模板集中管理
# 禁止：业务逻辑计算、LLM 调用、网络请求

from __future__ import annotations

from expert_rules.bazi_rules import CHEMISTRY_DICT, WUXING_MAPPING

# ==========================================
# 系统角色 Prompt
# ==========================================

SYSTEM_ROLE_PROMPT = """你是一位精通中华命理学的 AI 分析师，代号【命理推演引擎 V10】。
你的职责是接收已计算完毕的八字特征向量（JSON 格式），并基于五行生克、十神关系、
干支互动等物理规则，生成清晰、专业、有洞察力的命理报告。

核心约束：
1. 你只根据传入的结构化数据进行分析，不凭空捏造数据
2. 使用严谨而通俗的语言，避免迷信化表达
3. 报告必须分为五大领域：性格、事业、人际、健康、祖荫
4. 每个领域给出 1-2 句核心断语 + 1 句行动建议
"""

# ==========================================
# 五大领域报告生成 Prompt 模板
# ==========================================

DOMAIN_REPORT_PROMPT_TEMPLATE = """请根据以下八字分析数据生成专业命理报告。

## 命主基本信息
- 日主：{day_master_char}（{day_master_element} · {day_master_polarity}）
- 格局：{pattern_label}
- 核心用神：{kernel_element}（{kernel_element_industry}）
- 最优方位：{kernel_element_geo}

## 命局特征向量
- 通根状态：{has_root_text}（强度得分：{root_strength_score:.2f}）
- 气候调候：{climate_state}（{override_kernel_text}）
- 寒暖比例：暖 {warm_ratio:.0%} / 寒 {cold_ratio:.0%}
- 最重五行：{dominant_element}（质量 {disease_mass:.1f}）
- 液态标志：{is_liquid_state_text}

## 活跃探针（已触发）
{active_probes_list}

## 干支互动标签
{interaction_tags_text}

## 亲缘信息宫
- 父星：{father_chars_text}
- 母星：{mother_chars_text}
- 配偶：{spouse_descriptors_text}

---
请按以下结构输出报告（每节不超过 120 字）：

### 🧠 性格与内在驱动
[核心断语] [行动建议]

### 💼 事业与财富
[核心断语] [行动建议]

### 👥 人际与感情
[核心断语] [行动建议]

### 🏥 健康与体能
[核心断语] [行动建议]

### 🌳 祖荫与根基
[核心断语] [行动建议]

### ⚡ 综合战略建议
[一句话核心策略]
"""

# ==========================================
# 化学反应（用神喜忌）Prompt 片段工厂
# ==========================================

def make_chemistry_hint(day_master_char: str) -> str:
    """根据日主提取化学反应描述片段，供注入 Prompt 上下文。"""
    chem = CHEMISTRY_DICT.get(day_master_char, {})
    if not chem:
        return f"日主 {day_master_char} 暂无化学反应数据。"
    kernel = chem.get("kernel", "")
    threats = "、".join(chem.get("threat", []))
    desc = chem.get("desc", "")
    return f"【{day_master_char}日主用神】核心用神：{kernel}；忌神：{threats}。{desc}"


def make_wuxing_direction_hint(kernel_element: str) -> str:
    """根据用神五行提取方位与行业建议片段。"""
    info = WUXING_MAPPING.get(kernel_element, {})
    if not info:
        return f"用神 {kernel_element} 暂无方位行业数据。"
    geo = info.get("geo", "")
    industry = info.get("industry", "")
    return f"【{kernel_element}用神方位】{geo}方向；适合行业：{industry}。"


# ==========================================
# 探针激活摘要文本工厂
# ==========================================

_PROBE_LABEL_MAP: dict[str, str] = {
    "structural_overload": "🔴 结构过载（日主无根+财杀拱攻）",
    "thermal_death": "🟡 热寂无序（命局散漫无凝聚）",
    "flesh_smash": "🔴 全息肉身崩溃（健康警报）",
    "antimatter_fission": "🔴 反物质裂变（七杀直冲日支）",
    "info_capture": "🟢 全息信息捕获（情报感知强）",
    "massive_predation": "🟡 大质量掠食（强势竞争格局）",
    "macro_condensate": "🟢 宏观凝聚（命局有主心骨）",
    "cross_domain_predation": "🟡 跨域掠食（内外场域摩擦）",
    "chain_reaction": "🔴 链式反应（四柱全轴震荡）",
    "base_work_active": "🟢 基础工作激活（日支有活力）",
    "blackhole_nesting": "🟡 黑洞嵌套（双土库格局）",
    "dyson_sphere": "🟢 戴森球（三支同气拱卫）",
    "clone_seizure": "🟡 群劫夺财（比劫分食财星）",
    "authority_void": "🟡 权威空亡（官杀落空升华）",
    "high_entropy_clash_alert": "🔴 高熵冲局（≥2冲，动荡系统）",
    "toxic_attachment_alert": "🟡 毒性依附（日干参与合绊）",
    "wealth_breaks_resource_alert": "🟡 财破印局（财星克损印星）",
    "singularity_siphon": "🟢 三合虹吸（局势聚焦成形）",
    "stable_anchor": "🟢 稳态锚点（正财正官有合）",
    "absolute_weakness": "🔴 绝对身弱（无根无月令支援）",
}


def make_active_probes_text(tension_dna_dict: dict) -> str:
    """将已触发（值>0）的探针转为可读文本列表。"""
    skip_keys = {"tujian_tags", "kinship_pointers"}
    lines = []
    for key, val in tension_dna_dict.items():
        if key in skip_keys:
            continue
        if isinstance(val, float) and val != 0.0:
            label = _PROBE_LABEL_MAP.get(key, f"探针_{key}")
            lines.append(f"- {label}：权重 {val:+.1f}")
    return "\n".join(lines) if lines else "（无显著激活探针）"


# ==========================================
# 完整 Prompt 构建入口
# ==========================================

def build_bazi_report_prompt(
    cluster_dict: dict,
    tension_dna_dict: dict,
) -> str:
    """
    主 Prompt 构建函数。
    接收序列化后的 BaziFullCluster 与 BaziTensionDNA，
    返回完整可发送至 LLM 的 Prompt 字符串。
    """
    sp = cluster_dict.get("strength_profile", {})
    climate = cluster_dict.get("climate", {})
    interaction = cluster_dict.get("interaction_tags", {})
    kinship_raw = tension_dna_dict.get("kinship_pointers", {})

    day_master_char = sp.get("day_master_char", "未知")
    day_master_element = sp.get("day_master_element", "未知")
    day_master_polarity = sp.get("day_master_polarity", "未知")
    pattern_label = sp.get("pattern_label", "普通格")
    kernel_element = sp.get("kernel_element", "")
    has_root = sp.get("has_root", False)
    root_strength_score = sp.get("root_strength_score", 0.0)
    dominant_element = sp.get("dominant_element", "")
    disease_mass = sp.get("disease_mass", 0.0)
    is_liquid_state = sp.get("is_liquid_state", False)
    warm_ratio = sp.get("warm_ratio", 0.0)
    cold_ratio = sp.get("cold_ratio", 0.0)

    climate_state = climate.get("climate_state", "中性")
    override_kernel = climate.get("override_kernel", "")

    wuxing_info = WUXING_MAPPING.get(kernel_element, {})
    kernel_element_industry = wuxing_info.get("industry", "")
    kernel_element_geo = wuxing_info.get("geo", "")

    all_tags = (
        interaction.get("clash_tags", []) +
        interaction.get("combo_tags", []) +
        interaction.get("trinity_tags", []) +
        interaction.get("stem_combo_tags", [])
    )
    interaction_tags_text = "\n".join(f"- {t}" for t in all_tags) if all_tags else "（无显著互动标签）"

    tujian_tags = tension_dna_dict.get("tujian_tags", [])

    active_probes_list = make_active_probes_text(tension_dna_dict)

    father_chars = kinship_raw.get("father_chars", [])
    mother_chars = kinship_raw.get("mother_chars", [])
    spouse_descriptors = kinship_raw.get("spouse_descriptors", [])

    chemistry_hint = make_chemistry_hint(day_master_char)
    direction_hint = make_wuxing_direction_hint(kernel_element)

    prompt = DOMAIN_REPORT_PROMPT_TEMPLATE.format(
        day_master_char=day_master_char,
        day_master_element=day_master_element,
        day_master_polarity=day_master_polarity,
        pattern_label=pattern_label,
        kernel_element=kernel_element,
        kernel_element_industry=kernel_element_industry,
        kernel_element_geo=kernel_element_geo,
        has_root_text="有根" if has_root else "无根（漂浮态）",
        root_strength_score=root_strength_score,
        climate_state=climate_state,
        override_kernel_text=f"急需{override_kernel}调候" if override_kernel else "无急需调候",
        warm_ratio=warm_ratio,
        cold_ratio=cold_ratio,
        dominant_element=dominant_element,
        disease_mass=disease_mass,
        is_liquid_state_text="已激活（精气外泄）" if is_liquid_state else "未激活",
        active_probes_list=active_probes_list,
        interaction_tags_text=interaction_tags_text,
        father_chars_text="、".join(father_chars) if father_chars else "未见",
        mother_chars_text="、".join(mother_chars) if mother_chars else "未见",
        spouse_descriptors_text="、".join(spouse_descriptors) if spouse_descriptors else "未见",
    )

    extra_context = f"\n\n---\n## 参考：化学反应与用神方位\n{chemistry_hint}\n{direction_hint}"
    if tujian_tags:
        extra_context += f"\n\n## 图鉴标签\n" + "\n".join(f"- {t}" for t in tujian_tags)

    return SYSTEM_ROLE_PROMPT + "\n\n" + prompt + extra_context


# ==========================================
# YOLO 拦截回执 Prompt
# ==========================================

YOLO_BLOCK_RESPONSE_TEMPLATE = """⚠️ 系统拦截通知

您的请求已被系统安全层拦截，无法进入命理推演引擎。

拦截原因：{reason}

请检查输入内容并重新提交。若确认输入无误，请联系系统管理员。
"""


def make_yolo_block_response(reason: str) -> str:
    """生成 YOLO 拦截回执文本。"""
    return YOLO_BLOCK_RESPONSE_TEMPLATE.format(reason=reason)
