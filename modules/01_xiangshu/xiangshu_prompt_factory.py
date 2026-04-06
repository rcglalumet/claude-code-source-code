# -*- coding: utf-8 -*-
# = [端口 F: L1 表现层 Prompt 工厂] =
# 路径: modules/01_xiangshu/xiangshu_prompt_factory.py
# @Layer: 📢 [L1] 象数派 Prompt 工厂（表现层）
# @Description: 将 XiangShuReport 的推演结论渲染为给 LLM 的指令或给用户的输出文本。
#               本模块仅负责文本模板填充，零推演逻辑，零 I/O，零网络调用。
#               所有硬编码输出文本在此集中管理，严禁散落在其他层。

from typing import List

from xiangshu_v102_topology import XiangShuFinding, XiangShuReport

# ==============================================================================
# [静态模板区] 所有给 LLM 的系统指令与给用户的输出框架
# ==============================================================================

# --- 系统角色指令模板 ---
SYSTEM_ROLE_PROMPT: str = (
    "你是一位精通象数风水的解读大师，擅长通过照片中的视觉元素进行形而上的能量解读。"
    "你的解读必须：\n"
    "1. 聚焦于五大宏观领域（性格、事业、人际、健康、祖荫）\n"
    "2. 语言犀利、直指核心，避免泛泛而谈\n"
    "3. 每条断语后必须给出具体的现实指引\n"
    "4. 语气自信果决，如同算命先生的当头棒喝\n"
    "严禁输出：免责声明、科学反驳、\"仅供参考\"等弱化语。"
)

# --- 用户请求注入模板 ---
USER_REQUEST_TEMPLATE: str = (
    "请根据以下象数推演报告，为用户生成一份完整的命盘解读报告。\n\n"
    "【图片ID】: {image_id}\n"
    "【推演数据】:\n{findings_block}\n\n"
    "【张量物理汇总】:\n"
    "- 总权重: {total_weight}\n"
    "- 张力指数: {tension} / 25.0（越高越凶险）\n"
    "- 质量场: {mass}（越负越虚耗）\n"
    "- 图谱熵值: {entropy}\n\n"
    "请按五大领域分组输出，每个领域最多输出 3 条最高权重的断语，"
    "每条断语后附带【待反馈选项】。"
)

# --- 单条推演结论文本模板 ---
FINDING_BLOCK_TEMPLATE: str = (
    "【{rule_id}】[{category}] 五行: {wuxing} | 权重: {tensor_weight}\n"
    "推演: {reasoning}\n"
    "断语: {summary}\n"
)

# --- 用户反馈选项模板 ---
FEEDBACK_OPTIONS_TEMPLATE: str = (
    "> 【待反馈选项】\n"
    "> 🔲 A. 极其准确，就是我本人/完全符合现状\n"
    "> 🔲 B. 部分符合，有说到点子上\n"
    "> 🔲 C. 感觉不像，存在偏差\n"
)

# --- YOLO 拦截用户提示模板 ---
YOLO_BLOCK_RESPONSE_TEMPLATE: str = (
    "⚠️ **系统提示**\n\n"
    "检测到输入内容无法进行有效的象数推演。\n"
    "原因：{veto_reason}\n\n"
    "请提供一张包含真实人物、场景或具体物件的清晰照片，以便进行完整的象数解读。"
)

# --- 报告头部模板 ---
REPORT_HEADER_TEMPLATE: str = (
    "═══════════════════════════════════════\n"
    "🔮 象数命盘解读报告 | 图片 ID: {image_id}\n"
    "═══════════════════════════════════════\n"
    "📊 能量汇总: 总权重 {total_weight:.1f} | "
    "张力 {tension:.1f}/25 | 质量场 {mass:.1f} | 熵值 {entropy:.2f}\n"
    "📋 五大领域命中: 性格×{personality} 事业×{career} "
    "人际×{relation} 健康×{health} 祖荫×{ancestry}\n"
    "───────────────────────────────────────\n"
)

# --- 领域分组标题模板 ---
DOMAIN_SECTION_TEMPLATE: str = "\n## {category}\n\n"

# --- 断语正文模板（含反馈选项）---
FINDING_OUTPUT_TEMPLATE: str = (
    "**[{rule_id}]** _{reasoning}_\n\n"
    "> 断语总结： {summary}\n"
    "> \n"
    "> 【待反馈选项】\n"
    "> 🔲 A. 极其准确，就是我本人/完全符合现状\n"
    "> 🔲 B. 部分符合，有说到点子上\n"
    "> 🔲 C. 感觉不像，存在偏差\n\n"
)


# ==============================================================================
# [工厂函数区] 纯文本拼装，零推演
# ==============================================================================

def render_finding_block(finding: XiangShuFinding) -> str:
    """将单条 XiangShuFinding 渲染为 LLM 注入用的结构化文本块。"""
    return FINDING_BLOCK_TEMPLATE.format(
        rule_id=finding.rule_id,
        category=finding.category,
        wuxing=finding.wuxing,
        tensor_weight=finding.tensor_weight,
        reasoning=finding.reasoning,
        summary=finding.summary,
    )


def render_finding_output(finding: XiangShuFinding) -> str:
    """将单条 XiangShuFinding 渲染为面向用户的 Markdown 输出（含反馈选项）。"""
    return FINDING_OUTPUT_TEMPLATE.format(
        rule_id=finding.rule_id,
        reasoning=finding.reasoning,
        summary=finding.summary,
    )


def render_report_header(report: XiangShuReport) -> str:
    """渲染报告头部摘要文本。"""
    return REPORT_HEADER_TEMPLATE.format(
        image_id=report.image_id,
        total_weight=report.total_weight,
        tension=report.tension,
        mass=report.mass,
        entropy=report.entropy,
        personality=report.personality_hit_count,
        career=report.career_hit_count,
        relation=report.relation_hit_count,
        health=report.health_hit_count,
        ancestry=report.ancestry_hit_count,
    )


def render_veto_response(report: XiangShuReport) -> str:
    """渲染 YOLO 拦截时的用户友好提示文本。"""
    return YOLO_BLOCK_RESPONSE_TEMPLATE.format(veto_reason=report.veto_reason)


def build_llm_user_message(report: XiangShuReport, top_n: int = 15) -> str:
    """
    构建注入给 LLM 的完整 user 消息文本。
    仅取 top_n 条权重最高的 findings（已在引擎层排序）。
    """
    top_findings = report.findings[:top_n]
    findings_block = "\n".join(render_finding_block(f) for f in top_findings)
    return USER_REQUEST_TEMPLATE.format(
        image_id=report.image_id,
        findings_block=findings_block,
        total_weight=report.total_weight,
        tension=report.tension,
        mass=report.mass,
        entropy=report.entropy,
    )


def build_user_facing_report(
    report: XiangShuReport,
    max_per_domain: int = 3,
) -> str:
    """
    构建面向用户的完整 Markdown 报告文本。

    - 按五大领域分组
    - 每个领域最多输出 max_per_domain 条（已按权重降序）
    - 若被 YOLO 拦截，直接返回拦截提示
    """
    if report.is_vetoed:
        return render_veto_response(report)

    # 领域分组（维持 findings 的权重降序，每组取 top max_per_domain）
    domain_order: List[str] = [
        "⛰️ 事业与财富",
        "🪞 性格与潜意识",
        "🔗 人际与情感",
        "⚔️ 健康与疾厄",
        "🌳 祖荫与本命",
    ]
    grouped = {domain: [] for domain in domain_order}
    for finding in report.findings:
        bucket = grouped.get(finding.category)
        if bucket is not None and len(bucket) < max_per_domain:
            bucket.append(finding)

    # 拼装报告
    parts = [render_report_header(report)]
    for domain in domain_order:
        domain_findings = grouped[domain]
        if not domain_findings:
            continue
        parts.append(DOMAIN_SECTION_TEMPLATE.format(category=domain))
        for f in domain_findings:
            parts.append(render_finding_output(f))

    return "".join(parts)
