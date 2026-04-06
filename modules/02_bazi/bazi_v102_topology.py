# === [L1 拓扑实体] ===
# 路径: modules/02_bazi/bazi_v102_topology.py
# Pydantic 纯净模型 — 将大白话映射为严格的英文标量字段
# 禁止：Enum/Literal 大枚举、LLM 调用、复杂 if/else 断语
# 必须：基础标量 + Field(description=...) 详细说明

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional


class BaziInputRequest(BaseModel):
    """外部入参拓扑 — 来自用户的原始出生信息"""

    birth_year: int = Field(
        description="出生年份，公历整数，有效范围 1900-2100"
    )
    birth_month: int = Field(
        description="出生月份，1-12"
    )
    birth_day: int = Field(
        description="出生日，1-31"
    )
    birth_hour: int = Field(
        description="出生小时，24小时制，0-23"
    )
    birth_minute: int = Field(
        default=0,
        description="出生分钟，0-59，默认为0"
    )
    gender: str = Field(
        default="unknown",
        description="性别：'male' / 'female' / 'unknown'"
    )
    is_dst_adjusted: bool = Field(
        default=False,
        description="是否已做夏令时校正"
    )
    timezone_offset: float = Field(
        default=8.0,
        description="时区偏移，东八区为 8.0"
    )
    location_note: str = Field(
        default="",
        description="出生地备注，纯文本，不参与计算"
    )


class BaziCharNode(BaseModel):
    """单个干支字符节点 — 八字中每个天干或地支的物理表示"""

    char: str = Field(description="干支字符，如 '甲'、'子'")
    pos: str = Field(
        description="柱位标识，如 '年干'、'月支'、'日干'、'时支'"
    )
    element: str = Field(description="五行归属：木/火/土/金/水")
    polarity: str = Field(description="阴阳极性：'阳' 或 '阴'")
    is_stem: bool = Field(description="True=天干节点，False=地支节点")
    is_month_branch: bool = Field(
        default=False, description="是否为月支，月支权重最高"
    )
    mass: float = Field(
        description="节点质量，天干基础5.0，地支基础10.0，月支翻倍为20.0"
    )
    position_weight: float = Field(
        description="坐标权重系数，来自 POSITION_WEIGHTS 映射表"
    )
    is_in_kongwang: bool = Field(
        default=False, description="是否落入日柱空亡"
    )
    ten_god: str = Field(
        default="",
        description="相对日主的十神关系：比肩/劫财/食神/伤官/偏财/正财/七杀/正官/偏印/正印"
    )


class BaziPillar(BaseModel):
    """单柱拓扑 — 年/月/日/时 柱的物理容器"""

    pillar_name: str = Field(description="柱名：'年'/'月'/'日'/'时'")
    stem: Optional[BaziCharNode] = Field(
        default=None, description="天干节点"
    )
    branch: Optional[BaziCharNode] = Field(
        default=None, description="地支节点"
    )
    pillar_index: int = Field(
        description="柱序号：年=0，月=1，日=2，时=3"
    )


class BaziClimate(BaseModel):
    """气候状态拓扑 — V7 调候分析结果"""

    month_branch: str = Field(description="月支字符")
    climate_state: str = Field(
        description="气候状态标识：'冻结态' / '焦躁态' / '中性'"
    )
    override_kernel: str = Field(
        default="",
        description="调候首需用神五行，如 '火'（冻结态需火）"
    )
    is_climate_override_active: bool = Field(
        description="调候急需是否已激活，激活时该用神权重提升"
    )


class BaziStrengthProfile(BaseModel):
    """日主强弱画像拓扑 — V118 宏观张量结算"""

    day_master_char: str = Field(description="日主干支字符，如 '甲'")
    day_master_element: str = Field(description="日主五行")
    day_master_polarity: str = Field(description="日主阴阳")

    has_root: bool = Field(
        description="日主是否通根（在地支中找到气根）"
    )
    root_branches: List[str] = Field(
        default_factory=list,
        description="通根的地支列表"
    )
    root_strength_score: float = Field(
        description="通根强度得分，0.0-1.0，越高越有力"
    )

    dominant_element: str = Field(
        description="命局最重五行元素"
    )
    disease_mass: float = Field(
        description="最重五行的质量数值，用于判断病药"
    )
    is_liquid_state: bool = Field(
        description="是否处于液态（食伤过旺而印星极弱，精气外泄）"
    )

    warm_ratio: float = Field(
        description="命局寒暖分析：暖性干支占比，0.0-1.0"
    )
    cold_ratio: float = Field(
        description="命局寒暖分析：寒性干支占比，0.0-1.0"
    )

    pattern_label: str = Field(
        default="普通格",
        description="命局格局标签，如 '身强'、'身弱'、'从格'、'化格'"
    )
    kernel_element: str = Field(
        default="",
        description="核心用神五行，调候或强弱计算后确定的最优用神"
    )


class BaziInteractionTags(BaseModel):
    """干支互动标签拓扑 — 冲合刑害结果集"""

    clash_tags: List[str] = Field(
        default_factory=list,
        description="地支相冲标签列表，如 ['TAG_地支相冲_子午']"
    )
    combo_tags: List[str] = Field(
        default_factory=list,
        description="地支六合标签列表，如 ['TAG_地支相合_寅亥']"
    )
    half_combo_tags: List[str] = Field(
        default_factory=list,
        description="地支半合标签列表"
    )
    trinity_tags: List[str] = Field(
        default_factory=list,
        description="地支三合局标签列表"
    )
    punish_tags: List[str] = Field(
        default_factory=list,
        description="地支相刑标签列表"
    )
    harm_tags: List[str] = Field(
        default_factory=list,
        description="地支相害标签列表"
    )
    stem_combo_tags: List[str] = Field(
        default_factory=list,
        description="天干五合标签列表"
    )
    stem_clash_tags: List[str] = Field(
        default_factory=list,
        description="天干相冲标签列表"
    )
    total_clash_count: int = Field(
        default=0, description="相冲总数，用于高熵系统判断"
    )


class BaziKinshipPointers(BaseModel):
    """亲缘指针拓扑 — Amulet V2.0 星宫定位结果"""

    father_chars: List[str] = Field(
        default_factory=list,
        description="父星字符列表（正财、偏财、正官、七杀映射父亲信息宫）"
    )
    mother_chars: List[str] = Field(
        default_factory=list,
        description="母星字符列表（正印、偏印、食神、伤官映射母亲信息宫）"
    )
    spouse_descriptors: List[str] = Field(
        default_factory=list,
        description="配偶描述列表，格式：字符(十神关系)，如 '壬(正官)'"
    )
    is_oppressed: bool = Field(
        default=False,
        description="是否受官杀过度压制（口语：老板穿小鞋），官杀无制且克身过重"
    )
    is_wealth_scattered: bool = Field(
        default=False,
        description="财星被群劫分夺，财运分散无法聚拢"
    )
    is_resource_blocked: bool = Field(
        default=False,
        description="印星被财星破坏，贵人扶助无效或学业受阻"
    )


class BaziTensionDNA(BaseModel):
    """大一统特征向量 — L2 输入端口（UnifiedBaziEngine 输出）"""

    disease_mass: float = Field(
        description="最重五行质量，病量指数"
    )
    is_liquid_state: float = Field(
        description="液态标志：1.0=精气外泄，0.0=正常"
    )
    has_root: float = Field(
        description="通根标志：1.0=有根，0.0=无根"
    )
    is_climate_override: float = Field(
        description="调候急需标志：1.0=命局极寒/极燥需强制调候"
    )

    structural_overload: float = Field(
        default=0.0,
        description="结构过载权重，触发值来自 BAZI_TENSION_POLARITY"
    )
    thermal_death: float = Field(
        default=0.0,
        description="高熵热寂权重（负值），命局散漫无活力"
    )
    flesh_smash: float = Field(
        default=0.0,
        description="全息肉身崩溃权重（负值），健康信息坍缩"
    )
    antimatter_fission: float = Field(
        default=0.0,
        description="反物质裂变权重，七杀直冲日支"
    )

    info_capture: float = Field(default=0.0, description="全息信息捕获探针结果")
    massive_predation: float = Field(default=0.0, description="大质量实体掠食探针")
    macro_condensate: float = Field(default=0.0, description="宏观凝聚态探针")
    cross_domain_predation: float = Field(default=0.0, description="跨域掠食探针")
    chain_reaction: float = Field(default=0.0, description="链式反应矩阵探针")
    base_work_active: float = Field(default=0.0, description="基础工作激活探针")
    blackhole_nesting: float = Field(default=0.0, description="黑洞嵌套探针")
    dyson_sphere: float = Field(default=0.0, description="戴森球拓扑探针")
    spatial_density: float = Field(default=0.0, description="空间密度探针")
    dual_protocol: float = Field(default=0.0, description="双协议轨道探针")
    interference_damping: float = Field(default=0.0, description="干涉阻尼探针")
    conditional_harm: float = Field(default=0.0, description="条件相害突破探针")
    z_axis_suppression: float = Field(default=0.0, description="Z轴二极管压制探针")
    isotopic_strike: float = Field(default=0.0, description="同位素绝对打击探针")
    entangled_convergence: float = Field(default=0.0, description="纠缠收敛探针")
    distance_insulation: float = Field(default=0.0, description="距离绝缘探针")
    high_energy_act: float = Field(default=0.0, description="高能激活探针")
    density_compression: float = Field(default=0.0, description="密度压缩探针")
    transient_entangle: float = Field(default=0.0, description="瞬态纠缠探针")
    stable_anchor: float = Field(default=0.0, description="稳态锚点探针")
    topo_reversal_stem: float = Field(default=0.0, description="天干拓扑反转探针")
    topo_reversal_branch: float = Field(default=0.0, description="地支拓扑反转探针")
    authority_void: float = Field(default=0.0, description="权威空亡升华探针")
    clone_seizure: float = Field(default=0.0, description="克隆体夺财探针")
    virtual_calc: float = Field(default=0.0, description="虚空计算探针")
    orbital_drag: float = Field(default=0.0, description="轨道拖拽探针")
    void_arch: float = Field(default=0.0, description="虚空奇点拱照探针")
    subatomic_pen: float = Field(default=0.0, description="亚原子穿透探针")
    quark_confinement: float = Field(default=0.0, description="夸克禁闭探针")
    quark_ascension: float = Field(default=0.0, description="夸克升腾探针")
    quantum_tunneling: float = Field(default=0.0, description="量子隧穿接地探针")
    singularity_siphon: float = Field(default=0.0, description="奇点虹吸三合探针")
    father_evaporation: float = Field(default=0.0, description="父星蒸发探针")
    terminal_void: float = Field(default=0.0, description="末端空亡衰变探针")
    containment_singularity: float = Field(default=0.0, description="墓库奇点探针")
    absolute_weakness: float = Field(default=0.0, description="绝对身弱探针")

    high_entropy_clash_alert: float = Field(
        default=0.0, description="图鉴专家：高熵冲局警报（≥2冲）"
    )
    toxic_attachment_alert: float = Field(
        default=0.0, description="图鉴专家：毒性依附警报（日干参与合绊）"
    )
    wealth_breaks_resource_alert: float = Field(
        default=0.0, description="图鉴专家：财破印局警报"
    )
    tujian_tags: List[str] = Field(
        default_factory=list,
        description="图鉴分类标签列表"
    )

    kinship_pointers: BaziKinshipPointers = Field(
        default_factory=BaziKinshipPointers,
        description="亲缘指针：父/母/配偶信息宫"
    )


class BaziFullCluster(BaseModel):
    """完整命局拓扑容器 — 汇总所有 L1 子模型"""

    input_request: BaziInputRequest = Field(
        description="原始输入请求"
    )
    pillars: List[BaziPillar] = Field(
        description="四柱列表：[年柱, 月柱, 日柱, 时柱]"
    )
    nodes: List[BaziCharNode] = Field(
        description="所有节点扁平列表（8个节点：4天干+4地支）"
    )
    kongwang_branches: List[str] = Field(
        default_factory=list,
        description="空亡地支列表"
    )
    climate: BaziClimate = Field(
        description="气候状态分析"
    )
    strength_profile: BaziStrengthProfile = Field(
        description="日主强弱画像"
    )
    interaction_tags: BaziInteractionTags = Field(
        description="干支互动标签集合"
    )
    tension_dna: Optional[BaziTensionDNA] = Field(
        default=None,
        description="大一统特征向量，由 UnifiedBaziEngine 填充后注入"
    )
    is_input_valid: bool = Field(
        default=True,
        description="输入是否通过 YOLO_VETO_RULES 校验，False 时拒绝推演"
    )
    veto_reason: str = Field(
        default="",
        description="若 is_input_valid=False，记录拦截原因"
    )
