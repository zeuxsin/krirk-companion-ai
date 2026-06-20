from dataclasses import dataclass


EMOTION_KEYWORDS: dict[str, list[str]] = {
    "neutro":       [],
    "feliz":        ["feliz", "ótimo", "maravilhoso", "incrível", "adorei", "que bom", "perfeito", "excelente", "sensacional"],
    "empolgada":    ["nossa", "uau", "wow", "fantástico", "demais", "que legal", "adorável", "épico", "animado"],
    "triste":       ["triste", "que pena", "lamentável", "perda", "chateada", "decepcionada", "saudade"],
    "zangada":      ["raiva", "chateado", "que saco", "odeio", "ridículo", "absurdo"],
    "surpresa":     ["não acredito", "surpreendente", "inesperado", "de repente"],
    "assustada":    ["assustador", "medo", "que susto", "perigoso", "cuidado", "atenção"],
    "envergonhada": ["envergonhada", "que vergonha", "me envergonhei", "embaraçoso"],
    "timida":       ["hmm", "não sei", "talvez", "acho que", "não tenho certeza"],
    "irritada":     ["irritante", "chato", "que raiva", "inaceitável", "frustrante"],
    "curiosa":      ["interessante", "curioso", "me pergunto", "estranho", "fascinante"],
    "concentrada":  ["deixa eu pensar", "processando", "analisando", "calculando", "verificando"],
    "orgulhosa":    ["consegui", "fiz isso", "orgulho", "excelente trabalho"],
    "cansada":      ["cansada", "exausta", "muito trabalho", "preciso de uma pausa", "preocupante", "complicado", "sinto muito"],
    "determinada":  ["vou fazer", "conseguirei", "estou determinada", "não vou desistir"],
    "codando":      ["código", "função", "bug", "programar", "erro", "compilar", "debug"],
    "jogando":      ["jogo", "jogar", "game", "gaming", "personagem", "fase", "nível"],
    "tranquila":    ["tranquilo", "calmo", "relaxado", "sem pressa", "tudo bem", "suave"],
    "pensando":     ["na verdade", "pensando bem", "de fato", "por outro lado", "hm"],
    "confusa":      ["hã", "o quê", "tô perdido", "não entendi", "como assim"],
}


@dataclass
class EmotionState:
    name: str = "neutro"
    intensity: float = 0.5
    decay_counter: int = 0


class EmotionEngine:
    DECAY_AFTER = 3

    def __init__(self, initial: str = "neutro"):
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
                self.state.name = "neutro"
                self.state.decay_counter = 0
        else:
            self.state.name = best
            self.state.decay_counter = 0

        return self.state.name

    def force_set(self, emotion: str):
        valid = set(EMOTION_KEYWORDS.keys())
        if emotion in valid:
            self.state.name = emotion
            self.state.decay_counter = 0
        # Se não reconhecido, mantém atual

    @staticmethod
    def valid_emotions() -> list[str]:
        return list(EMOTION_KEYWORDS.keys())
