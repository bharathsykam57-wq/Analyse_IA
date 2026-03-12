# backend/api/main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import time
import os
from dotenv import load_dotenv
from backend.api.routes.health import router as health_router
from backend.api.auth.router import router as auth_router
from backend.api.routes.files import router as files_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"
DOCS_URL = None if IS_PRODUCTION else "/docs"
REDOC_URL = None if IS_PRODUCTION else "/redoc"

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Analyse_IA API starting — environment: {ENVIRONMENT}")
    yield
    logger.info("Analyse_IA API shutting down...")


app = FastAPI(
    title="Analyse_IA",
    description="Votre Data Scientist Autonome — API",
    version="0.5.0",
    lifespan=lifespan,
    docs_url=DOCS_URL,
    redoc_url=REDOC_URL,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time_ms = (time.time() - start_time) * 1000

    logger.info(
        f"{request.method} {request.url.path} "
        f"→ {response.status_code} "
        f"({process_time_ms:.2f}ms)"
    )

    # Expose timing to frontend/debugging tools
    response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
    return response


# Register routes
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(files_router)


@app.get("/")
async def root():
    return {
        "app": "Analyse_IA",
        "version": "0.5.0",
        "status": "running",
        "environment": ENVIRONMENT,
        "phase": 5,
    }