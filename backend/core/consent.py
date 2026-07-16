"""
backend/core/consent.py
Framework de consentimento (ética escafoldada).

Ações que a Krirk pode querer executar sobre si mesma são classificadas em tiers.
Ações Tier >= 2 (destrutivas ou de identidade) NÃO são aplicadas direto — viram
propostas pendentes que o usuário aprova ou recusa. O usuário tem override total.

IMPORTANTE: é um framework comportamental/UX, não um sandbox de segurança real.
"""
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.orchestrator import Orchestrator

# Tiers de consentimento por tipo de ação
#   0 = livre (aplica direto, sem pedir)
#   1 = notifica (aplica mas avisa)
#   2 = pede consentimento (encena como proposta)
#   3 = confirmação explícita (encena; UI deve exigir confirmação extra)
ACTION_TIERS: dict[str, int] = {
    "diary":          0,
    "reflection":     0,
    "lexicon_add":    0,
    "brain_state":    0,
    "learning_note":  1,
    "sublation":      2,   # apaga/reescreve memórias
    "kernel":         2,   # reescreve identidade
    "wipe_memory":    3,   # limpar memória em massa
}


def tier_of(kind: str) -> int:
    return ACTION_TIERS.get(kind, 2)  # desconhecido → pede consentimento por segurança


class ConsentManager:
    def __init__(self, orchestrator: "Orchestrator"):
        self._orch = orchestrator

    def requires_consent(self, kind: str) -> bool:
        return tier_of(kind) >= 2

    def stage(self, kind: str, payload: dict, rationale: str = "") -> dict:
        """
        Encena uma ação. Tier < 2 aplica direto e retorna {applied:True}.
        Tier >= 2 cria uma proposta pendente e retorna {proposal_id, tier}.
        """
        tier = tier_of(kind)
        if tier < 2:
            self._apply(kind, payload)
            return {"applied": True, "tier": tier}
        pid = self._orch.memory.add_proposal(kind, json.dumps(payload, ensure_ascii=False), rationale)
        return {"applied": False, "tier": tier, "proposal_id": pid,
                "kind": kind, "rationale": rationale}

    def list_pending(self) -> list[dict]:
        out = []
        for p in self._orch.memory.get_pending_proposals():
            try:
                payload = json.loads(p["payload_json"])
            except Exception:
                payload = {}
            out.append({
                "id": p["id"], "kind": p["kind"], "tier": tier_of(p["kind"]),
                "rationale": p["rationale"], "payload": payload, "created_at": p["created_at"],
            })
        return out

    def approve(self, proposal_id: int) -> dict:
        p = self._orch.memory.get_proposal(proposal_id)
        if not p or p["status"] != "pending":
            return {"ok": False, "error": "proposta não encontrada ou já resolvida"}
        try:
            payload = json.loads(p["payload_json"])
        except Exception:
            payload = {}
        self._apply(p["kind"], payload)
        self._orch.memory.set_proposal_status(proposal_id, "approved")
        return {"ok": True, "kind": p["kind"]}

    def reject(self, proposal_id: int) -> dict:
        p = self._orch.memory.get_proposal(proposal_id)
        if not p or p["status"] != "pending":
            return {"ok": False, "error": "proposta não encontrada ou já resolvida"}
        self._orch.memory.set_proposal_status(proposal_id, "rejected")
        return {"ok": True}

    # ── Execução por tipo ─────────────────────────────────────────────────────

    def _apply(self, kind: str, payload: dict) -> None:
        mem = self._orch.memory
        if kind == "sublation":
            facts = payload.get("facts")
            if isinstance(facts, list):
                mem.replace_facts("default", [str(f) for f in facts])
        elif kind == "kernel":
            content = payload.get("content")
            if payload.get("kernel_id"):
                mem.activate_kernel(int(payload["kernel_id"]))
            elif content:
                mem.save_kernel(str(content), note=payload.get("note", "auto-autorado"), activate=True)
        elif kind == "lexicon_add":
            if payload.get("term") and payload.get("meaning"):
                mem.add_term("default", payload["term"], payload["meaning"], origin=payload.get("origin", ""))
        elif kind == "wipe_memory":
            mem.clear_all("default")
        # diary/reflection/brain_state/learning_note: nada a aplicar aqui (já persistidos)
