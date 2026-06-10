"""
tests/test_krirk.py
Roda com:  .venv\\Scripts\\python.exe tests\\test_krirk.py
Sem pytest -- script standalone que mostra PASS / FAIL por categoria.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

# Carrega .env
from pathlib import Path
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# ── Helpers de output ─────────────────────────────────────────────────────────

RESET = "\033[0m"
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
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

def section(title: str):
    print(f"\n{BOLD}{title}{RESET}")
    print("  " + "-" * 50)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Configuração
# ─────────────────────────────────────────────────────────────────────────────

section("1. Configuracao")

try:
    import yaml
    config_path = Path(__file__).parent.parent / "configs" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    ok("config.yaml carregado")
except Exception as e:
    fail("config.yaml carregado", str(e))
    config = {}

# Chaves de API no env
for key in ["NVIDIA_API_KEY", "GOOGLE_API_KEY", "CEREBRAS_API_KEY"]:
    val = os.getenv(key, "")
    if val and len(val) > 10:
        ok(f"{key} presente", f"len={len(val)}")
    else:
        fail(f"{key} presente", "nao encontrada no .env")

# Modelos nvidia no config
nvidia_models = config.get("providers", {}).get("nvidia", {}).get("models", {})
for task in ["chat", "tools", "code"]:
    m = nvidia_models.get(task, "")
    if m:
        ok(f"nvidia.{task} configurado", m)
    else:
        fail(f"nvidia.{task} configurado", "ausente no config.yaml")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Provider NVIDIA (SSL + latencia)
# ─────────────────────────────────────────────────────────────────────────────

section("2. Provider NVIDIA NIM")

async def test_nvidia():
    try:
        from backend.providers.openai_compat import make_nvidia
        p = make_nvidia()
        if not p.is_available():
            fail("NVIDIA disponivel", "NVIDIA_API_KEY ausente")
            return

        model = nvidia_models.get("chat", "meta/llama-3.3-70b-instruct")
        t0 = time.perf_counter()
        result = await p.chat(
            messages=[{"role": "user", "content": "respond with exactly: pong"}],
            model=model,
            max_tokens=10,
        )
        elapsed = time.perf_counter() - t0

        if result and len(result) > 0:
            ok("NVIDIA chat responde", f"{elapsed:.1f}s | {result.strip()[:40]}")
        else:
            fail("NVIDIA chat responde", "resposta vazia")
    except Exception as e:
        fail("NVIDIA chat responde", str(e)[:120])

asyncio.run(test_nvidia())

async def test_nvidia_tools():
    try:
        from backend.providers.openai_compat import make_nvidia
        p = make_nvidia()
        if not p.is_available():
            return
        model = nvidia_models.get("tools", "mistralai/mistral-small-4-119b-2603")
        t0 = time.perf_counter()
        result = await p.chat(
            messages=[{"role": "user", "content": "respond with exactly: pong"}],
            model=model,
            max_tokens=10,
        )
        elapsed = time.perf_counter() - t0
        if result:
            ok("NVIDIA tools model responde", f"{elapsed:.1f}s")
        else:
            fail("NVIDIA tools model responde", "resposta vazia")
    except Exception as e:
        fail("NVIDIA tools model responde", str(e)[:120])

asyncio.run(test_nvidia_tools())


# ─────────────────────────────────────────────────────────────────────────────
# 3. Router com fallback
# ─────────────────────────────────────────────────────────────────────────────

section("3. Router (cadeia de fallback)")

async def test_router():
    try:
        from backend.providers.router import build_router
        router = build_router(config)
        ok("build_router inicializa")

        t0 = time.perf_counter()
        result = await router.complete(
            "chat",
            [{"role": "user", "content": "responda apenas: oi"}],
            max_tokens=15,
        )
        elapsed = time.perf_counter() - t0

        if result and len(result.strip()) > 0:
            ok("router.complete('chat') retorna", f"{elapsed:.1f}s | {result.strip()[:50]}")
        else:
            fail("router.complete('chat') retorna", "vazio")

        t0 = time.perf_counter()
        result2 = await router.complete(
            "tools",
            [{"role": "user", "content": "que horas sao? return tool name or 'none'"}],
            max_tokens=20,
        )
        elapsed2 = time.perf_counter() - t0
        if result2:
            ok("router.complete('tools') retorna", f"{elapsed2:.1f}s | {result2.strip()[:50]}")
        else:
            fail("router.complete('tools') retorna", "vazio")

    except Exception as e:
        fail("router funciona", str(e)[:200])

asyncio.run(test_router())


# ─────────────────────────────────────────────────────────────────────────────
# 4. Ferramenta execute_python
# ─────────────────────────────────────────────────────────────────────────────

section("4. Tool execute_python")

async def test_execute_python():
    try:
        from backend.tools.builtin.code_tools import make_execute_python
        tool = make_execute_python()
        ok("make_execute_python() cria Tool")

        # Calculo simples
        result = await tool.func(code="print(2 ** 10)")
        if "1024" in result:
            ok("executa print(2**10)", result.strip())
        else:
            fail("executa print(2**10)", f"saida inesperada: {result}")

        # Captura stderr
        result2 = await tool.func(code="raise ValueError('test error')")
        if "ValueError" in result2 or "error" in result2.lower():
            ok("captura excecao Python", result2.strip()[:60])
        else:
            fail("captura excecao Python", result2)

        # Timeout
        result3 = await tool.func(code="import time; time.sleep(20)", timeout=2.0)
        if "timeout" in result3.lower() or "Timeout" in result3:
            ok("timeout funciona (2s)", result3.strip())
        else:
            fail("timeout funciona (2s)", result3)

    except Exception as e:
        fail("execute_python funciona", str(e)[:200])

asyncio.run(test_execute_python())


# ─────────────────────────────────────────────────────────────────────────────
# 5. Registry de ferramentas
# ─────────────────────────────────────────────────────────────────────────────

section("5. ToolRegistry")

try:
    from backend.tools.registry import build_default_registry
    tools_cfg = config.get("tools", {})
    registry = build_default_registry(tools_cfg)
    tool_names = registry.list_names()
    ok(f"registry carregado ({len(tool_names)} ferramentas)", ", ".join(tool_names[:6]) + "...")

    if "execute_python" in tool_names:
        ok("execute_python no registry")
    else:
        fail("execute_python no registry", f"ferramentas: {tool_names}")

    if "get_time" in tool_names:
        ok("get_time no registry")
    else:
        fail("get_time no registry")

except Exception as e:
    fail("registry carregado", str(e)[:200])


# ─────────────────────────────────────────────────────────────────────────────
# 6. Ollama local
# ─────────────────────────────────────────────────────────────────────────────

section("6. Ollama local")

async def test_ollama():
    try:
        import ollama
        client = ollama.AsyncClient()
        models_resp = await client.list()
        model_names = [m.model for m in models_resp.models]

        required = ["gemma3:4b", "qwen2.5-coder:7b", "nomic-embed-text"]
        for m in required:
            # verifica prefixo (o ollama pode adicionar :latest)
            present = any(n.startswith(m.split(":")[0]) for n in model_names)
            if present:
                ok(f"ollama modelo {m}")
            else:
                fail(f"ollama modelo {m}", f"modelos disponiveis: {model_names}")

        # Ping rapido
        t0 = time.perf_counter()
        resp = await client.chat(
            model="gemma3:4b",
            messages=[{"role": "user", "content": "responda so: oi"}],
            options={"num_predict": 5},
        )
        elapsed = time.perf_counter() - t0
        content = resp.get("message", {}).get("content", "")
        if content:
            ok("gemma3:4b responde", f"{elapsed:.1f}s")
        else:
            fail("gemma3:4b responde", "vazio")

    except Exception as e:
        fail("ollama acessivel", str(e)[:200])

asyncio.run(test_ollama())


# ─────────────────────────────────────────────────────────────────────────────
# 7. WebSocket (precisa do backend rodando)
# ─────────────────────────────────────────────────────────────────────────────

section("7. WebSocket (requer backend rodando em localhost:8000)")

async def test_websocket():
    try:
        import websockets
        uri = "ws://localhost:8000/ws/test_suite"
        async with websockets.connect(uri, open_timeout=3) as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg.get("type") == "connected":
                ok("WebSocket conecta e recebe 'connected'")
            else:
                fail("WebSocket conecta e recebe 'connected'", f"tipo: {msg.get('type')}")

            # Envia chat simples
            await ws.send(json.dumps({"type": "chat", "content": "diga apenas: teste ok"}))
            tokens = []
            deadline = time.time() + 45  # NVIDIA pode demorar até ~10s para 1º token
            got_response_complete = False
            while time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                try:
                    raw2 = await asyncio.wait_for(ws.recv(), timeout=min(12.0, remaining))
                    ev = json.loads(raw2)
                    if ev.get("type") == "token":
                        tokens.append(ev.get("content", ""))
                    elif ev.get("type") == "response_complete":
                        got_response_complete = True
                        break
                except asyncio.TimeoutError:
                    if tokens:  # já recebeu tokens, parou de chegar
                        break
                    # ainda aguardando 1º token — continua

            full = "".join(tokens)
            if full.strip():
                ok("WebSocket streaming chat", full.strip()[:60])
            else:
                fail("WebSocket streaming chat", "nenhum token recebido")

    except (ConnectionRefusedError, OSError):
        print(f"  {YELLOW}SKIP{RESET} WebSocket — backend nao esta rodando (inicie com start_backend.bat)")
    except Exception as e:
        fail("WebSocket", str(e)[:200])

asyncio.run(test_websocket())


# ─────────────────────────────────────────────────────────────────────────────
# 8. WebSocket — Modo Coder
# ─────────────────────────────────────────────────────────────────────────────

section("8. WebSocket Modo Coder (requer backend rodando)")

async def test_code_ws():
    try:
        import websockets
        uri = "ws://localhost:8000/ws/test_coder"
        async with websockets.connect(uri, open_timeout=3) as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)  # connected

            await ws.send(json.dumps({
                "type": "code_chat",
                "content": "escreva um hello world em python de uma linha"
            }))
            tokens = []
            deadline = time.time() + 45
            while time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(12.0, remaining))
                    ev = json.loads(raw)
                    if ev.get("type") == "token":
                        tokens.append(ev.get("content", ""))
                    elif ev.get("type") == "response_complete":
                        break
                except asyncio.TimeoutError:
                    if tokens:
                        break

            full = "".join(tokens)
            if "print" in full.lower() or "hello" in full.lower():
                ok("code_chat retorna codigo Python", full.strip()[:80])
            elif full.strip():
                ok("code_chat retorna resposta", full.strip()[:80])
            else:
                fail("code_chat retorna resposta", "nenhum token")

    except (ConnectionRefusedError, OSError):
        print(f"  {YELLOW}SKIP{RESET} code_chat — backend nao esta rodando")
    except Exception as e:
        fail("code_chat WebSocket", str(e)[:200])

asyncio.run(test_code_ws())


# ─────────────────────────────────────────────────────────────────────────────
# Resultado final
# ─────────────────────────────────────────────────────────────────────────────

total = len(passed) + len(failed)
print(f"\n{'='*54}")
print(f"{BOLD}Resultado: {GREEN}{len(passed)} PASS{RESET}{BOLD} / {RED}{len(failed)} FAIL{RESET}{BOLD} de {total} testes{RESET}")
if failed:
    print(f"\n{RED}Falharam:{RESET}")
    for name in failed:
        print(f"  - {name}")
print()
sys.exit(1 if failed else 0)
