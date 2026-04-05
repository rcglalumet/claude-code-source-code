"""
training_camp/mcts_constant_distiller.py
------------------------------------------
Alumet OS — MCTS 夜间张量蒸馏器（深度睡眠与梦境学习机制）

核心使命：
  系统的"深度睡眠与梦境学习机制"——在算力闲置期（如凌晨的 Cron 任务），
  读取日间积累的对话推演原材料（raw_cases/），通过蒙特卡洛树搜索（MCTS）
  与 LLM 反思机制进行复盘，提取新的业务铁律，
  生成可以反哺 L5（expert_rules/）的静态规则草稿。

设计哲学（KAIROS 守护进程模拟）：
  Claude Code 中的 KAIROS 守护进程在系统空闲时执行"自我进化"——
  它不依赖外部训练数据，而是从自身的历史行为轨迹中提炼规律。

  本模块模拟这一机制：
    1. 读取阶段（Input）：     从 raw_cases/ 加载日间 Trace 数据
    2. MCTS 复盘阶段（Think）：对每条 Trace 展开搜索树，评估行为路径质量
    3. 提炼阶段（Distill）：   从高质量路径中抽象出业务常识或铁律
    4. 输出阶段（Output）：    生成规则草稿写入 expert_rules/，等待人工审核

MCTS 在此的语义（非游戏树搜索）：
  传统 MCTS 用于博弈树搜索（棋类游戏）。
  在此语境中，MCTS 被重新语义化为"行为路径质量评估"：
    - 节点（Node）：对话中的一个决策点（工具调用 or 生成回复）
    - 扩展（Expansion）：枚举该决策点的可能替代行为
    - 模拟（Simulation/Rollout）：通过启发式函数或 LLM 评估替代行为的质量
    - 反向传播（Backpropagation）：将叶节点的评分传播到根节点
    - 选择（Selection）：选取 UCB1 分数最高的行为路径
  最终，被多次"高分选择"的行为模式被提炼为业务铁律。

Fail-Safe 设计：
  - 所有蒸馏操作在独立进程中运行（通过 Cron 触发），不影响主服务。
  - 生成的规则草稿需要人工审核后才能合并到 L5（不自动部署）。
  - 单条 Trace 解析失败不中断整个蒸馏流程（跳过并记录）。
  - 蒸馏器无任何写权限到核心配置——只能写 expert_rules/drafts/ 目录。
"""

from __future__ import annotations

import json
import logging
import math
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

RAW_CASES_DIR: Path = Path("data_center/raw_cases")
EXPERT_RULES_DIR: Path = Path("data_center/expert_rules")
DRAFTS_DIR: Path = EXPERT_RULES_DIR / "drafts"

# ---------------------------------------------------------------------------
# MCTS 超参数
# ---------------------------------------------------------------------------

# UCB1 探索系数 C：控制探索（Exploration）与利用（Exploitation）的平衡
# C 越大 → 更倾向探索未尝试的节点；C 越小 → 更倾向加深已知高分节点
UCB1_C: float = 1.414  # √2，MCTS 经典默认值

# 每个决策节点的最大扩展数（枚举替代行为的数量上限）
MAX_EXPANSION: int = 5

# 每条 Trace 的 MCTS 迭代次数
MCTS_ITERATIONS: int = 50

# 规则提炼的最低置信度阈值（低于此分数的规则不写入草稿）
MIN_RULE_CONFIDENCE: float = 0.65

# 单次蒸馏会话处理的最大 Trace 文件数
MAX_FILES_PER_SESSION: int = 100

# 规则草稿文件的最大条数（防止草稿无限堆积）
MAX_DRAFT_RULES_PER_FILE: int = 20


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class TraceRecord:
    """
    从 raw_cases/ 读取的原材料 Trace 记录。
    与 async_background_housekeeping.py 中的 TraceRecord 结构对齐。
    """

    trace_id: str
    session_id: str
    user_intent: str
    tool_call_sequence: list[dict[str, Any]]
    final_output: str
    success: bool
    total_turns: int
    estimated_tokens: int
    created_at: float = 0.0
    tags: list[str] = field(default_factory=list)


@dataclass
class MctsNode:
    """
    MCTS 搜索树中的单个节点。

    在行为路径评估语境中，节点代表对话中的一个决策点：
      - 该节点对应的"动作"（action）是工具调用或生成回复
      - visit_count：该节点被访问（评估）的次数
      - total_score：历次评估分数之和（用于计算平均分）
      - children：从此节点扩展出的子节点（替代行为）

    UCB1 公式（选择阶段使用）：
      UCB1 = Q(v) + C * √(ln(N(parent)) / N(v))
      其中：
        Q(v) = total_score / visit_count（利用：已知平均分）
        C * √(ln(N) / n)（探索：访问少的节点奖励）
    """

    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    action: dict[str, Any] = field(default_factory=dict)  # 对应的工具调用或行为描述
    visit_count: int = 0
    total_score: float = 0.0
    parent: "MctsNode | None" = None
    children: list["MctsNode"] = field(default_factory=list)
    is_terminal: bool = False   # 是否为叶节点（对话结束点）
    depth: int = 0

    @property
    def q_value(self) -> float:
        """利用值 Q：已知行为的平均质量分。"""
        return self.total_score / self.visit_count if self.visit_count > 0 else 0.0

    def ucb1(self, parent_visits: int, c: float = UCB1_C) -> float:
        """
        UCB1 分数：用于在选择阶段权衡探索与利用。

        未访问节点返回无穷大（确保所有节点至少被访问一次）。
        """
        if self.visit_count == 0:
            return float("inf")
        exploration = c * math.sqrt(math.log(parent_visits) / self.visit_count)
        return self.q_value + exploration

    def backpropagate(self, score: float) -> None:
        """
        反向传播：将叶节点的评估分数沿父链传播到根节点。

        每个祖先节点的 total_score 和 visit_count 均更新，
        使 Q 值逐渐收敛为该子树中所有路径的平均质量。
        """
        self.visit_count += 1
        self.total_score += score
        if self.parent is not None:
            self.parent.backpropagate(score)


@dataclass
class DistilledRule:
    """
    蒸馏器提炼出的业务铁律草稿。

    这是蒸馏流程的最终输出，将写入 expert_rules/drafts/ 目录，
    等待人工审核后决定是否提升为 L5 正式规则。

    字段设计（对标 Claude Code 的规则体系）：
      rule_id:     全局唯一标识，便于追踪与审核
      rule_text:   规则的自然语言表述（供人类审核）
      rule_pattern:以半结构化格式表述的规则模式（供机器检索）
      evidence_traces: 支持此规则的 Trace ID 列表（提供证据链）
      confidence:  规则的置信度评分（基于 MCTS 收敛情况计算）
      category:    规则类别（tool_selection / error_handling / user_intent / safety）
      suggested_action: 建议的落地动作（UPDATE_PROMPT / ADD_EXAMPLE / ADD_FILTER）
    """

    rule_id: str
    rule_text: str
    rule_pattern: str
    evidence_traces: list[str]
    confidence: float
    category: str
    suggested_action: str
    created_at: float = field(default_factory=time.time)
    distiller_version: str = "mcts_v1"
    requires_human_review: bool = True  # 永远为 True：蒸馏器不自动部署规则


@dataclass
class DistillationReport:
    """单次蒸馏会话的完整报告。"""

    session_id: str
    started_at: float
    finished_at: float
    traces_loaded: int
    traces_processed: int
    traces_skipped: int
    rules_extracted: int
    rules_above_threshold: int
    draft_files_written: int
    total_duration_seconds: float

    def __str__(self) -> str:
        return (
            f"[蒸馏报告] 会话={self.session_id[:8]} | "
            f"Trace: 加载={self.traces_loaded}, 处理={self.traces_processed}, "
            f"跳过={self.traces_skipped} | "
            f"规则: 提取={self.rules_extracted}, 过阈值={self.rules_above_threshold} | "
            f"草稿文件={self.draft_files_written} | "
            f"耗时={self.total_duration_seconds:.1f}s"
        )


# ---------------------------------------------------------------------------
# MCTS 蒸馏器主体
# ---------------------------------------------------------------------------

class MctsConstantDistiller:
    """
    Alumet OS MCTS 夜间张量蒸馏器。

    运行时机：算力闲置期（凌晨 Cron 任务），非实时，允许长时间运行。

    蒸馏流程：
      Step 1: load_raw_cases()       → 从 raw_cases/ 批量读取 Trace 文件
      Step 2: distill_traces()       → 对每条 Trace 执行 MCTS 复盘
      Step 3: extract_rules()        → 从 MCTS 结果中提炼业务铁律
      Step 4: write_draft_rules()    → 将规则草稿写入 expert_rules/drafts/
      Step 5: archive_processed()    → 将已处理的原材料文件移动到 processed/ 子目录

    完整流程封装在 run_distillation_session() 中，供 Cron 脚本直接调用。
    """

    def __init__(
        self,
        raw_cases_dir: Path = RAW_CASES_DIR,
        drafts_dir: Path = DRAFTS_DIR,
        mcts_iterations: int = MCTS_ITERATIONS,
        min_confidence: float = MIN_RULE_CONFIDENCE,
        score_fn: Callable[[TraceRecord, MctsNode], float] | None = None,
    ) -> None:
        """
        Args:
            raw_cases_dir:    原材料目录（由后台 GC 守护进程填充）。
            drafts_dir:       规则草稿输出目录。
            mcts_iterations:  每条 Trace 的 MCTS 迭代次数。
            min_confidence:   规则写入草稿的最低置信度阈值。
            score_fn:         自定义节点评分函数（依赖注入，用于测试与扩展）。
                              若为 None，使用内置启发式评分函数。
        """
        self._raw_dir = raw_cases_dir
        self._drafts_dir = drafts_dir
        self._iterations = mcts_iterations
        self._min_confidence = min_confidence
        self._score_fn = score_fn or _default_score_fn

        # 确保目录存在
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._drafts_dir.mkdir(parents=True, exist_ok=True)
        (self._raw_dir / "processed").mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # 主入口：完整蒸馏会话
    # ------------------------------------------------------------------

    def run_distillation_session(self) -> DistillationReport:
        """
        执行完整的夜间蒸馏会话，返回蒸馏报告。

        此方法是 Cron 脚本的调用入口：
          0 2 * * * python -c "from training_camp.mcts_constant_distiller import MctsConstantDistiller; MctsConstantDistiller().run_distillation_session()"

        Fail-Safe 保证：
          任何单步失败（文件读取/MCTS 计算/草稿写入）均被捕获并记录，
          不中断整个会话。蒸馏器偏向"尽力而为"而非"全有或全无"。
        """
        session_id = str(uuid.uuid4())
        started_at = time.time()
        logger.info("[蒸馏器] 夜间蒸馏会话启动: session=%s", session_id)

        # Step 1：加载原材料
        trace_files, traces = self._load_raw_cases()
        traces_loaded = len(traces)

        # Step 2~3：MCTS 复盘 + 规则提炼
        all_rules: list[DistilledRule] = []
        traces_processed = 0
        traces_skipped = 0

        for trace in traces:
            try:
                rules = self._distill_single_trace(trace)
                all_rules.extend(rules)
                traces_processed += 1
            except Exception as exc:
                # 单条 Trace 处理失败：记录并跳过，不中断整个会话
                logger.warning(
                    "[蒸馏器] Trace %s 处理失败，已跳过: %s: %s",
                    trace.trace_id[:8], type(exc).__name__, exc,
                )
                traces_skipped += 1

        # 过滤低置信度规则
        high_confidence_rules = [r for r in all_rules if r.confidence >= self._min_confidence]

        # Step 4：写入草稿规则文件
        draft_files_written = self._write_draft_rules(high_confidence_rules, session_id)

        # Step 5：将已处理的原材料文件归档（移到 processed/ 子目录）
        self._archive_processed_files(trace_files)

        finished_at = time.time()
        report = DistillationReport(
            session_id=session_id,
            started_at=started_at,
            finished_at=finished_at,
            traces_loaded=traces_loaded,
            traces_processed=traces_processed,
            traces_skipped=traces_skipped,
            rules_extracted=len(all_rules),
            rules_above_threshold=len(high_confidence_rules),
            draft_files_written=draft_files_written,
            total_duration_seconds=finished_at - started_at,
        )

        logger.info("[蒸馏器] 蒸馏会话完成: %s", report)
        return report

    # ------------------------------------------------------------------
    # Step 1：加载原材料
    # ------------------------------------------------------------------

    def _load_raw_cases(self) -> tuple[list[Path], list[TraceRecord]]:
        """
        从 raw_cases/ 目录读取所有未处理的 .jsonl 文件，解析为 TraceRecord 列表。

        读取上限：每次蒸馏最多处理 MAX_FILES_PER_SESSION 个文件，
        防止单次蒸馏耗时过长（剩余文件留待下次会话处理）。

        Returns:
            (已读取的文件路径列表, 解析成功的 TraceRecord 列表)
        """
        # 只读取 .jsonl 文件，跳过 processed/ 子目录
        all_files = sorted(
            [f for f in self._raw_dir.glob("*.jsonl") if f.is_file()],
            key=lambda f: f.stat().st_mtime,  # 按修改时间排序，优先处理最早的文件
        )[:MAX_FILES_PER_SESSION]

        if not all_files:
            logger.info("[蒸馏器] raw_cases/ 目录无待处理文件，本次蒸馏无原材料。")
            return [], []

        logger.info("[蒸馏器] 发现 %d 个原材料文件，开始加载...", len(all_files))

        traces: list[TraceRecord] = []
        for filepath in all_files:
            try:
                file_traces = _parse_jsonl_file(filepath)
                traces.extend(file_traces)
                logger.debug("[蒸馏器] 文件 %s 加载 %d 条 Trace", filepath.name, len(file_traces))
            except Exception as exc:
                logger.warning("[蒸馏器] 文件 %s 解析失败，已跳过: %s", filepath.name, exc)

        logger.info("[蒸馏器] 共加载 %d 条 Trace（来自 %d 个文件）", len(traces), len(all_files))
        return all_files, traces

    # ------------------------------------------------------------------
    # Step 2~3：MCTS 复盘 + 规则提炼（单条 Trace）
    # ------------------------------------------------------------------

    def _distill_single_trace(self, trace: TraceRecord) -> list[DistilledRule]:
        """
        对单条 Trace 执行 MCTS 复盘，提炼出业务铁律草稿。

        MCTS 在此的运作方式：
          1. 以 Trace 的工具调用链为基础，构建初始行为树（根节点）。
          2. 对每个调用节点，枚举可能的替代行为（扩展）。
          3. 通过评分函数（_default_score_fn 或注入的自定义函数）评估替代行为质量。
          4. 反向传播分数，更新各节点的 Q 值与 UCB1 分数。
          5. 迭代 MCTS_ITERATIONS 次后，选取 Q 值最高的行为路径。
          6. 从高分路径中抽象出业务常识，生成 DistilledRule。

        Returns:
            本条 Trace 蒸馏出的规则列表（可能为空）。
        """
        if not trace.tool_call_sequence:
            # 无工具调用的 Trace：仅通过文本分析提炼意图级规则
            return self._extract_intent_rules(trace)

        # 构建初始搜索树：根节点 → 工具调用链节点
        root = MctsNode(action={"type": "root", "intent": trace.user_intent}, depth=0)
        current = root
        for step_idx, tool_call in enumerate(trace.tool_call_sequence):
            child = MctsNode(
                action=tool_call,
                parent=current,
                depth=step_idx + 1,
                is_terminal=(step_idx == len(trace.tool_call_sequence) - 1),
            )
            current.children.append(child)
            current = child

        # 执行 MCTS 迭代
        for _ in range(self._iterations):
            # Selection：从根节点沿 UCB1 最高路径向下选择
            node = self._select(root)
            # Expansion：若非叶节点，扩展替代行为子节点
            if not node.is_terminal and node.visit_count > 0:
                node = self._expand(node, trace)
            # Simulation（Rollout）：评估当前节点的质量分
            score = self._score_fn(trace, node)
            # Backpropagation：将分数向上传播
            node.backpropagate(score)

        # 从搜索树中提炼规则
        rules = self._extract_rules_from_tree(root, trace)
        return rules

    def _select(self, node: MctsNode) -> MctsNode:
        """
        选择阶段：从根节点沿 UCB1 最高的子节点向下选择，直到叶节点或未访问节点。
        """
        current = node
        while current.children and not current.is_terminal:
            # 选取 UCB1 分数最高的子节点
            best = max(current.children, key=lambda c: c.ucb1(current.visit_count))
            current = best
        return current

    def _expand(self, node: MctsNode, trace: TraceRecord) -> MctsNode:
        """
        扩展阶段：为当前节点生成替代行为子节点，返回一个随机新子节点。

        替代行为的生成策略（启发式，不依赖 LLM 实时调用）：
          1. 基于工具名称生成同类型工具的替代变体。
          2. 基于参数变异生成不同参数组合的替代。
          3. 基于对话历史中的其他成功工具调用进行迁移。

        在生产环境中，此步骤可替换为低成本 LLM 调用
        （如 Llama-8B 生成替代行为），但保持启发式版本的备用路径。
        """
        if len(node.children) >= MAX_EXPANSION:
            # 已达最大扩展数，返回现有子节点中的随机一个
            return random.choice(node.children)

        # 生成替代行为（启发式：基于原始 action 的变异）
        original_action = node.action.copy()
        alternative_action = _mutate_action(original_action)

        new_child = MctsNode(
            action=alternative_action,
            parent=node,
            depth=node.depth + 1,
        )
        node.children.append(new_child)
        return new_child

    def _extract_rules_from_tree(
        self, root: MctsNode, trace: TraceRecord
    ) -> list[DistilledRule]:
        """
        从 MCTS 搜索树中提炼业务铁律。

        提炼策略：
          1. 遍历所有节点，筛选出 visit_count ≥ 3 且 Q 值 ≥ 0.6 的高分节点。
          2. 将这些高分节点的行为模式抽象为自然语言规则。
          3. 计算规则置信度（基于 Q 值、访问次数与树深度的综合评分）。
        """
        rules: list[DistilledRule] = []
        high_value_nodes = self._collect_high_value_nodes(root)

        for node in high_value_nodes:
            if node.visit_count < 2:
                continue

            # 从节点行为生成规则文本
            rule_text, rule_pattern, category = _node_to_rule(node, trace)
            if not rule_text:
                continue

            # 置信度 = Q 值 × (1 - 1/visit_count) 的调和修正
            # 访问次数越多，置信度修正越接近 Q 值本身
            confidence = node.q_value * (1.0 - 1.0 / max(node.visit_count, 1))
            confidence = min(max(confidence, 0.0), 1.0)

            rule = DistilledRule(
                rule_id=str(uuid.uuid4()),
                rule_text=rule_text,
                rule_pattern=rule_pattern,
                evidence_traces=[trace.trace_id],
                confidence=confidence,
                category=category,
                suggested_action=_suggest_action(category, confidence),
            )
            rules.append(rule)

        return rules

    def _collect_high_value_nodes(self, root: MctsNode) -> list[MctsNode]:
        """BFS 遍历搜索树，收集所有 Q 值 ≥ 0.6 的节点。"""
        result: list[MctsNode] = []
        queue = [root]
        while queue:
            node = queue.pop(0)
            if node.q_value >= 0.6 and node.visit_count > 0:
                result.append(node)
            queue.extend(node.children)
        return result

    def _extract_intent_rules(self, trace: TraceRecord) -> list[DistilledRule]:
        """
        对无工具调用的 Trace 执行意图级规则提炼（轻量版，不走 MCTS 树）。

        主要提炼：
          - 成功 Trace 中的高频意图模式（what works）
          - 失败 Trace 中的危险意图特征（what to avoid）
        """
        rules: list[DistilledRule] = []
        intent = trace.user_intent.strip()
        if not intent:
            return rules

        if trace.success:
            rule_text = f"当用户意图为「{intent[:100]}」时，无需工具调用即可直接响应，属于纯生成任务。"
            category = "user_intent"
            confidence = 0.70
        else:
            rule_text = f"意图「{intent[:100]}」在无工具辅助下失败，建议为此类意图配备相关工具。"
            category = "tool_selection"
            confidence = 0.65

        rules.append(DistilledRule(
            rule_id=str(uuid.uuid4()),
            rule_text=rule_text,
            rule_pattern=f"intent_pattern: {intent[:50]}",
            evidence_traces=[trace.trace_id],
            confidence=confidence,
            category=category,
            suggested_action="ADD_EXAMPLE" if trace.success else "ADD_TOOL_MAPPING",
        ))
        return rules

    # ------------------------------------------------------------------
    # Step 4：写入草稿规则文件
    # ------------------------------------------------------------------

    def _write_draft_rules(
        self, rules: list[DistilledRule], session_id: str
    ) -> int:
        """
        将提炼出的规则草稿写入 expert_rules/drafts/ 目录。

        每个蒸馏会话生成一个草稿文件：
          expert_rules/drafts/draft_{timestamp}_{session_id[:8]}.json

        文件格式：
          {
            "session_id": "...",
            "distilled_at": ...,
            "rules_count": N,
            "requires_human_review": true,  ← 永远为 True
            "rules": [ {...}, {...} ]
          }

        安全约束：
          - 草稿文件只写入 drafts/ 子目录，不写入 expert_rules/ 根目录。
          - 文件包含 requires_human_review: true 标记，
            提示自动化 CI 不得将此文件自动合并到 L5。
          - 不超过 MAX_DRAFT_RULES_PER_FILE 条规则写入单个文件。

        Returns:
            实际写入的草稿文件数。
        """
        if not rules:
            logger.info("[蒸馏器] 无高置信度规则，跳过草稿写入。")
            return 0

        # 按置信度降序排列，优先写入高置信度规则
        sorted_rules = sorted(rules, key=lambda r: -r.confidence)

        # 分批写入（每文件最多 MAX_DRAFT_RULES_PER_FILE 条）
        batches = [
            sorted_rules[i : i + MAX_DRAFT_RULES_PER_FILE]
            for i in range(0, len(sorted_rules), MAX_DRAFT_RULES_PER_FILE)
        ]

        files_written = 0
        for batch_idx, batch in enumerate(batches):
            timestamp = int(time.time())
            filename = f"draft_{timestamp}_{session_id[:8]}_{batch_idx:02d}.json"
            filepath = self._drafts_dir / filename

            draft_doc = {
                "schema": "alumet_rule_draft_v1",
                "session_id": session_id,
                "distilled_at": time.time(),
                "rules_count": len(batch),
                "requires_human_review": True,  # 永远为 True，不自动部署
                "distiller": "mcts_constant_distiller",
                "rules": [asdict(r) for r in batch],
            }

            try:
                tmp_path = filepath.with_suffix(".json.tmp")
                tmp_path.write_text(
                    json.dumps(draft_doc, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                tmp_path.replace(filepath)
                files_written += 1
                logger.info(
                    "[蒸馏器] 草稿写入: %s（%d 条规则，最高置信度=%.2f）",
                    filename, len(batch), batch[0].confidence,
                )
            except OSError as e:
                logger.error("[蒸馏器] 草稿文件写入失败: %s: %s", filepath, e)

        return files_written

    # ------------------------------------------------------------------
    # Step 5：归档已处理的原材料文件
    # ------------------------------------------------------------------

    def _archive_processed_files(self, files: list[Path]) -> None:
        """
        将已处理的 .jsonl 文件移动到 raw_cases/processed/ 子目录。

        归档后的文件不再参与下次蒸馏，但保留在磁盘上以备审计。
        生产环境可配置定时清理策略（如保留 30 天后删除）。
        """
        processed_dir = self._raw_dir / "processed"
        processed_dir.mkdir(exist_ok=True)

        for filepath in files:
            try:
                dest = processed_dir / filepath.name
                filepath.replace(dest)
                logger.debug("[蒸馏器] 原材料文件已归档: %s → processed/", filepath.name)
            except OSError as e:
                logger.warning("[蒸馏器] 原材料文件归档失败: %s: %s", filepath.name, e)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _parse_jsonl_file(filepath: Path) -> list[TraceRecord]:
    """
    解析单个 .jsonl 文件，返回 TraceRecord 列表。

    每行为一个独立的 JSON 对象，解析失败的行跳过并记录 WARNING。
    """
    records: list[TraceRecord] = []
    content = filepath.read_text(encoding="utf-8", errors="replace")

    for line_num, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            # 构造 TraceRecord，未知字段忽略（向前兼容）
            known_fields = set(TraceRecord.__dataclass_fields__.keys())
            filtered = {k: v for k, v in data.items() if k in known_fields}
            records.append(TraceRecord(**filtered))
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("[蒸馏器] %s 第 %d 行解析失败: %s", filepath.name, line_num, e)

    return records


def _default_score_fn(trace: TraceRecord, node: MctsNode) -> float:
    """
    默认节点评分函数（启发式，不依赖 LLM 实时调用）。

    评分维度：
      1. Trace 整体成功标记（success=True → 基础分 0.6）
      2. 节点深度奖励（工具调用链越靠后的节点信息价值越高）
      3. Token 效率奖励（低 Token 消耗完成任务的路径更有价值）
      4. 动作类型奖励（read-only 工具比 write 工具更安全，给予轻微奖励）

    生产环境扩展建议：
      将此函数替换为低成本 LLM 调用（如 Llama-8B 打分），
      获得更精准的行为质量评估，同时保持与主算力节点的成本不对称。
    """
    score = 0.6 if trace.success else 0.3  # 基础分

    # 深度奖励：工具调用链中的靠后节点更有价值（见证了更多上下文）
    depth_bonus = min(node.depth * 0.05, 0.2)
    score += depth_bonus

    # Token 效率奖励：少于 500 Token 完成任务的 Trace 给予额外奖励
    if trace.estimated_tokens < 500 and trace.success:
        score += 0.1

    # 轻微随机扰动（模拟 MCTS 的 rollout 随机性，防止搜索树退化为确定性）
    score += random.gauss(0, 0.05)

    return min(max(score, 0.0), 1.0)  # 裁剪到 [0, 1]


def _mutate_action(action: dict[str, Any]) -> dict[str, Any]:
    """
    对工具调用动作进行轻微变异，生成替代行为候选。

    变异策略（启发式）：
      - 修改参数值（参数微变）
      - 添加可选参数（参数扩展）
      - 移除一个非必要参数（参数精简）
    """
    mutated = action.copy()
    mutation_type = random.choice(["param_vary", "param_add", "param_remove"])

    if mutation_type == "param_vary" and "arguments" in mutated:
        args = dict(mutated.get("arguments", {}))
        if args:
            key = random.choice(list(args.keys()))
            old_val = args[key]
            if isinstance(old_val, str):
                args[key] = old_val + "_alt"
            elif isinstance(old_val, int):
                args[key] = old_val + 1
            mutated["arguments"] = args

    elif mutation_type == "param_add":
        args = dict(mutated.get("arguments", {}))
        args[f"alt_param_{random.randint(1, 99)}"] = "alternative"
        mutated["arguments"] = args

    elif mutation_type == "param_remove" and "arguments" in mutated:
        args = dict(mutated.get("arguments", {}))
        if len(args) > 1:
            key = random.choice(list(args.keys()))
            del args[key]
            mutated["arguments"] = args

    mutated["_is_alternative"] = True
    return mutated


def _node_to_rule(
    node: MctsNode, trace: TraceRecord
) -> tuple[str, str, str]:
    """
    将高质量的 MCTS 节点转化为自然语言规则描述。

    返回 (rule_text, rule_pattern, category)。
    若无法生成有意义的规则，返回 ("", "", "")。
    """
    action = node.action
    tool_name = action.get("tool_name", action.get("type", ""))

    if not tool_name or tool_name in ("root", ""):
        return "", "", ""

    is_alternative = action.get("_is_alternative", False)
    success_context = "成功完成" if trace.success else "尝试（最终失败）"

    if is_alternative:
        # 替代行为节点：说明原行为可能有更优的替代方案
        rule_text = (
            f"在意图「{trace.user_intent[:60]}」的场景中，"
            f"工具 '{tool_name}' 存在参数优化空间（Q={node.q_value:.2f}）。"
            f"建议探索参数变体以提升任务{success_context}率。"
        )
        category = "tool_selection"
    else:
        # 原始调用节点：强化已验证的行为模式
        rule_text = (
            f"在意图「{trace.user_intent[:60]}」的场景中，"
            f"调用工具 '{tool_name}'（深度={node.depth}）的路径质量评分为 {node.q_value:.2f}，"
            f"经 {node.visit_count} 次迭代验证，建议纳入标准工具选择规则。"
        )
        category = "tool_selection" if "tool" in tool_name.lower() else "error_handling"

    rule_pattern = f"intent=~'{trace.user_intent[:40]}' → tool='{tool_name}' @ depth={node.depth}"
    return rule_text, rule_pattern, category


def _suggest_action(category: str, confidence: float) -> str:
    """根据规则类别与置信度，推荐落地动作。"""
    if confidence >= 0.85:
        return "ADD_TO_EXPERT_RULES"   # 高置信度：建议加入 L5 正式规则（仍需人工确认）
    elif confidence >= 0.70:
        return "ADD_EXAMPLE"           # 中等置信度：建议加入 Few-Shot 示例
    else:
        return "OBSERVE_AND_COLLECT"   # 低置信度：继续收集数据，暂不行动
