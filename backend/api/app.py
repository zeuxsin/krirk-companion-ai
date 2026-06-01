import yaml
import uuid
from pathlib import Path
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core.orchestrator import Orchestrator
from backend.api.websocket import handle_websocket


def load_config(path: str = "configs/config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_app() -> FastAPI:
    config = load_config()

    app = FastAPI(
        title="KRIRK Companion AI",
        description="Backend da Companion AI KRIRK — Fase 1 MVP",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config["server"]["cors_origins"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    orchestrator = Orchestrator(config)

    @app.get("/health")
    async def health():
        return {"status": "ok", **orchestrator.get_status()}

    @app.get("/api/personality")
    async def get_personality():
        return {
            "name": orchestrator.personality.name,
            "emotion": orchestrator.emotion.current_emotion,
        }

    @app.get("/api/memory/stats")
    async def memory_stats(user_id: str = "default"):
        return orchestrator.memory.get_stats(user_id)

    @app.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str):
        await handle_websocket(websocket, client_id, orchestrator)

    @app.websocket("/ws")
    async def websocket_anon(websocket: WebSocket):
        client_id = str(uuid.uuid4())[:8]
        await handle_websocket(websocket, client_id, orchestrator)

    return app
