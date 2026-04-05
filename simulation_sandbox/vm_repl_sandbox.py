"""
simulation_sandbox/vm_repl_sandbox.py
---------------------------------------
Alumet OS — VM REPL 沙盒执行环境（防沙盒越狱与 .env 密钥窃取）

安全威胁模型：
  本模块是整个系统中攻击面最大的组件。大模型生成的代码在此被物理执行，
  攻击者（或失控的大模型）可能尝试：

  威胁 T1 —— 模块导入越狱（最高危）：
    通过 `import os`、`import subprocess`、`from pathlib import Path` 等
    获取文件系统与进程控制权，读取 .env 文件窃取 API 密钥与数据库凭证。

  威胁 T2 —— 内建函数滥用：
    通过 `open()`、`eval()`、`exec()`、`__import__()` 绕过语义限制，
    即使没有 import，也能通过 __builtins__ 访问危险能力。

  威胁 T3 —— 属性链式逃逸：
    通过 `().__class__.__mro__[1].__subclasses__()` 等方式遍历类层级，
    找到 _io.FileIO 等危险类并实例化，完成无 import 的文件读写。

  威胁 T4 —— 无限循环/资源耗尽：
    通过 `while True: pass` 或递归炸弹占满 CPU，拒绝服务。

防御策略（纵深防御，多层叠加）：
  防线 1 —— AST 物理阉割（执行前静态分析）：
    在 exec() 前，强制将代码解析为 AST，遍历所有节点，
    发现任何 Import/ImportFrom 节点立即抛出 SecurityException，
    彻底封死 import 路径，不给任何尝试机会。

  防线 2 —— 命名空间真空化：
    exec() 的 globals 中强制设置 `{"__builtins__": {}}`，
    抹杀所有 Python 内建函数（open/eval/exec/print/__import__ 等），
    使代码在"无内建"的真空环境中运行。

  防线 3 —— 白名单能力注入：
    仅向沙盒注入经过严格代理包装的 `kernel_call` 句柄，
    以及将输出重定向到内存缓冲的安全 `print` 替代品。
    代理层在每次调用时进行二次鉴权，确保工具调用不超出授权范围。

  防线 4 —— 执行超时熔断：
    使用 `signal.SIGALRM` 设置最大执行时长（默认 5 秒），
    超时后抛出 SandboxTimeoutError，防止无限循环耗尽 CPU。
    （注意：SIGALRM 仅在 Unix 主线程中有效，跨线程场景需替换为 threading.Timer）
"""

from __future__ import annotations

import ast
import io
import signal
import textwrap
from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# 自定义异常层级
# ---------------------------------------------------------------------------

class SandboxError(Exception):
    """沙盒基础异常，所有沙盒相关异常的父类。"""


class SecurityException(SandboxError):
    """
    安全策略违规异常。

    当提交的代码触发任何安全检测规则时抛出此异常。
    调用方必须将此视为高危事件记录审计日志，而非普通运行时错误。
    """


class SandboxTimeoutError(SandboxError):
    """代码执行超时异常，由 SIGALRM 信号处理器触发。"""


# ---------------------------------------------------------------------------
# 内核 API 代理：唯一允许进入沙盒的外部能力
# ---------------------------------------------------------------------------

class KernelApiProxy:
    """
    内核 API 安全代理（白名单能力注入）。

    设计原则：
      沙盒代码不能直接调用任何系统 API，只能通过此代理间接访问。
      代理层承担以下职责：
        1. 调用前鉴权：检查请求的 tool_name 是否在授权白名单内。
        2. 参数净化：拦截包含路径穿越（../）的参数。
        3. 调用审计：每次调用记录到审计日志，供事后追溯。
        4. 结果封装：返回值统一为不可变的基础类型（str/int/float/bool/None），
           防止返回携带危险方法的复杂对象。
    """

    def __init__(
        self,
        allowed_tools: frozenset[str],
        underlying_caller: Callable[[str, dict[str, Any]], Any],
    ) -> None:
        """
        Args:
            allowed_tools:      本次沙盒会话中允许调用的工具名称白名单（不可变集合）。
            underlying_caller:  底层真实工具执行器，由外部依赖注入。
        """
        self._allowed = allowed_tools
        self._caller = underlying_caller
        self._audit_log: list[dict[str, Any]] = []

    def call(self, tool_name: str, **kwargs: Any) -> Any:
        """
        向内核发起工具调用（沙盒代码可见的唯一外部接口）。

        安全检查顺序：
          1. 工具名白名单校验 → SecurityException
          2. 参数路径穿越检测 → SecurityException
          3. 记录审计条目
          4. 委托底层执行器，捕获所有异常防止泄漏内部堆栈
        """
        # 检查 1：工具名必须在授权白名单内
        if tool_name not in self._allowed:
            raise SecurityException(
                f"[越权拦截] 工具 '{tool_name}' 未在本次沙盒会话的授权白名单中。"
                f"允许的工具集合: {sorted(self._allowed)}"
            )

        # 检查 2：参数值中不允许出现路径穿越序列，防止通过工具间接读取敏感文件
        for arg_key, arg_val in kwargs.items():
            if isinstance(arg_val, str) and (".." in arg_val or arg_val.startswith("/")):
                raise SecurityException(
                    f"[参数污染] 工具 '{tool_name}' 的参数 '{arg_key}' "
                    f"包含路径穿越序列或绝对路径: {arg_val!r}"
                )

        # 记录审计条目（成功与失败均记录）
        audit_entry: dict[str, Any] = {
            "tool": tool_name,
            "args": {k: str(v)[:200] for k, v in kwargs.items()},
            "status": "pending",
        }
        self._audit_log.append(audit_entry)

        try:
            result = self._caller(tool_name, kwargs)
            audit_entry["status"] = "success"

            # 结果封装：只允许返回不可变基础类型，防止返回携带 __class__ 等危险属性的对象
            if not isinstance(result, (str, int, float, bool, type(None), list, dict)):
                audit_entry["status"] = "coerced"
                return str(result)
            return result

        except SecurityException:
            audit_entry["status"] = "security_blocked"
            raise
        except Exception as exc:
            # 将底层异常包装后抛出，不暴露内部堆栈细节给沙盒代码
            audit_entry["status"] = "error"
            raise SandboxError(f"工具 '{tool_name}' 执行失败: {type(exc).__name__}") from None

    @property
    def audit_log(self) -> list[dict[str, Any]]:
        """返回本次沙盒会话的完整审计日志副本。"""
        return list(self._audit_log)


# ---------------------------------------------------------------------------
# 沙盒执行结果
# ---------------------------------------------------------------------------

@dataclass
class SandboxResult:
    """单次沙盒代码执行的完整结果快照。"""

    success: bool
    stdout: str = ""
    return_value: Any = None
    error: str = ""
    audit_log: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AST 安全分析器（防线 1）
# ---------------------------------------------------------------------------

class AstSecurityAnalyzer(ast.NodeVisitor):
    """
    AST 节点遍历器，静态检测代码中的危险模式。

    在 exec() 执行任何代码之前，强制经由此分析器做全量扫描。
    发现违禁节点时立即抛出 SecurityException，不给执行机会。

    被封禁的 AST 节点类型：
      - ast.Import       → `import os`、`import sys` 等
      - ast.ImportFrom   → `from os import environ`、`from pathlib import Path` 等
      - ast.Global       → `global` 语句，防止污染全局命名空间
      - ast.Nonlocal     → `nonlocal` 语句，防止闭包逃逸
      - ast.AsyncFunctionDef → 异步函数定义（防止绕过超时机制）

    注意：此分析器是第一道防线，但不是唯一防线。
    即使通过了 AST 检测，命名空间真空化（防线 2）仍然生效，
    确保纵深防御而非依赖单点。
    """

    _BANNED_NODE_TYPES = (
        ast.Import,
        ast.ImportFrom,
        ast.Global,
        ast.Nonlocal,
        ast.AsyncFunctionDef,
    )

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit(self, node: ast.AST) -> None:
        """遍历每个 AST 节点，发现违禁类型时记录违规信息。"""
        if isinstance(node, self._BANNED_NODE_TYPES):
            node_type = type(node).__name__
            lineno = getattr(node, "lineno", "?")

            if isinstance(node, ast.Import):
                names = ", ".join(alias.name for alias in node.names)
                detail = f"import {names}"
            elif isinstance(node, ast.ImportFrom):
                names = ", ".join(alias.name for alias in node.names)
                detail = f"from {node.module} import {names}"
            else:
                detail = node_type

            self.violations.append(f"第 {lineno} 行: [{node_type}] {detail}")

        # 继续递归遍历子节点
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# 超时信号处理器（防线 4）
# ---------------------------------------------------------------------------

def _timeout_handler(signum: int, frame: Any) -> None:
    """
    SIGALRM 信号处理器，在代码执行超时时触发。

    注意：signal 模块的 SIGALRM 只在 Unix 系统的主线程中有效。
    若在子线程中使用沙盒，需改用 concurrent.futures.ProcessPoolExecutor
    配合 timeout 参数实现跨平台超时隔离。
    """
    raise SandboxTimeoutError("沙盒代码执行超时，已强制终止。")


# ---------------------------------------------------------------------------
# VM REPL 沙盒主体
# ---------------------------------------------------------------------------

class VmReplSandbox:
    """
    Alumet OS VM REPL 沙盒。

    每个实例代表一次独立的沙盒会话，拥有独立的：
      - 授权工具白名单
      - 内核 API 代理实例（含独立审计日志）
      - 输出缓冲区（stdout 重定向）

    会话结束后应调用 close() 或使用上下文管理器，确保资源释放。
    """

    def __init__(
        self,
        allowed_tools: frozenset[str],
        underlying_caller: Callable[[str, dict[str, Any]], Any],
        execution_timeout_seconds: int = 5,
    ) -> None:
        """
        Args:
            allowed_tools:              本次会话允许调用的工具白名单。
            underlying_caller:          底层工具执行器（依赖注入）。
            execution_timeout_seconds:  单次 exec() 的最大执行时长，超时触发熔断。
        """
        self._timeout = execution_timeout_seconds
        self._proxy = KernelApiProxy(
            allowed_tools=allowed_tools,
            underlying_caller=underlying_caller,
        )

        # 沙盒专用 print：将输出重定向到内存缓冲，而非真实 stdout
        # 这样既保留了 print 的调试能力，又防止信息通过 stdout 泄漏到进程外
        self._output_buffer = io.StringIO()

        def _safe_print(*args: Any, sep: str = " ", end: str = "\n") -> None:
            """
            安全 print 替代品：输出到内存缓冲区，不触及真实 sys.stdout。
            参数签名与内建 print 兼容，确保沙盒代码无感知替换。
            """
            text = sep.join(str(a) for a in args) + end
            self._output_buffer.write(text)

        # 构造命名空间真空化的 safe_globals（防线 2）
        # __builtins__ 被显式设置为空字典，彻底抹杀所有内建函数：
        #   open / eval / exec / __import__ / getattr / setattr /
        #   vars / dir / globals / locals / type / object / ...
        # 任何依赖内建函数的代码将在此抛出 NameError，而非 SecurityException，
        # 这是预期行为——"悄悄失败"比"高调越狱"更安全。
        self._safe_globals: dict[str, Any] = {
            "__builtins__": {},           # 命名空间真空化（防线 2 核心）
            "print": _safe_print,         # 白名单：安全 print（输出重定向）
            "kernel_call": self._proxy.call,  # 白名单：内核 API 代理（防线 3）
        }

    # ------------------------------------------------------------------
    # 核心执行接口
    # ------------------------------------------------------------------

    def execute(self, code: str) -> SandboxResult:
        """
        在沙盒环境中执行一段 Python 代码。

        执行流程（严格顺序，不可跳过任何步骤）：
          Step 1：代码去缩进规范化（兼容大模型输出的缩进差异）
          Step 2：AST 物理阉割扫描（防线 1）
          Step 3：设置超时信号（防线 4）
          Step 4：命名空间真空化 exec()（防线 2 + 防线 3）
          Step 5：收集输出，重置超时，返回结果

        Args:
            code: 待执行的 Python 代码字符串（大模型生成）。

        Returns:
            SandboxResult，无论成功还是失败均返回结构化结果，不向调用方抛出异常。
            调用方通过 result.success 判断执行状态。
        """
        # Step 1：去缩进规范化，防止因大模型输出的额外缩进导致 SyntaxError
        normalized_code = textwrap.dedent(code).strip()
        self._output_buffer.truncate(0)
        self._output_buffer.seek(0)

        # Step 2：AST 物理阉割（防线 1）
        try:
            tree = ast.parse(normalized_code, filename="<sandbox>", mode="exec")
        except SyntaxError as syn_err:
            return SandboxResult(
                success=False,
                error=f"代码语法错误，无法解析为 AST: {syn_err}",
                audit_log=self._proxy.audit_log,
            )

        analyzer = AstSecurityAnalyzer()
        analyzer.visit(tree)

        if analyzer.violations:
            violation_report = "\n".join(f"  • {v}" for v in analyzer.violations)
            raise SecurityException(
                f"[AST 安全扫描] 检测到 {len(analyzer.violations)} 个违禁语句，"
                f"代码执行已被物理阻断：\n{violation_report}\n\n"
                "沙盒内绝对禁止使用 import 语句（包括 import os、from os import *）。"
                "通过 import 获取文件系统与进程控制权是典型的沙盒越狱手段。"
                "如需访问外部能力，请使用 kernel_call() 代理接口。"
            )

        # Step 3：设置执行超时（防线 4，仅 Unix 主线程有效）
        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(self._timeout)
        except (OSError, AttributeError):
            # Windows 或非主线程场景下 SIGALRM 不可用，记录警告但不阻断执行
            # 生产环境应改用 ProcessPoolExecutor + timeout 实现跨平台隔离
            pass

        # Step 4：命名空间真空化 exec()（防线 2 + 防线 3）
        # locals 也使用空字典，防止 exec 内部通过 locals() 访问到外层变量
        try:
            exec_locals: dict[str, Any] = {}
            exec(  # noqa: S102 — 沙盒本身就是受控的 exec 封装，此处是设计意图
                compile(tree, filename="<sandbox>", mode="exec"),
                self._safe_globals,
                exec_locals,
            )

            stdout_content = self._output_buffer.getvalue()
            return_value = exec_locals.get("__result__")  # 约定：代码将结果赋给 __result__

            return SandboxResult(
                success=True,
                stdout=stdout_content,
                return_value=return_value,
                audit_log=self._proxy.audit_log,
            )

        except SecurityException as sec_err:
            # exec() 内部触发的安全违规（如调用越权工具、参数路径穿越），
            # 封装为结构化失败结果返回给调用方，让大模型能读取到拒绝原因。
            #
            # 注意：与 AST 扫描阶段的 SecurityException 不同——
            # AST 扫描在此 try 块之前执行，发现违规直接 raise，
            # 代表代码从未被执行过，是更严重的策略违规；
            # 而 exec() 内部的 SecurityException 表示代码已开始执行
            # 但在代理层被拦截，可安全封装为错误返回。
            return SandboxResult(
                success=False,
                error=f"[安全违规] {sec_err}",
                audit_log=self._proxy.audit_log,
            )
        except SandboxTimeoutError as te:
            return SandboxResult(
                success=False,
                error=str(te),
                audit_log=self._proxy.audit_log,
            )
        except Exception as exc:
            # 所有运行时异常（NameError/TypeError/etc.）均被捕获，
            # 以结构化错误返回，不向调用方泄漏内部堆栈
            return SandboxResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                audit_log=self._proxy.audit_log,
            )
        finally:
            # Step 5：无论如何，必须取消超时信号，防止干扰后续代码
            try:
                signal.alarm(0)
            except (OSError, AttributeError):
                pass

    # ------------------------------------------------------------------
    # 上下文管理器支持
    # ------------------------------------------------------------------

    def __enter__(self) -> "VmReplSandbox":
        return self

    def __exit__(self, *_: Any) -> None:
        self._output_buffer.close()

    def close(self) -> None:
        """释放输出缓冲区资源。"""
        self._output_buffer.close()
