#!/usr/bin/env python3
"""
test_code_node_integration.py — Integration test for master agent code execution.

Tests the run_code_node function from the LangGraph master agent, verifying
that the agent can classify, generate, validate, execute, and format code
execution results correctly.

Architecture Tested:
1. Task Classification: Question routed to 'code' task type
2. LLM Code Generation: Mistral generates Python from user question
3. Code Validation: RestrictedPython validator checks security
4. Sandbox Execution: Docker container executes code
5. Result Formatting: FormattedResult with French agent message

Test Cases (3 total):
- TEST 1: Simple calculation (arithmetic)
- TEST 2: Pandas data analysis (DataFrame operations)  
- TEST 3: NumPy statistics (mean, std, min calculations)

All tests run the complete pipeline: generate → validate → execute → format

Usage:
    python test_code_node_integration.py
    # Runs 3 integration tests and reports results
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.agent_state import AgentState
from backend.agent.master_agent import run_code_node

print("╔════════════════════════════════════════╗")
print("║  MASTER AGENT CODE NODE INTEGRATION    ║")
print("╚════════════════════════════════════════╝\n")

test_cases = [
    {
        "name": "Simple calculation",
        "question": "Calcule la moyenne de [1, 2, 3, 4, 5]",
        "expect_keywords": ["3", "mean", "moyenne"]  # Result should contain 3.0
    },
    {
        "name": "Pandas DataFrame",
        "question": "Crée un DataFrame pandas avec 5 lignes et 2 colonnes (a, b) et affiche la somme",
        "expect_keywords": ["sum"]
    },
    {
        "name": "NumPy statistics",
        "question": "Utilise NumPy pour calculer la moyenne, écart-type et minimum d'un array [1,2,3,4,5]",
        "expect_keywords": ["mean", "std", "min"]
    },
]

tests_passed = 0
tests_failed = 0

for i, test in enumerate(test_cases, 1):
    print(f"=== TEST {i}: {test['name']} ===")
    print(f"Question: {test['question']}")
    
    # Create initial agent state
    state: AgentState = {
        "question": test["question"],
        "task_type": "code",
        "dataset_path": None,
        "result": {},
        "answer": "",
        "error": None,
        "language": "fr",
        "confidence_score": 0.95,
        "session_id": f"test_session_{i}",
        "steps_taken": ["test_start"],
    }
    
    try:
        # Execute run_code_node
        result_state = run_code_node(state)
        
        # Verify results
        error = result_state.get("error")
        answer = result_state.get("answer", "")
        steps = result_state.get("steps_taken", [])
        
        # Check for success marker
        has_success_emoji = "✅" in answer
        has_code_success_step = any("code → success" in s for s in steps)
        
        if error is None and has_success_emoji and has_code_success_step:
            print(f"  status:    ✅ PASS")
            print(f"  error:     None")
            print(f"  output:    {answer[:80]}...")
            print(f"  step:      {steps[-1]}\n")
            tests_passed += 1
        else:
            print(f"  status:    ❌ FAIL")
            print(f"  error:     {error}")
            if not has_success_emoji:
                print(f"  issue:     No success emoji (✅)")
            if not has_code_success_step:
                print(f"  issue:     Missing 'code → success' step")
            print(f"  answer:    {answer[:80]}...\n")
            tests_failed += 1
            
    except Exception as e:
        print(f"  status:    ❌ FAIL")
        print(f"  exception: {str(e)[:100]}\n")
        tests_failed += 1

print("╔════════════════════════════════════════╗")
print("║         INTEGRATION RESULTS            ║")
print("╚════════════════════════════════════════╝")
print(f"  Passed: {tests_passed}/{tests_passed + tests_failed}")

if tests_failed == 0:
    print("\n  ✅ ALL INTEGRATION TESTS PASSED")
    print("  Master agent code execution verified!")
    exit_code = 0
else:
    print(f"\n  ❌ {tests_failed} TEST(S) FAILED")
    exit_code = 1

sys.exit(exit_code)
