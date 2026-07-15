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

# Roundtrip write → read → list em pasta temporária (dentro do home no Windows)
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
# Resultado
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n{BOLD}{'='*54}{RESET}")
total = len(passed) + len(failed)
color = GREEN if not failed else RED
print(f"{color}{BOLD}  {len(passed)}/{total} testes passaram{RESET}")
if failed:
    print(f"{RED}  Falhas: {', '.join(failed)}{RESET}")
sys.exit(1 if failed else 0)
