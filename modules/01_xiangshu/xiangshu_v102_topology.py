# -*- coding: utf-8 -*-
# = [端口 T: L1 拓扑实体] =
# 路径: modules/01_xiangshu/xiangshu_v102_topology.py
# @Layer: [L1] 象数派拓扑实体 (V11 Pydantic 强类型版)
# @Description:
#   以 VLM 11 维象数载荷 JSON 为唯一真理源，逐维建模。
#   所有字段均为基础标量 (str, int, float, bool) 或基础标量列表。
#   严禁使用 Enum / Literal 罗列庞大选项（防缓存击穿）。
#   所有中文语义强行映射为冰冷的英文标量字段名。

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==============================================================================
# [Dim-01] 格式塔拟态与笔画解构
# JSON key: gestalt_mimicry_and_text_decomposition
# ==============================================================================
class GestaltMimicryDim(BaseModel):
    text_structure_separation: str = Field(
        default="",
        description=(
            "画面上下镜像割裂的结构描述文本。"
            "映射为 T068（坤土撕裂）/ T101（丙火颠覆）探针激活条件。"
        ),
    )
    stroke_component_micro_gestalt: str = Field(
        default="",
        description=(
            "微观笔画/轮廓与活体脏器骨骼的格式塔映射文本。"
            "映射为 T056（坤土成象）探针激活条件；"
            "含「肋骨/心血管」时额外激活 T080（离火破相）。"
        ),
    )
    physical_enclosing_and_wrapping: str = Field(
        default="",
        description=(
            "物理包围与容纳结构描述。"
            "「双向囊袋」激活 T046（乾金画地）；"
            "「广域空间包围」激活 T057（乾金画地-头部框架）。"
        ),
    )

    # --- 派生标量（Parser 从文本中抽取，供引擎 O(1) 查询）---
    has_mirror_split: bool = Field(
        default=False,
        description="画面是否存在上下镜像割裂（中轴水平线物理切断）。",
    )
    has_organ_gestalt: bool = Field(
        default=False,
        description="微观纹理是否激活活体脏器/骨骼格式塔映射。",
    )
    enclosure_type: str = Field(
        default="none",
        description=(
            "包围类型标量。可选值（不强制枚举）："
            "none / half_wrap / full_wrap / dual_bag / wide_open"
        ),
    )


# ==============================================================================
# [Dim-02] 截断与内部映射
# JSON key: truncation_and_interior_mapping
# ==============================================================================
class TruncationDim(BaseModel):
    double_end_truncation: str = Field(
        default="",
        description=(
            "双端截断情况描述。"
            "「未截断/尖锐延伸」激活 T041（金木相战-穿刺）；"
            "「有截断」激活 T016（水金交战）。"
        ),
    )
    top_defect_and_lighting_mapping: str = Field(
        default="",
        description=(
            "顶部骨架完整性与光照映射描述。"
            "「顶部完整+强光照射」激活 T012（离火穿天）；"
            "「强烈聚光/吊灯映射」激活 T095（丙火偏枯）。"
        ),
    )

    # --- 派生标量 ---
    has_double_end_truncation: bool = Field(
        default=False,
        description="是否存在物理双端截断（端点丢失）。",
    )
    top_is_intact: bool = Field(
        default=True,
        description="顶部骨架是否完整闭合（True=完整，False=残缺）。",
    )
    top_lighting_intensity: str = Field(
        default="normal",
        description=(
            "顶部光照强度标量："
            "none / weak / normal / strong / extreme"
        ),
    )


# ==============================================================================
# [Dim-03] 表面老化与整洁度
# JSON key: surface_aging_and_neatness
# ==============================================================================
class SurfaceAgingDim(BaseModel):
    surface_peeling_scabbing: str = Field(
        default="",
        description=(
            "表面剥落/结痂/白斑病理质感描述。"
            "激活 T020（坤土生斑）、T103（庚金肃杀-枯萎）。"
        ),
    )
    structural_absolute_neatness: str = Field(
        default="",
        description=(
            "宏观骨架对称洁癖 vs 微观粗糙病灶的矛盾描述。"
            "激活 T057（乾金画地-方形框架）；微观粗糙激活 T049（辛金散见）。"
        ),
    )

    # --- 派生标量 ---
    peeling_severity: str = Field(
        default="none",
        description="剥落/结痂严重程度：none / mild / moderate / severe / necrotic",
    )
    macro_symmetry_score: float = Field(
        default=0.0,
        description="宏观结构对称性评分 [0.0, 1.0]，1.0=完美对称（病态洁癖），0.0=完全混乱。",
    )
    micro_roughness_present: bool = Field(
        default=False,
        description="微观表面是否存在可识别的粗糙刮痕或灰尘病灶。",
    )


# ==============================================================================
# [Dim-04] 阵列方向与异常增生
# JSON key: array_orientation_and_protrusion
# ==============================================================================
class ArrayOrientationDim(BaseModel):
    horizontal_vertical_crossing: str = Field(
        default="",
        description=(
            "横竖正交十字结构描述。"
            "「草甸阵列 X 山峰轴线」激活 T052（己土划界）、T068（坤土撕裂）。"
        ),
    )
    abnormal_protrusion_hyperplasia: str = Field(
        default="",
        description=(
            "两极向外突兀延伸/几何骨刺增生描述。"
            "激活 T041（金木相战-物理穿刺）、T037（震木破局）。"
        ),
    )

    # --- 派生标量 ---
    has_orthogonal_cross: bool = Field(
        default=False,
        description="是否存在明确的水平+垂直正交交叉结构（十字/T形/工字）。",
    )
    protrusion_direction: str = Field(
        default="none",
        description=(
            "增生/骨刺延伸方向标量："
            "none / up / down / both / left / right / radial"
        ),
    )
    protrusion_sharpness: str = Field(
        default="none",
        description="增生端点锐利度：none / blunt / sharp / needle / blade",
    )


# ==============================================================================
# [Dim-05] 物理倾斜与暴露截面
# JSON key: physical_tilt_and_exposed_facet
# ==============================================================================
class PhysicalTiltDim(BaseModel):
    overall_tilt_vector: str = Field(
        default="",
        description=(
            "整体倾斜矢量描述文本。"
            "「倾斜矢量为零/垂直锚定」不激活 T062；"
            "「明显倾斜」激活 T062（庚金斜裁）。"
        ),
    )
    absolute_exposed_facet: str = Field(
        default="",
        description=(
            "暴露截面类型描述。"
            "「正前方绝对暴露面」激活 T095（丙火偏枯）；"
            "「完全公开」激活 T085（离火借明）。"
        ),
    )

    # --- 派生标量 ---
    tilt_degrees: float = Field(
        default=0.0,
        description="整体倾斜角度（度），正值=右倾，负值=左倾，绝对值 >= 5.0 触发 T062。",
    )
    is_vertically_anchored: bool = Field(
        default=False,
        description="是否呈现定海神针式的死寂垂直居中锚定状态。",
    )
    facet_exposure_type: str = Field(
        default="partial",
        description="截面暴露类型：none / partial / full_frontal / all_sides",
    )


# ==============================================================================
# [Dim-06] 不对称高低差与断裂节点
# JSON key: asymmetrical_height_disparity
# ==============================================================================
class AsymmetricHeightDim(BaseModel):
    left_right_height_disparity: str = Field(
        default="",
        description=(
            "左右山脊线（震木/兑金方向）高低差描述。"
            "「完美对称」不激活 T059；「明显高低落差」激活 T059（震木跛行）。"
        ),
    )
    fracture_node_absolute_count: str = Field(
        default="",
        description=(
            "垂直扫描断裂节点描述。"
            "「物质在中央坐标点断裂消亡」激活 T092（辛金错断）、T016（水金交战）。"
        ),
    )

    # --- 派生标量 ---
    left_right_height_delta: float = Field(
        default=0.0,
        description="左右高度差的归一化绝对值 [0.0, 1.0]，0.0=完全对称，1.0=极端不对称。",
    )
    has_central_fracture: bool = Field(
        default=False,
        description="是否存在物质在中央水平轴处突然断裂/消亡的物理节点。",
    )
    fracture_node_count: int = Field(
        default=0,
        description="垂直方向上可识别的断裂节点绝对数量。",
    )


# ==============================================================================
# [Dim-07] 流体密度匹配与跨宫迁移
# JSON key: fluid_density_matching_and_migration
# ==============================================================================
class FluidDensityDim(BaseModel):
    medium_density_match: str = Field(
        default="",
        description=(
            "高密度固态物质与零密度光学虚影的密度配对描述。"
            "激活 T054（水土交战-介质反差）、T013（坎水死寂）。"
        ),
    )
    medium_cross_palace_trajectory: str = Field(
        default="",
        description=(
            "介质跨宫迁移路径描述。"
            "「实体被中央防线阻断，仅光子跨界」激活 T076（木土交杂）、T027（乾金壁立）。"
        ),
    )

    # --- 派生标量 ---
    solid_density_level: str = Field(
        default="medium",
        description="固态介质密度级别：zero / low / medium / high / extreme",
    )
    mirror_density_level: str = Field(
        default="zero",
        description="镜像/光学虚影密度级别：zero / low / medium / high / extreme",
    )
    cross_palace_blocked: bool = Field(
        default=False,
        description="实体介质是否被中央水平轴防线阻断，无法完成物理跨宫迁移。",
    )
    photon_projection_active: bool = Field(
        default=False,
        description="光子辐射是否实现了从离宫向坎宫的跨界投射（形成镜像倒影）。",
    )


# ==============================================================================
# [Dim-08] 颗粒物理与边缘锐利度
# JSON key: granular_physics_and_edge_sharpness
# ==============================================================================
class GranularPhysicsDim(BaseModel):
    granular_medium_hardness: str = Field(
        default="",
        description=(
            "颗粒介质硬度描述（冷岩/冰砂/植物纤维）。"
            "「极硬冷岩」激活 T046（乾金画地）；"
            "「软植物纤维」激活 T019（坎水浮萍）。"
        ),
    )
    solid_edge_sharpness: str = Field(
        default="",
        description=(
            "主体轮廓与背景交界线的锐利度描述。"
            "「手术刀级别绝对锐利」激活 T015（乾金切喉）、T041（金木相战）。"
        ),
    )

    # --- 派生标量 ---
    primary_medium_hardness: str = Field(
        default="medium",
        description="主要介质硬度标量：ultra_soft / soft / medium / hard / ultra_hard / crystalline",
    )
    secondary_medium_hardness: str = Field(
        default="soft",
        description="次要介质（如隔离带）硬度标量，同上枚举。",
    )
    edge_sharpness_level: str = Field(
        default="normal",
        description="轮廓边缘锐利度：blurry / soft / normal / sharp / surgical",
    )


# ==============================================================================
# [Dim-09] 角落挤压与流体湍流
# JSON key: corner_jamming_and_turbulence
# ==============================================================================
class CornerJammingDim(BaseModel):
    corner_jamming_halflife: str = Field(
        default="",
        description=(
            "角落挤压半衰期描述。"
            "「彻底剥离角落」激活 T057（乾金画地-中宫霸占）；"
            "「严重角落挤压」激活 T043（坤土失陷）。"
        ),
    )
    fluid_turbulence_degree: str = Field(
        default="",
        description=(
            "下半部坎宫流体湍流程度描述。"
            "「平滑如镜/动势归零」激活 T013（坎水死寂）；"
            "「剧烈湍流」激活 T075（震雷激变）、T029（水火未济）。"
        ),
    )

    # --- 派生标量 ---
    corner_pressure_type: str = Field(
        default="none",
        description="角落挤压类型：none / mild / severe / full_escape（完全脱离角落压迫）",
    )
    fluid_turbulence_score: float = Field(
        default=0.0,
        description="坎宫流体湍流分数 [0.0, 1.0]，0.0=完全静止如镜，1.0=极度湍流沸腾。",
    )
    is_fluid_frozen: bool = Field(
        default=False,
        description="坎宫流体是否处于被冰封/窒息的绝对静止状态。",
    )


# ==============================================================================
# [Dim-10] 流体浸染与三维堆叠
# JSON key: fluid_soaking_and_3d_stacking
# ==============================================================================
class FluidSoaking3DDim(BaseModel):
    fluid_organ_absolute_soaking: str = Field(
        default="",
        description=(
            "倒影被水体吞噬浸染描述。"
            "「彻底浸染/水下幻影」激活 T007（坎水极旺）、T060（坎水漏厄）。"
        ),
    )
    implicit_3d_stacking: str = Field(
        default="",
        description=(
            "物理地表高维与水面折射低维世界的垂直堆叠描述。"
            "「空间对折」激活 T101（丙火颠覆）、T054（水土交战）。"
        ),
    )

    # --- 派生标量 ---
    soaking_coverage_ratio: float = Field(
        default=0.0,
        description="倒影被流体浸染覆盖的比例 [0.0, 1.0]，1.0=完全淹没。",
    )
    dimension_fold_present: bool = Field(
        default=False,
        description="是否存在上层3D物理空间与下层折射虚空间的垂直对折堆叠结构。",
    )
    inversion_axis: str = Field(
        default="none",
        description="空间对折轴方向：none / horizontal / vertical / diagonal",
    )


# ==============================================================================
# [Dim-11] 色形味映射与微观致命穿刺
# JSON key: color_shape_taste_and_piercing
# ==============================================================================
class ColorShapePiercingDim(BaseModel):
    material_shape_taste_mapping: str = Field(
        default="",
        description=(
            "物质色形味多感官映射描述（金/火/水三元素碰撞）。"
            "激活 T021（离火共振）、T029（水火未济）、T015（乾金切喉）。"
        ),
    )
    micro_fatal_piercing: str = Field(
        default="",
        description=(
            "双向锐角三角形致命穿刺描述。"
            "「向上刺穿天空」激活 T041（金木相战）；"
            "「向下刺入湖底」激活 T060（坎水漏厄）。"
        ),
    )

    # --- 派生标量 ---
    dominant_wuxing_elements: List[str] = Field(
        default_factory=list,
        description=(
            "画面中主导五行元素列表，值域：METAL / FIRE / WATER / WOOD / EARTH。"
            "多元素并存时按视觉强度降序排列。"
        ),
    )
    upward_piercing: bool = Field(
        default=False,
        description="是否存在向上刺穿天穹/上层宫位的锐角穿刺形态。",
    )
    downward_piercing: bool = Field(
        default=False,
        description="是否存在向下刺入深渊/下层宫位的锐角穿刺形态。",
    )
    wuxing_collision_count: int = Field(
        default=0,
        description="画面中相互碰撞/对抗的五行元素对数量（每对+1）。",
    )


# ==============================================================================
# [L1] 引擎拓扑节点实体（engine_topology.nodes[]）
# ==============================================================================
class XiangShuNode(BaseModel):
    node_id: str = Field(
        alias="id",
        description="节点唯一 ID，如 obj_mountain_real",
    )
    entity_type: str = Field(
        default="unknown",
        description="实体类型字符串，如「自然/能量」、「活体/生命」、「虚体/线条」",
    )
    concept: str = Field(
        default="",
        description="节点语义概念描述，如「高耸火山实体」",
    )
    palace: str = Field(
        default="CENTER",
        description=(
            "所在宫位字符串（文王八卦宫位名）："
            "LI / KAN / ZHEN / DUI / GEN / XUN / QIAN / KUN / CENTER"
        ),
    )
    properties: List[str] = Field(
        default_factory=list,
        description="VLM 提取的属性标签列表，供倒排索引碰撞",
    )

    # 派生/计算字段
    palace_index: int = Field(
        default=5,
        description="洛书九宫格 index [1-9]，由 palace 字符串映射，5=中宫",
    )
    is_background: bool = Field(
        default=False,
        description="是否为背景白名单节点（跳过推演）",
    )
    is_primary_subject: bool = Field(
        default=False,
        description="是否为寻主算法确定的画面主体",
    )

    model_config = {"populate_by_name": True}


# ==============================================================================
# [L1] 图谱边实体（engine_topology.edges[]）
# ==============================================================================
class XiangShuEdge(BaseModel):
    source_id: str = Field(description="源节点 ID")
    target_id: str = Field(description="目标节点 ID")
    relation_type: str = Field(
        default="NONE",
        description=(
            "边关系类型字符串（不强制枚举）："
            "DIVIDES / CROSSES / MISSING / OPPRESSES / BLOCKS / "
            "POINTS_TO / SUPPORTS / PULLS / NONE"
        ),
    )
    context: str = Field(
        default="",
        description="边的自然语言上下文描述，如「草甸防线截断火山向上延伸」",
    )
    relation_score: float = Field(
        default=0.0,
        description="关系量化分数 [-1.0, 1.0]，由 relation_to_score() 映射后填入",
    )


# ==============================================================================
# [L1] V11 完整 11 维象数载荷图谱（VLM Payload 根对象）
# ==============================================================================
class XiangShuGraph(BaseModel):
    image_id: str = Field(default="unknown", description="图片唯一 ID")

    # --- 11 维分析维度 ---
    gestalt_mimicry: GestaltMimicryDim = Field(
        default_factory=GestaltMimicryDim,
        description="[Dim-01] 格式塔拟态与笔画解构",
    )
    truncation: TruncationDim = Field(
        default_factory=TruncationDim,
        description="[Dim-02] 截断与内部映射",
    )
    surface_aging: SurfaceAgingDim = Field(
        default_factory=SurfaceAgingDim,
        description="[Dim-03] 表面老化与整洁度",
    )
    array_orientation: ArrayOrientationDim = Field(
        default_factory=ArrayOrientationDim,
        description="[Dim-04] 阵列方向与异常增生",
    )
    physical_tilt: PhysicalTiltDim = Field(
        default_factory=PhysicalTiltDim,
        description="[Dim-05] 物理倾斜与暴露截面",
    )
    asymmetric_height: AsymmetricHeightDim = Field(
        default_factory=AsymmetricHeightDim,
        description="[Dim-06] 不对称高低差与断裂节点",
    )
    fluid_density: FluidDensityDim = Field(
        default_factory=FluidDensityDim,
        description="[Dim-07] 流体密度匹配与跨宫迁移",
    )
    granular_physics: GranularPhysicsDim = Field(
        default_factory=GranularPhysicsDim,
        description="[Dim-08] 颗粒物理与边缘锐利度",
    )
    corner_jamming: CornerJammingDim = Field(
        default_factory=CornerJammingDim,
        description="[Dim-09] 角落挤压与流体湍流",
    )
    fluid_soaking_3d: FluidSoaking3DDim = Field(
        default_factory=FluidSoaking3DDim,
        description="[Dim-10] 流体浸染与三维堆叠",
    )
    color_shape_piercing: ColorShapePiercingDim = Field(
        default_factory=ColorShapePiercingDim,
        description="[Dim-11] 色形味映射与微观致命穿刺",
    )

    # --- 引擎拓扑节点与边 ---
    nodes: Dict[str, XiangShuNode] = Field(
        default_factory=dict,
        description="节点字典，key 为 node_id（来自 engine_topology.nodes[]）",
    )
    edges: List[XiangShuEdge] = Field(
        default_factory=list,
        description="边列表（来自 engine_topology.edges[]）",
    )

    # --- 元数据 ---
    primary_subject_id: str = Field(
        default="",
        description="寻主算法确定的主体节点 ID",
    )
    avatar_category: str = Field(
        default="misc_landscape",
        description=(
            "头像分类字符串："
            "real_photo / anime_manga / misc_landscape / isolated_object / group_photo"
        ),
    )
    is_inverted: bool = Field(
        default=False,
        description="画面是否存在物理倒置元素（T101 直接触发条件）",
    )
    crop_slant_degrees: float = Field(
        default=0.0,
        description="裁切倾斜角度，绝对值 >= 5.0 触发 T062",
    )


# ==============================================================================
# [L1] 单条推演结论实体（L1.5 引擎输出的原子断语）
# ==============================================================================
class XiangShuFinding(BaseModel):
    rule_id: str = Field(description="命中的规则 ID，如 T015")
    category: str = Field(description="五大宏观领域之一")
    wuxing: str = Field(description="五行归属字符串，如 METAL")
    tensor_weight: float = Field(description="本条断语的张量权重（float）")
    reasoning: str = Field(description="物理逻辑推演文本")
    summary: str = Field(description="一针见血的断语结论文本")
    triggered_node_ids: List[str] = Field(
        default_factory=list,
        description="触发本条规则的节点 ID 列表",
    )
    triggered_dim: str = Field(
        default="",
        description="触发本条规则的 11 维维度字段名，如 granular_physics.edge_sharpness_level",
    )


# ==============================================================================
# [L1] 象数分析最终报告实体
# ==============================================================================
class XiangShuReport(BaseModel):
    image_id: str = Field(description="原始图片 ID")
    findings: List[XiangShuFinding] = Field(
        default_factory=list,
        description="所有命中规则的推演结论列表，已按 tensor_weight 降序排列",
    )

    # 五大宏观领域分类命中数
    personality_hit_count: int = Field(default=0, description="性格与潜意识领域命中条数")
    career_hit_count: int = Field(default=0, description="事业与财富领域命中条数")
    relation_hit_count: int = Field(default=0, description="人际与情感领域命中条数")
    health_hit_count: int = Field(default=0, description="健康与疾厄领域命中条数")
    ancestry_hit_count: int = Field(default=0, description="祖荫与本命领域命中条数")

    # 张量物理汇总
    total_weight: float = Field(default=0.0, description="所有命中规则的权重总和")
    tension: float = Field(default=0.0, description="张力（越高越凶险），上限 25.0")
    mass: float = Field(default=0.0, description="质量场（越负越虚耗），下限 -15.0")
    entropy: float = Field(default=0.0, description="图谱复杂度熵值 [0, 1]")

    # YOLO 拦截标志
    is_vetoed: bool = Field(default=False, description="是否被 YOLO 拦截规则阻断")
    veto_reason: str = Field(default="", description="拦截原因说明")

    # 原始图谱快照（供 L2 汇聚层引用）
    graph_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        description="原始 XiangShuGraph 的序列化快照（.model_dump()）",
    )
