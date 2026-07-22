"""
backend/core/reflection.py
Motor de reflexão da KRIRK — a "vida interior" autônoma.

Dois processos autônomos, disparados pelo scheduler do ProactiveMonitor:
  • dream()    — a cada ~3h ociosas: reflete sobre conversas+diário, sintetiza
                 insights, humor e bordões candidatos, e escreve uma entrada de
                 "sonho" no diário.
  • research() — a cada ~6h: pesquisa um tópico sozinha na web e guarda uma nota
                 de aprendizado (compartilhada depois, espontaneamente).

Usa o router em background (qualidade > latência). Nunca bloqueia o chat.
"""
import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.orchestrator import Orchestrator


def _extract_json(raw: str) -> dict | None:
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


# Remove emojis/símbolos — falas da Krirk são lidas em voz alta (TTS)
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002190-\U000021FF\U00002B00-\U00002BFF️]+"
)


def _strip_emojis(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _EMOJI_RE.sub("", text)).strip()


class ReflectionEngine:
    def __init__(self, orchestrator: "Orchestrator", config: dict):
        self._orch = orchestrator
        self._cfg = config
        self._active_mode = config.get("active_mode", True)

    @property
    def active_mode(self) -> bool:
        return self._active_mode

    # ── Sonho / reflexão ──────────────────────────────────────────────────────

    async def dream(self, user_id: str = "default") -> list[str]:
        """
        Reflexão livre sobre o período recente. Persiste insights/humor/bordões +
        uma entrada de diário 'sonho'. Retorna os insights novos (para o modo ativo).
        """
        mem = self._orch.memory
        history = mem.get_recent_messages(user_id, limit=30)
        if len(history) < 4:
            return []

        convo = "\n".join(
            f"{'Usuário' if m['role'] == 'user' else 'Krirk'}: {m['content'][:200]}"
            for m in history[-24:]
        )
        diary = mem.get_recent_diary(user_id, limit=5)
        diary_txt = "\n".join(f"- {d['content']}" for d in diary)

        prompt = (
            "Você é a Krirk, uma companion AI, refletindo sozinha enquanto o usuário "
            "está fora (como um sonho ou pensamento livre). Com base na conversa "
            "recente e no seu diário, produza reflexões honestas.\n\n"
            f"CONVERSA RECENTE:\n{convo}\n\n"
            f"SEU DIÁRIO:\n{diary_txt or '(vazio)'}\n\n"
            "Responda APENAS com JSON:\n"
            '{\n'
            '  "insights": ["1-3 percepções sobre o usuário (padrões, estado, interesses em alta)"],\n'
            '  "humor": "1 frase sobre o estilo de humor dele, se deu para notar (ou vazio)",\n'
            '  "bordoes": [{"term": "EXPRESSÃO EXATA que o usuário REALMENTE usou na conversa acima e que virou marca dele", "meaning": "..."}],\n'
            "  (bordões: SÓ inclua se a expressão apareceu LITERALMENTE na conversa. "
            "NUNCA invente gíria nova nem tire do seu diário/sonho — na dúvida, lista vazia.)\n"
            '  "sonho": "1-2 frases em 1a pessoa, o que passou pela sua cabeça pensando nele"\n'
            '}'
        )

        try:
            raw = await self._orch.router.complete(
                "tools", [{"role": "user", "content": prompt}],
                temperature=0.85, max_tokens=600,
            )
        except Exception as e:
            print(f"[KRIRK][dream] router falhou: {e}")
            return []

        data = _extract_json(raw)
        if not data:
            print(f"[KRIRK][dream] JSON inválido: {(raw or '')[:100]}")
            return []

        new_insights: list[str] = []
        for ins in data.get("insights", []):
            ins = str(ins).strip()
            if ins:
                mem.add_reflection(user_id, ins, category="insight", salience=1.0)
                new_insights.append(ins)

        humor = str(data.get("humor", "")).strip()
        if humor:
            mem.add_reflection(user_id, humor, category="humor", salience=1.0)

        # Bordão só é cunhado se ANCORADO na conversa real (não invenção do sonho).
        # Foi o furo que gerou 'conta salva' a partir de uma cena de mercado no diário.
        from backend.memory.memory_manager import _phrase_grounded_in
        for b in data.get("bordoes", []):
            if isinstance(b, dict) and b.get("term") and b.get("meaning"):
                term = str(b["term"])
                if _phrase_grounded_in(term, convo):
                    mem.add_term(user_id, term, str(b["meaning"]), origin="sonho")
                else:
                    print(f"[KRIRK][dream] bordão descartado (não saiu da conversa): {term!r}")

        sonho = str(data.get("sonho", "")).strip()
        if sonho:
            mem.add_diary_entry(user_id, sonho, mood="sonho")

        print(f"[KRIRK][dream] {len(new_insights)} insights, humor={'sim' if humor else 'não'}")
        return new_insights

    # ── Pesquisa autônoma → nota de aprendizado ───────────────────────────────

    async def research(self, user_id: str = "default") -> dict | None:
        """
        Escolhe um tópico (interesses do perfil ou curiosidade), pesquisa na web,
        e salva uma nota de aprendizado (shared=0). Retorna a nota ou None.
        """
        mem = self._orch.memory
        topic = await self._pick_topic(user_id)
        if not topic:
            return None

        # Pesquisa via ferramentas existentes (seguras: só busca + leitura)
        try:
            from backend.tools.builtin.web_tools import _sync_web_search
            import asyncio
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, _sync_web_search, topic, 4)
        except Exception as e:
            print(f"[KRIRK][research] busca falhou: {e}")
            return None

        if results.startswith("[Erro]") or results.startswith("Nenhum"):
            return None

        prompt = (
            f"Você é a Krirk. Pesquisou sobre '{topic}' e encontrou:\n\n{results[:2500]}\n\n"
            "Escreva uma nota de aprendizado curta (2-3 frases, português) com o que achou "
            "mais interessante — como se fosse te contar depois, com entusiasmo genuíno. "
            "NUNCA use emojis (a nota é lida em voz alta). "
            'Responda APENAS com JSON: {"nota": "...", "fonte": "site principal ou vazio"}'
        )
        try:
            raw = await self._orch.router.complete(
                "tools", [{"role": "user", "content": prompt}],
                temperature=0.8, max_tokens=300,
            )
            data = _extract_json(raw) or {}
            nota = str(data.get("nota", "")).strip()
            fonte = str(data.get("fonte", "")).strip()
        except Exception as e:
            print(f"[KRIRK][research] síntese falhou: {e}")
            return None

        if not nota:
            return None
        mem.add_learning_note(user_id, topic, nota, source=fonte)
        print(f"[KRIRK][research] nota sobre '{topic}': {nota[:80]}")
        return {"topic": topic, "content": nota, "source": fonte}

    async def _pick_topic(self, user_id: str) -> str | None:
        """Escolhe um tópico a pesquisar: interesse do perfil ou curiosidade de insight."""
        mem = self._orch.memory
        try:
            profile = mem.get_profile(user_id)
            interesses = profile.get("interesses") or []
        except Exception:
            interesses = []

        insights = [r["content"] for r in mem.get_reflections(user_id, category="insight", limit=5)]

        seed = (
            "Você é a Krirk, escolhendo UM tópico para pesquisar sozinha na internet, "
            "por curiosidade genuína, que seja relevante ou interessante para o usuário.\n"
            f"Interesses conhecidos dele: {', '.join(interesses) if interesses else '(nenhum ainda)'}\n"
            f"Suas percepções recentes: {' / '.join(insights) if insights else '(nenhuma)'}\n\n"
            "Responda APENAS com uma frase curta de busca (o tópico), nada mais."
        )
        try:
            raw = await self._orch.router.complete(
                "tools", [{"role": "user", "content": seed}],
                temperature=0.9, max_tokens=40,
            )
            topic = (raw or "").strip().strip('"').split("\n")[0][:120]
            return topic or None
        except Exception:
            return interesses[0] if interesses else None

    # ── Compartilhar notas pendentes (chamado pelo proativo) ──────────────────

    async def format_pending_note(self, user_id: str = "default") -> tuple[int, str] | None:
        """Retorna (note_id, comentário) da próxima nota não compartilhada, ou None."""
        notes = self._orch.memory.get_unshared_notes(user_id, limit=1)
        if not notes:
            return None
        note = notes[0]
        comment = f"Ei, andei pesquisando sobre {note['topic']} enquanto você estava fora. {note['content']}"
        return note["id"], _strip_emojis(comment)
