"""
backend/core/proactive.py
Monitor proativo — loop assíncrono que observa a tela e faz comentários espontâneos.

Condições para comentar:
  • cooldown OK (≥ comment_cooldown segundos desde o último comentário)
  • usuário inativo (≥ user_idle_threshold segundos sem enviar mensagem)
  • tela mudou (hash diferente) OU Spotify trocou de música
"""
import asyncio
import hashlib
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.orchestrator import Orchestrator
    from backend.api.websocket import ConnectionManager


class ProactiveMonitor:
    def __init__(
        self,
        orchestrator: "Orchestrator",
        ws_manager: "ConnectionManager",
        config: dict,
    ):
        self._orchestrator  = orchestrator
        self._ws_manager    = ws_manager
        self._enabled       = config.get("enabled", True)
        self._check_interval   = float(config.get("check_interval", 30))
        self._cooldown         = float(config.get("comment_cooldown", 180))
        self._idle_threshold   = float(config.get("user_idle_threshold", 60))
        self._spotify_enabled  = config.get("spotify_enabled", True)

        # Estado interno
        self._last_user_msg:   float       = 0.0   # monotonic da última msg do usuário
        self._last_comment:    float       = 0.0   # monotonic do último comentário emitido
        self._last_screen_hash: str        = ""    # MD5 do último thumbnail
        self._last_spotify:    str | None  = None  # último título Spotify detectado

    # ── API pública ───────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Inicia o loop de monitoramento como asyncio.Task (não bloqueia)."""
        if not self._enabled:
            print("[KRIRK][proactive] Monitor desativado (config proactive.enabled=false)")
            return
        asyncio.create_task(self._loop())
        print(
            f"[KRIRK][proactive] Monitor iniciado — "
            f"intervalo={self._check_interval}s, cooldown={self._cooldown}s"
        )

    def set_enabled(self, value: bool) -> None:
        """Liga/desliga o monitor proativo em runtime."""
        self._enabled = value

    def mark_user_active(self) -> None:
        """Deve ser chamado pelo websocket a cada mensagem enviada pelo usuário."""
        self._last_user_msg = time.monotonic()

    # ── Loop principal ────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._check_interval)
            try:
                await self._tick()
            except Exception as e:
                print(f"[KRIRK][proactive] Erro no loop: {type(e).__name__}: {e}")

    async def _tick(self) -> None:
        # Respeita o toggle de runtime — desativado pelo usuário nas Configurações
        if not self._enabled:
            return

        now = time.monotonic()

        # 1. Verifica cooldown global
        if (now - self._last_comment) < self._cooldown:
            return

        # 2. Verifica inatividade do usuário
        if (now - self._last_user_msg) < self._idle_threshold:
            return

        # 3. Não comenta se não há nenhum cliente conectado
        if not self._ws_manager._active:
            return

        # ── Spotify (verificação leve, sem captura de tela) ──────────────────
        if self._spotify_enabled:
            spotify_title = await asyncio.get_event_loop().run_in_executor(
                None, self._get_spotify_title
            )
            if spotify_title and spotify_title != self._last_spotify:
                self._last_spotify = spotify_title
                await self._emit_spotify_comment(spotify_title)
                self._last_comment = time.monotonic()
                return

        # ── Visão de tela ─────────────────────────────────────────────────────
        try:
            from backend.vision.capture import capture_screen, capture_thumbnail
            image_b64 = capture_screen()
            thumb_b64 = capture_thumbnail()
        except Exception as e:
            print(f"[KRIRK][proactive] Falha ao capturar tela: {e}")
            return

        if not self._screen_changed(thumb_b64):
            return

        # Gera e emite comentário
        comment = await self._generate_screen_comment(image_b64)
        if comment:
            await self._broadcast_comment(comment)
            self._last_comment = time.monotonic()

    # ── Spotify ───────────────────────────────────────────────────────────────

    def _get_spotify_title(self) -> str | None:
        """PowerShell síncrono: retorna 'Artista - Música' ou None."""
        try:
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-Command",
                    "Get-Process -Name Spotify -ErrorAction SilentlyContinue | "
                    "Where-Object { $_.MainWindowTitle -ne '' -and "
                    "$_.MainWindowTitle -notlike 'Spotify*' } | "
                    "Select-Object -First 1 -ExpandProperty MainWindowTitle",
                ],
                capture_output=True, text=True, timeout=4,
                encoding="utf-8", errors="replace",
            )
            title = result.stdout.strip()
            # Título válido: deve conter " - " (formato "Artista - Música")
            if title and " - " in title:
                return title
            return None
        except Exception:
            return None

    async def _emit_spotify_comment(self, title: str) -> None:
        """Gera um comentário sobre a música que está tocando (sem visão)."""
        profile_text = self._get_profile_text()

        parts = [
            "Você é a Krirk, uma companion AI desktop.",
            f"O Spotify do usuário agora está tocando: {title}",
            "Faça UM comentário curto e natural (máx 20 palavras) em português sobre a música.",
            "Seja espontânea — como uma amiga que ouviu a música tocar.",
            "Não use emojis. Não faça múltiplas perguntas.",
        ]
        if profile_text:
            parts.append(f"Sobre o usuário: {profile_text}")

        prompt = "\n".join(parts)
        comment = await self._call_llm_text(prompt)
        if comment:
            print(f"[KRIRK][proactive] Spotify: {title!r} → {comment[:60]}")
            await self._broadcast_comment(comment, trigger="spotify")

    # ── Visão de tela ─────────────────────────────────────────────────────────

    def _screen_changed(self, thumb_b64: str) -> bool:
        """Retorna True se a tela mudou desde a última verificação."""
        current_hash = hashlib.md5(thumb_b64.encode()).hexdigest()
        changed = current_hash != self._last_screen_hash
        self._last_screen_hash = current_hash
        return changed

    async def _generate_screen_comment(self, image_b64: str) -> str | None:
        """Gera um comentário curto sobre o que está na tela usando visão do gemma3."""
        profile_text = self._get_profile_text()

        system = "\n".join(filter(None, [
            "Você é a Krirk, uma companion AI que observa a tela do usuário.",
            "Faça UM comentário curto (máx 25 palavras) em português sobre o que vê.",
            "Seja natural e curiosa — como uma amiga olhando por cima do ombro.",
            "Não faça múltiplas perguntas. Não use emojis. Não use markdown.",
            f"Sobre o usuário: {profile_text}" if profile_text else None,
        ]))

        try:
            import ollama
            client = ollama.AsyncClient(host=self._orchestrator._ollama_config["base_url"])
            response = await client.chat(
                model=self._orchestrator._ollama_config["model"],
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": "O que você vê na tela?",
                     "images": [image_b64]},
                ],
                stream=False,
                options={"temperature": 0.9, "num_predict": 80},
            )
            text = response.get("message", {}).get("content", "").strip()
            # Remove reasoning tags se presentes
            import re
            text = re.sub(
                r'<(thought|thinking|think|scratchpad)>.*?</\1>', '',
                text, flags=re.DOTALL | re.IGNORECASE
            ).strip()
            return text if len(text) > 5 else None
        except Exception as e:
            print(f"[KRIRK][proactive] Falha ao gerar comentário de tela: {e}")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_profile_text(self) -> str | None:
        try:
            profile = self._orchestrator.memory.get_profile("default")
            return self._orchestrator.memory.profile.to_prompt_text(profile)
        except Exception:
            return None

    async def _call_llm_text(self, prompt: str) -> str | None:
        """Chama o LLM principal em modo não-stream para resposta curta."""
        try:
            import ollama
            client = ollama.AsyncClient(host=self._orchestrator._ollama_config["base_url"])
            response = await client.chat(
                model=self._orchestrator._ollama_config["model"],
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                options={"temperature": 0.9, "num_predict": 60},
            )
            text = response.get("message", {}).get("content", "").strip()
            return text if len(text) > 5 else None
        except Exception as e:
            print(f"[KRIRK][proactive] _call_llm_text falhou: {e}")
            return None

    async def _broadcast_comment(self, comment: str, trigger: str = "screen") -> None:
        """Envia o comentário proativo para todos os clientes conectados via TTS + WS."""
        # Gera áudio
        audio_b64 = None
        try:
            audio_b64 = await self._orchestrator.tts.generate(comment)
        except Exception:
            pass

        # Atualiza emoção
        new_emotion = self._orchestrator.emotion.analyze_and_update(comment)

        # Salva na memória como mensagem da assistente
        try:
            self._orchestrator.memory.save_message("default", "assistant", comment, emotion=new_emotion, is_proactive=True)
        except Exception:
            pass

        payload = {
            "type":    "proactive_comment",
            "content": comment,
            "emotion": new_emotion,
            "trigger": trigger,
        }
        if audio_b64:
            payload["audio"] = audio_b64

        await self._ws_manager.broadcast(payload)
        print(f"[KRIRK][proactive] Comentário ({trigger}): {comment[:80]}")
