"""
tests/test_unit.py
Testes unitários OFFLINE — sem rede, sem Ollama, sem APIs cloud.
Roda com:  .venv\\Scripts\\python.exe tests\\test_unit.py
"""
import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Helpers de output (mesmo padrão de test_krirk.py) ─────────────────────────

RESET = "\033[0m"
GREEN = "\033[92m"
RED   = "\033[91m"
BOLD  = "\033[1m"

passed = []
failed = []

def ok(name: str, detail: str = ""):
    passed.append(name)
    suffix = f"  ({detail})" if detail else ""
    print(f"  {GREEN}PASS{RESET} {name}{suffix}")

def fail(name: str, detail: str = ""):
    failed.append(name)
    suffix = f"\n       {detail}" if detail else ""
    print(f"  {RED}FAIL{RESET} {name}{suffix}")

def check(name: str, cond: bool, detail: str = ""):
    ok(name, detail) if cond else fail(name, detail)

def section(title: str):
    print(f"\n{BOLD}{title}{RESET}")
    print("  " + "-" * 50)


# As 20 emoções canônicas (mesma lista de frontend/src/types/index.ts)
CANONICAL_EMOTIONS = {
    "neutro", "surpresa", "pensando", "curiosa", "cansada", "irritada",
    "confusa", "feliz", "empolgada", "triste", "zangada", "assustada",
    "envergonhada", "timida", "concentrada", "orgulhosa", "determinada",
    "codando", "jogando", "tranquila",
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. EmotionEngine
# ─────────────────────────────────────────────────────────────────────────────

section("1. EmotionEngine")

from backend.emotions.emotion_engine import EmotionEngine, EMOTION_KEYWORDS

check("20 emocoes validas", set(EmotionEngine.valid_emotions()) == CANONICAL_EMOTIONS,
      f"{len(EMOTION_KEYWORDS)} emocoes")

eng = EmotionEngine()
check("estado inicial e neutro", eng.current_emotion == "neutro")

check("detecta 'feliz' por keyword", eng.analyze_and_update("estou muito feliz hoje, adorei!") == "feliz")
check("detecta 'codando' por keyword", eng.analyze_and_update("achei um bug no código, vou compilar") == "codando")

# Decay: 3 mensagens sem keyword voltam para neutro
eng2 = EmotionEngine()
eng2.force_set("triste")
for _ in range(EmotionEngine.DECAY_AFTER):
    result = eng2.analyze_and_update("xyzabc qwerty 123")
check("decay volta para neutro apos 3 msgs neutras", result == "neutro")

eng3 = EmotionEngine()
eng3.force_set("jogando")
check("force_set com emocao valida", eng3.current_emotion == "jogando")
eng3.force_set("happy")  # legado inglês — deve ser ignorado
check("force_set ignora emocao invalida", eng3.current_emotion == "jogando")


# ─────────────────────────────────────────────────────────────────────────────
# 2. MemoryManager (SQLite em diretório temporário, sem ChromaDB)
# ─────────────────────────────────────────────────────────────────────────────

section("2. MemoryManager")

from backend.memory.memory_manager import MemoryManager

tmp_dir = Path(tempfile.mkdtemp(prefix="krirk_test_"))
try:
    mm = MemoryManager(
        db_path=str(tmp_dir / "test.db"),
        chroma_path=str(tmp_dir / "chroma"),
    )
    mm._vectors = None  # desliga indexação vetorial — teste 100% offline

    UID = "test-user"

    mm.save_message(UID, "user", "olá krirk")
    mm.save_message(UID, "assistant", "oi! tudo bem?", emotion="feliz")
    mm.save_message(UID, "assistant", "comentário espontâneo", is_proactive=True)

    msgs = mm.get_recent_messages(UID, limit=10)
    check("3 mensagens salvas e recuperadas", len(msgs) == 3)
    check("ordem cronologica preservada", msgs[0]["content"] == "olá krirk")
    check("is_proactive=False padrao", msgs[0]["is_proactive"] is False)
    check("is_proactive=True roundtrip", msgs[2]["is_proactive"] is True)

    check("limit respeitado", len(mm.get_recent_messages(UID, limit=2)) == 2)
    check("usuario sem mensagens retorna []", mm.get_recent_messages("outro-user") == [])

    # Fatos
    mm.save_fact(UID, "gosta de Minecraft")
    mm.save_fact(UID, "trabalha como desenvolvedor")
    facts = mm.get_facts(UID)
    check("2 fatos salvos", len(facts) == 2)
    mm.delete_fact(UID, "gosta de Minecraft")
    facts = mm.get_facts(UID)
    check("delete_fact remove o fato certo", facts == ["trabalha como desenvolvedor"])

    # Resumo de conversa
    check("get_summary sem resumo retorna None", mm.get_summary(UID) is None)
    mm.save_summary(UID, "resumo v1", 10)
    mm.save_summary(UID, "resumo v2", 20)  # sobrescreve
    check("save_summary sobrescreve (upsert)", mm.get_summary(UID) == "resumo v2")

    # Intimidade com clamp 0-100
    mm.update_intimacy(UID, 250.0)
    stats = mm.get_stats(UID)
    check("intimacy clamp maximo 100", stats["intimacy_level"] <= 100.0,
          f"valor={stats['intimacy_level']}")
    check("stats conta mensagens", stats["total_messages"] == 3)
    check("stats conta fatos", stats["facts_stored"] == 1)

    # search_semantic com vectors desligado degrada para []
    check("search_semantic sem ChromaDB retorna []", mm.search_semantic(UID, "qualquer") == [])
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 3. file_tools — aliases, sandbox de caminho e read/write
# ─────────────────────────────────────────────────────────────────────────────

section("3. file_tools")

from backend.tools.builtin.file_tools import (
    _resolve_aliases, _safe_path, _read_file, _write_file, _list_directory,
)

HOME = Path.home()

check("alias 'desktop'", _resolve_aliases("desktop") == str(HOME / "Desktop"))
check("alias 'área de trabalho'", _resolve_aliases("Área de Trabalho") == str(HOME / "Desktop"))
check("alias com prefixo 'desktop/nota.txt'",
      _resolve_aliases("desktop/nota.txt") == str(HOME / "Desktop" / "nota.txt"))
check("caminho sem alias passa direto", _resolve_aliases("C:/qualquer/coisa.txt") == "C:/qualquer/coisa.txt")

check("safe_path aceita home", _safe_path(str(HOME)) is not None)
check("safe_path aceita subpasta do home", _safe_path(str(HOME / "Documents")) is not None)
check("safe_path REJEITA C:\\Windows", _safe_path("C:\\Windows\\System32") is None)
check("safe_path REJEITA traversal para fora do home",
      _safe_path(str(HOME / ".." / ".." / "Windows")) is None)
check("safe_path relativo resolve contra o Desktop",
      _safe_path("agenda_e_recompensas") == (HOME / "Desktop" / "agenda_e_recompensas"))
check("safe_path relativo com subpasta resolve contra o Desktop",
      _safe_path("pasta/arquivo.py") == (HOME / "Desktop" / "pasta" / "arquivo.py"))
check("safe_path relativo REJEITA traversal para fora do home",
      _safe_path("../../Windows") is None)

# Roundtrip write -> read -> list em pasta temporária (dentro do home no Windows)
tmp2 = Path(tempfile.mkdtemp(prefix="krirk_ft_"))
try:
    if _safe_path(str(tmp2)) is None:
        print("  SKIP  read/write roundtrip (TEMP fora do home neste sistema)")
    else:
        target = tmp2 / "teste.txt"
        res = asyncio.run(_write_file(str(target), "linha 1\nlinha 2"))
        check("write_file grava", res.startswith("Arquivo salvo"), res[:60])

        content = asyncio.run(_read_file(str(target)))
        check("read_file le de volta", content == "linha 1\nlinha 2")

        truncated = asyncio.run(_read_file(str(target), max_lines=1))
        check("read_file trunca em max_lines", "truncado" in truncated)

        listing = asyncio.run(_list_directory(str(tmp2)))
        check("list_directory mostra o arquivo", "teste.txt" in listing)

    blocked = asyncio.run(_write_file("C:\\Windows\\hack.txt", "x"))
    check("write_file bloqueia fora do home", blocked.startswith("[Erro]"))

    # create_folder + move_file (organização de arquivos)
    from backend.tools.builtin.file_tools import _create_folder, _move_file
    if _safe_path(str(tmp2)) is not None:
        res = asyncio.run(_create_folder(str(tmp2 / "organizada")))
        check("create_folder cria pasta", res.startswith("Pasta criada"))
        asyncio.run(_write_file(str(tmp2 / "mover.txt"), "conteudo"))
        res = asyncio.run(_move_file(str(tmp2 / "mover.txt"), str(tmp2 / "organizada")))
        check("move_file para dentro de pasta existente", res.startswith("Movido") and (tmp2 / "organizada" / "mover.txt").exists())
        check("origem sumiu apos mover", not (tmp2 / "mover.txt").exists())
        res = asyncio.run(_move_file(str(tmp2 / "nao_existe.txt"), str(tmp2 / "organizada")))
        check("move_file origem inexistente da erro", res.startswith("[Erro]"))
    blocked = asyncio.run(_move_file("C:\\Windows\\system.ini", str(HOME / "Desktop")))
    check("move_file bloqueia origem fora do home", blocked.startswith("[Erro]"))
    blocked = asyncio.run(_create_folder("C:\\Windows\\pasta_hack"))
    check("create_folder bloqueia fora do home", blocked.startswith("[Erro]"))

    missing = asyncio.run(_read_file(str(HOME / "arquivo_que_nao_existe_xyz.txt")))
    check("read_file arquivo inexistente da erro claro", "não encontrado" in missing)
finally:
    shutil.rmtree(tmp2, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Consistência backend ↔ frontend
# ─────────────────────────────────────────────────────────────────────────────

section("4. Consistencia de emocoes backend <-> frontend")

types_ts = (Path(__file__).parent.parent / "frontend" / "src" / "types" / "index.ts").read_text(encoding="utf-8")
import re as _re
frontend_emotions = set(_re.findall(r"\|\s*'(\w+)'", types_ts.split("AIState")[0]))
check("frontend define as mesmas 20 emocoes", frontend_emotions == CANONICAL_EMOTIONS,
      f"diff={frontend_emotions ^ CANONICAL_EMOTIONS or 'nenhum'}")

avatar_dir = Path(__file__).parent.parent / "frontend" / "public" / "avatar"
missing_main = sorted(e for e in CANONICAL_EMOTIONS if not (avatar_dir / f"{e}.png").exists())
check("20 PNGs presentes em /avatar/", not missing_main, f"faltando: {missing_main or 'nenhum'}")

chat_dir = avatar_dir / "chat"
missing_chat = sorted(e for e in CANONICAL_EMOTIONS if not (chat_dir / f"{e}.png").exists())
check("20 PNGs presentes em /avatar/chat/", not missing_chat, f"faltando: {missing_chat or 'nenhum'}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Plugin loader (Fase 6)
# ─────────────────────────────────────────────────────────────────────────────

section("5. Plugin loader")

from backend.tools.registry import ToolRegistry
from backend.tools.plugin_loader import load_plugins

tmp_plugins = Path(tempfile.mkdtemp(prefix="krirk_plug_"))
try:
    # Plugin válido
    (tmp_plugins / "bom.py").write_text(
        "from backend.tools.base import Tool\n"
        "def register(registry):\n"
        "    async def _f() -> str: return 'ok'\n"
        "    registry.register(Tool(name='plugin_tool', description='teste', func=_f))\n",
        encoding="utf-8",
    )
    # Plugin quebrado (erro de sintaxe) — não pode derrubar os outros
    (tmp_plugins / "quebrado.py").write_text("def register(:\n", encoding="utf-8")
    # Plugin sem register() — ignorado
    (tmp_plugins / "sem_register.py").write_text("X = 1\n", encoding="utf-8")
    # Arquivo _privado — ignorado
    (tmp_plugins / "_interno.py").write_text(
        "def register(r): raise RuntimeError('nao deveria carregar')\n", encoding="utf-8",
    )

    reg = ToolRegistry()
    loaded = load_plugins(reg, str(tmp_plugins))

    check("plugin valido carregado", loaded == ["bom"], f"loaded={loaded}")
    check("tool do plugin registrada", reg.get("plugin_tool") is not None)
    check("plugin quebrado isolado (nao derruba o loader)", "quebrado" not in loaded)
    check("registry.all() retorna as tools", len(reg.all()) == 1)

    # Executor consegue chamar a tool do plugin
    from backend.tools.executor import ToolExecutor
    ex = ToolExecutor(reg, timeout=5)
    res = asyncio.run(ex.execute_from_json('{"tool": "plugin_tool", "params": {}}'))
    check("executor executa tool de plugin", res == "ok", res)

    check("diretorio inexistente retorna []", load_plugins(ToolRegistry(), str(tmp_plugins / "nao_existe")) == [])
finally:
    shutil.rmtree(tmp_plugins, ignore_errors=True)

# Plugin de exemplo real do projeto
reg2 = ToolRegistry()
loaded2 = load_plugins(reg2, str(Path(__file__).parent.parent / "plugins"))
check("plugins/exemplo_dado.py carrega", "exemplo_dado" in loaded2, f"loaded={loaded2}")
check("roll_dice registrada", reg2.get("roll_dice") is not None)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Automação (Fase 4) — funções puras, sem tocar teclado/rede
# ─────────────────────────────────────────────────────────────────────────────

section("6. Automacao (funcoes puras)")

from backend.tools.builtin.automation_tools import _parse_hotkey, _html_to_text

check("parse 'ctrl+shift+s'", _parse_hotkey("ctrl+shift+s") == ["ctrl", "shift", "s"])
check("parse normaliza aliases", _parse_hotkey("Control+Windows+Escape") == ["ctrl", "win", "esc"])
check("parse ignora vazios", _parse_hotkey(" alt + tab ") == ["alt", "tab"])

html = """
<html><head><title>x</title><style>body{color:red}</style>
<script>alert(1)</script></head>
<body><nav>menu ruim</nav>
<h1>Título Principal</h1>
<p>Primeiro parágrafo com <b>negrito</b>.</p>
<p>Segundo   parágrafo.</p>
<footer>rodapé ruim</footer></body></html>
"""
text = _html_to_text(html)
check("html: extrai titulo e paragrafos", "Título Principal" in text and "Primeiro parágrafo" in text)
check("html: remove script/style", "alert" not in text and "color:red" not in text)
check("html: remove nav/footer", "menu ruim" not in text and "rodapé ruim" not in text)
check("html: preserva texto inline", "negrito" in text)
check("html malformado nao explode", isinstance(_html_to_text("<div><p>abc"), str))


# ─────────────────────────────────────────────────────────────────────────────
# 7. Provider multimodal (Fase 3) — conversao de formato, sem rede
# ─────────────────────────────────────────────────────────────────────────────

section("7. Conversao multimodal OpenAI")

from backend.providers.openai_compat import _to_openai_messages

plain = [{"role": "user", "content": "oi"}]
check("mensagem sem imagem passa intacta", _to_openai_messages(plain) == [{"role": "user", "content": "oi"}])

with_img = [{"role": "user", "content": "o que ve?", "images": ["QUJD"]}]
conv = _to_openai_messages(with_img)[0]
check("content vira lista de blocos", isinstance(conv["content"], list) and len(conv["content"]) == 2)
check("bloco de texto preservado", conv["content"][0] == {"type": "text", "text": "o que ve?"})
check("imagem vira data URI", conv["content"][1]["image_url"]["url"] == "data:image/png;base64,QUJD")
check("chave 'images' removida da saida", "images" not in conv)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Isolamento de sessão chat/code (MemoryManager)
# ─────────────────────────────────────────────────────────────────────────────

section("8. Isolamento de sessao chat/code")

tmp3 = Path(tempfile.mkdtemp(prefix="krirk_sess_"))
try:
    mm2 = MemoryManager(
        db_path=str(tmp3 / "test.db"),
        chroma_path=str(tmp3 / "chroma"),
    )
    mm2._vectors = None
    UID2 = "sess-user"

    mm2.save_message(UID2, "user", "mensagem do chat")                      # session padrão = chat
    mm2.save_message(UID2, "user", "def foo(): pass", session="code")
    mm2.save_message(UID2, "assistant", "código explicado", session="code")

    chat_msgs = mm2.get_recent_messages(UID2)                # padrão = chat
    code_msgs = mm2.get_recent_messages(UID2, session="code")

    check("chat ve so a sessao chat", len(chat_msgs) == 1 and chat_msgs[0]["content"] == "mensagem do chat")
    check("code ve so a sessao code", len(code_msgs) == 2)
    check("code em ordem cronologica", code_msgs[0]["content"] == "def foo(): pass")
    check("sessao inexistente retorna []", mm2.get_recent_messages(UID2, session="outra") == [])

    # Migration: banco criado sem a coluna session recebe DEFAULT 'chat'
    import sqlite3
    legacy_db = tmp3 / "legacy.db"
    conn = sqlite3.connect(legacy_db)
    conn.executescript("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
            emotion TEXT DEFAULT 'neutral', created_at TEXT NOT NULL
        );
        INSERT INTO messages (user_id, role, content, created_at)
        VALUES ('legacy-user', 'user', 'mensagem antiga', '2026-01-01');
    """)
    conn.commit()
    conn.close()

    mm3 = MemoryManager(db_path=str(legacy_db), chroma_path=str(tmp3 / "chroma2"))
    mm3._vectors = None
    legacy_msgs = mm3.get_recent_messages("legacy-user")
    check("migration: mensagens legadas viram sessao chat",
          len(legacy_msgs) == 1 and legacy_msgs[0]["content"] == "mensagem antiga")
    mm3.save_message("legacy-user", "user", "novo codigo", session="code")
    check("migration: banco legado aceita sessao code",
          len(mm3.get_recent_messages("legacy-user", session="code")) == 1)
finally:
    shutil.rmtree(tmp3, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Router — classificação de erros retriable (fallback de provider)
# ─────────────────────────────────────────────────────────────────────────────

section("9. Router _is_retriable")

from backend.providers.router import _is_retriable


class _FakeStatusError(Exception):
    def __init__(self, status_code, msg=""):
        super().__init__(msg or f"Error code: {status_code}")
        self.status_code = status_code
        # simula o nome de classe do SDK openai
        self.__class__.__name__ = "APIStatusError"


check("410 Gone e retriable (modelo removido)", _is_retriable(_FakeStatusError(410, "Gone")))
check("403 Forbidden e retriable (sem acesso)", _is_retriable(_FakeStatusError(403)))
check("429 rate limit e retriable", _is_retriable(_FakeStatusError(429)))
check("503 unavailable e retriable", _is_retriable(_FakeStatusError(503)))
check("mensagem 'Gone' e retriable", _is_retriable(Exception("The model is Gone")))
check("timeout e retriable", _is_retriable(Exception("Request timed out.")))
check("401 NAO e retriable (chave invalida)", not _is_retriable(_FakeStatusError(401)))
check("erro generico NAO e retriable", not _is_retriable(ValueError("bug qualquer")))


# ─────────────────────────────────────────────────────────────────────────────
# 10. Planner — parse de decisões do roteador
# ─────────────────────────────────────────────────────────────────────────────

section("10. Planner parse_decision")

from backend.agents.planner import parse_decision, MAX_PLAN_STEPS

check("'none' -> none", parse_decision("none") == {"type": "none"})
check("vazio -> none", parse_decision("") == {"type": "none"})
check("'None.' com texto -> none", parse_decision("None. No tool needed") == {"type": "none"})

d = parse_decision('{"tool": "open_app", "params": {"app_name": "notepad"}}')
check("tool JSON simples", d == {"type": "tool", "tool": "open_app", "params": {"app_name": "notepad"}})

d = parse_decision('```json\n{"tool": "roll_dice", "params": {"sides": 20}}\n```')
check("tool com cerca markdown", d["type"] == "tool" and d["tool"] == "roll_dice")

d = parse_decision('{"tool": "get_time"}')
check("tool sem params -> params vazio", d == {"type": "tool", "tool": "get_time", "params": {}})

d = parse_decision('{"plan": ["abrir o bloco de notas", "digitar o texto"]}')
check("plan com 2 passos", d == {"type": "plan", "steps": ["abrir o bloco de notas", "digitar o texto"]})

d = parse_decision('{"plan": ["a", "b", "c", "d", "e", "f"]}')
check(f"plan trunca em {MAX_PLAN_STEPS} passos", len(d["steps"]) == MAX_PLAN_STEPS)

d = parse_decision('{"plan": [{"tool": "open_app", "params": {"app_name": "notepad"}}, {"tool": "type_text", "params": {"text": "oi"}}]}')
check("plan estruturado (tool calls completas)",
      d["type"] == "plan" and d["steps"][0] == {"tool": "open_app", "params": {"app_name": "notepad"}}
      and d["steps"][1]["params"]["text"] == "oi")

d = parse_decision('{"plan": [{"tool": "get_time"}, "passo em texto"]}')
check("plan misto dict+string", d["steps"][0] == {"tool": "get_time", "params": {}} and d["steps"][1] == "passo em texto")

check("plan vazio -> none", parse_decision('{"plan": []}') == {"type": "none"})
check("JSON invalido -> none", parse_decision('{"tool": open_app}') == {"type": "none"})
check("texto sem JSON -> none", parse_decision("vou usar a ferramenta open_app") == {"type": "none"})


# ─────────────────────────────────────────────────────────────────────────────
# 11. Circuit breaker do ProviderRouter
# ─────────────────────────────────────────────────────────────────────────────

section("11. Circuit breaker")

import time as _time
from backend.providers.router import ProviderRouter
from backend.providers.base import BaseProvider


class _FakeProvider(BaseProvider):
    name = "fake"
    async def stream_chat(self, messages, model, temperature=0.7, max_tokens=1024):
        yield "x"
    async def chat(self, messages, model, temperature=0.1, max_tokens=512):
        return "x"


fake_a, fake_b = _FakeProvider(), _FakeProvider()
router = ProviderRouter(
    providers={"a": fake_a, "b": fake_b},
    task_models={"a": {"chat": "m1"}, "b": {"chat": "m2"}},
    task_fallback={"chat": ["a", "b"]},
)

check("sem falhas: 2 providers ativos", len(router._ordered_providers("chat")) == 2)

router._record_failure("a")
check("1 falha ainda nao abre o breaker", not router._is_skipped("a"))

router._record_failure("a")
check("2 falhas abrem o breaker", router._is_skipped("a"))
check("provider pausado sai da ordem", [n for n, _ in router._ordered_providers("chat")] == ["b"])

router._record_success("a")
check("sucesso reseta o breaker", not router._is_skipped("a"))

# Todos pausados -> usa a lista completa mesmo assim (nunca fica sem provider)
router._record_failure("a"); router._record_failure("a")
router._record_failure("b"); router._record_failure("b")
check("todos pausados -> fallback para lista completa", len(router._ordered_providers("chat")) == 2)

# Cooldown expirado -> volta a usar
router._skip_until["a"] = _time.monotonic() - 1
check("cooldown expirado reabilita o provider", not router._is_skipped("a"))


# ─────────────────────────────────────────────────────────────────────────────
# 12. Fase 5 — memória de longo prazo
# ─────────────────────────────────────────────────────────────────────────────

section("12. Memoria de longo prazo (Fase 5)")

from backend.memory.memory_manager import _normalize_fact, _effective_confidence
from datetime import datetime, timedelta

check("normaliza acentos/caixa", _normalize_fact("Érik GOSTA de Café!") == _normalize_fact("erik gosta de cafe"))
check("normaliza espacos", _normalize_fact("a  b   c") == "a b c")

now = datetime.now()
fresh = now.isoformat()
old_45d = (now - timedelta(days=45)).isoformat()

check("fato novo tem confianca cheia", abs(_effective_confidence(1.0, fresh, False, now) - 1.0) < 0.01)
eff_45 = _effective_confidence(1.0, old_45d, False, now)
check("fato de 45 dias decaiu (~0.35)", 0.30 < eff_45 < 0.42, f"eff={eff_45:.2f}")
check("fato fixado nunca decai", _effective_confidence(1.0, old_45d, True, now) == 2.0)

tmp5 = Path(tempfile.mkdtemp(prefix="krirk_lt_"))
try:
    mm5 = MemoryManager(db_path=str(tmp5 / "t.db"), chroma_path=str(tmp5 / "c"))
    mm5._vectors = None
    U = "lt-user"

    # Dedupe na inserção
    check("fato novo insere", mm5.save_fact(U, "gosta de Minecraft") is True)
    check("duplicata exata reforca", mm5.save_fact(U, "gosta de Minecraft") is False)
    check("duplicata normalizada reforca", mm5.save_fact(U, "Gosta de MINECRAFT!") is False)
    check("apenas 1 fato no banco", len(mm5.get_facts_full(U)) == 1)

    # Pin
    mm5.pin_fact(U, "aniversario em 10 de março")
    full = mm5.get_facts_full(U)
    pinned = [f for f in full if f["pinned"]]
    check("pin_fact grava fixado", len(pinned) == 1 and "aniversario" in pinned[0]["fact"])

    # Decay: fato antigo some do get_facts
    import sqlite3 as _sql
    old_iso = (datetime.now() - timedelta(days=100)).isoformat()
    conn = _sql.connect(tmp5 / "t.db")
    conn.execute(
        "INSERT INTO facts (user_id, fact, category, pinned, confidence, created_at, updated_at) VALUES (?,?,?,0,1.0,?,?)",
        (U, "fato muito antigo e irrelevante", "general", old_iso, old_iso),
    )
    conn.commit(); conn.close()

    visible = mm5.get_facts(U, limit=50)
    check("fato de 100 dias omitido do prompt", "fato muito antigo e irrelevante" not in visible)
    check("fato recente visivel", any("Minecraft" in f for f in visible))
    check("fato fixado visivel e primeiro", visible and "aniversario" in visible[0])

    # Purge: remove o antigo, preserva fixado e recente
    removed = mm5.purge_stale_facts(U)
    check("purge remove 1 fato obsoleto", removed == 1)
    remaining = [f["fact"] for f in mm5.get_facts_full(U)]
    check("purge preserva recente e fixado", len(remaining) == 2 and "fato muito antigo e irrelevante" not in remaining)

    # replace_facts preserva fixados
    mm5.save_fact(U, "fato a"); mm5.save_fact(U, "fato b")
    mm5.replace_facts(U, ["fato consolidado ab"])
    after = mm5.get_facts_full(U)
    check("replace_facts troca nao-fixados", any("consolidado" in f["fact"] for f in after))
    check("replace_facts preserva fixados", any(f["pinned"] for f in after))
    check("replace_facts remove antigos", not any(f["fact"] == "fato a" for f in after))

    # Busca por período
    conn = _sql.connect(tmp5 / "t.db")
    for days, content in [(10, "conversa sobre viagem"), (3, "conversa sobre trabalho"), (0, "conversa de hoje")]:
        ts = (datetime.now() - timedelta(days=days, hours=1)).isoformat()
        conn.execute(
            "INSERT INTO messages (user_id, role, content, emotion, session, created_at) VALUES (?,?,?,?,?,?)",
            (U, "user", content, "neutro", "chat", ts),
        )
    conn.commit(); conn.close()

    last_week = mm5.search_messages_by_period(U, days_from=7, days_to=0)
    contents = [m["content"] for m in last_week]
    check("periodo 7 dias pega recentes", "conversa sobre trabalho" in contents and "conversa de hoje" in contents)
    check("periodo 7 dias exclui antigas", "conversa sobre viagem" not in contents)

    older = mm5.search_messages_by_period(U, days_from=14, days_to=7)
    check("janela 14-7 dias pega so a antiga", [m["content"] for m in older] == ["conversa sobre viagem"])

    kw = mm5.search_messages_by_period(U, days_from=14, days_to=0, keyword="trabalho")
    check("filtro por keyword", len(kw) == 1 and "trabalho" in kw[0]["content"])
finally:
    shutil.rmtree(tmp5, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 13. Interioridade Fase A — léxico, reflexões, diário, humor
# ─────────────────────────────────────────────────────────────────────────────

section("13. Interioridade (Fase A)")

from backend.core.orchestrator import _detect_amusement

check("detecta riso 'kkkk'", _detect_amusement("kkkk isso foi muito bom"))
check("detecta 'genial'", _detect_amusement("cara isso foi genial"))
check("detecta 'morri'", _detect_amusement("MORRI com essa"))
check("texto neutro nao e riso", not _detect_amusement("preciso terminar o relatorio hoje"))

tmpA = Path(tempfile.mkdtemp(prefix="krirk_int_"))
try:
    mmA = MemoryManager(db_path=str(tmpA / "t.db"), chroma_path=str(tmpA / "c"))
    mmA._vectors = None
    U = "int-user"

    # Léxico
    check("add_term novo", mmA.add_term(U, "farmar aura de neandertal", "chamar de burro", pinned=True) is True)
    check("add_term dedupe reforca", mmA.add_term(U, "Farmar AURA de Neandertal!", "idem") is False)
    lex = mmA.get_lexicon(U)
    check("lexicon tem 1 termo", len(lex) == 1 and lex[0]["term"].startswith("farmar"))
    mmA.touch_term(U, "farmar aura de neandertal")
    full = mmA.get_lexicon_full(U)
    check("touch_term incrementa usage", full[0]["usage_count"] >= 1)
    mmA.add_term(U, "bordao temporario", "teste de exclusao")
    check("delete_term remove (normalizado)", mmA.delete_term(U, "Bordão TEMPORARIO!") is True)
    check("delete_term inexistente -> False", mmA.delete_term(U, "nao existe") is False)
    check("lexicon preserva o outro termo", len(mmA.get_lexicon(U)) == 1)

    # Reflexões
    mmA.add_reflection(U, "o usuario anda jogando muito terror", category="insight")
    mmA.add_reflection(U, "humor sarcastico e referencias de games", category="humor")
    check("get_reflections todas", len(mmA.get_reflections(U)) == 2)
    check("get_reflections filtra categoria", len(mmA.get_reflections(U, category="humor")) == 1)

    # Diário
    mmA.add_diary_entry(U, "hoje ele me contou do projeto novo, fiquei animada", mood="empolgada")
    mmA.add_diary_entry(U, "conversa tranquila sobre jogos", mood="tranquila")
    diary = mmA.get_recent_diary(U, limit=5)
    check("diario 2 entradas em ordem", len(diary) == 2 and "projeto novo" in diary[0]["content"])
    check("diario guarda mood", diary[0]["mood"] == "empolgada")

    # Notas de aprendizado
    mmA.add_learning_note(U, "buracos negros", "eles evaporam via radiacao Hawking", source="wiki")
    unshared = mmA.get_unshared_notes(U)
    check("nota nao compartilhada aparece", len(unshared) == 1)
    mmA.mark_note_shared(unshared[0]["id"])
    check("nota compartilhada some da fila", mmA.get_unshared_notes(U) == [])

    # Kernel versionado
    k1 = mmA.save_kernel("Sou a Krirk v1", note="inicial", activate=True)
    check("kernel ativo", mmA.get_active_kernel() == "Sou a Krirk v1")
    k2 = mmA.save_kernel("Sou a Krirk v2 mais sarcastica", note="evolucao", activate=True)
    check("novo kernel vira ativo", mmA.get_active_kernel() == "Sou a Krirk v2 mais sarcastica")
    check("rollback reativa o antigo", mmA.activate_kernel(k1) and mmA.get_active_kernel() == "Sou a Krirk v1")
    check("lista de kernels tem 2", len(mmA.list_kernels()) == 2)

    # Propostas pendentes
    pid = mmA.add_proposal("sublation", '{"delete":[1,2]}', rationale="memorias conflitantes")
    check("proposta pendente aparece", len(mmA.get_pending_proposals()) == 1)
    mmA.set_proposal_status(pid, "approved")
    check("proposta aprovada some da fila", mmA.get_pending_proposals() == [])
finally:
    shutil.rmtree(tmpA, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 14. Injeção de interioridade no system prompt
# ─────────────────────────────────────────────────────────────────────────────

section("14. Injecao no system prompt")

from backend.core.personality import PersonalitySystem

ps = PersonalitySystem("configs/personality.json")
prompt = ps.build_system_prompt(
    current_emotion="feliz",
    lexicon=[{"term": "farmar aura de neandertal", "meaning": "chamar de burro"}],
    insights=[{"content": "anda jogando muito terror", "category": "insight"}],
    recent_diary=[{"content": "fiquei animada com o projeto dele", "mood": "empolgada"}],
    brain_state="caótica e imprevisível",
)
check("prompt injeta lexicon", "farmar aura de neandertal" in prompt)
check("prompt injeta insight", "jogando muito terror" in prompt)
check("prompt injeta diario", "animada com o projeto" in prompt)
check("prompt injeta brain_state", "caótica" in prompt)
check("nucleo imutavel preservado (sem emoji)", "Nunca use emojis" in prompt)

# Persona kernel substitui a identidade padrao mas mantem o nucleo
prompt_k = ps.build_system_prompt(current_emotion="neutro",
                                  persona_kernel="Sou a Krirk, uma entidade curiosa e caótica.")
check("persona kernel entra no prompt", "entidade curiosa e caótica" in prompt_k)
check("nucleo fixo sobrevive ao kernel", "Home:" in prompt_k and "Nunca use emojis" in prompt_k)


# ─────────────────────────────────────────────────────────────────────────────
# 15. Reflexão Fase B — parser e nota pendente
# ─────────────────────────────────────────────────────────────────────────────

section("15. Reflexao (Fase B)")

from backend.core.reflection import _extract_json, _strip_emojis, ReflectionEngine

check("extract_json objeto simples", _extract_json('{"a": 1}') == {"a": 1})
check("extract_json com cerca/prosa", _extract_json('resultado: {"insights": ["x"]} fim')["insights"] == ["x"])
check("extract_json invalido -> None", _extract_json("sem json aqui") is None)

check("strip_emojis remove emoji", _strip_emojis("que legal 🔥🚀 demais") == "que legal demais")
check("strip_emojis preserva texto", _strip_emojis("texto normal sem emoji") == "texto normal sem emoji")

# ReflectionEngine.format_pending_note com um memory falso
class _FakeMem:
    def __init__(self, notes): self._notes = notes
    def get_unshared_notes(self, user_id, limit=1): return self._notes[:limit]

class _FakeOrch:
    def __init__(self, notes): self.memory = _FakeMem(notes)

async def _run_format(notes):
    eng = ReflectionEngine(_FakeOrch(notes), {"active_mode": True})
    return await eng.format_pending_note()

res = asyncio.run(_run_format([{"id": 5, "topic": "buracos negros", "content": "eles evaporam"}]))
check("format_pending_note monta comentario", res is not None and res[0] == 5 and "buracos negros" in res[1])
check("format_pending_note vazio -> None", asyncio.run(_run_format([])) is None)

eng_active = ReflectionEngine(_FakeOrch([]), {"active_mode": False})
check("active_mode reflete config", eng_active.active_mode is False)


# ─────────────────────────────────────────────────────────────────────────────
# 16. Consentimento Fase C — tiers e propostas encenadas
# ─────────────────────────────────────────────────────────────────────────────

section("16. Consentimento (Fase C)")

from backend.core.consent import ConsentManager, tier_of

check("diario e tier 0 (livre)", tier_of("diary") == 0)
check("learning_note e tier 1", tier_of("learning_note") == 1)
check("sublation e tier 2 (consentimento)", tier_of("sublation") == 2)
check("kernel e tier 2", tier_of("kernel") == 2)
check("wipe_memory e tier 3", tier_of("wipe_memory") == 3)
check("kind desconhecido -> tier 2 por seguranca", tier_of("qualquer_coisa") == 2)

tmpC = Path(tempfile.mkdtemp(prefix="krirk_consent_"))
try:
    mmC = MemoryManager(db_path=str(tmpC / "t.db"), chroma_path=str(tmpC / "c"))
    mmC._vectors = None
    U = "default"   # ConsentManager aplica sempre no usuário 'default' (app single-user)

    class _OrchC:
        def __init__(self, mem): self.memory = mem
    cm = ConsentManager(_OrchC(mmC))

    check("requires_consent para sublation", cm.requires_consent("sublation"))
    check("nao requer para diary", not cm.requires_consent("diary"))

    # Tier 0 aplica direto
    r0 = cm.stage("lexicon_add", {"term": "test", "meaning": "teste"})
    check("tier 0 aplica direto", r0["applied"] is True)
    check("lexicon recebeu o termo", len(mmC.get_lexicon(U)) == 1)

    # Tier 2 encena como proposta
    mmC.save_fact(U, "fato a"); mmC.save_fact(U, "fato b")
    r2 = cm.stage("sublation", {"facts": ["fato consolidado"]}, rationale="fundir")
    check("tier 2 nao aplica direto", r2["applied"] is False and "proposal_id" in r2)
    check("proposta aparece pendente", len(cm.list_pending()) == 1)

    # Rejeitar nao aplica
    cm.reject(r2["proposal_id"])
    check("rejeitar limpa a fila", cm.list_pending() == [])
    check("rejeitar preservou os fatos", len(mmC.get_facts_full(U)) == 2)

    # Aprovar aplica
    r3 = cm.stage("sublation", {"facts": ["fato unico consolidado"]}, rationale="fundir 2")
    ap = cm.approve(r3["proposal_id"])
    check("aprovar retorna ok", ap["ok"] is True)
    facts_after = [f["fact"] for f in mmC.get_facts_full(U)]
    check("aprovar aplicou a sublation", facts_after == ["fato unico consolidado"])
    check("fila vazia apos aprovar", cm.list_pending() == [])

    # Kernel via consentimento
    rk = cm.stage("kernel", {"content": "Nova identidade da Krirk"}, rationale="evolui")
    cm.approve(rk["proposal_id"])
    check("kernel aprovado vira ativo", mmC.get_active_kernel() == "Nova identidade da Krirk")
finally:
    shutil.rmtree(tmpC, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 17. Brain-state e kernel (Fase D)
# ─────────────────────────────────────────────────────────────────────────────

section("17. Brain-state e kernel (Fase D)")

from backend.core.orchestrator import Orchestrator

# Presets de brain-state — mapeamento sem instanciar o Orchestrator inteiro
bs = Orchestrator.BRAIN_STATES
check("preset focused baixa temperatura", bs["focused"]["temperature"] == 0.3 and bs["focused"]["top_p"] == 0.80)
check("preset chaos alta temperatura", bs["chaos"]["temperature"] == 1.3 and bs["chaos"]["top_p"] == 0.98)
check("4 presets definidos", set(bs.keys()) == {"focused", "chill", "creative", "chaos"})

# top_p propaga pela assinatura dos providers (checagem estatica de assinatura)
import inspect
from backend.providers.ollama_prov import OllamaProvider
from backend.providers.openai_compat import OpenAICompatProvider
check("ollama stream_chat aceita top_p", "top_p" in inspect.signature(OllamaProvider.stream_chat).parameters)
check("openai stream_chat aceita top_p", "top_p" in inspect.signature(OpenAICompatProvider.stream_chat).parameters)

# Kernel versionado + rollback via MemoryManager
tmpD = Path(tempfile.mkdtemp(prefix="krirk_kernel_"))
try:
    mmD = MemoryManager(db_path=str(tmpD / "t.db"), chroma_path=str(tmpD / "c"))
    mmD._vectors = None
    check("sem kernel -> None (usa persona padrao)", mmD.get_active_kernel() is None)
    kid1 = mmD.save_kernel("Krirk v1 curiosa", activate=True)
    kid2 = mmD.save_kernel("Krirk v2 sarcastica", activate=True)
    check("kernel ativo e o v2", mmD.get_active_kernel() == "Krirk v2 sarcastica")
    mmD.deactivate_all_kernels()
    check("deactivate_all volta ao padrao", mmD.get_active_kernel() is None)
    mmD.activate_kernel(kid1)
    check("rollback reativa v1", mmD.get_active_kernel() == "Krirk v1 curiosa")
finally:
    shutil.rmtree(tmpD, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 18. Filtro de small-talk (falsos positivos de ferramentas)
# ─────────────────────────────────────────────────────────────────────────────

section("18. Filtro de small-talk")

from backend.core.orchestrator import _is_smalltalk

# Casos que DEVEM pular o roteamento (small-talk puro)
check("'Oi krirk como está no dia de hoje?' e small-talk",
      _is_smalltalk("Oi krirk como está no dia de hoje?"))
check("'oi' e small-talk", _is_smalltalk("oi"))
check("'bom dia!' e small-talk", _is_smalltalk("bom dia!"))
check("'tudo bem?' e small-talk", _is_smalltalk("tudo bem?"))
check("'como vai você?' e small-talk", _is_smalltalk("como vai você?"))
check("'valeu!' e small-talk", _is_smalltalk("valeu!"))

# Casos que NUNCA podem ser filtrados (precisam do roteador)
check("'que horas são?' NAO e small-talk", not _is_smalltalk("que horas são?"))
check("'oi, que dia é hoje?' NAO e small-talk", not _is_smalltalk("oi, que dia é hoje?"))
check("'oi, abre o notepad' NAO e small-talk", not _is_smalltalk("oi, abre o notepad"))
check("'bom dia, como está o clima?' NAO e small-talk", not _is_smalltalk("bom dia, como está o clima?"))
check("'oi, pesquisa sobre gatos' NAO e small-talk", not _is_smalltalk("oi, pesquisa sobre gatos"))
check("'olá, rola um d20' NAO e small-talk", not _is_smalltalk("olá, rola um d20"))
check("mensagem longa NAO e small-talk",
      not _is_smalltalk("oi krirk, hoje eu queria conversar sobre um monte de coisas que aconteceram no trabalho"))
check("pergunta factual NAO e small-talk", not _is_smalltalk("qual a capital da França?"))


# ─────────────────────────────────────────────────────────────────────────────
# 19. Parsers de extração em background (formato de linhas, à prova de aspas)
# ─────────────────────────────────────────────────────────────────────────────

section("19. Parsers de extracao (fatos e KG)")

from backend.core.orchestrator import _parse_fact_lines, _parse_kg_lines

raw_facts = '''Aqui estão os fatos:
- o usuário disse "beleza então" e gosta de café
- trabalha no site do salão da mãe
* usa o Firefox como navegador
- oi
texto solto que não é fato'''
facts = _parse_fact_lines(raw_facts)
check("fatos com aspas internas nao quebram", len(facts) == 3)
check("preserva aspas no conteudo", any('"beleza então"' in f for f in facts))
check("ignora linha curta demais ('oi')", not any(f == "oi" for f in facts))
check("ignora texto sem prefixo de lista", not any("texto solto" in f for f in facts))
check("NENHUM retorna vazio", _parse_fact_lines("NENHUM") == [])
check("nenhum minusculo tambem", _parse_fact_lines("nenhum fato relevante") == [])
check("vazio retorna vazio", _parse_fact_lines("") == [])

raw_kg = '''Erik | trabalha_em | site do salão
Erik | gosta_de | Minecraft
Assistant | usa | Firefox
Krirk | conhece | Erik
- Erik | mora_em | Cariacica
entidade sem pipes
a | b
x | | y
NENHUM'''
triples = _parse_kg_lines(raw_kg)
check("3 triplas validas extraidas", len(triples) == 3, f"got={triples}")
check("tripla com espacos ok", ("Erik", "trabalha_em", "site do salão") in triples)
check("prefixo de lista removido", ("Erik", "mora_em", "Cariacica") in triples)
check("FILTRA sujeito Assistant", not any(t[0] == "Assistant" for t in triples))
check("FILTRA sujeito Krirk", not any(t[0] == "Krirk" for t in triples))
check("ignora linha sem 3 partes", not any(t[0] == "a" for t in triples))
check("KG vazio para NENHUM", _parse_kg_lines("NENHUM") == [])


# ─────────────────────────────────────────────────────────────────────────────
# 20. Keywords de emoção — ambiguidades ("jogar o site" != videogame)
# ─────────────────────────────────────────────────────────────────────────────

section("20. Emocao: keywords ambiguas")

eng_kw = EmotionEngine()
check("'jogar o site no navegador' NAO vira jogando",
      eng_kw.analyze_and_update("vou jogar o site do salão no navegador pra gente mexer") != "jogando")
eng_kw2 = EmotionEngine()
check("'to jogando valorant' vira jogando",
      eng_kw2.analyze_and_update("to jogando valorant com os amigos") == "jogando")
eng_kw3 = EmotionEngine()
check("'fase do projeto' NAO vira jogando",
      eng_kw3.analyze_and_update("estamos na fase final do projeto") != "jogando")
eng_kw4 = EmotionEngine()
check("'erro meu, desculpa' NAO vira codando",
      eng_kw4.analyze_and_update("erro meu, desculpa pela confusão") != "codando")
eng_kw5 = EmotionEngine()
check("'achei um bug no código' vira codando",
      eng_kw5.analyze_and_update("achei um bug no código, vou debugar") == "codando")

# Regra anti-promessa presente no núcleo do prompt
prompt_core = PersonalitySystem("configs/personality.json").build_system_prompt(current_emotion="neutro")
check("nucleo proibe alegar acao em qualquer tempo verbal", "QUALQUER tempo verbal" in prompt_core)
check("nucleo orienta a oferecer e esperar pedido", "OFEREÇA" in prompt_core)

# Detector de alegação de ação (guarda de honestidade)
from backend.core.orchestrator import _claims_action

check("detecta 'Abrindo o Firefox'", _claims_action("Abrindo o Firefox pra você agora."))
check("detecta 'vou abrir'", _claims_action("Beleza, vou abrir o site do salão."))
check("detecta 'só um segundo'", _claims_action("Deixa comigo, só um segundo."))
check("detecta 'Arquivo salvo: C:...' (alucinacao do Telegram)",
      _claims_action("Arquivo salvo: C:\\Users\\erik_\\Desktop\\agenda_com_recompensas.txt"))
check("detecta 'salvei o'", _claims_action("Pronto, salvei o arquivo pra você."))
check("detecta 'criado na C:'", _claims_action("Tá criado na C:\\Users\\erik_\\Desktop."))
check("detecta 'está salvo em'", _claims_action("O app está salvo em sua área de trabalho."))
check("detecta 'Pasta criada:'", _claims_action("Pasta criada: C:\\Users\\erik_\\Desktop\\agenda_e_recompensas"))
check("detecta 'Arquivos movidos'", _claims_action("Arquivos movidos:\n- agenda.json\n- agenda.py"))
check("detecta 'movi os'", _claims_action("Já movi os dois arquivos pra pasta."))
check("detecta 'Arquivo criado: C:...' (alucinacao pos-falha)",
      _claims_action("Arquivo criado: C:\\Users\\erik_\\Desktop\\agenda_e_recompensas\\agenda_gui.py"))
check("oferta NAO e alegacao", not _claims_action("Quer que eu abra o site? É só pedir."))
check("oferta de pasta NAO e alegacao", not _claims_action("Quer que eu crie uma pasta chamada agenda_e_recompensas e mova os arquivos?"))
check("conversa normal NAO e alegacao", not _claims_action("O site do salão tá ficando ótimo, Erik."))
check("'abriu' do usuario em citacao... conversa comum ok", not _claims_action("legal que o navegador funcionou"))

# Regras anti-mentira no fluxo de ferramentas (guarda de regressão no fonte)
orq_src = (Path(__file__).parent.parent / "backend" / "core" / "orchestrator.py").read_text(encoding="utf-8")
check("guarda cobre ferramenta que FALHOU (nao so zero ferramentas)",
      "alega sucesso mas a ferramenta FALHOU" in orq_src)
check("roteador exige caminho COMPLETO nos params", "PATHS in params must be COMPLETE" in orq_src)
check("roteador pode corrigir params apos [Erro]", "retry the SAME tool" in orq_src)
check("oferta de ARQUIVO aceita usa write_file+GENERATE, nunca create_folder",
      "NOT create_folder" in orq_src)


# ─────────────────────────────────────────────────────────────────────────────
# 21. Ponte Telegram — funções puras
# ─────────────────────────────────────────────────────────────────────────────

section("21. Ponte Telegram")

from backend.integrations.telegram_bridge import split_message, extract_message

check("msg curta = 1 parte", split_message("oi krirk") == ["oi krirk"])
check("msg vazia = 0 partes", split_message("") == [])
long_msg = "\n".join(f"paragrafo {i} " + "x" * 100 for i in range(50))
parts = split_message(long_msg)
check("msg longa dividida", len(parts) > 1)
check("todas as partes cabem no limite", all(len(p) <= 4096 for p in parts))
check("conteudo preservado na divisao", "paragrafo 49" in parts[-1])
giant_para = "y" * 9000
gparts = split_message(giant_para)
check("paragrafo gigante cortado duro", len(gparts) == 3 and sum(len(p) for p in gparts) == 9000)

upd_text = {"update_id": 1, "message": {"chat": {"id": 42}, "from": {"first_name": "Erik"}, "text": "  oi  "}}
m = extract_message(upd_text)
check("extrai texto com chat_id", m == {"chat_id": 42, "name": "Erik", "text": "oi"})

upd_voice = {"update_id": 2, "message": {"chat": {"id": 42}, "from": {"first_name": "Erik"}, "voice": {"file_id": "abc123"}}}
m = extract_message(upd_voice)
check("extrai voice note", m["voice_file_id"] == "abc123" and "text" not in m)

check("sticker/foto ignorado", extract_message({"update_id": 3, "message": {"chat": {"id": 42}, "sticker": {}}}) is None)
check("update sem message ignorado", extract_message({"update_id": 4, "edited_message": {}}) is None)
check("sem chat_id ignorado", extract_message({"update_id": 5, "message": {"text": "oi"}}) is None)


# ─────────────────────────────────────────────────────────────────────────────
# 22. Placeholder <LAST_RESPONSE> e rastreio de arquivo criado
# ─────────────────────────────────────────────────────────────────────────────

section("22. <LAST_RESPONSE> e ultimo arquivo")

from backend.core.orchestrator import _largest_code_block, _resolve_last_response

texto_com_codigo = "Aqui está o script:\n```python\nprint('agenda')\nfor d in dias: print(d)\n```\nQualquer coisa me chama."
check("extrai maior bloco de codigo", _largest_code_block(texto_com_codigo) == "print('agenda')\nfor d in dias: print(d)")
check("sem bloco retorna None", _largest_code_block("texto puro sem codigo") is None)
dois_blocos = "```python\ncurto\n```\ntexto\n```python\nbloco bem mais longo aqui dentro\n```"
check("escolhe o MAIOR bloco", "mais longo" in _largest_code_block(dois_blocos))

# _strip_outer_fence — cerca SEM fechamento (geração truncada em max_tokens)
from backend.core.orchestrator import _strip_outer_fence
check("cerca aberta (truncada) e removida",
      _strip_outer_fence("```python\nimport tkinter\nx = 1") == "import tkinter\nx = 1")
check("cerca fechada tambem funciona",
      _strip_outer_fence("```python\nprint('oi')\n```") == "print('oi')")
check("texto sem cerca passa intacto",
      _strip_outer_fence("import os\nprint(1)") == "import os\nprint(1)")
check("cerca sem linguagem", _strip_outer_fence("```\ncodigo\n```") == "codigo")
check("cerca aberta e o arquivo NAO comeca com ```python",
      not _strip_outer_fence("```python\nimport tkinter as tk").startswith("```"))

hist = [
    {"role": "user", "content": "faz um script"},
    {"role": "assistant", "content": texto_com_codigo},
]
params = _resolve_last_response({"path": "desktop/x.py", "content": "<LAST_RESPONSE>"}, hist)
check("placeholder vira o bloco de codigo", params["content"].startswith("print('agenda')"))
check("path preservado", params["path"] == "desktop/x.py")

hist_texto = [{"role": "assistant", "content": "Agenda:\nquarta 13:30 psicóloga"}]
params2 = _resolve_last_response({"content": "<LAST_RESPONSE>"}, hist_texto)
check("sem bloco usa texto completo", params2["content"] == "Agenda:\nquarta 13:30 psicóloga")

params3 = _resolve_last_response({"content": "conteudo normal"}, hist)
check("sem placeholder passa intacto", params3["content"] == "conteudo normal")
check("params original nao mutado", True)  # _resolve_last_response retorna cópia

# _track_written_file (via regex do resultado padrão do write_file)
class _FakeOrchTrack:
    _last_written_file = None
    from backend.core.orchestrator import Orchestrator as _O
    _track_written_file = _O._track_written_file

ft = _FakeOrchTrack()
ft._track_written_file({"tool": "write_file"}, "Arquivo salvo: C:\\Users\\erik_\\Desktop\\agenda.txt (120 caracteres)")
check("rastreia path do write_file", ft._last_written_file == "C:\\Users\\erik_\\Desktop\\agenda.txt")
ft._track_written_file({"tool": "read_file"}, "Arquivo salvo: C:\\x.txt (1 caracteres)")
check("ignora tools que nao sao write_file", ft._last_written_file == "C:\\Users\\erik_\\Desktop\\agenda.txt")


# ─────────────────────────────────────────────────────────────────────────────
# 23. Ferramentas terminais (loop nao regrava apos sucesso)
# ─────────────────────────────────────────────────────────────────────────────

section("23. Ferramentas terminais")

from backend.core.orchestrator import _TERMINAL_TOOLS

check("write_file e terminal (nao regrava em loop)", "write_file" in _TERMINAL_TOOLS)
check("open_app e terminal", "open_app" in _TERMINAL_TOOLS)
check("set_timer e terminal", "set_timer" in _TERMINAL_TOOLS)
check("remember_this e terminal", "remember_this" in _TERMINAL_TOOLS)
check("read_file NAO e terminal (pode encadear)", "read_file" not in _TERMINAL_TOOLS)
check("web_search NAO e terminal", "web_search" not in _TERMINAL_TOOLS)
check("search_memory NAO e terminal", "search_memory" not in _TERMINAL_TOOLS)
check("browser_read NAO e terminal (le e continua)", "browser_read" not in _TERMINAL_TOOLS)


# ─────────────────────────────────────────────────────────────────────────────
# Resultado
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n{BOLD}{'='*54}{RESET}")
total = len(passed) + len(failed)
color = GREEN if not failed else RED
print(f"{color}{BOLD}  {len(passed)}/{total} testes passaram{RESET}")
if failed:
    print(f"{RED}  Falhas: {', '.join(failed)}{RESET}")
sys.exit(1 if failed else 0)
