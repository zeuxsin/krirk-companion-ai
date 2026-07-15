"""
backend/tools/base.py
Tipos base para o sistema de ferramentas da KRIRK.
"""
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any


@dataclass
class ToolParam:
    """Describe um parâmetro de uma ferramenta."""
    name: str
    description: str
    type: str          # "string", "int", "bool", "path"
    required: bool = True
    default: Any = None


@dataclass
class Tool:
    """
    Uma ferramenta que a KRIRK pode usar.
    func deve ser uma coroutine async que recebe os params como kwargs
    e retorna uma string com o resultado (ou mensagem de erro).
    timeout: sobrescreve o timeout padrão do executor (None = usa o padrão).
    """
    name: str
    description: str
    params: list[ToolParam] = field(default_factory=list)
    func: Callable[..., Awaitable[str]] = field(default=None, repr=False)  # type: ignore
    timeout: float | None = None

    def format_for_prompt(self) -> str:
        """Formata a descrição da tool para ser injetada no system prompt."""
        lines = [f"• {self.name}: {self.description}"]
        for p in self.params:
            req = "obrigatório" if p.required else f"opcional, padrão: {p.default!r}"
            lines.append(f"    - {p.name} ({p.type}, {req}): {p.description}")
        return "\n".join(lines)
