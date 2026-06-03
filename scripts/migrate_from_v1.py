"""
Migra dados do Krirk 1.0 (protótipo) para o projeto KRIRK atual.
Execute uma vez: python scripts/migrate_from_v1.py

O que é migrado:
  - ChromaDB antigo (krirk_memorias): textos extraídos e re-embedados com nomic-embed-text
  - user_profile.json: nome, interesses, etc. → salvos como fatos no SQLite/ChromaDB
  - short_term_cache.json: histórico de conversa → salvo como mensagens
"""
import sys
import json
import uuid
from pathlib import Path

# Garante import dos módulos do projeto a partir da raiz
sys.path.insert(0, str(Path(__file__).parent.parent))

OLD_CHROMA  = r"C:\Users\erik_\Downloads\Krirk_1.0\Krirk_1.0\data\chroma"
OLD_PROFILE = r"C:\Users\erik_\Downloads\Krirk_1.0\Krirk_1.0\data\user_profile.json"
OLD_CACHE   = r"C:\Users\erik_\Downloads\Krirk_1.0\Krirk_1.0\data\short_term_cache.json"

USER_ID = "default"  # ID fixo do projeto atual (single-user)


def main():
    import chromadb
    from backend.memory.memory_manager import MemoryManager

    print("=" * 50)
    print("  Migracao Krirk 1.0 -> KRIRK atual")
    print("=" * 50)

    mm = MemoryManager("data/memory.db", "data/chroma")

    if mm._vectors is None:
        print("\n[ERRO] ChromaDB não inicializou. Verifique se o Ollama está rodando.")
        return

    # ── 1. ChromaDB antigo: extrai textos e re-embeda ──────────────────────
    print("\n[1/3] Lendo ChromaDB do protótipo...")
    total_chroma = 0
    try:
        old_client = chromadb.PersistentClient(path=OLD_CHROMA)
        collections = old_client.list_collections()
        print(f"      Coleções encontradas: {[c.name for c in collections]}")

        for col_meta in collections:
            col = old_client.get_collection(col_meta.name)
            results = col.get(include=["documents", "metadatas"])
            docs  = results.get("documents") or []
            metas = results.get("metadatas") or []
            print(f"      '{col_meta.name}': {len(docs)} documentos")

            for doc, meta in zip(docs, metas):
                if not doc or not doc.strip():
                    continue
                cat = (meta or {}).get("category", "")
                doc_type = "fact" if cat in ("fact", "fato", "memory") else "message"
                doc_id = f"v1-{uuid.uuid4().hex[:12]}"
                mm._vectors.add(doc_id, doc, {
                    "user_id": USER_ID,
                    "type":    doc_type,
                    "role":    "assistant" if doc_type == "message" else "",
                    "emotion": "neutral",
                })
                total_chroma += 1
                print(f"      + [{doc_type}] {doc[:60]}...")

        print(f"\n      Migrados: {total_chroma} documentos para ChromaDB novo")
    except Exception as e:
        print(f"      [AVISO] Erro ao ler ChromaDB antigo: {e}")

    # ── 2. user_profile.json → fatos ───────────────────────────────────────
    print("\n[2/3] Migrando perfil do usuário...")
    facts_added = 0
    profile_path = Path(OLD_PROFILE)
    if not profile_path.exists():
        print("      Arquivo não encontrado, pulando.")
    else:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        print(f"      Perfil: {profile}")

        mappings = [
            ("name",       lambda v: f"O nome do usuário é {v}"),
            ("age",        lambda v: f"O usuário tem {v} anos"),
            ("profession", lambda v: f"O usuário trabalha como {v}"),
            ("location",   lambda v: f"O usuário mora em {v}"),
        ]
        for field, factory in mappings:
            val = profile.get(field)
            if val:
                fact = factory(val)
                mm.save_fact(USER_ID, fact)
                print(f"      + {fact}")
                facts_added += 1

        for topic in (profile.get("preferences") or {}).get("topics", []):
            if topic:
                fact = f"O usuário tem interesse em {topic}"
                mm.save_fact(USER_ID, fact)
                print(f"      + {fact}")
                facts_added += 1

        for tool in (profile.get("preferences") or {}).get("tools", []):
            if tool and len(tool) > 3:
                fact = f"O usuário usa/prefere: {tool}"
                mm.save_fact(USER_ID, fact)
                print(f"      + {fact}")
                facts_added += 1

        for project in profile.get("projects", []):
            if project:
                fact = f"Projeto do usuário: {project}"
                mm.save_fact(USER_ID, fact)
                print(f"      + {fact}")
                facts_added += 1

        print(f"\n      Migrados: {facts_added} fatos do perfil")

    # ── 3. short_term_cache.json → mensagens ───────────────────────────────
    print("\n[3/3] Migrando histórico de conversa...")
    msgs_added = 0
    cache_path = Path(OLD_CACHE)
    if not cache_path.exists():
        print("      Arquivo não encontrado, pulando.")
    else:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        # Suporta tanto lista plana quanto dict com chave "messages"
        messages = raw if isinstance(raw, list) else raw.get("messages", [])
        print(f"      {len(messages)} entradas encontradas")

        for msg in messages:
            role    = msg.get("role", "")
            content = msg.get("content", "").strip()
            if role in ("user", "assistant") and content:
                mm.save_message(USER_ID, role, content)
                label = "usuário" if role == "user" else "KRIRK"
                print(f"      + [{label}] {content[:60]}...")
                msgs_added += 1

        print(f"\n      Migradas: {msgs_added} mensagens")

    # ── Resumo ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("  Migração concluída!")
    stats = mm.get_stats(USER_ID)
    print(f"  Documentos no ChromaDB: {stats.get('semantic_memories', 0)}")
    print(f"  Fatos no SQLite:        {stats.get('facts_stored', 0)}")
    print(f"  Mensagens no SQLite:    {stats.get('total_messages', 0)}")
    print("=" * 50)
    print("\nPróximo passo: reinicie o backend e pergunte 'você sabe meu nome?'")


if __name__ == "__main__":
    main()
