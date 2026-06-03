import json
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from backend.core.orchestrator import Orchestrator


class ConnectionManager:
    def __init__(self):
        self._active: dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, client_id: str):
        await ws.accept()
        self._active[client_id] = ws

    def disconnect(self, client_id: str):
        self._active.pop(client_id, None)

    async def send(self, client_id: str, data: dict):
        ws = self._active.get(client_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data, ensure_ascii=False))
            except Exception:
                self.disconnect(client_id)

    async def broadcast(self, data: dict):
        dead = []
        for cid, ws in self._active.items():
            try:
                await ws.send_text(json.dumps(data, ensure_ascii=False))
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)


manager = ConnectionManager()


async def handle_websocket(
    websocket: WebSocket,
    client_id: str,
    orchestrator: Orchestrator,
):
    await manager.connect(websocket, client_id)

    # Carrega histórico recente do usuário e envia ao frontend
    history = orchestrator.memory.get_recent_messages(
        client_id,
        limit=orchestrator._config["memory"]["short_term_limit"],
    )
    await manager.send(client_id, {
        "type": "connected",
        "history": history,   # [{role, content}, ...] — vazio na primeira vez
        "status": orchestrator.get_status(),
    })

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send(client_id, {"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = payload.get("type")

            if msg_type == "chat":
                content = payload.get("content", "").strip()
                if not content:
                    continue
                last_response = ""
                async for event in orchestrator.process_text(content, user_id=client_id):
                    await manager.send(client_id, event)
                    if event.get("type") == "response_complete":
                        last_response = event.get("content", "")
                # Extrai fatos em background — sem bloquear próximas mensagens
                if last_response:
                    asyncio.create_task(
                        orchestrator.extract_facts_bg(content, last_response, client_id)
                    )

            elif msg_type == "audio":
                audio_data = payload.get("data", "")
                if not audio_data:
                    continue
                async for event in orchestrator.process_audio(audio_data, user_id=client_id):
                    await manager.send(client_id, event)

            elif msg_type == "status":
                await manager.send(client_id, {
                    "type": "status_response",
                    **orchestrator.get_status(),
                })

            elif msg_type == "settings":
                key = payload.get("key")
                value = payload.get("value")
                if key == "tts_enabled":
                    orchestrator.tts.set_enabled(bool(value))
                    await manager.send(client_id, {"type": "ack", "key": key, "value": value})
                elif key == "voice":
                    orchestrator.tts.set_voice(str(value))
                    await manager.send(client_id, {"type": "ack", "key": key, "value": value})

            elif msg_type == "screenshot":
                prompt = payload.get("prompt", "Descreva o que você vê na minha tela.")
                async for event in orchestrator.process_screenshot(prompt, user_id=client_id):
                    await manager.send(client_id, event)

            elif msg_type == "memory_stats":
                stats = orchestrator.memory.get_stats(client_id)
                await manager.send(client_id, {"type": "memory_stats", **stats})

            else:
                await manager.send(client_id, {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
