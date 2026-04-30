from app.logging_config import setup_logging

# Initialize logging before anything else
setup_logging()

# Attach SSE streaming handler immediately after base logging is ready
from app.core.logging_streamer import setup_streaming_handler
setup_streaming_handler()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router as api_router
from app.api.library_endpoints import router as library_router
from app.core.auth import verify_clerk_token
from app.core.config import settings
from app.db.database import Base, engine
import app.db.models  # noqa: F401 — ensures all models are registered before create_all

import uvicorn

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup; release resources on shutdown."""
    logger.info("Startup: creating database tables if not exist...")
    Base.metadata.create_all(bind=engine)
    logger.info("Startup: database ready.")
    yield
    logger.info("Shutdown: disposing DB engine.")
    engine.dispose()


app = FastAPI(title="EstudoHub Pro API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(library_router, prefix="/api/v1/biblioteca", tags=["Biblioteca"])


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {"status": "healthy", "service": "backend"}


@app.get("/api/v1/me", tags=["Auth"])
async def me(payload: dict = Depends(verify_clerk_token)) -> dict:
    """Retorna o perfil do usuário autenticado via JWT do Clerk."""
    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "session_id": payload.get("sid"),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
