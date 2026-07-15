"""
backend/agents/planner.py
Parser das decisões do modelo roteador (multi-agente lite).

O roteador pode responder de três formas:
  1. "none"                                          → nenhuma ferramenta
  2. {"tool": "nome", "params": {...}}               → uma ferramenta direta
  3. {"plan": [{"tool": ..., "params": {...}}, ...]} → pedido multi-etapas:
     lista COMPLETA de tool calls, executadas em sequência sem re-roteamento

Passos de plano como strings (formato legado de modelos pequenos) também são
aceitos — o orchestrator os re-roteia com o contexto do pedido original.

parse_decision() é tolerante a cercas markdown (```json) e texto extra.
"""
import json
import re

MAX_PLAN_STEPS = 4


def parse_decision(raw: str) -> dict:
    """
    Interpreta a resposta crua do roteador.
    Retorna:
      {"type": "none"}
      {"type": "tool", "tool": str, "params": dict}
      {"type": "plan", "steps": [...]}   (1..MAX_PLAN_STEPS passos)
        cada passo: {"tool": str, "params": dict}  (execução direta)
                    ou str                          (re-roteado pelo orchestrator)
    """
    raw = (raw or "").strip()
    if not raw or raw.lower().startswith("none"):
        return {"type": "none"}

    data = _extract_json(raw)
    if not isinstance(data, dict):
        return {"type": "none"}

    plan = data.get("plan")
    if isinstance(plan, list):
        steps: list = []
        for s in plan:
            if isinstance(s, dict) and str(s.get("tool", "")).strip():
                params = s.get("params")
                steps.append({
                    "tool": str(s["tool"]).strip(),
                    "params": params if isinstance(params, dict) else {},
                })
            elif str(s).strip():
                steps.append(str(s).strip())
        if steps:
            return {"type": "plan", "steps": steps[:MAX_PLAN_STEPS]}
        return {"type": "none"}

    tool = data.get("tool")
    if isinstance(tool, str) and tool.strip():
        params = data.get("params")
        return {
            "type": "tool",
            "tool": tool.strip(),
            "params": params if isinstance(params, dict) else {},
        }

    return {"type": "none"}


def _extract_json(raw: str) -> dict | None:
    """Extrai o primeiro objeto JSON válido do texto (ignora cercas e prosa)."""
    # Tentativa 1: greedy — do primeiro { ao último }
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    # Tentativa 2: objeto com um nível de aninhamento (padrão antigo)
    m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None
