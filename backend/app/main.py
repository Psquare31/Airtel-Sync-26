import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.data.loader import get_dataset
from app.db import get_engine
from app.graph.journey import get_graph
from app.routers import backoffice, journey, misc
from app.services.llm import get_router
from app.services.retention import purge_expired

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()
app = FastAPI(title="Udyam Digital API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(journey.router)
app.include_router(misc.router)
app.include_router(backoffice.router)


@app.on_event("startup")
def startup() -> None:
    get_dataset()
    get_engine()
    get_graph()
    purge_expired()


@app.get("/health")
@app.head("/health")
def health():
    router = get_router()
    return {
        "ok": True,
        "env": settings.env,
        "db": "postgres" if settings.database_url else "sqlite",
        "llm_configured": router.available(),
        "models": router.status(settings.chat_models),
    }
