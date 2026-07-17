"""
backend/integrations/telegram_bridge.py
A Krirk no celular via Telegram — bot oficial, long polling, 100% local-first.

Arquitetura:
  • Roda como asyncio.Task DENTRO do backend (igual ao ProactiveMonitor) —
    acesso direto ao orchestrator, sem HTTP loopback.
  • Long polling (getUpdates): o PC conecta PARA FORA; nada exposto.
  • Sem dependências novas: usa httpx (já instalado via openai) direto na Bot API.

Segurança:
  • Token vem do .env (TELEGRAM_BOT_TOKEN) — nunca do config.yaml.
  • Auto-bind: o PRIMEIRO chat que enviar /start vira o dono (persistido em
    data/settings.json como telegram_owner_chat_id). Qualquer outro chat é
    ignorado silenciosamente. Para trocar o dono, apague a chave do settings.

Recursos:
  • Texto → process_text (pipeline completo: tools, memória, personalidade)
  • Voice note do usuário → process_audio (STT Whisper local)
  • Resposta com áudio TTS (sendAudio) quando o TTS está ligado
  • Mensagens espontâneas (proativo/reflexão) encaminhadas ao dono
"""
import asyncio
import base64
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.orchestrator import Orchestrator

_SETTINGS_PATH = Path("data/settings.json")
_TG_MSG_LIMIT = 4096


def split_message(text: str, limit: int = _TG_MSG_LIMIT) -> list[str]:
    """Divide mensagens longas respeitando o limite do Telegram (por parágrafo)."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for para in text.split("\n"):
        candidate = f"{current}\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                parts.append(current)
            # Parágrafo sozinho maior que o limite → corta duro
            while len(para) > limit:
                parts.append(para[:limit])
                para = para[limit:]
            current = para
    if current:
        parts.append(current)
    return parts


def extract_message(update: dict) -> dict | None:
    """
    Extrai o essencial de um update do Telegram.
    Retorna {"chat_id", "text"?, "voice_file_id"?, "name"} ou None se irrelevante.
    """
    msg = update.get("message")
    if not isinstance(msg, dict):
        return None
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return None
    out: dict = {
        "chat_id": chat_id,
        "name": (msg.get("from") or {}).get("first_name", ""),
    }
    text = (msg.get("text") or "").strip()
    voice = msg.get("voice") or msg.get("audio")
    if text:
        out["text"] = text
    elif isinstance(voice, dict) and voice.get("file_id"):
        out["voice_file_id"] = voice["file_id"]
    else:
        return None  # sticker/foto/etc — ignora por ora
    return out


class TelegramBridge:
    def __init__(self, orchestrator: "Orchestrator", token: str):
        self._orch = orchestrator
        self._token = token
        self._api = f"https://api.telegram.org/bot{token}"
        self._offset = 0
        self._owner_chat_id: int | None = self._load_owner()
        self._running = False

    # ── Persistência do dono ──────────────────────────────────────────────────

    def _load_owner(self) -> int | None:
        try:
            if _SETTINGS_PATH.exists():
                data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
                owner = data.get("telegram_owner_chat_id")
                return int(owner) if owner else None
        except Exception:
            pass
        return None

    def _save_owner(self, chat_id: int) -> None:
        try:
            _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8")) if _SETTINGS_PATH.exists() else {}
            data["telegram_owner_chat_id"] = chat_id
            _SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[KRIRK][telegram] Falha ao salvar dono: {e}")

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _client(self, timeout: float = 60.0):
        import ssl

        import httpx
        try:
            import truststore
            ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            ctx = ssl.create_default_context()
        return httpx.AsyncClient(timeout=timeout, verify=ctx)

    async def _call(self, method: str, http_timeout: float = 30.0, **payload) -> dict:
        async with self._client(http_timeout) as client:
            r = await client.post(f"{self._api}/{method}", json=payload)
            return r.json()

    async def _send_text(self, chat_id: int, text: str) -> None:
        for part in split_message(text):
            await self._call("sendMessage", chat_id=chat_id, text=part)

    async def _send_audio(self, chat_id: int, audio_b64: str) -> None:
        """Envia o áudio TTS (MP3) como mensagem de áudio."""
        try:
            audio = base64.b64decode(audio_b64)
            async with self._client(60.0) as client:
                await client.post(
                    f"{self._api}/sendAudio",
                    data={"chat_id": str(chat_id), "title": "Krirk"},
                    files={"audio": ("krirk.mp3", audio, "audio/mpeg")},
                )
        except Exception as e:
            print(f"[KRIRK][telegram] Falha ao enviar áudio: {e}")

    async def _download_voice(self, file_id: str) -> str | None:
        """Baixa uma voice note e retorna base64 (para o STT)."""
        try:
            info = await self._call("getFile", file_id=file_id)
            path = (info.get("result") or {}).get("file_path")
            if not path:
                return None
            async with self._client(60.0) as client:
                r = await client.get(f"https://api.telegram.org/file/bot{self._token}/{path}")
                return base64.b64encode(r.content).decode()
        except Exception as e:
            print(f"[KRIRK][telegram] Falha ao baixar voice: {e}")
            return None

    # ── API pública (usada pelo ProactiveMonitor) ─────────────────────────────

    async def send_to_owner(self, text: str, audio_b64: str | None = None) -> None:
        """Mensagem espontânea da Krirk para o dono (proativo/reflexão)."""
        if self._owner_chat_id is None:
            return
        try:
            await self._send_text(self._owner_chat_id, text)
            if audio_b64:
                await self._send_audio(self._owner_chat_id, audio_b64)
        except Exception as e:
            print(f"[KRIRK][telegram] Falha no envio espontâneo: {e}")

    # ── Loop principal ────────────────────────────────────────────────────────

    async def start(self) -> None:
        me = await self._call("getMe", http_timeout=15.0)
        if not me.get("ok"):
            print(f"[KRIRK][telegram] Token inválido — bridge desativada: {me}")
            return
        username = me["result"].get("username", "?")
        owner = self._owner_chat_id or "aguardando /start"
        print(f"[KRIRK][telegram] Bridge ativa: @{username} (dono: {owner})")
        self._running = True
        asyncio.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                # http_timeout > timeout do long-poll para a conexão não morrer antes
                updates = await self._call(
                    "getUpdates", http_timeout=60.0,
                    offset=self._offset, timeout=50,
                )
                for update in updates.get("result", []):
                    self._offset = update["update_id"] + 1
                    try:
                        await self._handle_update(update)
                    except Exception as e:
                        print(f"[KRIRK][telegram] Erro no update: {type(e).__name__}: {e}")
            except Exception as e:
                print(f"[KRIRK][telegram] Poll falhou ({type(e).__name__}) — retry em 10s")
                await asyncio.sleep(10)

    async def _handle_update(self, update: dict) -> None:
        msg = extract_message(update)
        if msg is None:
            return
        chat_id = msg["chat_id"]

        # ── Vínculo de dono ───────────────────────────────────────────────────
        if self._owner_chat_id is None:
            if msg.get("text", "").startswith("/start"):
                self._owner_chat_id = chat_id
                self._save_owner(chat_id)
                print(f"[KRIRK][telegram] Dono vinculado: chat_id={chat_id} ({msg['name']})")
                await self._send_text(chat_id, "Oi! Agora esse é o nosso canal. Pode falar comigo por aqui, inclusive por áudio.")
            return

        if chat_id != self._owner_chat_id:
            return  # ignora estranhos silenciosamente

        if msg.get("text", "").startswith("/start"):
            await self._send_text(chat_id, "Já estamos conectados. Manda ver.")
            return

        # ── Mensagem do dono → pipeline da Krirk ─────────────────────────────
        await self._call("sendChatAction", chat_id=chat_id, action="typing")

        if "voice_file_id" in msg:
            audio_b64 = await self._download_voice(msg["voice_file_id"])
            if not audio_b64:
                await self._send_text(chat_id, "Não consegui baixar seu áudio, tenta de novo?")
                return
            events = self._orch.process_audio(audio_b64, user_id="default")
        else:
            events = self._orch.process_text(msg["text"], user_id="default")

        response, audio_out = "", None
        async for ev in events:
            et = ev.get("type")
            if et == "transcription" and ev.get("content"):
                await self._send_text(chat_id, f"(ouvi: {ev['content']})")
            elif et == "tool_call" and ev.get("tool") and ev["tool"] != "planner":
                await self._call("sendChatAction", chat_id=chat_id, action="typing")
            elif et == "response_complete":
                response = ev.get("content", "")
                audio_out = ev.get("audio")
            elif et == "error" and ev.get("message"):
                response = response or f"Deu erro aqui: {ev['message']}"

        if response:
            await self._send_text(chat_id, response)
        if audio_out:
            await self._send_audio(chat_id, audio_out)
