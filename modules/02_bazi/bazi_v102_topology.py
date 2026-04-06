# = [端口 T: L1 拓扑实体] =
# 路径: modules/02_bazi/bazi_v102_topology.py
# 纯净 Pydantic 模型层——禁止包含推演逻辑、禁止使用 Enum/Literal 庞大枚举

from typing import List, Optional
from pydantic import BaseModel, Field


class BaziNodeTopology(BaseModel):
    """单干支节点的物理拓扑描述"""

    char: str = Field(description="天干或地支汉字，如 '甲'、'子'")
    pos: str = Field(description="柱位名称，如 '年干'、'月支'、'日干'、'时支'")
    elem: str = Field(description="五行属性标量：木/火/土/金/水")
    polar: str = Field(description="阴阳极性标量：阳/阴")
    is_stem: bool = Field(description="True=天干节点，False=地支节点")
    is_month_branch: bool = Field(description="True=月令节点（权重最重）")
    mass: float = Field(description="仓位权重质量，月支=9.0，其他按位权缩放")
    ten_god: str = Field(default="", description="与日主的十神关系，如 '正官'、'偏财'")
    has_root: bool = Field(default=False, description="天干是否在地支中有通根")
    is_void: bool = Field(default=False, description="该节点是否落入日柱空亡")


class BaziPillarTopology(BaseModel):
    """单柱（年/月/日/时）拓扑结构"""

    name: str = Field(description="柱名：年/月/日/时")
    stem_char: str = Field(default="", description="天干汉字")
    branch_char: str = Field(default="", description="地支汉字")
    stem_elem: str = Field(default="", description="天干五行")
    branch_elem: str = Field(default="", description="地支五行")
    stem_ten_god: str = Field(default="", description="天干十神")
    branch_ten_god: str = Field(default="", description="地支十神")


class BaziInteractionTopology(BaseModel):
    """干支互动关系拓扑（冲/合/刑/害/墓）"""

    interaction_type: str = Field(
        description="互动类型标量：地支相冲/地支六合/地支三合/地支刑/地支害/天干相合/天干相冲/入墓"
    )
    char_a: str = Field(description="参与互动的第一个字符")
    char_b: str = Field(description="参与互动的第二个字符")
    pos_a: str = Field(description="char_a 的柱位")
    pos_b: str = Field(description="char_b 的柱位")
    is_active: bool = Field(
        default=True,
        description="互动是否有效激活（被合化或被冲破时为 False）",
    )


class BaziClimateTopology(BaseModel):
    """调候状态拓扑"""

    is_frozen_state: bool = Field(
        default=False, description="True=冻结态（生于亥/子/丑/寅月）"
    )
    is_scorched_state: bool = Field(
        default=False, description="True=焦躁态（生于巳/午/未月）"
    )
    climate_override_elem: str = Field(
        default="",
        description="调候急需五行标量，冻结态='火'，焦躁态='水'，正常态=''",
    )
    month_branch: str = Field(default="", description="月令地支字符")


class BaziKinshipTopology(BaseModel):
    """六亲星宫定位拓扑"""

    father_chars: List[str] = Field(
        default_factory=list,
        description="代表父星的干支字符列表（正财/偏财/正官/七杀）",
    )
    mother_chars: List[str] = Field(
        default_factory=list,
        description="代表母星的干支字符列表（正印/偏印等）",
    )
    spouse_chars: List[str] = Field(
        default_factory=list,
        description="代表配偶星的干支字符列表（含十神标注）",
    )


class BaziStrengthTopology(BaseModel):
    """日主强弱与格局拓扑"""

    day_master_char: str = Field(description="日主天干字符")
    day_master_elem: str = Field(description="日主五行")
    day_master_polar: str = Field(description="日主阴阳")
    strength_score: float = Field(
        description="日主强度归一化分值 [0.0, 1.0]，越高越旺"
    )
    has_root: bool = Field(description="日主是否在四柱地支中有通根")
    is_weak: bool = Field(description="True=日主偏弱，False=日主偏旺")
    is_liquid_state: bool = Field(
        description="True=泄气过重（资源不足但输出旺盛），类液态失衡"
    )
    kernel_elem: str = Field(
        default="", description="命局核心用神五行标量（调候+抑扶综合判断）"
    )
    pattern_label: str = Field(
        default="普通格",
        description="命局格局标签，如 '正官格'、'食神格'、'从财格' 等",
    )


class BaziVoidTopology(BaseModel):
    """空亡（旬空）拓扑"""

    void_branch_1: str = Field(default="", description="日柱旬空地支一")
    void_branch_2: str = Field(default="", description="日柱旬空地支二")
    void_activated_chars: List[str] = Field(
        default_factory=list,
        description="命局中落空亡且带关键十神（官/杀）的地支字符列表",
    )


class BaziTujianTopology(BaseModel):
    """图鉴专家系统拓扑（Amulet V2.0）"""

    tujian_tags: List[str] = Field(
        default_factory=list,
        description="图鉴分类标签列表，如 '图鉴_CLASS_高熵冲突系统'",
    )
    tujian_strategies: List[str] = Field(
        default_factory=list,
        description="图鉴建议策略列表，如 '动中求财'",
    )
    high_entropy_clash_alert: bool = Field(
        default=False, description="True=高熵相冲预警激活"
    )
    toxic_attachment_alert: bool = Field(
        default=False, description="True=日干贪合忌神预警激活"
    )
    wealth_breaks_resource_alert: bool = Field(
        default=False, description="True=财星破印格局激活"
    )


class BaziUnifiedTopology(BaseModel):
    """
    八字大一统物理拓扑（V102 完整体）.
    由 L1 Parser 填充，交付 L1.5 Engine 推演。
    严禁在此类中包含任何推演逻辑或 if/else 断语。
    """

    raw_input_tags: List[str] = Field(
        description="原始输入标签列表，格式: ['年干_甲', '月支_子', ...]"
    )
    nodes: List[BaziNodeTopology] = Field(
        default_factory=list, description="全部干支节点列表（共8个）"
    )
    pillars: List[BaziPillarTopology] = Field(
        default_factory=list, description="四柱结构列表（年/月/日/时）"
    )
    interactions: List[BaziInteractionTopology] = Field(
        default_factory=list, description="所有干支互动关系列表"
    )
    climate: BaziClimateTopology = Field(
        default_factory=BaziClimateTopology, description="调候状态"
    )
    kinship: BaziKinshipTopology = Field(
        default_factory=BaziKinshipTopology, description="六亲星宫"
    )
    strength: Optional[BaziStrengthTopology] = Field(
        default=None, description="日主强弱格局（由 Engine 填充）"
    )
    void_info: BaziVoidTopology = Field(
        default_factory=BaziVoidTopology, description="空亡信息"
    )
    tujian: BaziTujianTopology = Field(
        default_factory=BaziTujianTopology, description="图鉴专家系统输出"
    )
    element_mass_vector: dict = Field(
        default_factory=dict,
        description="五行质量张量，键=五行字符串，值=float 质量分",
    )
    is_input_valid: bool = Field(
        default=True, description="YOLO 拦截结果：False=输入被否决"
    )
    veto_reason: str = Field(
        default="", description="YOLO 否决原因，is_input_valid=False 时有效"
    )
