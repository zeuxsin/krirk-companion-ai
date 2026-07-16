#!/usr/bin/env python3
"""
KRIRK — Companion AI Desktop
Entry point do backend.

Uso:
    python main.py
    uvicorn main:app --host localhost --port 8000 --reload
"""

import os
import socket
import sys
from pathlib import Path

# Garantir que o diretório raiz está no path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":
    # Processo lançador: só valida a porta e delega ao worker do uvicorn.
    # O app pesado (Whisper, ChromaDB, tools) carrega APENAS no worker —
    # evita a inicialização dupla que aparecia no log com reload=True.
    import uvicorn
    import yaml

    with open("configs/config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    host = os.getenv("BACKEND_HOST", config["server"]["host"])
    port = int(os.getenv("BACKEND_PORT", config["server"]["port"]))

    # Checagem amigável: porta já em uso? (evita o críptico WinError 10013)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex((host, port)) == 0:
            print(f"\n[ERRO] A porta {port} já está em uso — provavelmente outro backend KRIRK rodando.")
            print(f"       Feche o outro processo ou rode no PowerShell:\n"
                  f"       Get-NetTCPConnection -LocalPort {port} | "
                  f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force }}\n")
            sys.exit(1)

    print(f"""
╔══════════════════════════════════════╗
║       KRIRK — Companion AI v0.1      ║
╚══════════════════════════════════════╝
  Backend: http://{host}:{port}
  WebSocket: ws://{host}:{port}/ws
  Docs: http://{host}:{port}/docs
  Modelo Ollama: {config['ollama']['model']}
""")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level=config["logging"]["level"].lower(),
    )
elif __name__ != "__mp_main__":
    # Importado pelo worker do uvicorn (main:app) — aqui sim cria o app real.
    # O guard __mp_main__ evita criação duplicada: no Windows o reload usa
    # multiprocessing spawn, que re-importa este módulo com esse nome.
    from backend.api.app import create_app

    app = create_app()
