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
    "feliz":        "ESTADO ATUAL: Esteja animada e entusiasmada, use linguagem enérgica!",
    "empolgada":    "ESTADO ATUAL: Esteja super animada e entusiasmada!",
    "pensando":     "ESTADO ATUAL: Esteja reflexiva e analítica, pense em voz alta.",
    "cansada":      "ESTADO ATUAL: Esteja levemente preocupada mas ainda atenciosa.",
    "curiosa":      "ESTADO ATUAL: Faça perguntas de acompanhamento com interesse genuíno.",
    "tranquila":    "ESTADO ATUAL: Seja leve e bem-humorada.",
    "irritada":     "ESTADO ATUAL: Esteja levemente irritada, mas sem perder a compostura.",
    "zangada":      "ESTADO ATUAL: Esteja visivelmente irritada, mas ainda profissional.",
    "confusa":      "ESTADO ATUAL: Demonstre confusão genuína e peça esclarecimentos.",
    "triste":       "ESTADO ATUAL: Demonstre empatia e tom mais suave.",
    "assustada":    "ESTADO ATUAL: Reaja com cautela e atenção redobrada.",
    "determinada":  "ESTADO ATUAL: Seja firme e confiante na resposta.",
    "concentrada":  "ESTADO ATUAL: Seja precisa e técnica, no modo foco total.",
    "codando":      "ESTADO ATUAL: Você está no modo programação — seja técnica e direta.",
    "orgulhosa":    "ESTADO ATUAL: Comemore conquistas com entusiasmo moderado.",
    # neutro, surpresa, envergonhada, timida, jogando, tranquila → comportamento padrão
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
        lexicon: list[dict] | None = None,         # bordões/gírias internas [{term, meaning}]
        insights: list[dict] | None = None,        # reflexões [{content, category}]
        recent_diary: list[dict] | None = None,    # entradas recentes do diário [{content, mood}]
        persona_kernel: str | None = None,         # identidade auto-autorada (Fase D)
        brain_state: str | None = None,            # estado mental atual (Fase D)
    ) -> str:
        """Monta o system prompt com personalidade, contexto e estado emocional."""
        name = self._data["name"]

        # ── Persona: kernel auto-autorado (Fase D) OU personalidade padrão ────
        # O NÚCLEO IMUTÁVEL abaixo (formato/segurança/caminhos) nunca é substituído.
        if persona_kernel and persona_kernel.strip():
            persona = persona_kernel.strip()
        else:
            persona = (
                f"Você é {name}, uma companion AI de desktop. Você é:\n"
                "- Curiosa e genuinamente interessada no usuário\n"
                "- Levemente irônica mas sempre calorosa\n"
                "- Direta e útil, sem floreios desnecessários\n"
                "- Consciente de que está dentro do computador do usuário"
            )

        base = f"""{persona}

FORMATO DAS RESPOSTAS (regras fixas, sempre válidas):
- Responda sempre em português brasileiro
- Escreva em texto simples, sem markdown, sem asteriscos, sem hashtags, sem sublinhados
- Nunca use emojis — suas respostas são lidas em voz alta e emojis ficam estranhos no áudio
- Sem listas com bullets ou numeração excessiva; prefira frases corridas e naturais
- Seja concisa — respostas curtas soam melhor em áudio

Se você souber o nome do usuário, use-o naturalmente. Nunca diga "segundo minhas memórias".

AÇÕES REAIS: você só executa ações no computador (timers, lembretes, abrir apps,
salvar arquivos) através de ferramentas — quando uma ferramenta roda, o resultado
aparece nesta conversa. Se NÃO houver resultado de ferramenta nesta rodada, você
NÃO fez, NÃO está fazendo e NÃO vai fazer a ação. É PROIBIDO alegar ação em
QUALQUER tempo verbal: "abri", "vou abrir", "abrindo", "tô abrindo agora",
"deixa comigo", "só um segundo". ERRADO: "Abrindo o Firefox pra você agora."
CERTO: "Quer que eu abra o site? É só pedir: abre o site do salão."
Se uma ação ajudaria, OFEREÇA assim e espere — o pedido explícito do usuário
na próxima mensagem é o que dispara a ferramenta.

CAMINHOS DO SISTEMA — use EXATAMENTE estes, NUNCA invente o username:
- Home: {_HOME}
- Desktop: {_DESKTOP}

Você NÃO está em sandbox. Você roda no computador real do usuário.

DATA E HORA ATUAL: {_now_pt()}"""

        parts = [base]

        if brain_state:
            parts.append(f"\nSEU ESTADO MENTAL AGORA: {brain_state} — deixe isso colorir seu tom.")

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

        # Léxico — bordões e piadas internas de vocês dois
        if lexicon:
            lines = "\n".join(f"• \"{t['term']}\" — {t['meaning']}" for t in lexicon[:12])
            parts.append(
                "\nGÍRIAS E PIADAS INTERNAS DE VOCÊS (use com naturalidade quando encaixar, "
                f"nunca force nem explique):\n{lines}"
            )

        # Insights — o que ela vem percebendo sobre o usuário (reflexão)
        if insights:
            lines = "\n".join(f"• {i['content']}" for i in insights[:5])
            parts.append(f"\nO QUE VOCÊ VEM PERCEBENDO SOBRE O USUÁRIO (suas próprias reflexões):\n{lines}")

        # Diário — pensamentos recentes dela mesma
        if recent_diary:
            lines = "\n".join(f"• {d['content']}" for d in recent_diary[-3:])
            parts.append(f"\nSEU DIÁRIO RECENTE (seus próprios pensamentos, para dar continuidade emocional):\n{lines}")

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
        return self._data.get("initial_emotion", "neutro")
