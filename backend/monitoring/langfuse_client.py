import os
import time
import logging
from functools import wraps
from typing import Optional, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Lazy singleton — only initialised once
_langfuse = None

def get_langfuse():
    global _langfuse
    if _langfuse is None:
        try:
            from langfuse import Langfuse
            _langfuse = Langfuse(
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            )
        except Exception as e:
            logger.warning(f"Langfuse init failed — monitoring disabled: {e}")
            _langfuse = None
    return _langfuse


def trace_llm_call(
    name: str,
    input_text: str,
    output_text: str,
    model: str = "mistral-nemo",
    latency_ms: Optional[float] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Log a single LLM call to Langfuse."""
    lf = get_langfuse()
    if lf is None:
        return
    try:
        trace = lf.trace(
            name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
        )
        trace.generation(
            name=name,
            model=model,
            input=input_text,
            output=output_text,
            end_time=None,
            metadata={
                "latency_ms": latency_ms,
                **(metadata or {}),
            },
        )
        lf.flush()
    except Exception as e:
        logger.warning(f"Langfuse trace failed: {e}")


def trace_analysis(
    user_id: str,
    session_id: str,
    question: str,
    answer: str,
    task_type: str,
    confidence_score: float,
    dataset_rows: Optional[int] = None,
    best_model: Optional[str] = None,
    latency_ms: Optional[float] = None,
) -> None:
    """Log a full analysis run to Langfuse."""
    lf = get_langfuse()
    if lf is None:
        return
    try:
        trace = lf.trace(
            name=f"analysis_{task_type}",
            user_id=user_id,
            session_id=session_id,
            input=question,
            output=answer,
            metadata={
                "task_type": task_type,
                "confidence_score": confidence_score,
                "dataset_rows": dataset_rows,
                "best_model": best_model,
                "latency_ms": latency_ms,
            },
        )
        lf.flush()
        logger.info(f"Langfuse trace logged: {task_type} for user {user_id}")
    except Exception as e:
        logger.warning(f"Langfuse analysis trace failed: {e}")


def flush():
    """Flush all pending traces — call on app shutdown."""
    lf = get_langfuse()
    if lf:
        try:
            lf.flush()
        except Exception:
            pass
