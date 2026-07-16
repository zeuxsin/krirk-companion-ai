"""
backend/tools/builtin/code_tools.py
Execução local de código Python para o Modo Coder.
"""
import asyncio
import sys

from backend.tools.base import Tool, ToolParam


async def _run_python(code: str, timeout: float = 8.0) -> str:
    """Executa um snippet Python via subprocess e captura stdout + stderr."""
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, '-c', code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return f'Erro: Python não encontrado em "{sys.executable}"'

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return f'⏱ Timeout: execução levou mais de {int(timeout)} segundos'

    out = stdout.decode('utf-8', errors='replace').strip()
    err = stderr.decode('utf-8', errors='replace').strip()

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
