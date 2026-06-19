import json
import yaml
from pathlib import Path
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.core.orchestrator import Orchestrator
from backend.core.proactive import ProactiveMonitor
from backend.api.websocket import handle_websocket, manager as ws_manager, set_proactive_monitor

_SETTINGS_PATH = Path("data/settings.json")


def load_config(path: str = "configs/config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_saved_settings() -> dict:
    if _SETTINGS_PATH.exists():
        try:
            return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_settings(patch: dict) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    current = _load_saved_settings()
    current.update(patch)
    _SETTINGS_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


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
        # Aplica configurações salvas em sessões anteriores
        saved = _load_saved_settings()
        if saved:
            if "tts_enabled"       in saved: orchestrator.tts.set_enabled(bool(saved["tts_enabled"]))
            if "tts_voice"         in saved: orchestrator.tts.set_voice(str(saved["tts_voice"]))
            if "stt_enabled"       in saved: orchestrator.stt.set_enabled(bool(saved["stt_enabled"]))
            if "proactive_enabled" in saved: proactive_monitor.set_enabled(bool(saved["proactive_enabled"]))
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

    @app.get("/api/memory")
    async def get_memory(user_id: str = "default"):
        """Retorna todos os dados de memória: stats, perfil, fatos e KG."""
        stats = orchestrator.memory.get_stats(user_id)
        kg_stats = orchestrator.memory.kg.get_stats(user_id)
        stats["kg_entities"] = kg_stats["entities"]
        stats["kg_relations"] = kg_stats["relations"]
        return {
            "stats":        stats,
            "profile":      orchestrator.memory.get_profile(user_id),
            "facts":        orchestrator.memory.get_facts(user_id, limit=200),
            "kg_relations": orchestrator.memory.kg.get_relations(user_id, limit=500),
        }

    @app.put("/api/memory/profile")
    async def update_profile(request: Request):
        body = await request.json()
        user_id = body.get("user_id", "default")
        orchestrator.memory.update_profile(user_id, body["profile"])
        return {"ok": True}

    @app.delete("/api/memory/fact")
    async def delete_fact(request: Request):
        body = await request.json()
        user_id = body.get("user_id", "default")
        orchestrator.memory.delete_fact(user_id, body["fact"])
        return {"ok": True}

    @app.delete("/api/memory/kg-relation")
    async def delete_kg_relation(request: Request):
        body = await request.json()
        user_id = body.get("user_id", "default")
        orchestrator.memory.kg.delete_relation(
            user_id,
            body["entity_from"],
            body["relation"],
            body["entity_to"],
        )
        return {"ok": True}

    @app.delete("/api/memory/all")
    async def clear_memory(user_id: str = "default"):
        orchestrator.memory.clear_all(user_id)
        return {"ok": True}

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
        to_persist: dict = {}

        if "tts_enabled"       in body:
            val = bool(body["tts_enabled"])
            orchestrator.tts.set_enabled(val)
            to_persist["tts_enabled"] = val
        if "tts_voice"         in body:
            val = str(body["tts_voice"])
            orchestrator.tts.set_voice(val)
            to_persist["tts_voice"] = val
        if "stt_enabled"       in body:
            val = bool(body["stt_enabled"])
            orchestrator.stt.set_enabled(val)
            to_persist["stt_enabled"] = val
        if "ollama_model"      in body:
            orchestrator._ollama_config["model"] = str(body["ollama_model"])
        if "temperature"       in body:
            orchestrator._ollama_config["temperature"] = float(body["temperature"])
        if "proactive_enabled" in body:
            val = bool(body["proactive_enabled"])
            proactive_monitor.set_enabled(val)
            to_persist["proactive_enabled"] = val
        if "krirk_name"        in body:
            orchestrator.personality.set_name(str(body["krirk_name"]))
        if "personality_notes" in body:
            orchestrator.personality.set_notes(str(body["personality_notes"]))

        if to_persist:
            _save_settings(to_persist)

        return {"ok": True}

    @app.websocket("/ws")
    async def websocket_anon(websocket: WebSocket):
        # ID fixo "default" — app single-user, garante que memórias persistem entre sessões
        await handle_websocket(websocket, "default", orchestrator)

    return app
