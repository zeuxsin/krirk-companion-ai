#!/usr/bin/env python3
"""
KRIRK — Companion AI Desktop
Entry point do backend.

Uso:
    python main.py
    uvicorn main:app --host localhost --port 8000 --reload
"""

import os
import sys
from pathlib import Path

# Garantir que o diretório raiz está no path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from backend.api.app import create_app
import uvicorn
import yaml

app = create_app()

if __name__ == "__main__":
    config_path = "configs/config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    host = os.getenv("BACKEND_HOST", config["server"]["host"])
    port = int(os.getenv("BACKEND_PORT", config["server"]["port"]))

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
