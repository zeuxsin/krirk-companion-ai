import yaml
from pathlib import Path
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.core.orchestrator import Orchestrator
from backend.core.proactive import ProactiveMonitor
from backend.api.websocket import handle_websocket, manager as ws_manager, set_proactive_monitor


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

    # Monitor proativo — inicia loop de observação de tela e Spotify
    proactive_cfg = config.get("proactive", {"enabled": False})
    proactive_monitor = ProactiveMonitor(orchestrator, ws_manager, proactive_cfg)

    @app.on_event("startup")
    async def _startup():
        set_proactive_monitor(proactive_monitor)
        await proactive_monitor.start()

    @app.get("/health")
    async def health():
        return {"status": "ok", **orchestrator.get_status()}

    @app.get("/api/system")
    async def system_stats():
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "cpu": psutil.cpu_percent(interval=0.1),
                "ram_used": round(mem.used / 1e9, 2),
                "ram_total": round(mem.total / 1e9, 2),
                "ram_percent": mem.percent,
            }
        except ImportError:
            return {"cpu": 0, "ram_used": 0, "ram_total": 0, "ram_percent": 0}

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

    @app.get("/api/settings")
    async def get_settings():
        return {
            "tts_enabled":       orchestrator.tts._enabled,
            "tts_voice":         orchestrator.tts._voice,
            "stt_enabled":       orchestrator.stt._enabled,
            "ollama_model":      orchestrator._ollama_config["model"],
            "temperature":       orchestrator._ollama_config["temperature"],
            "proactive_enabled": proactive_monitor._enabled,
            "krirk_name":        orchestrator.personality.name,
            "personality_notes": orchestrator.personality.personality_notes,
        }

    @app.post("/api/settings")
    async def update_settings(request: Request):
        body = await request.json()
        if "tts_enabled"       in body:
            orchestrator.tts.set_enabled(bool(body["tts_enabled"]))
        if "tts_voice"         in body:
            orchestrator.tts.set_voice(str(body["tts_voice"]))
        if "stt_enabled"       in body:
            orchestrator.stt.set_enabled(bool(body["stt_enabled"]))
        if "ollama_model"      in body:
            orchestrator._ollama_config["model"] = str(body["ollama_model"])
        if "temperature"       in body:
            orchestrator._ollama_config["temperature"] = float(body["temperature"])
        if "proactive_enabled" in body:
            proactive_monitor.set_enabled(bool(body["proactive_enabled"]))
        if "krirk_name"        in body:
            orchestrator.personality.set_name(str(body["krirk_name"]))
        if "personality_notes" in body:
            orchestrator.personality.set_notes(str(body["personality_notes"]))
        return {"ok": True}

    @app.websocket("/ws")
    async def websocket_anon(websocket: WebSocket):
        # ID fixo "default" — app single-user, garante que memórias persistem entre sessões
        await handle_websocket(websocket, "default", orchestrator)

    return app
