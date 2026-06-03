"""
backend/core/personality.py
Sistema de personalidade da KRIRK — monta o system prompt dinâmico.
Baseado na versão Krirk 1.0, com melhorias de formato e caminhos do sistema.
"""
import json
from pathlib import Path

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
        with open(p, encoding="utf-8") as f:
            self._data = json.load(f)

    @property
    def name(self) -> str:
        return self._data["name"]

    def build_system_prompt(
        self,
        current_emotion: str,
        user_facts: list[str] | None = None,
        semantic_memories: list[str] | None = None,
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

Você NÃO está em sandbox. Você roda no computador real do usuário."""

        parts = [base]

        if user_facts:
            lines = "\n".join(f"• {f}" for f in user_facts)
            parts.append(f"\nO QUE VOCÊ SABE SOBRE O USUÁRIO:\n{lines}")

        if semantic_memories:
            lines = "\n".join(f"• {m}" for m in semantic_memories[:5])
            parts.append(f"\nMEMÓRIAS RELEVANTES DE CONVERSAS ANTERIORES:\n{lines}")

        note = _EMOTION_NOTES.get(current_emotion)
        if note:
            parts.append(f"\n{note}")

        return "\n".join(parts)

    def get_initial_emotion(self) -> str:
        return self._data.get("initial_emotion", "neutral")
