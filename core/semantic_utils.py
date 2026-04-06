#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/semantic_utils.py - Alumet OS V10 通用工具代谢库
从 alumet_surgeon.py 物理平移的"脂肪"层工具函数。
零外部依赖，仅 Python 标准库。
"""

import os
import sys
import re
import json
import glob
import time
import shutil
import asyncio
import importlib.util
import logging
from datetime import datetime

# ============================================================
# 彩色终端
# ============================================================
_ANSI = {
    "green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
    "blue": "\033[94m",  "cyan": "\033[96m", "magenta": "\033[95m",
    "reset": "\033[0m",
}

def _c(text: str, color: str = "green") -> str:
    return f"{_ANSI.get(color, _ANSI['reset'])}{text}{_ANSI['reset']}"

def pc(text: str, color: str = "green") -> None:
    print(_c(text, color))

# ============================================================
# 文件安全写入与备份
# ============================================================
def _write_bak(path: str) -> None:
    """写入前创建 .bak 备份，防抖覆盖防线。"""
    if os.path.exists(path) and not path.endswith(".bak"):
        try:
            shutil.copy2(path, path + ".bak")
        except Exception:
            pass

def safe_write(path: str, content: str, force: bool = False) -> str:
    """
    防抖覆盖写入。
    force=False: 已存在的 .py 文件导入隔离草稿舱，不直接覆写。
    所有写入前生成 .bak 备份。
    返回实际写入路径。
    """
    if not content.strip():
        return path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    actual_path = path
    if not force and path.endswith(".py") and os.path.exists(path):
        actual_path = path.replace(".py", f"_SURGEON_DRAFT_{int(time.time())}.py")
        pc(f"  ⚠️ [防抖] {path} 已存在 -> 隔离草稿舱: {actual_path}", "yellow")
    _write_bak(actual_path)
    try:
        with open(actual_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        logging.error(f"[write] 写入失败 {actual_path}: {e}")
    return actual_path

def safe_append_inject(path: str, content: str, marker: str = None) -> str:
    """
    智能增量注入（无损缝合）。
    文件不存在则新建；已存在且含 marker 则跳过；否则追加。
    返回: 'created' | 'skipped' | 'appended'
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not os.path.exists(path):
        _write_bak(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return "created"
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        existing = f.read()
    if marker and marker in existing:
        return "skipped"
    _write_bak(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + content)
    return "appended"

# ============================================================
# 垃圾回收
# ============================================================
def cleanup_stale_drafts(days_to_keep: int = 3) -> None:
    """清理超过 N 天的 _SURGEON_DRAFT_ 草稿与 .draft 文件。"""
    threshold = time.time() - days_to_keep * 86400
    deleted = 0
    patterns = (
        glob.glob("**/*_SURGEON_DRAFT_*.py", recursive=True) +
        glob.glob("**/*.draft*", recursive=True)
    )
    for fp in patterns:
        if os.path.isfile(fp) and os.path.getmtime(fp) < threshold:
            try:
                os.remove(fp)
                deleted += 1
            except Exception as e:
                logging.error(f"[GC] 清理失败 {fp}: {e}")
    if deleted:
        pc(f"🧹 [智能清道夫] 已清理 {deleted} 个过期草稿", "green")

# ============================================================
# 全局备份
# ============================================================
def create_backup() -> None:
    """创建全局 ZIP 备份快照。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"../ALUMET_OS_V10_BACKUP_{ts}"
    pc(f"📦 [Step 1] 创建全局备份快照: {backup_name}.zip ...", "blue")
    try:
        shutil.make_archive(backup_name, "zip", ".")
        pc(f"  ✅ 备份完成: {backup_name}.zip", "green")
    except Exception as e:
        pc(f"  ⚠️ 备份失败 (非阻断): {e}", "yellow")

# ============================================================
# 基础设施探针
# ============================================================
def detect_infra_missing() -> bool:
    """轻量探测：关键目录缺失 >= 2 则视为首次运行。"""
    markers = ["agentic_workflow", "expert_rules", "modules/01_xiangshu", "data_center"]
    return sum(1 for m in markers if not os.path.exists(m)) >= 2

# ============================================================
# 象数基因注入管线
# ============================================================
def inject_xiangshu_genome(raw_json_str: str) -> None:
    """
    通过管道无缝全自动注入高维物理张量至 expert_rules/xiangshu_rules.py。
    自动分配递增 T-ID，安全追加，不覆盖历史序列。
    """
    RULES_FILE = "expert_rules/xiangshu_rules.py"
    pc("\n🧬 [基因管线] 探测到 JSON 蒸馏张量，启动 AST 无感注入...", "yellow")
    os.makedirs("expert_rules", exist_ok=True)
    if not os.path.exists(RULES_FILE):
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            f.write("XIANGSHU_GENOMES = {}\n")
    try:
        clean = re.sub(r"```json\s*|\s*```", "", raw_json_str).strip()
        new_data = json.loads(clean)
        payload = new_data.get("T_NEW") or list(new_data.values())[0]
    except Exception as e:
        pc(f"[-] 基因序列解析失败: {e}", "red")
        return
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    existing_ids = re.findall(r'"(T\d+)"', content)
    next_id = "T001" if not existing_ids else f"T{str(max(int(i[1:]) for i in existing_ids) + 1).zfill(3)}"
    pc(f"[+] 装配新张量序列: {next_id}", "blue")
    formatted = json.dumps(payload, indent=4, ensure_ascii=False)
    indented = formatted.replace("\n", "\n    ")
    new_entry = f'    "{next_id}": {indented},'
    if "XIANGSHU_GENOMES = {" in content:
        updated = content.replace("XIANGSHU_GENOMES = {", f"XIANGSHU_GENOMES = {{\n{new_entry}")
    else:
        updated = content + f'\nXIANGSHU_GENOMES["{next_id}"] = {formatted}\n'
    _write_bak(RULES_FILE)
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        f.write(updated)
    pc(f"[√] 张量 {next_id} 已锚定至 {RULES_FILE}！", "green")

# ============================================================
# AutoDream 内联任务 (同步包装)
# ============================================================
async def _housekeeping_coroutine() -> None:
    """AutoDream 后台任务协程：清稿 + 两阶段GC + MCTS 探针。"""
    threshold = time.time() - 3 * 86400
    deleted = 0
    for pattern in ["**/*_SURGEON_DRAFT_*.py", "**/*.draft*"]:
        for fp in glob.glob(pattern, recursive=True):
            if os.path.isfile(fp) and os.path.getmtime(fp) < threshold:
                try:
                    os.remove(fp)
                    deleted += 1
                except Exception:
                    pass
    if deleted:
        pc(f"🧹 [AutoDream] 已清理 {deleted} 个过期草稿", "green")
    gc_dir = "data_center/bookkeeping_gc"
    if os.path.isdir(gc_dir):
        for fname in os.listdir(gc_dir):
            if fname.endswith(".orphaned_at"):
                continue
            fpath = os.path.join(gc_dir, fname)
            marker = fpath + ".orphaned_at"
            if os.path.exists(marker):
                try:
                    os.remove(fpath)
                    os.remove(marker)
                    pc(f"♻️ [AutoDream GC] 两阶段回收: {fname}", "green")
                except Exception:
                    pass
    if os.path.exists("training_camp/mcts_constant_distiller.py"):
        pc("🧠 [AutoDream] MCTS 蒸馏器已就位。", "cyan")
    pc("✅ [AutoDream] 后台任务完成。", "green")

def run_housekeeping_inline() -> None:
    """同步入口，供 CLI 主循环调用。"""
    asyncio.run(_housekeeping_coroutine())
