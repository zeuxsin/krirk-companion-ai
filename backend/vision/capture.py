"""
backend/vision/capture.py
Captura de tela para análise de visão computacional (Fase 3).
"""

import base64
import io


def capture_screen() -> str:
    """Captura o monitor primário e retorna PNG em base64 (resolução original)."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        monitor = sct.monitors[1]  # monitor primário (0 = todos combinados)
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()


def capture_thumbnail(max_width: int = 400) -> str:
    """Captura o monitor primário e retorna um JPEG comprimido em base64 (para exibir no chat)."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        ratio = max_width / img.width
        new_h = int(img.height * ratio)
        img = img.resize((max_width, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return base64.b64encode(buf.getvalue()).decode()
