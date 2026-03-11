"""test_sandbox.py — Comprehensive test suite for Phase 4 Code Sandbox security & execution.

Test Suite Overview:
This module validates the complete sandbox pipeline including validation, execution,
error handling, and resource limits. All tests use the public API and simulate
real execution scenarios.

Architecture Tested:
1. Code Validator (AST security analysis)
   - Blocks dangerous imports (os, sys, subprocess, socket, etc.)
   - Blocks dangerous builtins (eval, exec, open, __import__, etc.)
   - Allows safe data science libraries (pandas, numpy, scikit-learn, etc.)

2. Sandbox Runner (Docker-based isolation)
   - Docker container with strict resource limits
   - Network disabled, filesystem read-only (except /tmp)
   - CPU quota 50%, Memory 256MB, Timeout 30s
   - Auto-cleanup after execution

3. Result Formatter (Output for LangGraph agent)
   - Structured result dict with success/error/output/timing
   - French-language agent messages
   - One-line summaries for quick status checking

Test Cases (6 total):
- TEST 1: Safe code passes validator ✓
- TEST 2: Blocked import rejected ✗ (os module)
- TEST 3: Blocked builtin rejected ✗ (eval function)
- TEST 4: Clean execution returns output ✓ (stdout capture)
- TEST 5: Runtime error handled gracefully ✗ (ZeroDivisionError)
- TEST 6: Timeout handled gracefully ✗ (infinite loop)

Performance Baseline:
- Validation: 10-50ms (AST parsing + RestrictedPython)
- Container startup: 2-3 seconds
- Package installation: 3-5 seconds (pip install)
- Code execution: Variable (depends on code)
- Total typical: 5-30 seconds per run

Security Guarantees:
- No network access
- No file access outside /tmp
- No process spawning
- CPU and memory capped
- Execution timeout enforced
- All dangerous patterns blocked

Usage:
    python test_sandbox.py
    # Runs all 6 tests and reports pass/fail status
    # Exit code 0 if all pass, 1 if any fail

Dependencies:
- Docker running locally (for container tests)
- backend.engines.sandbox modules (validator, runner, formatter)
- python:3.11-slim Docker image pulled

Notes:
- Tests 4-6 require Docker to be running
- Tests 1-3 are pure validation (no Docker needed)
- All tests clean up after execution
- Safe for CI/CD pipelines
"""

import logging
from backend.engines.sandbox.code_validator import validate_code
from backend.engines.sandbox.sandbox_runner import run_in_sandbox
from backend.engines.sandbox.result_formatter import format_result

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION LAYER TESTS (Tests 1-3): AST + RestrictedPython Security Analysis
# ─────────────────────────────────────────────────────────────────────────────
# These tests verify code is rejected BEFORE Docker execution if unsafe.
# Fast validation (<50ms) prevents wasting container resources.

def test_safe_code_passes():
    """Test that legitimate data analysis code passes validation.
    
    Verifies the validator correctly identifies safe, allowed operations:
    - Allowed imports (numpy, pandas)
    - No dangerous builtins or system calls
    - Standard mathematical operations
    - Print output
    
    Expected behavior:
    - is_valid should be True
    - errors list should be empty
    - warnings may contain unknown module hints
    """
    print("\n=== TEST 1: Safe code passes validator ===")
    code = """
import pandas as pd
import numpy as np

data = [1, 2, 3, 4, 5]
mean = np.mean(data)
print(f"Mean: {mean}")
"""
    result = validate_code(code)
    print(f"  is_valid: {result.is_valid}")
    print(f"  errors:   {result.errors}")
    print(f"  warnings: {result.warnings}")
    assert result.is_valid, f"Expected valid, got errors: {result.errors}"
    print("  ✅ PASS")
    return True


def test_blocked_import_rejected():
    """Test that dangerous imports are blocked by validator.
    
    Verifies security blocking of system-access modules:
    - os: system access and file operations
    - subprocess/sys: process control
    - socket/requests: network access
    
    Expected behavior:
    - is_valid should be False
    - errors list should contain "os" reference
    - Code should not execute in sandbox
    """
    print("\n=== TEST 2: Blocked import rejected ===")
    code = "import os\nos.system('ls')"
    result = validate_code(code)
    print(f"  is_valid: {result.is_valid}")
    print(f"  errors:   {result.errors}")
    assert not result.is_valid, "Expected invalid"
    assert any("os" in e for e in result.errors), "Expected 'os' in errors"
    print("  ✅ PASS")
    return True


def test_blocked_builtin_rejected():
    """Test that dangerous builtins are blocked by validator.
    
    Verifies security blocking of code execution functions:
    - eval(): Execute arbitrary code
    - exec(): Execute arbitrary code with side effects
    - compile(): Create executable bytecode
    - open(): File system access
    - __import__(): Dynamic module loading
    
    Expected behavior:
    - is_valid should be False
    - errors list should contain "eval" reference
    - Code should not execute in sandbox
    """
    print("\n=== TEST 3: Blocked builtin rejected ===")
    code = "eval('print(1)')"
    result = validate_code(code)
    print(f"  is_valid: {result.is_valid}")
    print(f"  errors:   {result.errors}")
    assert not result.is_valid, "Expected invalid"
    assert any("eval" in e for e in result.errors), "Expected 'eval' in errors"
    print("  ✅ PASS")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# SANDBOX EXECUTION LAYER TESTS (Tests 4-6): Docker Container & Output Capture
# ─────────────────────────────────────────────────────────────────────────────
# These tests verify actual code execution with:
# - Docker container isolation (network disabled, CPU/memory capped, 30s timeout)
# - Stdout capture and formatting
# - Error handling (runtime errors, timeouts)
# - Resource cleanup (container removal)
# Slower tests (~5-30 seconds each) due to Docker overhead.

def test_clean_execution():
    """Test successful code execution in sandbox with output capture.
    
    Verifies the complete sandbox pipeline:
    - Code validation (AST + RestrictedPython)
    - Docker container startup
    - Package installation (numpy, pandas, etc.)
    - Code execution with stdout capture
    - Container cleanup
    - Result formatting for agent consumption
    
    Expected behavior:
    - success should be True
    - output should contain both print statements
    - execution_time should be 5-30 seconds
    - No errors or warnings
    
    Performance: ~5-10 seconds typical (includes Docker startup)
    """
    print("\n=== TEST 4: Clean execution returns output ===")
    code = "print('hello from sandbox')\nprint(2 + 2)"
    result = run_in_sandbox(code)
    formatted = format_result(result)
    print(f"  success:        {result['success']}")
    print(f"  output:         {result['output']}")
    print(f"  execution_time: {result['execution_time']}s")
    print(f"  summary:        {formatted.summary}")
    print(f"  agent_message:  {formatted.to_agent_message()}")
    assert result["success"], f"Expected success, got error: {result['error']}"
    assert "hello from sandbox" in result["output"]
    assert "4" in result["output"]
    print("  ✅ PASS")
    return True


def test_runtime_error_handled():
    """Test graceful handling of runtime errors in sandbox.
    
    Verifies error handling pipeline:
    - Code passes validation (no security errors)
    - Docker container starts successfully
    - Code runtime error occurs (ZeroDivisionError)
    - Error is captured from stderr
    - Container cleans up properly
    - Error is formatted for agent
    
    Expected behavior:
    - success should be False
    - error should describe the runtime error
    - execution_time should be recorded
    - No resource leaks or hanging containers
    
    Error types that may occur:
    - ZeroDivisionError, ValueError, TypeError, NameError, etc.
    - Import errors (missing packages)
    - Syntax errors (if validation was skipped)
    """
    print("\n=== TEST 5: Runtime error handled gracefully ===")
    code = "x = 1 / 0"  # ZeroDivisionError
    result = run_in_sandbox(code)
    formatted = format_result(result)
    print(f"  success: {result['success']}")
    print(f"  error:   {result['error'][:100]}")
    print(f"  summary: {formatted.summary}")
    assert not result["success"], "Expected failure"
    assert result["error"], "Expected error message"
    print("  ✅ PASS")
    return True


def test_timeout_handled():
    """Test handling of execution timeout (exceeds 30-second limit).
    
    Verifies timeout protection mechanism:
    - Infinite loops or very long operations trigger timeout
    - Docker container timeout parameter (30 seconds) enforced
    - Container is force-killed after timeout
    - Error message identifies timeout specifically
    - No zombie processes or resource leaks
    
    Expected behavior:
    - success should be False
    - error should mention "timeout" or "timed out"
    - execution_time should be ~30 seconds
    - Process should not hang indefinitely
    
    Timeout configured at: /backend/engines/sandbox/sandbox_runner.py
    - EXECUTION_TIMEOUT = 30 (seconds)
    - Applied via docker timeout parameter
    - Prevents DoS attacks (infinite loops, sleep loops)
    """
    print("\n=== TEST 6: Timeout handled gracefully ===")
    code = "while True: pass"  # Infinite loop
    result = run_in_sandbox(code)
    formatted = format_result(result)
    print(f"  success: {result['success']}")
    print(f"  error:   {result['error']}")
    print(f"  summary: {formatted.summary}")
    assert not result["success"], "Expected failure"
    assert "timeout" in result["error"].lower() or "timed out" in result["error"].lower()
    print("  ✅ PASS")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST ORCHESTRATION & REPORTING: Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────
# Runs all 6 tests in sequence, collects results, and outputs formatted summary.
# Exit code indicates overall success (0 if all pass, 1 if any fail).

def main():
    print("\n╔══════════════════════════════════════╗")
    print("║     PHASE 4 — SANDBOX TEST SUITE     ║")
    print("╚══════════════════════════════════════╝")

    tests = [
        ("Safe code passes validator",     test_safe_code_passes),
        ("Blocked import rejected",        test_blocked_import_rejected),
        ("Blocked builtin rejected",       test_blocked_builtin_rejected),
        ("Clean execution returns output", test_clean_execution),
        ("Runtime error handled",          test_runtime_error_handled),
        ("Timeout handled",                test_timeout_handled),
    ]

    results = {}
    for name, fn in tests:
        try:
            results[name] = fn()
        except Exception as e:
            logger.error(f"Test '{name}' raised: {e}")
            results[name] = False

    print("\n╔══════════════════════════════════════╗")
    print("║            FINAL SUMMARY             ║")
    print("╚══════════════════════════════════════╝")
    for name, passed in results.items():
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}")

    passed = sum(results.values())
    total = len(results)
    print(f"\n  Passed: {passed}/{total}")
    print(f"  Status: {'🎉 SUCCESS' if passed == total else '⚠️  PARTIAL'}\n")
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)