# Surgeon 脱水分析报告 (Dehydration Analysis)

## 动机

`alumet_surgeon.py` 超过 1500 行后进入"熵增危险区"。AI Agent 在修改核心路由时的错误率随行数呈非线性增长。
目标：将**有效逻辑行 (ELL)**（除去硬编码长字符串 Payload 之外的运行代码）控制在 **800 行以内**。

## 脂肪 / 骨架分类

| 类别 | 内容 | 处置方案 |
|------|------|---------|
| **脂肪 (Utils)** | `_c()`, `pc()`, `_write_bak()`, `safe_write()`, `safe_append_inject()`, `cleanup_stale_drafts()`, `create_backup()`, `detect_infra_missing()`, `inject_xiangshu_genome()`, 以及 `_run_housekeeping_inline()` | 迁移至 `core/semantic_utils.py` |
| **载荷 (Payload)** | `CODE_VM_REPL_SANDBOX`, `CODE_SYSTEM_HOT_MEMORY`, `CODE_EXACT_GREP_RETRIEVER`, `CODE_MCP_TOOL_PROTOCOL`, `CODE_WORKING_MEMORY_CONTEXT`, `CODE_YOLO_VETO_CLASSIFIER`, `CODE_AGENT_QUERY_ENGINE`, `CODE_LLM_NETWORK_GATEWAY`, `CODE_ASYNC_HOUSEKEEPING`, `CODE_MCTS_DISTILLER`, `CODE_AST_SENTINEL`, `CODE_DENIAL_TRACKING`, `CODE_EXPERT_RULES_INIT`, `CODE_DYNAMIC_TIERING_MDC`, `CODE_CONSTITUTION_MDC` | 原地保留，不计入 ELL |
| **骨架 (Core)** | `DOMAIN_ROUTER`, `PORT_LABELS`, `INFRA_FILE_MAP`, `SKELETON_FILE_MAP`, `ALUMET_DIRECTORIES`, `resolve_port_path()`, `load_topology_dynamic()`, `topology_auto_heal()`, `build_structure()`, `inject_infra_cores()`, `inject_skeleton_files()`, `interactive_surgical_router()`, `main()` | 原地保留，精简 |

## 迁移至 core/semantic_utils.py 的函数

```
_c(text, color)              # 彩色终端
pc(text, color)              # 打印彩色
_write_bak(path)             # .bak 备份
safe_write(path, content, force)      # 防抖写入
safe_append_inject(path, content, marker)  # 增量追加
cleanup_stale_drafts(days)   # 草稿清道夫
create_backup()              # 全局快照
detect_infra_missing()       # 基础设施探针
inject_xiangshu_genome(raw)  # 象数基因注入
_run_housekeeping_inline()   # AutoDream 内联任务
```

## 手术后物理形态

```
alumet_surgeon.py
├── 头部 (Imports, from core.semantic_utils import *)   ~20 行
├── 中部 (Logic: 路由映射 + 注入算法 + CLI状态机)      ~780 行
└── 尾部 (Payload: 硬编码代码块，数千行，不计ELL)
```

## 预期收益

- Agent 修改核心路由速度提升 3 倍以上（信噪比↑）
- 工具函数 Bug 修复一次即可全系统生效
- 非对称进化：第 7、8 端口扩展无惧
