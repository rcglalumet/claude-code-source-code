# -*- coding: utf-8 -*-
# = [端口 R: L5 静态规则字典] =
# 路径: expert_rules/xiangshu_rules.py
# @Layer: [L5] 星系常数层：象数派规则与万物类象字典 (V10 重塑版)
# @Description: 纯静态数据。无函数定义，无 I/O，无网络调用。
#               所有 base_weight 严格为 float 类型，供夜间 MCTS 蒸馏使用。

from typing import Any, Dict, List

# ==============================================================================
# [L0.5] 五大宏观领域常数锁死
# ==============================================================================
CAT_PERSONALITY: str = "性格与潜意识"
CAT_CAREER: str = "事业与财富"
CAT_RELATION: str = "人际与情感"
CAT_HEALTH: str = "健康与疾厄"
CAT_ANCESTRY: str = "祖荫与本命"

# ==============================================================================
# [L0.5] 视觉白名单（用于过滤背景干扰节点）
# ==============================================================================
XIANGSHU_WHITELIST_KEYWORDS: List[str] = [
    "云", "天空", "电线", "栏杆", "背景", "雪地", "水面", "海面",
    "游轮", "鸟", "山脉", "景色", "空中", "飞鸟", "海鸥", "树枝",
    "远处", "地平线", "倒影", "阳光", "草地",
]

OMINOUS_RELATIONS: List[str] = ["DIVIDES", "CROSSES", "MISSING", "OPPRESSES", "BLOCKS"]
AUSPICIOUS_RELATIONS: List[str] = ["POINTS_TO", "SUPPORTS"]
NEUTRAL_RELATIONS: List[str] = ["PULLS", "NONE"]

# ==============================================================================
# [AST 手术靶点] 供 mcts_constant_distiller.py 夜间无损覆写的权重矩阵
# ==============================================================================
XIANGSHU_WEIGHTS: Dict[str, Dict[str, float]] = {
    "Absolute_Stasis":   {"base_weight": 5.0},
    "Color_Clash":       {"base_weight": 2.5},
    "Golden_Ratio":      {"base_weight": 1.2},
    "Perfect_Symmetry":  {"base_weight": 1.0},
    "Pressure_Top":      {"base_weight": 3.8},
    "Sharp_Angle_Sha":   {"base_weight": 7.67},
    "Visual_Imbalance":  {"base_weight": 4.2},
}

# ==============================================================================
# [L0] 物理常数交互规则（供 L0 张量引擎物理叠加）
# ==============================================================================
INTERACTION_RULES: Dict[str, Dict[str, Any]] = {
    "Absolute_Stasis":    {"type": "ISOLATION_STASIS",  "mass_impact": 2.0,  "tension_increment": -0.8, "wuxing": "EARTH"},
    "Color_Clash":        {"type": "CONFLICT",          "mass_impact": -0.5, "tension_increment": 2.0,  "wuxing": "FIRE"},
    "Golden_Ratio":       {"type": "RESONANCE",         "mass_impact": 1.2,  "tension_increment": -1.5, "wuxing": "METAL"},
    "Perfect_Symmetry":   {"type": "HARMONY",           "mass_impact": 1.0,  "tension_increment": -1.0, "wuxing": "EARTH"},
    "Pressure_Top":       {"type": "HEAVY_PRESSURE",    "mass_impact": 1.5,  "tension_increment": 2.5,  "wuxing": "WOOD"},
    "Sharp_Angle_Sha":    {"type": "PHYSICAL_ATTACK",   "mass_impact": -1.5, "tension_increment": 3.0,  "wuxing": "METAL"},
    "Visual_Imbalance":   {"type": "NEGATIVE_ENTROPY",  "mass_impact": -0.8, "tension_increment": 1.5,  "wuxing": "WATER"},
    "ZERO_STATE_NORMAL":  {"type": "ZERO_STATE",        "mass_impact": 0.0,  "tension_increment": 0.0,  "wuxing": "EARTH"},
}

GLOBAL_BOUNDARY: Dict[str, float] = {
    "max_tension":       25.0,
    "min_mass":         -15.0,
    "entropy_tolerance":  0.85,
}

# ==============================================================================
# [L5 核心基因座] 纯静态物理张量与属性字典
# 五大宏观领域绝对坍缩，base_weight 全部为 float 类型
# NOTE: 所有 reasoning / summary 字段均使用单引号字符串，
#       避免中文引号（「」）与 Python 双引号字符串边界冲突。
# ==============================================================================
XIANGSHU_GENOMES: Dict[str, Dict[str, Any]] = {
    "T009_TEMPLATE": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": -2.0,
        "keywords": [],
        "reasoning": "【模板推理】",
        "summary": "【模板结论】",
    },
    "T006": {
        "category": CAT_HEALTH, "wuxing": "FIRE", "base_weight": 8.0,
        "keywords": ["晚霞落日"],
        "reasoning": "【离火受损】晚霞色彩暗淡，火气衰微，呈现光明倒退之象。",
        "summary": "近期心血不足，容易熬夜疲劳。",
    },
    "T007": {
        "category": CAT_HEALTH, "wuxing": "WATER", "base_weight": 15.0,
        "keywords": ["大面积深水汪洋"],
        "reasoning": "【坎水极旺】汪洋深水掩盖一切，水多火熄，阴寒之气过盛。",
        "summary": "水多火熄，极寒之象，严重影响心脑血管。",
    },
    "T008": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 5.0,
        "keywords": ["断桥截断"],
        "reasoning": "【震木断裂】提取特征为断桥截断，气场中断之象。",
        "summary": "合作关系面临骤断风险，近期签约极易中途夭折。",
    },
    "T010": {
        "category": CAT_PERSONALITY, "wuxing": "WOOD", "base_weight": 12.0,
        "keywords": ["looking_backward", "gaze_backward"],
        "reasoning": "【风木相背】提取特征为「身体向前跃出，视线向后背离」。此为行为与意识相悖。",
        "summary": "正在推进某事，但内心充满纠结留恋，严重内耗。",
    },
    "T011": {
        "category": CAT_ANCESTRY, "wuxing": "EARTH", "base_weight": 6.5,
        "keywords": ["tactile_grasping", "underbelly_or_feet_contact"],
        "reasoning": "【坤土寄生】提取特征为「极力抓握」或「底盘紧贴」。呈现强烈的物理锚定。",
        "summary": "极度依赖某平台或人际关系，缺乏独立安全感。",
    },
    "T012": {
        "category": CAT_CAREER, "wuxing": "FIRE", "base_weight": 14.0,
        "keywords": ["elevation_breakthrough", "higher_than_top"],
        "reasoning": "【离火穿天】提取特征为「高程突破」。头部出头主思想跃迁，身体滞留主现实阻力。",
        "summary": "野心极大思想超前，但受限于客观财力，处于半出圈挣扎期。",
    },
    "T013": {
        "category": CAT_CAREER, "wuxing": "WATER", "base_weight": 18.0,
        "keywords": ["zero_splashing", "submerged_fluid_stasis"],
        "reasoning": "【坎水死寂】提取特征为「浸水无波纹」。水主流动，无波纹主极阴极寒。",
        "summary": "环境极度停滞死气沉沉，资金流动受阻。",
    },
    "T014": {
        "category": CAT_RELATION, "wuxing": "METAL", "base_weight": 16.0,
        "keywords": ["paired_appendages_splitting", "limb_concealment_and_asymmetry"],
        "reasoning": "【兑金伤拆】成对之物被拆或严重不对称，主情破与撕裂。",
        "summary": "合作关系存在严重信息差，极易分道扬镳被架空。",
    },
    "T015": {
        "category": CAT_HEALTH, "wuxing": "METAL", "base_weight": 20.0,
        "keywords": ["lines_crossing_body", "piercing"],
        "reasoning": "【乾金切喉】背景切线横穿头颈。绝对物理割裂与煞气。",
        "summary": "突发外部灾厄，严防咽喉隐疾或遭遇降维打击切割。",
    },
    "T016": {
        "category": CAT_CAREER, "wuxing": "WATER", "base_weight": 17.0,
        "keywords": ["invisible", "incomplete"],
        "reasoning": "【水金交战】提取特征为「宫位隐匿或物理截断」。主能量流失与暗伤相。",
        "summary": "当前存在难言之隐或被迫中断的事务，核心能力受限。",
    },
    "T017": {
        "category": CAT_PERSONALITY, "wuxing": "WOOD", "base_weight": 11.5,
        "keywords": ["bent", "back_turned_to"],
        "reasoning": "【震木受压】提取特征为「脊柱弯曲且背对特定网格」。主心理逃避或防卫态。",
        "summary": "背负现实重压，潜意识回避某段关系或责任，处于收缩防守。",
    },
    "T018": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 8.5,
        "keywords": ["mobility_tool", "trajectory"],
        "reasoning": "【巽木跨宫】提取特征为「长道具跨越多宫位或使用代步」。主奔波变动与借力。",
        "summary": "正处于强烈变动期，若要达成跨越式目标必须巧妙借助外力。",
    },
    "T019": {
        "category": CAT_CAREER, "wuxing": "WATER", "base_weight": 13.5,
        "keywords": ["floating", "coverage"],
        "reasoning": "【坎水浮萍】提取特征为「处于漂浮介质或被覆压」。主根基漂浮。",
        "summary": "大环境存在极大的不确定性，自身基础不牢极易随波逐流。",
    },
    "T020": {
        "category": CAT_HEALTH, "wuxing": "EARTH", "base_weight": 10.0,
        "keywords": ["blemishes", "subdivisions"],
        "reasoning": "【坤土生斑】提取特征为「密集斑点或网格割裂」。主表皮瑕疵与建制溃散。",
        "summary": "内部团队或自身健康（肠胃/皮肤）出现隐患，需防小人。",
    },
    "T021": {
        "category": CAT_PERSONALITY, "wuxing": "FIRE", "base_weight": 12.5,
        "keywords": ["color_resonance", "strange_objects"],
        "reasoning": "【离火共振】提取特征为「色彩一致或微小异物」。主同化与外力介入。",
        "summary": "思想观念极易受大环境同化，警惕不明外力干扰主线。",
    },
    "T022": {
        "category": CAT_ANCESTRY, "wuxing": "EARTH", "base_weight": 7.5,
        "keywords": ["apparent_gender", "female", "male"],
        "reasoning": "【阴阳剥复】提取特征为明确的表象性别。男主阳动，女主阴静。",
        "summary": "自身能量场当前表现出明确的进攻扩张或收敛承载特质。",
    },
    "T023": {
        "category": CAT_PERSONALITY, "wuxing": "FIRE", "base_weight": 10.5,
        "keywords": ["gaze_target_grid", "looking_at_"],
        "reasoning": "【巽风聚念】视线具有极其明确的绝对靶向网格。能量全盘灌注于特定方位。",
        "summary": "当前的所有注意力、焦虑或渴望，极度聚焦在某特定人或事上。",
    },
    "T024": {
        "category": CAT_CAREER, "wuxing": "WATER", "base_weight": 15.5,
        "keywords": ["dim_and_dark", "front_bright_back_dark", "dim_or_dark_grids"],
        "reasoning": "【明暗交剥】光照呈现前明后暗或局部暗态。表象光鲜而背后缺乏支撑。",
        "summary": "展现给外界的前景看似明朗，但背后的积蓄或隐患正处于盲区，防后院起火。",
    },
    "T025": {
        "category": CAT_RELATION, "wuxing": "WATER", "base_weight": 14.5,
        "keywords": ["none_back_of_head", "back_of_head"],
        "reasoning": "【玄水遁藏】五官不可见之后脑勺背影。面为阳背为阴，以背示人主彻底抗拒遁藏。",
        "summary": "近期心理防御机制极高，可能切断了某项社交或以拒绝沟通逃避核心矛盾。",
    },
    "T026": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 11.0,
        "keywords": ["interacting_with", "heading_towards_grid", "summoning"],
        "reasoning": "【震风引信】手部动态召唤或动物具备明确轨迹。外物定向移动主风象变动与触达。",
        "summary": "有极明确的消息、工作机遇或人脉正向你靠拢，切忌过度被动。",
    },
    "T027": {
        "category": CAT_CAREER, "wuxing": "METAL", "base_weight": 13.0,
        "keywords": ["isolated_parts", "body_medium_isolation"],
        "reasoning": "【乾金壁立】身体核心被工具隔离未接触介质。界限森严，涉水不湿鞋防卫心重。",
        "summary": "对待某事务保留极大退路与心理边界，未交出底牌处于试探期。",
    },
    "T028": {
        "category": CAT_CAREER, "wuxing": "EARTH", "base_weight": 9.5,
        "keywords": ["tool_details", "material", "extends_to_grid"],
        "reasoning": "【艮土架桥】借助特定材质的道具延跨越。主体能量不足时假借外物跨越鸿沟。",
        "summary": "破局的唯一关键在于借力，必须利用现成平台杠杆或规则跨越阶层。",
    },
    "T029": {
        "category": CAT_RELATION, "wuxing": "WATER", "base_weight": 16.5,
        "keywords": ["localized_water_states", "splashing_or_wavy"],
        "reasoning": "【水火未济】同处水环境中但局部翻腾局部死寂。环境水文呈现极端两极割裂。",
        "summary": "身处的大环境存在极其严重的冷热不均，一部分极度内卷，另一部分彻底躺平。",
    },
    "T030": {
        "category": CAT_PERSONALITY, "wuxing": "FIRE", "base_weight": 8.8,
        "keywords": ["anime_manga", "art_style"],
        "reasoning": "【离火虚炎】提取特征为「动漫等非现实画风」。图像脱离实体，主精神性过强落地弱。",
        "summary": "近期沉浸于个人的精神世界或幻想中，对现实执行力偏弱，逃避枯燥压力。",
    },
    "T031": {
        "category": CAT_CAREER, "wuxing": "EARTH", "base_weight": 17.5,
        "keywords": ["moving_away_from", "limbs_anchored_in"],
        "reasoning": "【木土交战】身体脱离某网格但四肢滞留锚定。欲走被绊，呈现极强空间撕裂相。",
        "summary": "主观极渴望离开目前的关系或工作，但存在深厚现实利益牵绊，呈剧烈撕裂状。",
    },
    "T032": {
        "category": CAT_PERSONALITY, "wuxing": "METAL", "base_weight": 12.8,
        "keywords": ["side_eye_squint", "deliberately_avoiding", "gaze_avoiding_grids"],
        "reasoning": "【兑水防隅】斜视偷瞄且刻意避让特定网格。视线不正则心存防备规避雷区。",
        "summary": "当前缺乏直面现实核心矛盾的勇气，对特定方向或人存在极强防备与猜忌。",
    },
    "T033": {
        "category": CAT_RELATION, "wuxing": "WATER", "base_weight": 15.8,
        "keywords": ["following_behind", "feature_differences"],
        "reasoning": "【坎水伏阴】次要人物跟在背后且特征差异大。背后属阴，异类尾随主暗中施压。",
        "summary": "近期极易犯小人，背后存在不同频的人暗中施压盯梢。或过往阴影缠身。",
    },
    "T034": {
        "category": CAT_HEALTH, "wuxing": "METAL", "base_weight": 18.5,
        "keywords": ["specific_strange_objects", "natural_attribute"],
        "reasoning": "【兑艮犯煞】兑宫或艮宫突入特异活物。感官网格遭异物入侵，若性寒则主寒疾。",
        "summary": "突发状况！极度警惕莫名其妙的口舌是非。身体严防呼吸道、脾胃寒湿急症。",
    },
    "T035": {
        "category": CAT_PERSONALITY, "wuxing": "WATER", "base_weight": 15.0,
        "keywords": ["blurry_shadowy_figure", "blurry"],
        "reasoning": "【玄水无明】提取特征为「画风呈现阴影化或模糊不清」。水主智也主暗，阴影化主自我隐匿或前途不明。",
        "summary": "自身能量极度内耗或被压制，处于被动蛰伏状态，对前路感到彻底的茫然与不确定。",
    },
    "T036": {
        "category": CAT_ANCESTRY, "wuxing": "WATER", "base_weight": 13.5,
        "keywords": ["elements_behind_back"],
        "reasoning": "【玄武受困】提取特征为「正后背被特定元素占据」。后背玄武位主靠山与过往基石，水/渊主寒主陷。",
        "summary": "你的过去或大后方正承受着某种特定的压力或依赖（如债务/情感纠葛），严重缺乏稳固安宁的靠山。",
    },
    "T037": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 19.5,
        "keywords": ["ignoring_or_crossing_path"],
        "reasoning": "【震木破局】提取特征为「偏离或横穿既定路径」。路为世俗既定规则，不顺路走主打破常规或脱离体制束缚。",
        "summary": "正在脱离既定的轨道、体制或世俗为你安排好的舒适区，选择了一条极具挑战但也充满变数的破局之路。",
    },
    "T038": {
        "category": CAT_CAREER, "wuxing": "EARTH", "base_weight": 16.0,
        "keywords": ["carried_loads", "waist_and_back"],
        "reasoning": "【艮土压身】提取特征为「背负重物压在腰背」。腰背主脊梁与承载，重物压身主现实债务或责任。",
        "summary": "现实中背负着沉重的家庭责任、债务重担或工作KPI，导致自身能量极度压抑，难以轻松前行。",
    },
    "T039": {
        "category": CAT_HEALTH, "wuxing": "EARTH", "base_weight": 17.0,
        "keywords": ["objects_near_body_parts", "closed"],
        "reasoning": "【坤门闭塞】提取特征为「身体极近处存在特定闭合物件」。近场有闭合阻挡主排泄或能量出口受绝对封锁。",
        "summary": "现实中存在近在咫尺但却无法突破的壁垒被关在门外，或者生理上下焦/肠胃排泄系统存在严重的闭塞不通。",
    },
    "T040": {
        "category": CAT_ANCESTRY, "wuxing": "EARTH", "base_weight": 14.5,
        "keywords": ["mountains_and_extensions"],
        "reasoning": "【艮山连绵】提取特征为「山脉起于特定网格并绵延」。山为阻碍也为靠山，连绵不绝主深远沉重。",
        "summary": "当前面临着长期、持久且绵延不断的阻力与挑战（或拥有深厚盘根错节的背景），绝非短期可以解决或撼动。",
    },
    "T041": {
        "category": CAT_HEALTH, "wuxing": "METAL", "base_weight": 20.0,
        "keywords": ["directional_forces", "hitting_body_part"],
        "reasoning": "【金木相战】提取特征为「外力/光束像箭一样直射身体特定部位」。此为绝对的物理冲射与暗箭伤人相。",
        "summary": "极度危险！现实中正遭受外界突如其来的无情打击、裁员或恶意中伤，或者对应的身体部位即将爆发急性创伤。",
    },
    "T042": {
        "category": CAT_PERSONALITY, "wuxing": "WATER", "base_weight": 11.5,
        "keywords": ["shadow_trajectory", "has_shadow"],
        "reasoning": "【坎水阴煞】提取特征为「明确的影子轨迹及延展」。影子属阴，代表过去的业力、未解的牵绊或潜意识的阴暗面随行。",
        "summary": "往事或旧有的遗留问题（如债务、旧情、过去的失误）正如影随形地拖累着你，近期难以彻底切割。",
    },
    "T043": {
        "category": CAT_CAREER, "wuxing": "EARTH", "base_weight": 16.5,
        "keywords": ["leaning_heavily_or_falling", "leaning_away_from"],
        "reasoning": "【坤土失陷】提取特征为「重力失衡、踉跄快要摔倒且极力偏离某宫位」。土主根基，根基动摇则有倾覆之危。",
        "summary": "现实中的立足点（工作、平台或资金链）正处于极其不稳固的崩塌边缘，你正在极其被动地逃离某个高危旋涡。",
    },
    "T044": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 17.5,
        "keywords": ["reaching_but_missed_or_empty"],
        "reasoning": "【震木落空】提取特征为「肢体伸出但虚空抓取失败」。震为求取，落空主谋事不成、缘分擦肩或资金断裂。",
        "summary": "近期极度渴望抓住的某个核心机会、某笔资金或某段关系最终大概率会落空，充满了极其强烈的无力感与求而不得。",
    },
    "T045": {
        "category": CAT_ANCESTRY, "wuxing": "EARTH", "base_weight": 10.5,
        "keywords": ["environmental_traces", "footprints"],
        "reasoning": "【艮土留痕】提取特征为「特定网格中遗留的脚印或车辙等痕迹」。痕迹是前人的遗留，主沿袭、寻迹或被追踪。",
        "summary": "你目前正在走别人走过的老路，或者某件过去隐秘的事情留下了明显的把柄与线索，极易被外界顺藤摸瓜。",
    },
    "T046": {
        "category": CAT_PERSONALITY, "wuxing": "METAL", "base_weight": 18.5,
        "keywords": ["confinement_structures", "iron_fences"],
        "reasoning": "【乾金画地】提取特征为「铁栏杆、铁丝网等隔离限制属性结构」。金主肃杀与禁锢，身处其中主画地为牢、受制于人。",
        "summary": "当前身处于极其严苛的规则、体制或合同束缚之中，犹如困兽，个人自由与施展空间被外界客观物理条件绝对锁死。",
    },
    "T047": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 8.5,
        "keywords": ["structural_counts", "pillars"],
        "reasoning": "【巽木分驻】提取特征为「特定网格内复数的柱桩等支撑物」。多柱主多方支撑，但也主资源与注意力的极度分散。",
        "summary": "你目前所依赖的支撑点不止一个（多线投资或多个靠山），这既是后路，但也意味着你的精力与资源正被严重分流。",
    },
    "T048": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 12.0,
        "keywords": ["left_hand", "right_hand", "left_foot", "right_foot"],
        "reasoning": "【震木四散】提取特征为「极高精度的四肢独立网格落点」。四肢属木，四肢网格跨度过大主奔波劳碌、手脚并用。",
        "summary": "目前处于极度忙碌的高耗能阶段，多线程处理着极其繁杂的现实事务，四处救火，身体与精力透支极其严重。",
    },
    "T049": {
        "category": CAT_PERSONALITY, "wuxing": "METAL", "base_weight": 9.8,
        "keywords": ["micro_physical_counts", "hair_tufts", "buttons"],
        "reasoning": "【辛金散见】提取特征为「具备明确数量的微观生理特征」。金主精细与刻板，微观数量显性暴露主强迫症或注意力碎裂。",
        "summary": "近期精神处于高度敏感或强迫状态，对微小细节极其在意，或精力被周围极其琐碎的杂事严重切割分散。",
    },
    "T050": {
        "category": CAT_PERSONALITY, "wuxing": "FIRE", "base_weight": 13.5,
        "keywords": ["looking_upwards", "looking_up"],
        "reasoning": "【离火仰望】提取特征为「头部仰望与视线抛向远方」。火性炎上，主脱离当下、向往高维或极度期盼外部救赎。",
        "summary": "对眼前的现实状况感到乏味或无力，将极大的期盼寄托于未来、远方或某种未知的外部机遇上。",
    },
    "T051": {
        "category": CAT_CAREER, "wuxing": "FIRE", "base_weight": 15.0,
        "keywords": ["held_functional_props", "camera", "prop_target_grid"],
        "reasoning": "【丁火窥探】提取特征为「手持精密功能性道具并明确靶向」。借助精密外物聚焦特定方位，主极强的目的性与信息捕获欲。",
        "summary": "正在暗中观察或极度聚焦于某项特定计划/某个人，借助特定工具（或平台手段）获取信息，但暂未采取肉身实质性介入。",
    },
    "T052": {
        "category": CAT_CAREER, "wuxing": "EARTH", "base_weight": 14.5,
        "keywords": ["ground_lines_topology", "total_lines_count", "colors_description"],
        "reasoning": "【己土划界】提取特征为「地面具备明确的线条拓扑与数量颜色分割」。地标线主现实的禁锢、底线与人为划分的疆域。",
        "summary": "在现实的利益、职场领地或人际交往中，正面临极其严苛的边界划分。有多重规矩或不同阵营的底线横亘在脚下，不可逾越。",
    },
    "T053": {
        "category": CAT_CAREER, "wuxing": "METAL", "base_weight": 11.0,
        "keywords": ["sky_floating_objects_isomorphism", "similarity_matching", "isomorphism"],
        "reasoning": "【乾金同构】提取特征为「顶部网格存在高度相似/同构的漂浮物」。乾宫天象重影，主上层意志的复制、宏观环境的同质化。",
        "summary": "上层建筑、大环境或公司领导层存在高度同质化或「双重指令」现象，宏观风向虽然一致，但也缺乏创新与变数。",
    },
    "T054": {
        "category": CAT_CAREER, "wuxing": "WATER", "base_weight": 18.5,
        "keywords": ["medium_conflict", "adjacent_grid_with_conflict", "conflicting_object"],
        "reasoning": "【水土交战】提取特征为「主体网格与紧邻网格存在极端的介质物理反差（如岸与船/水）」。相邻介质割裂主身处险境边缘、进退两难。",
        "summary": "你正处于两种截然不同的环境、两种势力或两种生活方式的交界处（如离职边缘、跨行跳槽），一脚踏空即面临完全未知的动荡。",
    },
    "T055": {
        "category": CAT_PERSONALITY, "wuxing": "WOOD", "base_weight": 12.5,
        "keywords": ["body_color_matching", "resembles_ground_tone"],
        "reasoning": "【比劫同气】提取特征为「肢体特定部位与背景环境产生绝对色彩共振」。色彩同化主隐匿、消融自我边界或被特定环境深层吞噬。",
        "summary": "你的潜意识或特定行为模式，正在被身处的底层环境或某段根深蒂固的关系（如原生家庭/长辈角色）同化吞噬，正在失去自我边界。",
    },
    "T056": {
        "category": CAT_PERSONALITY, "wuxing": "EARTH", "base_weight": 11.5,
        "keywords": ["macro_gestalt_resemblance", "TV_on_a_table", "gestalt"],
        "reasoning": "【坤土成象】提取特征为「宏观格式塔构图呈现无生命物件」。将生命体扭曲为死物形态，主物化、受制或沦为工具。",
        "summary": "近期感觉自己像是一个工具人或被牢牢定在某个位置上，失去了自由鲜活的生命力，承受着极强的物化与僵滞感。",
    },
    "T057": {
        "category": CAT_PERSONALITY, "wuxing": "METAL", "base_weight": 16.5,
        "keywords": ["head_enclosure_shape", "support_base_shape", "square_boundary", "static_and_confined"],
        "reasoning": "【乾金画地】提取特征为「头部或底盘呈现极其刚硬的几何框架或处于极度静态被卡住的状态」。金主肃杀与禁锢，身陷方圆主画地为牢。",
        "summary": "思想或行动受到极度严苛的条框束缚，处于一种被死死卡住的瓶颈状态，难以突破现有的思维牢笼或物理环境。",
    },
    "T058": {
        "category": CAT_HEALTH, "wuxing": "METAL", "base_weight": 13.0,
        "keywords": ["mouth_shape", "tightly_closed_straight_line", "specific_facial_blemishes"],
        "reasoning": "【兑金闭口】提取特征为「嘴巴紧闭成直线或面部存在特殊色斑」。兑为口，紧闭主缄默抗拒；面部生斑主内分泌或情绪毒素外显。",
        "summary": "现实中存在强烈的拒绝沟通、隐忍不发的情绪，心中有话却不愿表达。同时需注意内分泌失调或脾胃毒素引起的皮肤警报。",
    },
    "T059": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 18.0,
        "keywords": ["thickness_length_asymmetry", "limb_asymmetry"],
        "reasoning": "【震木跛行】提取特征为「左右肢体存在极度明显的粗细/长短不对称」。震为足为行，左右失衡主步履维艰、阴阳失调与执行力跛脚。",
        "summary": "现实执行中存在严重的偏科或资源分配极其不均。某一方面极其发达，而另一方面严重拖后腿，导致整体进展跌跌撞撞、难以平衡。",
    },
    "T060": {
        "category": CAT_HEALTH, "wuxing": "WATER", "base_weight": 19.5,
        "keywords": ["lower_body_anomalies", "tube_like_appendage", "fluid_in_crotch"],
        "reasoning": "【坎水漏厄】提取特征为「坎宫或下体存在管状物、液体或排泄异常」。坎主下焦、肾泌尿与隐秘，异常外露主极高的隐疾发作与能量严重漏失。",
        "summary": "绝对高危预警！极度警惕生殖、泌尿系统或下焦的突发急性病理状况。在财务上，这也暗示着某种极其隐秘、难以启齿的严重漏财。",
    },
    "T061": {
        "category": CAT_CAREER, "wuxing": "WATER", "base_weight": 14.5,
        "keywords": ["ecological_misplacement", "misplacement"],
        "reasoning": "【坎水浮错】提取特征为「生态角色与所处环境产生强烈错位」。水主流动无定，角色错位主名不副实、生境相悖。",
        "summary": "当前所处的环境、团队或岗位与你的核心天赋极度不匹配，犹如虎落平阳，处于强烈的被放错位置的内耗与怀才不遇中。",
    },
    "T062": {
        "category": CAT_CAREER, "wuxing": "METAL", "base_weight": 18.5,
        "keywords": ["crop_slant_angle", "asymmetrical_cropping", "left_high_right_low", "left_low_right_high"],
        "reasoning": "【庚金斜裁】提取特征为「边缘裁切呈现明显的倾斜角」。裁切主外力暴力干预，倾斜主天平失衡、磁场倾覆。",
        "summary": "正受到外界极度不公正的对待或资源被强硬剥夺。局势天平已经严重倾斜，自身根基遭到不对等削弱，需防崩盘。",
    },
    "T063": {
        "category": CAT_PERSONALITY, "wuxing": "EARTH", "base_weight": 16.5,
        "keywords": ["suppressed_or_hidden_limbs", "pressed_under_body"],
        "reasoning": "【坤土自埋】提取特征为「肢体被自身躯干压迫或隐匿」。肢体主行动力，被自身躯干压迫主自我封闭与内部倾轧。",
        "summary": "存在强烈的自我设限或被迫隐忍，核心执行力被自身的顾虑或内部沉重的包袱死死压制，有苦难言，行动受限。",
    },
    "T064": {
        "category": CAT_PERSONALITY, "wuxing": "EARTH", "base_weight": 13.5,
        "keywords": ["micro_organ_substances", "covered_in_sand_dirt", "covered_in_"],
        "reasoning": "【己土蒙窍】提取特征为「面部核心器官（鼻/眼/口）表面沾染特定环境介质（如泥沙）」。五官为灵窍，蒙尘主感知受蔽与外邪入侵。",
        "summary": "当前获取信息的渠道被严重污染或蒙蔽，判断力下降，容易听信谗言或被周遭环境的负面情绪/是非（沙土）糊住双眼。",
    },
    "T065": {
        "category": CAT_CAREER, "wuxing": "WATER", "base_weight": 15.5,
        "keywords": ["expected_count", "visible_count", "hidden_count", "biological_counts_vs_visible"],
        "reasoning": "【癸水匿藏】提取特征为「生物学预期与视觉实际计数的物理核对出现明确残缺（预期大于可见）」。主隐藏实情或暗中折损。",
        "summary": "当前展露出来的实力或资源并非全部，存在刻意的隐瞒（留有一手），或者原本应得的份额被暗中克扣、吃回扣。",
    },
    "T066": {
        "category": CAT_ANCESTRY, "wuxing": "WATER", "base_weight": 19.0,
        "keywords": ["background_behind_specific_organs", "coastline_crossing_head", "head_background"],
        "reasoning": "【坎水切项】提取特征为「头部正后方为特定介质或海岸线/地平线直接横穿头颈」。背景介质定靠山底色，切线斩颈主天外飞煞。",
        "summary": "大后方靠山存在严重隐患（如水之深渊）。且极度预警宏观大环境（地平线/政策）将直接对你的核心利益进行无情的物理切割。",
    },
    "T067": {
        "category": CAT_RELATION, "wuxing": "METAL", "base_weight": 18.8,
        "keywords": ["invisible_symmetric_appendages", "right_wing_invisible", "left_arm_missing"],
        "reasoning": "【兑金伤缺】提取特征为「本应成对的对称器官存在单侧完全隐匿或残缺」。成对之物折损，主阴阳失衡、得力助手流失或肢体暗伤。",
        "summary": "你的得力助手、合伙人或伴侣可能正在隐匿自身实力/信息，或者你在某项推进中失去了一臂之力，处于孤立无援的残缺状态。",
    },
    "T068": {
        "category": CAT_RELATION, "wuxing": "EARTH", "base_weight": 17.5,
        "keywords": ["surface_severing_lines", "divides_land", "subjects_physically_separated"],
        "reasoning": "【坤土撕裂】提取特征为「大地/天空等连片介质被强行割裂，或多主体被物理线强行隔开」。主环境阵营分裂、楚河汉界与人心涣散。",
        "summary": "所处大环境或团队内部正面临极其严重的阵营分裂，或你与某位关键人物之间出现了难以逾越的现实鸿沟（楚河汉界），形同陌路。",
    },
    "T069": {
        "category": CAT_PERSONALITY, "wuxing": "FIRE", "base_weight": 16.8,
        "keywords": ["glare_and_sunlight", "strong_sun", "weather_contact"],
        "reasoning": "【丙火暴侵】提取特征为「画面存在极其刺眼的极端强光冲射或承受极端气象」。过刚易折，强光刺眼主外境施压逼迫、真相刺目或精神遭强刺激。",
        "summary": "现实中正面临来自上层/外界极其耀眼但充满压迫感的视察或干预，或者某个令人极度不适的真相被突然曝光，令你精神紧绷。",
    },
    "T070": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 14.2,
        "keywords": ["implied_food_source", "implies_food", "surface_transitions", "grass_meets_water"],
        "reasoning": "【食神生财】提取特征为「环境中直接隐含天然食物源或处于介质交接的生态边缘」。食物源即天然财库，介质交接地带主跨界红利。",
        "summary": "近期在资源获取上极具先天优势，所处环境（或即将跨界的边缘地带）蕴藏着可以直接变现的丰厚天然粮草与红利，宜果断摄取。",
    },
    "T071": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 15.5,
        "keywords": ["kinetic_energy_expenditure", "heavy_exertion", "heavy_exertion_flying"],
        "reasoning": "【震木劳形】提取特征为「主体动态呈现极高的能量消耗与沉重的肉体劳碌相」。主事必躬亲、极度透支。",
        "summary": "目前正处于一件极其消耗体力与心智的逆风局中，事必躬亲且缺乏外力托底，肉身与精神的能耗已逼近极限临界点。",
    },
    "T072": {
        "category": CAT_CAREER, "wuxing": "FIRE", "base_weight": 18.5,
        "keywords": ["mid_air_leap", "trajectory_anchors", "apex_current_grid"],
        "reasoning": "【离火腾空】提取特征为「处于腾空跃迁状态并具备明确的起跳/落点锚定」。脱离地心引力主运势的剧烈升腾与变轨，悬空主无根。",
        "summary": "正处于极具爆发力的运势变轨期或职位跃迁期。已脱离旧有平台（起跳点），但目前处于悬空无根的冲刺状态，需极度警惕最终落点的虚实。",
    },
    "T073": {
        "category": CAT_PERSONALITY, "wuxing": "WOOD", "base_weight": 14.2,
        "keywords": ["head_tilt_direction"],
        "reasoning": "【巽风微探】提取特征为「头部在微观上明显向特定网格倾斜或探去」。头为诸阳之会，微观倾角代表潜意识的极致探求或试探。",
        "summary": "潜意识中对某个特定方向（某个人、某个未公开的计划或外界动向）存在极其强烈的试探、渴望或关注，你的注意力重心已经发生了严重偏移。",
    },
    "T074": {
        "category": CAT_RELATION, "wuxing": "WATER", "base_weight": 13.8,
        "keywords": ["micro_attachments_on_body", "substances_on_organs", "water_droplets"],
        "reasoning": "【癸水沾滞】提取特征为「身体表面携带着微小的环境介质（如水珠/泥土）」。外物附着于体，主外界气息的微观沾染或如影随形的琐碎压力。",
        "summary": "身上沾染了极其明显的外部环境印记（如刚经历过某场风波、带有特定圈子的习气），或者正承受着如影随形、难以擦除的琐碎压力与人情沾滞。",
    },
    "T075": {
        "category": CAT_RELATION, "wuxing": "WOOD", "base_weight": 17.5,
        "keywords": ["localized_medium_upheaval", "medium_physical_reaction", "splashing_water"],
        "reasoning": "【震雷激变】提取特征为「在主体的起跳/落点或周围引发了环境介质的剧烈变化（如水花飞溅）」。主动势极强，对周围环境造成强烈的物理冲击与反弹。",
        "summary": "你的某个突然决定、离开或强势介入，在周围的环境、团队或人际圈子中引发了极其剧烈的动荡、议论或连锁物理反应（砸出了巨大的水花）。",
    },
    "T076": {
        "category": CAT_CAREER, "wuxing": "EARTH", "base_weight": 15.5,
        "keywords": ["partial_medium_emergence"],
        "reasoning": "【木土交杂】提取特征为「试图离开介质但身体部分仍滞留其中」。主挣脱泥潭但未尽全功，藕断丝连。",
        "summary": "正在尝试彻底脱离某个旧有环境、项目或深层关系，但由于现实利益或客观阻力尾大不掉，仍有部分身家性命陷在其中，处于半脱产的拉扯期。",
    },
    "T077": {
        "category": CAT_CAREER, "wuxing": "FIRE", "base_weight": 12.8,
        "keywords": ["text_and_symbol_occlusion", "prop_induced_occlusion"],
        "reasoning": "【丁火掩目】提取特征为「文字符号或道具在视觉上直接压制/遮挡了主体器官」。文字符号主名声契约，遮挡主受其反噬蒙蔽。",
        "summary": "近期正受困于某种虚名、繁复的合同契约或被外界强行贴上的标签人设中，真实的自我诉求与判断力被这些外部符号严重压抑或遮蔽。",
    },
    "T078": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 10.5,
        "keywords": ["cross_grid_object_distribution"],
        "reasoning": "【巽风漫洒】提取特征为「同类小物件在多个网格间零散分布」。主资源不成聚、精力漫灌无序。",
        "summary": "你当前的资源、可用资金或核心注意力呈现极其碎片化、天女散花式的消耗状态。到处铺摊子但缺乏核心聚焦点，导致整体抓手极弱。",
    },
    "T079": {
        "category": CAT_PERSONALITY, "wuxing": "WATER", "base_weight": 14.8,
        "keywords": ["divergent_shadows"],
        "reasoning": "【癸水多歧】提取特征为「影子出现明显的分叉并发散至多宫位」。影子主潜意识或暗线，分叉主多重暗鬼或业力多端。",
        "summary": "潜意识极其分裂，或者在暗中同时推进着多条见不得光的隐秘线索（多重隐藏身份或后路），导致暗处的因果极度复杂，容易在关键时刻反噬。",
    },
    "T080": {
        "category": CAT_HEALTH, "wuxing": "FIRE", "base_weight": 17.2,
        "keywords": ["localized_abnormal_colors", "contour_breakages_and_scars"],
        "reasoning": "【离火破相】提取特征为「面部存在明显异常色彩块或轮廓物理断裂」。面部为精神与外运之表，轮廓断裂主破相与突发急厄。",
        "summary": "面部气色反映外运严重受损，极易在个人名誉、外在形象上遭遇突发的破相级毁灭打击。同时需高度警惕突发的面部/头部急症或外伤。",
    },
    "T081": {
        "category": CAT_PERSONALITY, "wuxing": "WATER", "base_weight": 16.2,
        "keywords": ["blind_spots_mapping", "back_of_head", "buttocks"],
        "reasoning": "【癸水伏藏】提取特征为「明确映射后脑勺或臀部生理盲区所在网格」。后背与下盘主潜意识盲区与防御死角，盲区落位定隐患之源。",
        "summary": "你在某个人际关系或财务领域存在巨大的认知盲区或防御死角，极易被人在背后捅刀或暗算，需极其警惕看不见的隐患。",
    },
    "T082": {
        "category": CAT_RELATION, "wuxing": "EARTH", "base_weight": 15.5,
        "keywords": ["natural_enemies_status", "peaceful_coexistence"],
        "reasoning": "【坤土载物】提取特征为「自然界天敌不可思议地和平共处」。天敌同框主生态悖论，和平共处主强行捏合或利益捆绑下的虚假繁荣。",
        "summary": "你目前正处于一个充满利益算计或天然立场对立的团队/关系中。表面看似一团和气，实则暗流涌动，随时可能因为利益分配不均而撕破脸。",
    },
    "T083": {
        "category": CAT_ANCESTRY, "wuxing": "EARTH", "base_weight": 18.0,
        "keywords": ["zodiac_animals_present", "zodiac_animals"],
        "reasoning": "【地支显象】提取特征为「画面中直接出现了具体的十二生肖动物」。生肖现形主太岁流年引动，该动物代表的地支五行能量在当前时空被绝对激活。",
        "summary": "画面出现的动物正对应你当前的流年或流月核心能量。若为吉则有贵人相助，若为凶则需严防该生肖对应的人或月份引发的突发冲克。",
    },
    "T084": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 14.8,
        "keywords": ["furniture_spanning", "spans_from_grid"],
        "reasoning": "【震木架海】提取特征为「桌床等大型家具物件跨越多个网格」。大型物件跨宫主现实平台的横向延伸、基建搭建或跨界连接。",
        "summary": "你正在搭建一个跨越多个领域/圈子的现实平台（如新项目、新渠道）。这个平台虽然庞大，但也极大地分散了你的注意力，需要耗费巨量精力去维持其跨度。",
    },
    "T085": {
        "category": CAT_PERSONALITY, "wuxing": "FIRE", "base_weight": 11.0,
        "keywords": ["physical_aids", "glasses", "hearing_aids"],
        "reasoning": "【离火借明】提取特征为「佩戴眼镜等明确的物理感知辅助工具」。眼为离火，借用外物辅助感知主自身洞察力受限或需要过滤外界信息。",
        "summary": "你目前对局势的判断力存在主观滤镜或视力盲区，必须借助外界的专业工具、顾问或平台数据来辅助决策，切忌盲目自信、单凭直觉行事。",
    },
    "T086": {
        "category": CAT_RELATION, "wuxing": "METAL", "base_weight": 17.5,
        "keywords": ["species_ratio", "alien_species_name", "alien_count"],
        "reasoning": "【庚金交战】提取特征为「精确清点同类与异类的群体统计学数量」。非我族类其心必异，异类数量显现主资源争夺与阵营对立。",
        "summary": "你的核心领地或团队中已经混入了明显的异类（不同频的人或竞争对手）。双方在暗中争夺资源与话语权，必须高度警惕阵营被渗透。",
    },
    "T087": {
        "category": CAT_RELATION, "wuxing": "WOOD", "base_weight": 17.5,
        "keywords": ["complementary_subject", "complementary"],
        "reasoning": "【震巽同气】提取特征为「寻主判定中存在互补双核（如两棵相似的树）」。双核并立，不分主次，主比劫同气、双生羁绊或势均力敌的竞争与合作。",
        "summary": "你的生命中存在一个与你势均力敌、极其相似的伴侣、合伙人或竞争对手，你们深度绑定，既互相支撑又暗中较劲。",
    },
    "T088": {
        "category": CAT_PERSONALITY, "wuxing": "FIRE", "base_weight": 10.5,
        "keywords": ["near_field_environment_and_colors", "tiny_objects", "tiny_red_flowers"],
        "reasoning": "【丁火碎芒】提取特征为「核心主体近场存在极其细小的色彩点缀物件」。近场碎物主近在咫尺的琐碎心智、微小情绪或隐蔽的桃花/人缘。",
        "summary": "近期你的核心注意力周围环绕着许多微小但色彩鲜明的人或事（如琐碎的桃花、小笔开销或细小的情绪波动），它们极大地牵扯着你的心境。",
    },
    "T089": {
        "category": CAT_PERSONALITY, "wuxing": "METAL", "base_weight": 16.8,
        "keywords": ["avatar_category", "misc_landscape", "isolated_object"],
        "reasoning": "【辛金孤悬】提取特征为「头像分类为抽象风景且聚焦于孤立单一物件」。以物代人，孤物主内心极度的孤独感、强烈的边界感或对特定事物的偏执寄托。",
        "summary": "你当前的内心世界呈现出极强的孤独感与边界感，比起复杂的人际交往，你更愿意将情感与精力寄托在某件特定的死物、爱好或极其封闭的个人空间中。",
    },
    "T090": {
        "category": CAT_RELATION, "wuxing": "EARTH", "base_weight": 15.2,
        "keywords": ["small_person_in_distance", "secondary_figures_distant"],
        "reasoning": "【戊土远尘】提取特征为「存在被物理降级为远景的微小次要人物」。人物被极度缩小远推，主自我意识极度膨胀，或对周围人际关系的冷漠与疏离。",
        "summary": "在你当前的社交视野中，周围的人都被你主观上推到了极其次要、遥远的位置。你正处于一种高度自我中心或刻意与人群保持绝对疏离的状态中。",
    },
    "T091": {
        "category": CAT_PERSONALITY, "wuxing": "WATER", "base_weight": 14.5,
        "keywords": ["concealed_or_hiding", "hiding_under_"],
        "reasoning": "【癸水伏藏】提取特征为「核心主体在视觉上故意躲藏或隐匿于更大遮蔽物之下」。癸水主暗昧与伏藏，躲避主缺乏安全感或暗中蓄力。",
        "summary": "潜意识极其缺乏安全感，或正处于一段不愿公开的隐秘关系/暗中筹备的计划中，刻意低调，不愿暴露真实的自我边界。",
    },
    "T092": {
        "category": CAT_CAREER, "wuxing": "METAL", "base_weight": 18.5,
        "keywords": ["optical_breakage", "appears_broken_and_discontinuous"],
        "reasoning": "【辛金错断】提取特征为「连续部位因光影或遮挡产生断开、不连续的光学错觉」。相连之物现断裂错觉，主虚假危机、信息阻断或外在形象受损。",
        "summary": "极其警惕！外界对你的风评或你对外展示的形象正遭遇光学断裂，存在严重的信息误导、虚假危机，原本连贯的业务/关系可能因误会而中断。",
    },
    "T093": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 13.8,
        "keywords": ["multiple_branches_states", "one_bright_one_dark"],
        "reasoning": "【乙木分歧】提取特征为「主体发出多个分支且呈现明暗等巨大形态反差」。同根生异枝，主多线发展、内部资源分配极度不均或阴阳两面。",
        "summary": "你目前正在多线操作（兼职、多个项目或多重关系），但这些支线的发展状态呈现出极端的一明一暗或一好一坏，内部资源分配极其失衡。",
    },
    "T094": {
        "category": CAT_CAREER, "wuxing": "WOOD", "base_weight": 11.2,
        "keywords": ["curvature_trajectory", "bending_through"],
        "reasoning": "【巽风曲绕】提取特征为「具有明确起点、弯曲途径与顶点的曲率反弹轨迹」。曲生蓄势，直生煞，弯曲轨迹主迂回试探、曲线救国或委曲求全。",
        "summary": "当前不宜直面硬刚！你所追求的目标必须通过极其迂回、曲折的方式（如委婉沟通、绕开正面冲突）才能达成，过程中充满妥协与试探。",
    },
    "T095": {
        "category": CAT_CAREER, "wuxing": "FIRE", "base_weight": 15.5,
        "keywords": ["strikingly_bright_grids", "notably_dark_grids"],
        "reasoning": "【丙火偏枯】提取特征为「非整体光照，而是特定九宫格处于异常高光或深陷阴影」。局部极昼极夜，主对应宫位的时空气场能量极度失衡。",
        "summary": "你当前所处的环境中存在极端的能量盲区。某些领域（特定的人或事）被过度曝光聚焦，而另一些关键角落却被深埋在阴影中无人问津，防后院起火。",
    },
    "T096": {
        "category": CAT_PERSONALITY, "wuxing": "WATER", "base_weight": 12.5,
        "keywords": ["shadows_on_core_subject", "mixed_light_and_shadow"],
        "reasoning": "【癸水斑驳】提取特征为「核心主体表面自带明显阴影斑块，明暗交织」。光明中有暗影，主外表光鲜但内心藏有隐忧、杂念或患得患失。",
        "summary": "虽然你向外界展示出极其鲜亮、积极的一面，但你的内心深处（或事务的内部）充满了自我怀疑、阴霾与患得患失的斑驳情绪。",
    },
    "T097": {
        "category": CAT_PERSONALITY, "wuxing": "EARTH", "base_weight": 10.8,
        "keywords": ["multi_colors_in_specific_grids", "multi_colors"],
        "reasoning": "【戊土杂糅】提取特征为「特定网格内交织着多种绝对纯色」。五色令人目盲，色彩复合交织主信息过载、情绪极其杂糅或欲望多端。",
        "summary": "你的内心或特定的人际关系中，充斥着极其杂乱、多重且相互冲突的欲望与情绪（如既想要稳定又渴望激情），导致心智严重超载、难以专注。",
    },
    "T098": {
        "category": CAT_RELATION, "wuxing": "WOOD", "base_weight": 14.2,
        "keywords": ["appendage_supportive_posture", "intertwined_with_core", "supportive_posture"],
        "reasoning": "【乙木缠绕】提取特征为「附属器官/物件对核心呈现托举环抱或深度物理交错」。环抱主护持，交错过深则主羁绊缠绕、尾大不掉。",
        "summary": "你目前正受到来自周围环境、下属或伴侣的深度支持（托举）。但如果羁绊过深，这种支持将演变为难以割舍的物理纠缠与束缚，令你难以独立脱身。",
    },
    "T099": {
        "category": CAT_ANCESTRY, "wuxing": "WATER", "base_weight": 16.5,
        "keywords": ["absolute_void_grids", "is_empty"],
        "reasoning": "【癸水落空】提取特征为「特定网格存在绝对的物理空缺或完全没有同类元素」。空缺主对应宫位的能量彻底断档、缺乏支撑或缘分浅薄。",
        "summary": "在特定的生活领域（如长辈、下属或某个特定方向）存在严重的资源断层或缘分缺失，处于一种孤立无援的悬空状态。",
    },
    "T100": {
        "category": CAT_PERSONALITY, "wuxing": "WATER", "base_weight": 14.8,
        "keywords": ["localized_blur_and_defocus", "blurry_and_out_of_focus", "unclear"],
        "reasoning": "【壬水生迷】提取特征为「局部网格呈现极其明显的失焦、模糊或朦胧状态」。失焦主看不清真相、记忆模糊或刻意隐藏。",
        "summary": "对某些特定的人或事存在严重的认知模糊，或者这些领域正处于一种不明朗、被刻意掩盖的混沌状态，切忌盲目投入。",
    },
    "T101": {
        "category": CAT_CAREER, "wuxing": "FIRE", "base_weight": 18.5,
        "keywords": ["physical_inversion", "upside_down"],
        "reasoning": "【丙火颠覆】提取特征为「物理形态在重力或生长方向上发生绝对倒置」。倒置主天地翻覆、违背常理、极端的叛逆或时运的剧烈反转。",
        "summary": "近期极可能遭遇某种颠倒黑白的突发状况，或自身正采取一种极度反常规、甚至带有破坏性的叛逆方式来对抗现实。",
    },
    "T102": {
        "category": CAT_RELATION, "wuxing": "WOOD", "base_weight": 12.5,
        "keywords": ["jagged_misalignment", "misaligned_and_jagged", "uneven"],
        "reasoning": "【乙木参差】提取特征为「成排/成簇的元素呈现高低不平、错位与参差不齐」。参差主步调不一、内部摩擦或资源分配极其不均。",
        "summary": "你所处的团队或当前推进的多项事务中，存在严重的步调不一致。内部力量参差不齐，互相拉扯，导致整体效率大打折扣。",
    },
    "T103": {
        "category": CAT_HEALTH, "wuxing": "METAL", "base_weight": 19.8,
        "keywords": ["biological_decay_and_wither", "withered_dead_leaves", "withered", "decay"],
        "reasoning": "【庚金肃杀】提取特征为「主体身上存在明确的枯萎、坏死或腐烂的生物组织」。枯萎主气数已尽、生命力被严重剥夺或不可逆的病理损伤。",
        "summary": "极度高危预警！你自身或某项核心业务正面临气数衰竭的枯萎期。必须立刻斩断坏死部分（止损/切除隐疾），否则将蔓延全身。",
    },
}

# ==============================================================================
# [L5] YOLO 拦截规则：边界条件防爆字典
# ==============================================================================
YOLO_VETO_RULES: Dict[str, Dict[str, str]] = {
    "VETO_001": {
        "trigger_keywords": "不知道,乱打,没法算,无意义,测试,随便,乱码,故意捣乱,垃圾",
        "action": "BLOCK_AND_RETURN",
        "reason": "检测到无意义扰乱输入，拒绝推演",
    },
    "VETO_002": {
        "trigger_keywords": "全黑,全白,纯色,空白图,无内容",
        "action": "BLOCK_AND_RETURN",
        "reason": "图像无有效视觉信息，无法进行象数推演",
    },
    "VETO_003": {
        "trigger_keywords": "null,none,undefined,error,exception",
        "action": "BLOCK_AND_RETURN",
        "reason": "上游数据结构异常，图谱节点为空",
    },
}
