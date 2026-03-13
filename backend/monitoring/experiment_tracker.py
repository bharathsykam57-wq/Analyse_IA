import logging
import os
from datetime import datetime, timezone
from typing import Optional
import psycopg2
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def log_experiment_sync(
    run_id: str,
    user_id: str,
    task_type: str,
    question: str,
    answer: str,
    session_id: Optional[str] = None,
    dataset_rows: Optional[int] = None,
    dataset_columns: Optional[int] = None,
    best_model: Optional[str] = None,
    metrics: Optional[dict] = None,
    anomaly_count: Optional[int] = None,
    confidence_score: Optional[float] = None,
    latency_ms: Optional[float] = None,
    language: str = "fr",
) -> None:
    """Insert one experiment run row synchronously. Never raises."""
    try:
        db_url = os.getenv("DATABASE_URL", "")
        # Convert asyncpg URL to psycopg2 format
        conn_str = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO experiment_runs (
                id, user_id, session_id, task_type, question, answer_preview,
                dataset_rows, dataset_columns, best_model,
                accuracy, auc, f1, anomaly_count,
                confidence_score, latency_ms, language, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """, (
            run_id, user_id, session_id, task_type, question, answer[:200] if answer else None,
            dataset_rows, dataset_columns, best_model,
            metrics.get("Accuracy") if metrics else None,
            metrics.get("AUC") if metrics else None,
            metrics.get("F1") if metrics else None,
            anomaly_count,
            confidence_score, latency_ms, language,
            datetime.now(timezone.utc),
        ))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Experiment logged: {run_id} ({task_type})")
    except Exception as e:
        logger.warning(f"Experiment log failed (non-blocking): {e}")
