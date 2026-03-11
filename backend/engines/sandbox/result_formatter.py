"""
result_formatter.py — Format sandbox execution results for the master agent.

Converts raw Docker output into structured, agent-readable responses.
Handles success, runtime errors, validation failures, and timeouts.
"""

from dataclasses import dataclass


@dataclass
class FormattedResult:
    """Structured result ready for agent consumption.
    
    Encapsulates sandbox execution results with both structured data (for
    programmatic handling) and human-readable French message (for display to users).
    
    Attributes:
        success: Whether code executed without fatal errors
        summary: One-line status summary for quick checking (e.g., "Execution succeeded")
        output: Full stdout from code execution (may be empty)
        error: Error message if execution failed (may be empty)
        execution_time: Wall-clock time spent in sandbox (seconds)
        warnings: List of non-fatal security validation warnings
    
    Usage:
        - Check 'success' flag first
        - Access 'output' for code results
        - Use 'error' for failure diagnostics
        - Call to_agent_message() for human-readable French output
    """
    success: bool
    summary: str            # One-line status for agent
    output: str             # Full stdout (may be empty)
    error: str              # Error message (may be empty)
    execution_time: float   # Seconds
    warnings: list          # Non-fatal validation warnings

    def to_dict(self) -> dict:
        """Convert FormattedResult to dictionary for JSON serialization.
        
        Useful for API responses, logging, or multi-process communication where
        the dataclass object needs to be converted to plain dict format.
        
        Returns:
            dict: Dictionary with keys matching FormattedResult fields:
                - success (bool): Execution status
                - summary (str): Status summary
                - output (str): Execution output
                - error (str): Error message
                - execution_time (float): Duration in seconds
                - warnings (list): Validation warnings
        """
        return {
            "success": self.success,
            "summary": self.summary,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "warnings": self.warnings,
        }

    def to_agent_message(self) -> str:
        """Format result as a human-readable French message for agent/user display.
        
        Generates a formatted message suitable for:
        - Display to end users in a user interface
        - Inclusion in agent's narrative response
        - Chat bot output formatting
        
        Format for success:
            ✅ Code exécuté en Xs.
            [Résultat: (output) or (Aucune sortie produite.)]
            [⚠️ Avertissements: warning1, warning2 (if any)]
        
        Format for failure:
            ❌ Échec de l'exécution.
            Erreur: (error message)
            [Avertissements: warning1, warning2 (if any)]
        
        Returns:
            str: Multi-line formatted message in French with emojis for visual clarity
        """
        if self.success:
            lines = [f"✅ Code exécuté en {self.execution_time}s."]
            if self.output:
                lines.append(f"\nRésultat :\n```\n{self.output}\n```")
            else:
                lines.append("\n(Aucune sortie produite.)")
            if self.warnings:
                lines.append(f"\n⚠️ Avertissements : {', '.join(self.warnings)}")
            return "\n".join(lines)
        else:
            lines = [f"❌ Échec de l'exécution."]
            if self.error:
                lines.append(f"Erreur : {self.error}")
            if self.warnings:
                lines.append(f"Avertissements : {', '.join(self.warnings)}")
            return "\n".join(lines)


def format_result(sandbox_result: dict) -> FormattedResult:
    """Convert raw sandbox_runner output into a FormattedResult.
    
    Transforms the raw dictionary returned from run_in_sandbox() into a
    structured FormattedResult object with formatted summary messages.
    
    Processing steps:
    1. Extract fields from sandbox_result dict
    2. Build human-readable one-line summary based on status
    3. Handle success case: include output line count
    4. Handle failure cases: detect reason (timeout, validation, runtime, Docker, etc.)
    5. Return FormattedResult ready for agent or user consumption
    
    Summary message logic:
    - Success: "Execution succeeded in Xs — N lines of output"
    - Timeout: "Execution timed out" (detected by "timed out" in error)
    - Validation failed: "Code rejected by security validator"
    - Runtime error: "Runtime error during execution"
    - Docker error: "Docker unavailable"
    - Generic failure: "Execution failed"
    
    Args:
        sandbox_result: dict returned from sandbox_runner.run_in_sandbox() with keys:
            - success (bool): Whether execution completed without errors
            - output (str): stdout from execution (may be empty)
            - error (str): Error message if failed (may be empty or None)
            - execution_time (float): Wall-clock time (seconds)
            - validation_warnings (list): Non-fatal security warnings

    Returns:
        FormattedResult: Structured result with:
            - Extracted fields
            - Formatted summary message
            - Ready for to_agent_message() or to_dict()
    """
    success = sandbox_result.get("success", False)
    output = sandbox_result.get("output", "").strip()
    error = sandbox_result.get("error") or ""
    execution_time = sandbox_result.get("execution_time", 0.0)
    warnings = sandbox_result.get("validation_warnings", [])

    # Build one-line summary
    if success:
        summary = f"Execution succeeded in {execution_time}s"
        if output:
            summary += f" — {len(output.splitlines())} lines of output"
    else:
        if "timed out" in error.lower():
            summary = "Execution timed out"
        elif "validation failed" in error.lower():
            summary = "Code rejected by security validator"
        elif "runtime error" in error.lower():
            summary = "Runtime error during execution"
        elif "docker" in error.lower():
            summary = "Docker unavailable"
        else:
            summary = "Execution failed"

    return FormattedResult(
        success=success,
        summary=summary,
        output=output,
        error=error,
        execution_time=execution_time,
        warnings=warnings,
    )