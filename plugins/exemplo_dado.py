"""
plugins/exemplo_dado.py
Plugin de exemplo da KRIRK — rolagem de dados.

Serve como modelo para criar seus próprios plugins:
1. Crie um arquivo .py nesta pasta
2. Defina uma função register(registry)
3. Dentro dela, registre uma ou mais Tools (func deve ser async e retornar str)
4. Reinicie o backend — a tool fica disponível para a KRIRK usar

Ferramentas de plugin NÃO passam pela whitelist do config.yaml —
o dono do plugin é responsável pelo que ela faz.
"""
import random

from backend.tools.base import Tool, ToolParam


def register(registry) -> None:
    async def _roll_dice(sides: int = 6, count: int = 1) -> str:
        sides = max(2, min(1000, int(sides)))
        count = max(1, min(20, int(count)))
        rolls = [random.randint(1, sides) for _ in range(count)]
        if count == 1:
            return f"Rolei um d{sides}: deu {rolls[0]}"
        return f"Rolei {count}d{sides}: {rolls} (total: {sum(rolls)})"

    registry.register(Tool(
        name="roll_dice",
        description="Rola dados (RPG). Ex: um d20, ou 3 dados de 6 lados.",
        params=[
            ToolParam("sides", "Número de lados do dado", "int", required=False, default=6),
            ToolParam("count", "Quantos dados rolar", "int", required=False, default=1),
        ],
        func=_roll_dice,
    ))
