"""
backend/integrations/claude_code.py
Delegação de tarefas de código ao Claude Code CLI.

Dois modos (config claude_code.interactive):
- INTERATIVO (padrão): abre a JANELA REAL do Claude Code na pasta de trabalho;
  o usuário acompanha ao vivo e a janela fica aberta. A tarefa vai por arquivo
  (_KRIRK_TAREFA.md) e o .bat lançador é ASCII puro (evita aspas/acentos no
  Windows). Fire-and-forget: a Krirk não rastreia a conclusão.
- HEADLESS: roda em segundo plano (stream-json), grava um log de progresso e
  anuncia a conclusão pelos canais proativos (WS + TTS + Telegram).
"""
import asyncio
import json
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Awaitable, Callable

from backend.tools.base import Tool, ToolParam

_HOME = Path.home()

# Fallback quando o instalador nativo não coloca o CLI no PATH do processo
_DEFAULT_CLI = _HOME / ".local" / "bin" / "claude.exe"

# Separador de fim de tarefa no log de progresso (a janela NÃO fecha sozinha:
# o usuário reutiliza a mesma janela e mantém o histórico das tarefas)
_END_SENTINEL = "=== FIM DA TAREFA ==="

# Log persistente de progresso — acumula todas as tarefas (data/ é gitignored)
_PROGRESS_LOG = Path("data") / "claude_code.log"


def find_cli() -> str | None:
    """Localiza o executável do Claude Code CLI."""
    found = shutil.which("claude")
    if found:
        return found
    if _DEFAULT_CLI.exists():
        return str(_DEFAULT_CLI)
    return None


def build_cli_args(model: str, max_turns: int) -> list[str]:
    """
    Argumentos do CLI (sem o executável). O prompt vai por STDIN — nunca
    por argv — para não brigar com aspas/acentos no Windows.
    """
    args = [
        "-p",
        # stream-json emite eventos linha a linha (progresso ao vivo na
        # janela de acompanhamento); o evento final "result" tem o mesmo
        # formato do modo json. --verbose é exigido pelo stream-json no -p.
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", "acceptEdits",
        "--max-turns", str(max_turns),
        "--allowedTools", "Bash(python *)",
    ]
    if model:
        args += ["--model", model]
    return args


def build_task_prompt(task: str) -> str:
    """Prompt que a Krirk envia ao agente delegado."""
    return (
        "Você é o executor de tarefas de código da assistente KRIRK, rodando "
        "no computador pessoal do usuário. O diretório atual (cwd) JÁ É a "
        "pasta do projeto: crie/edite os arquivos DIRETO nela, sem criar uma "
        "subpasta com o nome do projeto. Trabalhe APENAS dentro dela. "
        "Execute esta tarefa por completo:\n\n"
        f"{task}\n\n"
        "Regras: código funcional e enxuto; prefira a biblioteca padrão do "
        "Python salvo pedido explícito; se fizer sentido, rode o código para "
        "conferir que funciona. Ao terminar, responda com um resumo curto em "
        "português (2-3 frases), texto puro SEM markdown (sem **, sem `), "
        "do que foi feito."
    )


def parse_cli_output(raw: str) -> tuple[str, bool]:
    """
    Extrai (resumo, deu_erro) da saída do CLI em --output-format json:
    {"type":"result","subtype":"success","is_error":false,"result":"..."}.
    Saída não-JSON vira texto cru (últimos 1500 chars).
    """
    raw = (raw or "").strip()
    if not raw:
        return "", True
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            txt = str(data.get("result") or "").strip()
            return txt, bool(data.get("is_error")) or not txt
    except json.JSONDecodeError:
        pass
    return raw[-1500:], False


def format_stream_event(raw_line: str) -> str | None:
    """
    Converte um evento stream-json do CLI em linha legível pro log de
    progresso (janela de acompanhamento). None = evento sem interesse.
    """
    try:
        ev = json.loads(raw_line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(ev, dict):
        return None
    t = ev.get("type")
    if t == "system" and ev.get("subtype") == "init":
        return f"[inicio] modelo {ev.get('model', '?')}"
    if t == "assistant":
        parts = []
        for block in (ev.get("message") or {}).get("content", []):
            bt = block.get("type")
            if bt == "text" and (block.get("text") or "").strip():
                parts.append(f"[claude] {block['text'].strip()}")
            elif bt == "tool_use":
                name = block.get("name", "?")
                inp = block.get("input") or {}
                target = str(
                    inp.get("file_path") or inp.get("path")
                    or inp.get("command") or inp.get("pattern") or ""
                )[:120]
                parts.append(f"[ferramenta] {name}: {target}" if target else f"[ferramenta] {name}")
        return "\n".join(parts) if parts else None
    if t == "result":
        status = "ERRO" if ev.get("is_error") else "ok"
        return f"[fim:{status}] {str(ev.get('result', ''))[:400]}"
    return None


def _append_progress(path: Path | None, text: str) -> None:
    if path is None or not text:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass


def run_cli_blocking(
    cli: str,
    args: list[str],
    prompt: str,
    cwd: str,
    timeout: int,
    progress_path: Path | None = None,
) -> tuple[int, str, str]:
    """
    Executa o CLI de forma BLOQUEANTE (chamar via asyncio.to_thread), lendo
    o stdout linha a linha: cada evento stream-json vira progresso legível
    no log e o evento final "result" vira o payload retornado (sem evento
    result, retorna as últimas linhas cruas — fallback).
    asyncio.create_subprocess_exec NÃO funciona aqui: o uvicorn usa
    SelectorEventLoop no Windows, que não implementa subprocess assíncrono
    (NotImplementedError com mensagem vazia).
    Timeout estourado mata o processo e levanta subprocess.TimeoutExpired.
    """
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [cli, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        creationflags=flags,
    )
    killed: list[bool] = []

    def _kill():
        killed.append(True)
        proc.kill()

    watchdog = threading.Timer(timeout, _kill)
    watchdog.start()
    result_line = ""
    tail: list[str] = []
    try:
        proc.stdin.write(prompt.encode("utf-8"))
        proc.stdin.close()
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line.strip():
                continue
            tail.append(line)
            if len(tail) > 200:
                tail.pop(0)
            pretty = format_stream_event(line)
            if pretty:
                _append_progress(progress_path, pretty)
            try:
                if json.loads(line).get("type") == "result":
                    result_line = line
            except (json.JSONDecodeError, AttributeError):
                pass
        err = proc.stderr.read().decode("utf-8", errors="replace")
        rc = proc.wait()
    finally:
        watchdog.cancel()
    if killed:
        raise subprocess.TimeoutExpired([cli], timeout)
    return rc, result_line or "\n".join(tail), err


def snapshot_dir(folder: Path) -> dict[str, float]:
    """Mapa arquivo-relativo → mtime (ignora __pycache__)."""
    snap: dict[str, float] = {}
    if not folder.exists():
        return snap
    for p in folder.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            try:
                snap[str(p.relative_to(folder))] = p.stat().st_mtime
            except OSError:
                pass
    return snap


def diff_snapshot(before: dict[str, float], after: dict[str, float]) -> list[str]:
    """Lista legível do que mudou entre dois snapshots."""
    changed: list[str] = []
    for rel in sorted(after):
        if rel not in before:
            changed.append(f"novo: {rel}")
        elif after[rel] != before[rel]:
            changed.append(f"alterado: {rel}")
    for rel in sorted(before):
        if rel not in after:
            changed.append(f"removido: {rel}")
    return changed


class ClaudeCodeDelegator:
    """
    Uma tarefa por vez (single-slot): start() retorna na hora e a execução
    segue em background; ao final, notify(texto) anuncia o resultado.
    """

    def __init__(
        self,
        config: dict,
        notify: Callable[[str], Awaitable],
        cli_path: str | None = None,
    ):
        self._cfg = config or {}
        self._notify = notify
        self._cli = cli_path if cli_path is not None else find_cli()
        self.job: dict | None = None
        self._window_proc: subprocess.Popen | None = None

    def is_available(self) -> bool:
        return bool(self._cli)

    def start(self, task: str, folder: Path) -> str:
        if not self._cli:
            return "[Erro] Claude Code CLI não encontrado neste computador."
        # Modo interativo (padrão): abre a JANELA REAL do Claude Code e o
        # usuário acompanha ao vivo. Modo headless: roda em segundo plano e
        # avisa quando termina.
        if self._cfg.get("interactive", True):
            return self._start_interactive(task, folder)

        if self.job is not None:
            mins = int((time.time() - self.job["started"]) // 60)
            return (
                f"[Erro] Já existe uma tarefa de código em andamento há {mins} min "
                f"('{self.job['task'][:60]}'). Espere o aviso de conclusão."
            )
        folder.mkdir(parents=True, exist_ok=True)
        self.job = {"task": task, "folder": str(folder), "started": time.time()}
        asyncio.create_task(self._run(task, folder))
        print(f"[KRIRK][claude-code] Delegado: '{task[:80]}' em {folder}")
        return (
            f"Tarefa delegada ao agente de código (Claude Code), rodando em "
            f"SEGUNDO PLANO na pasta {folder}: {task[:150]}\n"
            "Você será avisado quando terminar — dá pra continuar conversando."
        )

    def _start_interactive(self, task: str, folder: Path) -> str:
        """
        Abre o Claude Code INTERATIVO numa janela nova, trabalhando em `folder`.
        A tarefa (com acentos) vai por ARQUIVO; o .bat lançador fica em ASCII
        puro (sem inferno de aspas no Windows). A janela fica aberta — o
        usuário acompanha e continua a sessão se quiser.
        """
        try:
            folder.mkdir(parents=True, exist_ok=True)
            task_file = folder / "_KRIRK_TAREFA.md"
            task_file.write_text(
                f"# Tarefa da KRIRK\n\n{task}\n", encoding="utf-8"
            )
        except OSError as e:
            return f"[Erro] Não consegui preparar a pasta de trabalho: {e}"

        model = str(self._cfg.get("model", "sonnet") or "sonnet")
        prompt = (
            "Leia o arquivo _KRIRK_TAREFA.md nesta pasta e realize a tarefa "
            "descrita nele. Trabalhe apenas nesta pasta. Prefira a biblioteca "
            "padrao do Python. Rode o codigo para conferir que funciona. Ao "
            "terminar, escreva um breve resumo do que fez."
        )
        # Autônomo (padrão): --dangerously-skip-permissions pula o prompt de
        # "confiar na pasta" e cada permissão — a janela trabalha sozinha e o
        # usuário só assiste. autonomous:false volta ao acceptEdits (o usuário
        # aprova a confiança + ações), útil se quiser controle passo a passo.
        if self._cfg.get("autonomous", True):
            perm = "--dangerously-skip-permissions"
        else:
            perm = '--permission-mode acceptEdits --allowedTools "Bash(python *)"'
        bat = Path(tempfile.gettempdir()) / f"krirk_claude_{int(time.time())}.bat"
        bat_body = (
            "@echo off\r\n"
            "title KRIRK - Claude Code\r\n"
            f'cd /d "{folder}"\r\n'
            f'"{self._cli}" --model {model} {perm} "{prompt}"\r\n'
            "echo.\r\n"
            "echo === Sessao do Claude Code encerrada. Feche quando quiser. ===\r\n"
        )
        try:
            bat.write_text(bat_body, encoding="ascii")
            subprocess.Popen(
                ["cmd", "/c", "start", "KRIRK - Claude Code", "cmd", "/k", str(bat)],
                cwd=str(folder),
            )
        except Exception as e:
            return f"[Erro] Não consegui abrir a janela do Claude Code: {e}"
        print(f"[KRIRK][claude-code] Janela interativa aberta em {folder}: '{task[:80]}'")
        return (
            f"Abri o Claude Code numa janela pra trabalhar nisso, na pasta "
            f"{folder}. Dá pra acompanhar tudo por lá ao vivo — a janela fica "
            "aberta. Não tem como eu saber daqui quando ele termina, então dá "
            "uma olhada na janela."
        )

    def _open_progress_window(self, log_path: Path) -> None:
        """
        Abre (ou REUTILIZA) o console que acompanha o log ao vivo. A janela
        NUNCA fecha sozinha: o usuário mantém o histórico de todas as tarefas
        e fecha quando quiser — se fechar, a próxima tarefa abre outra
        mostrando as últimas 400 linhas (contexto preservado no log).
        """
        if self._window_proc is not None and self._window_proc.poll() is None:
            return  # janela ainda aberta — o log em -Wait puxa o novo conteúdo
        ps_cmd = (
            "$host.UI.RawUI.WindowTitle = 'KRIRK - Claude Code'; "
            f"Get-Content -LiteralPath '{log_path}' -Wait -Tail 400"
        )
        try:
            self._window_proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-Command", ps_cmd],
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
        except Exception as e:
            print(f"[KRIRK][claude-code] Janela de progresso falhou: {e}")

    async def _run(self, task: str, folder: Path) -> None:
        timeout = int(self._cfg.get("timeout_seconds", 600))
        model = str(self._cfg.get("model", "") or "")
        max_turns = int(self._cfg.get("max_turns", 30))

        # Janela de acompanhamento (config claude_code.show_window) — log
        # persistente: cada tarefa é um bloco novo no mesmo arquivo
        progress: Path | None = None
        if self._cfg.get("show_window", True):
            progress = _PROGRESS_LOG
            try:
                progress.parent.mkdir(parents=True, exist_ok=True)
                if not progress.exists():
                    # utf-8-sig: BOM faz o Get-Content do PS 5.1 ler acentos
                    progress.write_text("", encoding="utf-8-sig")
                _append_progress(
                    progress,
                    "\n" + "═" * 60 + "\n"
                    f"NOVA TAREFA — {time.strftime('%d/%m %H:%M:%S')}\n"
                    f"Tarefa: {task}\nPasta: {folder}\n" + "─" * 60,
                )
                self._open_progress_window(progress)
            except OSError:
                progress = None

        before = snapshot_dir(folder)
        summary, ok = "", False
        try:
            rc, out, err = await asyncio.to_thread(
                run_cli_blocking,
                self._cli, build_cli_args(model, max_turns),
                build_task_prompt(task), str(folder), timeout, progress,
            )
        except subprocess.TimeoutExpired:
            summary = f"passou do limite de {timeout // 60} minutos e foi cancelada"
        except Exception as e:
            summary = f"falha ao executar o CLI: {type(e).__name__}: {e}"
        else:
            parsed, is_err = parse_cli_output(out)
            if rc == 0 and not is_err:
                summary, ok = parsed, True
            else:
                summary = parsed or err.strip()[-400:] or f"CLI saiu com código {rc}"
        _append_progress(
            progress,
            f"\n{_END_SENTINEL} ({'concluída' if ok else 'FALHOU'}) — "
            f"{time.strftime('%H:%M:%S')}",
        )

        changed = diff_snapshot(before, snapshot_dir(folder))
        status = "ok" if ok else "FALHOU"
        print(f"[KRIRK][claude-code] Tarefa {status} — {len(changed)} mudança(s) em {folder}")
        await self._announce(task, folder, summary, ok, changed)
        self.job = None

    async def _announce(
        self, task: str, folder: Path, summary: str, ok: bool, changed: list[str]
    ) -> None:
        # O aviso passa pelo TTS — markdown vira ruído falado
        summary = summary.replace("**", "").replace("`", "").replace("#", "").strip()
        if ok:
            msg = f"Terminei aquela tarefa de código. {summary}".strip()
            if changed:
                msg += "\nMudanças em " + str(folder) + ": " + "; ".join(changed[:10])
                if len(changed) > 10:
                    msg += f" (+{len(changed) - 10})"
            elif "removido" not in summary:
                msg += f"\nObs: nenhum arquivo mudou em {folder} — confere se era isso mesmo."
        else:
            msg = (
                f"Não consegui terminar a tarefa de código ('{task[:80]}'). "
                f"Problema: {summary[:300]}. Quer que eu tente de novo?"
            )
        try:
            await self._notify(msg)
        except Exception as e:
            print(f"[KRIRK][claude-code] Falha ao anunciar conclusão: {e}")


def make_delegate_code(delegator: ClaudeCodeDelegator, work_dir: str = "Desktop") -> Tool:
    from backend.tools.builtin.file_tools import _resolve_aliases, _safe_path

    async def _delegate(task: str = "", folder: str = "") -> str:
        task = (task or "").strip()
        if not task:
            return "[Erro] Descreva a tarefa de código a delegar (param 'task')."
        # Sem pasta específica → workspace padrão (Krirk Code)
        alvo = (folder or "").strip() or work_dir
        safe = _safe_path(_resolve_aliases(alvo))
        if safe is None:
            return f"[Erro] Pasta não permitida: {alvo}"
        return delegator.start(task, safe)

    return Tool(
        name="delegate_code",
        description=(
            "Delega trabalho de código SUBSTANCIAL (criar ou modificar app/script/"
            "projeto, várias mudanças) ao Claude Code, que abre uma JANELA e edita "
            f"os arquivos. Por padrão trabalha na pasta de código ({work_dir}); passe "
            "'folder' só para mexer num projeto existente em outro lugar."
        ),
        params=[
            ToolParam("task", "descrição completa da tarefa em português, com todos os detalhes do pedido", "string"),
            ToolParam("folder", "pasta do projeto SÓ se for um projeto já existente noutro lugar (ex: Desktop/meu_app); vazio = pasta de código padrão", "path", required=False, default=""),
        ],
        func=_delegate,
    )
