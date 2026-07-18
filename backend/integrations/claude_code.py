"""
backend/integrations/claude_code.py
Delegação de tarefas de código ao Claude Code CLI (headless, em background).

A Krirk monta a descrição da tarefa e o CLI executa como agente de verdade:
lê os arquivos reais, edita no lugar, pode rodar/testar. Ao terminar, a
conclusão é anunciada pelos mesmos canais dos comentários proativos
(WS + TTS + Telegram) e salva na memória.
"""
import asyncio
import json
import shutil
import time
from pathlib import Path
from typing import Awaitable, Callable

from backend.tools.base import Tool, ToolParam

_HOME = Path.home()

# Fallback quando o instalador nativo não coloca o CLI no PATH do processo
_DEFAULT_CLI = _HOME / ".local" / "bin" / "claude.exe"


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
        "--output-format", "json",
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

    def is_available(self) -> bool:
        return bool(self._cli)

    def start(self, task: str, folder: Path) -> str:
        if not self._cli:
            return "[Erro] Claude Code CLI não encontrado neste computador."
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

    async def _run(self, task: str, folder: Path) -> None:
        timeout = int(self._cfg.get("timeout_seconds", 600))
        model = str(self._cfg.get("model", "") or "")
        max_turns = int(self._cfg.get("max_turns", 30))
        before = snapshot_dir(folder)
        summary, ok = "", False
        try:
            proc = await asyncio.create_subprocess_exec(
                self._cli, *build_cli_args(model, max_turns),
                cwd=str(folder),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, err = await asyncio.wait_for(
                    proc.communicate(build_task_prompt(task).encode("utf-8")),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                summary = f"passou do limite de {timeout // 60} minutos e foi cancelada"
            else:
                parsed, is_err = parse_cli_output(out.decode("utf-8", errors="replace"))
                if proc.returncode == 0 and not is_err:
                    summary, ok = parsed, True
                else:
                    err_txt = err.decode("utf-8", errors="replace").strip()[-400:]
                    summary = parsed or err_txt or f"CLI saiu com código {proc.returncode}"
        except Exception as e:
            summary = f"falha ao executar o CLI: {e}"

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


def make_delegate_code(delegator: ClaudeCodeDelegator) -> Tool:
    from backend.tools.builtin.file_tools import _resolve_aliases, _safe_path

    async def _delegate(task: str = "", folder: str = "Desktop") -> str:
        task = (task or "").strip()
        if not task:
            return "[Erro] Descreva a tarefa de código a delegar (param 'task')."
        safe = _safe_path(_resolve_aliases(str(folder or "Desktop")))
        if safe is None:
            return f"[Erro] Pasta não permitida (deve estar dentro de {_HOME}): {folder}"
        return delegator.start(task, safe)

    return Tool(
        name="delegate_code",
        description=(
            "Delega trabalho de código SUBSTANCIAL (criar ou modificar app/script/"
            "projeto, várias mudanças) a um agente de código real que edita os "
            "arquivos na pasta. Roda em SEGUNDO PLANO e o usuário é avisado ao "
            "terminar — nunca prometa resultado imediato."
        ),
        params=[
            ToolParam("task", "descrição completa da tarefa em português, com todos os detalhes do pedido", "string"),
            ToolParam("folder", "pasta do projeto (ex: Desktop/meu_app)", "path", required=False, default="Desktop"),
        ],
        func=_delegate,
    )
