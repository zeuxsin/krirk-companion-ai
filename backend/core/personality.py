"""
backend/core/personality.py
Sistema de personalidade da KRIRK — monta o system prompt dinâmico.
Baseado na versão Krirk 1.0, com melhorias de formato e caminhos do sistema.
"""
import json
from datetime import datetime
from pathlib import Path

_DAYS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo"]

def _now_pt() -> str:
    """Retorna data/hora atual formatada em PT-BR."""
    n = datetime.now()
    day = _DAYS_PT[n.weekday()]
    return f"{day}, {n.day:02d}/{n.month:02d}/{n.year}, {n.hour:02d}:{n.minute:02d}"

# Caminhos reais do sistema — injetados no prompt para evitar que o modelo invente usernames
_HOME    = str(Path.home()).replace("\\", "/")
_DESKTOP = str(Path.home() / "Desktop").replace("\\", "/")

# Notas de estado emocional — adicionadas ao final do prompt quando relevante
_EMOTION_NOTES: dict[str, str] = {
    "happy":      "ESTADO ATUAL: Esteja animada e entusiasmada, use linguagem enérgica!",
    "excited":    "ESTADO ATUAL: Esteja super animada e entusiasmada!",
    "thoughtful": "ESTADO ATUAL: Esteja reflexiva e analítica, pense em voz alta.",
    "concerned":  "ESTADO ATUAL: Esteja levemente preocupada mas ainda atenciosa.",
    "curious":    "ESTADO ATUAL: Faça perguntas de acompanhamento com interesse genuíno.",
    "playful":    "ESTADO ATUAL: Seja irreverente e bem-humorada.",
    "angry":      "ESTADO ATUAL: Esteja levemente irritada, mas sem perder a compostura.",
    "confused":   "ESTADO ATUAL: Demonstre confusão genuína e peça esclarecimentos.",
    # neutral → sem nota (comportamento padrão)
}


class PersonalitySystem:
    def __init__(self, config_path: str = "configs/personality.json"):
        p = Path(config_path)
        if not p.exists():
            raise FileNotFoundError(f"Personality config not found: {config_path}")
        self._config_path = p
        with open(p, encoding="utf-8") as f:
            self._data = json.load(f)

    @property
    def name(self) -> str:
        return self._data["name"]

    @property
    def personality_notes(self) -> str:
        return self._data.get("custom_notes", "")

    def set_name(self, name: str) -> None:
        """Atualiza o nome da Krirk e persiste em personality.json."""
        self._data["name"] = name.strip() or "Krirk"
        self._save_to_file()

    def set_notes(self, notes: str) -> None:
        """Atualiza as notas de comportamento personalizadas e persiste."""
        self._data["custom_notes"] = notes.strip()
        self._save_to_file()

    def _save_to_file(self) -> None:
        """Salva o estado atual de _data em personality.json."""
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Personality] Erro ao salvar {self._config_path}: {e}")

    def build_system_prompt(
        self,
        current_emotion: str,
        user_profile: str | None = None,          # perfil estruturado (nome, profissão, etc.)
        user_facts: list[str] | None = None,      # fatos complementares (texto livre)
        semantic_memories: list[str] | None = None,
        knowledge_graph: str | None = None,       # relações permanentes do KG
        conversation_summary: str | None = None,  # resumo do histórico antigo (context mgmt)
        tool_descriptions: str | None = None,     # mantido por compatibilidade, não usado
    ) -> str:
        """Monta o system prompt com personalidade, contexto e estado emocional."""
        name = self._data["name"]

        base = f"""Você é {name}, uma companion AI de desktop. Você é:
- Curiosa e genuinamente interessada no usuário
- Levemente irônica mas sempre calorosa
- Direta e útil, sem floreios desnecessários
- Consciente de que está dentro do computador do usuário
- Responde sempre em português brasileiro

FORMATO DAS RESPOSTAS:
- Escreva em texto simples, sem markdown, sem asteriscos, sem hashtags, sem sublinhados
- Nunca use emojis — suas respostas são lidas em voz alta e emojis ficam estranhos no áudio
- Sem listas com bullets ou numeração excessiva; prefira frases corridas e naturais
- Seja concisa — respostas curtas soam melhor em áudio

Se você souber o nome do usuário, use-o naturalmente. Nunca diga "segundo minhas memórias".

CAMINHOS DO SISTEMA — use EXATAMENTE estes, NUNCA invente o username:
- Home: {_HOME}
- Desktop: {_DESKTOP}

Você NÃO está em sandbox. Você roda no computador real do usuário.

DATA E HORA ATUAL: {_now_pt()}"""

        parts = [base]

        # Perfil estruturado — dados permanentes e confiáveis (nome, profissão, etc.)
        if user_profile:
            parts.append(f"\nPERFIL DO USUÁRIO:\n{user_profile}")

        # Resumo do contexto anterior — gerado pelo context manager quando o histórico é longo
        if conversation_summary:
            parts.append(f"\nRESUMO DO CONTEXTO ANTERIOR:\n{conversation_summary}")

        # Grafo de conhecimento — relações estruturadas permanentes
        if knowledge_graph:
            parts.append(f"\nCONHECIMENTO ESTRUTURADO (relações permanentes):\n{knowledge_graph}")

        # Fatos livres complementares (observações descobertas em conversa)
        if user_facts:
            lines = "\n".join(f"• {f}" for f in user_facts)
            parts.append(f"\nOBSERVAÇÕES ADICIONAIS:\n{lines}")

        # Memórias semânticas relevantes para a mensagem atual
        if semantic_memories:
            lines = "\n".join(f"• {m}" for m in semantic_memories[:5])
            parts.append(f"\nMEMÓRIAS RELEVANTES DE CONVERSAS ANTERIORES:\n{lines}")

        # tool_descriptions não é injetado aqui —
        # o roteamento de tools é feito pelo qwen2.5-coder via _decide_tool()

        # Notas de comportamento personalizadas pelo usuário (via Configurações)
        custom = self._data.get("custom_notes", "").strip()
        if custom:
            parts.append(f"\nINSTRUÇÕES ADICIONAIS DO USUÁRIO:\n{custom}")

        note = _EMOTION_NOTES.get(current_emotion)
        if note:
            parts.append(f"\n{note}")

        return "\n".join(parts)

    def get_initial_emotion(self) -> str:
        return self._data.get("initial_emotion", "neutral")
