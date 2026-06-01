import re
from dataclasses import dataclass


EMOTION_KEYWORDS: dict[str, list[str]] = {
    "happy": ["feliz", "ótimo", "maravilhoso", "incrível", "adorei", "que bom", "perfeito", "excelente", "sensacional"],
    "excited": ["nossa", "uau", "wow", "incrível", "fantástico", "demais", "que legal", "adorável", "épico"],
    "curious": ["interessante", "curioso", "me pergunto", "como funciona", "por quê", "fascinante", "estranho", "hm"],
    "playful": ["haha", "rs", "brincadeira", "piada", "engraçado", "divertido", "que ridículo", "😄", "😂"],
    "concerned": ["preocupante", "cuidado", "atenção", "problema", "difícil", "complicado", "triste", "sinto muito"],
    "thoughtful": ["bem", "na verdade", "pensando bem", "veja", "de fato", "considerando", "por outro lado"],
    "neutral": [],
}


@dataclass
class EmotionState:
    name: str = "neutral"
    intensity: float = 0.5
    decay_counter: int = 0


class EmotionEngine:
    DECAY_AFTER = 3

    def __init__(self, initial: str = "neutral"):
        self.state = EmotionState(name=initial)

    @property
    def current_emotion(self) -> str:
        return self.state.name

    def analyze_and_update(self, text: str) -> str:
        text_lower = text.lower()
        scores: dict[str, int] = {e: 0 for e in EMOTION_KEYWORDS}

        for emotion, keywords in EMOTION_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[emotion] += 1

        best = max(scores, key=lambda e: scores[e])
        if scores[best] == 0:
            self.state.decay_counter += 1
            if self.state.decay_counter >= self.DECAY_AFTER:
                self.state.name = "neutral"
                self.state.decay_counter = 0
        else:
            self.state.name = best
            self.state.decay_counter = 0

        return self.state.name

    def force_set(self, emotion: str):
        if emotion in EMOTION_KEYWORDS:
            self.state.name = emotion
            self.state.decay_counter = 0
