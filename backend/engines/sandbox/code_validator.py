"""
code_validator.py — 2-layer security validation for agent-generated Python code.

Layer 1: AST static analysis (fast, no execution, no dependencies)
Layer 2: RestrictedPython compilation (whitelist-based, if available)

Never executes code — validation only.
"""

import ast
from dataclasses import dataclass, field

try:
    from RestrictedPython import compile_restricted  # type: ignore
    RESTRICTED_PYTHON_AVAILABLE = True
except ImportError:
    RESTRICTED_PYTHON_AVAILABLE = False


# ─── Blocklists ───────────────────────────────────────────────────────────────

BLOCKED_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "requests", "urllib",
    "http", "ftplib", "smtplib", "pathlib", "glob", "importlib", "ctypes",
    "mmap", "signal", "pty", "pickle", "shelve", "multiprocessing",
    "threading", "concurrent", "asyncio", "ssl", "builtins", "__builtins__",
}

BLOCKED_BUILTINS = {
    "exec", "eval", "compile", "__import__", "open", "input",
    "memoryview", "breakpoint", "vars", "dir", "globals", "locals",
    "getattr", "setattr", "delattr", "hasattr",
}

ALLOWED_MODULES = {
    "pandas", "numpy", "scipy", "sklearn", "matplotlib", "seaborn",
    "plotly", "statsmodels", "math", "statistics", "random", "datetime",
    "collections", "itertools", "functools", "typing", "json", "csv",
    "io", "re", "string", "time", "copy", "pprint",
}


# ─── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    is_valid: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.is_valid:
            return "Code passed validation"
        return f"Code rejected: {'; '.join(self.errors)}"


# ─── AST Visitor ──────────────────────────────────────────────────────────────

class SecurityVisitor(ast.NodeVisitor):
    """Walk the AST and collect all security violations.
    
    Traverses the Abstract Syntax Tree (AST) of Python code to detect dangerous
    patterns and blocked operations. Acts as Layer 1 of the 2-layer validation system.
    
    Violations detected:
    - Blocked module imports (os, sys, subprocess, requests, etc.)
    - Dangerous builtin calls (eval, exec, __import__, open, etc.)
    - System calls (os.system, subprocess.run, etc.)
    - Dunder attribute access (__class__, __globals__, etc.)
    
    Each violation is categorized as:
    - error: Fatal violation blocking execution
    - warning: Non-fatal issue flagged but allows execution
    """

    def __init__(self):
        self.errors = []
        self.warnings = []

    def visit_Import(self, node):
        """Check for blocked module imports (import X statement).
        
        Validates each imported module against blocklist and allowlist.
        Blocked modules pose security risks (network, system access, code execution).
        Unknown modules generate warnings (may indicate untested dependencies).
        
        Examples:
            import os → ERROR (blocked)
            import sklearn → OK (allowed)
            import my_lib → WARNING (unknown)
        """
        for alias in node.names:
            module = alias.name.split(".")[0]
            if module in BLOCKED_MODULES:
                self.errors.append(f"Blocked import: '{alias.name}'")
            elif module not in ALLOWED_MODULES:
                self.warnings.append(f"Unknown module: '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Check for blocked module imports (from X import Y statement).
        
        Similar to visit_Import() but handles 'from X import Y' syntax.
        Checks the source module (X) against blocklist and allowlist.
        
        Examples:
            from os import system → ERROR (blocked)
            from pandas import DataFrame → OK (allowed)
            from helpers import process → WARNING (unknown)
        """
        if node.module:
            module = node.module.split(".")[0]
            if module in BLOCKED_MODULES:
                self.errors.append(f"Blocked import: 'from {node.module}'")
            elif module not in ALLOWED_MODULES:
                self.warnings.append(f"Unknown module: '{node.module}'")
        self.generic_visit(node)

    def visit_Call(self, node):
        """Check for dangerous function/method calls (exec, eval, os.system, etc.).
        
        Detects two categories of dangerous calls:
        1. Direct builtin calls: eval(), exec(), __import__(), open()
           - Checked against BLOCKED_BUILTINS
        2. System method calls: os.system(), subprocess.run(), os.popen()
           - Checked by attribute name regardless of module
        
        Both categories block execution:
        - eval/exec: Execute arbitrary code (compromise)
        - open: File access (read/write)
        - system/run/popen: Shell execution (sandbox bypass)
        
        Examples:
            eval(code) → ERROR (blocked builtin)
            os.system('ls') → ERROR (blocked system call)
            subprocess.run(['cmd']) → ERROR (blocked system call)
        """
        # Block dangerous builtin calls: eval(), exec()
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_BUILTINS:
                self.errors.append(f"Blocked builtin: '{node.func.id}()'")
        # Block system calls: os.system(), subprocess.run()
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in {"system", "popen", "run", "call", "Popen"}:
                self.errors.append(f"Blocked system call: '.{node.func.attr}()'")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        """Check for dangerous dunder (double-underscore) attribute access.
        
        Dunder attributes are Python internals that enable sandbox escape:
        - __class__: Access to object's class (chain to hierarchy)
        - __globals__: Module namespace (read/modify variables)
        - __dict__: Object attributes (modify state)
        - __builtins__: Access dangerous functions
        - __code__: Function bytecode
        - __subclasses__: Class hierarchy traversal
        
        Blocking all dunders because:
        1. Implementation details (may change)
        2. Clever chaining can exploit obscure dunders
        3. False positives acceptable (legitimate code rarely uses dunders)
        
        Examples:
            obj.__class__ → ERROR (blocked dunder)
            func.__globals__ → ERROR (blocked dunder)
            x.__dict__['key'] → ERROR (blocked dunder)
        """
        # Block dunder access: __class__, __globals__
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self.errors.append(f"Blocked dunder access: '.{node.attr}'")
        self.generic_visit(node)

    def visit_Name(self, node):
        """Check for dangerous builtin function references (use without calling).
        
        Detects when blocked builtins are referenced (not just called):
        - Passing as argument: map(eval, code_list)
        - Storing in variable: dangerous = exec
        - Using in expression: if eval: ...
        
        Defense layer: A reference could be exploited by the agent later,
        even if the call itself is not in the original code.
        
        Complements visit_Call() which catches actual invocations.
        
        Examples:
            x = eval → ERROR (reference to blocked builtin)
            funcs = [exec, compile] → ERROR (reference in list)
            map(eval, data) → ERROR (passing builtin as argument)
        """
        if node.id in BLOCKED_BUILTINS:
            self.errors.append(f"Blocked builtin reference: '{node.id}'")
        self.generic_visit(node)


# ─── Public API ───────────────────────────────────────────────────────────────

def validate_code(code: str) -> ValidationResult:
    """
    Validate agent-generated Python code before sandbox execution.

    Args:
        code: Python source code string

    Returns:
        ValidationResult(is_valid, errors, warnings)
    """
    if not code or not code.strip():
        return ValidationResult(is_valid=False, errors=["Empty code"])

    # Layer 1: Parse to AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ValidationResult(is_valid=False, errors=[f"Syntax error: {e}"])

    # Layer 1: Walk AST
    visitor = SecurityVisitor()
    visitor.visit(tree)

    errors = list(visitor.errors)
    warnings = list(visitor.warnings)

    # Layer 2: RestrictedPython (if installed)
    if RESTRICTED_PYTHON_AVAILABLE:
        try:
            result = compile_restricted(code, filename="<agent>", mode="exec")
            if result is None:
                errors.append("RestrictedPython: compilation rejected")
        except Exception as e:
            errors.append(f"RestrictedPython: {e}")
    else:
        warnings.append("RestrictedPython not installed — AST-only validation active")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)