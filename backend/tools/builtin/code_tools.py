"""
backend/tools/builtin/code_tools.py
Execução local de código Python para o Modo Coder.
"""
import asyncio
import subprocess
import sys

from backend.tools.base import Tool, ToolParam


def _run_python_blocking(code: str, timeout: float) -> tuple[str, str]:
    """Python BLOQUEANTE (via asyncio.to_thread). asyncio subprocess não
    funciona sob o uvicorn no Windows (SelectorEventLoop → NotImplementedError)."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    p = subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True, timeout=timeout, creationflags=flags,
    )
    return (p.stdout.decode('utf-8', errors='replace').strip(),
            p.stderr.decode('utf-8', errors='replace').strip())


async def _run_python(code: str, timeout: float = 8.0) -> str:
    """Executa um snippet Python via subprocess e captura stdout + stderr."""
    try:
        out, err = await asyncio.to_thread(_run_python_blocking, code, timeout)
    except subprocess.TimeoutExpired:
        return f'⏱ Timeout: execução levou mais de {int(timeout)} segundos'
    except FileNotFoundError:
        return f'Erro: Python não encontrado em "{sys.executable}"'

    if err and not out:
        return f'Erro:\n{err}'
    if err:
        return f'{out}\n\nStderr:\n{err}'
    return out or '(sem saída)'


def make_execute_python() -> Tool:
    return Tool(
        name='execute_python',
        description=(
            'Executa um snippet de código Python e retorna a saída (stdout/stderr). '
            'Use APENAS quando o usuário pedir para rodar/testar código, ou para '
            'computação genuinamente pesada. Contas simples são respondidas na conversa. '
            'Para criar arquivos use write_file.'
        ),
        params=[
            ToolParam(
                name='code',
                description='Código Python a executar. Pode ter múltiplas linhas.',
                type='string',
                required=True,
            )
        ],
        func=_run_python,
    )
