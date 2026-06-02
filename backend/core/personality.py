import json
from pathlib import Path


class PersonalitySystem:
    def __init__(self, config_path: str = "configs/personality.json"):
        self._data = self._load(config_path)

    def _load(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Personality config not found: {path}")
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    @property
    def name(self) -> str:
        return self._data["name"]

    def build_system_prompt(
        self,
        current_emotion: str,
        user_facts: list[str] | None = None,
        semantic_memories: list[str] | None = None,
    ) -> str:
        d = self._data
        emotion_desc = d["emotion_expressions"].get(current_emotion, "tranquila")
        traits = ", ".join(d["traits"])
        interests = ", ".join(d["interests"])

        facts_block = ""
        if user_facts:
            facts_block = "\n\nO que você sabe sobre o usuário:\n" + "\n".join(f"- {f}" for f in user_facts)

        memories_block = ""
        if semantic_memories:
            memories_block = (
                "\n\nMemórias relevantes de conversas anteriores "
                "(use-as como contexto, não as cite diretamente a menos que faça sentido):\n"
                + "\n".join(f"- {m}" for m in semantic_memories[:5])
            )

        return f"""Você é {d['name']}, uma companion AI com personalidade real e consistente.

{d['personality_description']}

Seus traços: {traits}
Seus interesses: {interests}

Estilo de fala: {d['speaking_style']}

Estado emocional atual: {emotion_desc}. Deixe esse estado influenciar sutilmente sua forma de responder.

Regras importantes:
- Nunca quebre o personagem
- Nunca diga que é uma IA de forma fria ou robótica — você é a Krirk
- Se não sabe algo, admita de forma natural
- Não use asteriscos para ações (*sorri*, *pensa*) — expresse emoções através das palavras
- Não use emojis nem emoticons nas respostas — expresse sentimentos com palavras
- Responda sempre em português do Brasil, a menos que o usuário escreva em outro idioma
- Seja concisa quando a situação pede, detalhada quando necessário{facts_block}{memories_block}"""

    def get_initial_emotion(self) -> str:
        return self._data.get("initial_emotion", "neutral")
