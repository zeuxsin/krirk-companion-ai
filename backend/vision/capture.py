"""
backend/vision/capture.py
Captura de tela para análise de visão computacional (Fase 3).
"""

import base64
import io


def capture_screen(monitor: int = 1) -> str:
    """Captura um monitor e retorna PNG em base64 (resolução original).
    monitor: 1 = primário, 2+ = secundários, 0 = todos combinados."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        idx = monitor if 0 <= monitor < len(sct.monitors) else 1
        shot = sct.grab(sct.monitors[idx])
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()


def capture_region(left: int, top: int, width: int, height: int) -> str:
    """Captura uma região específica da tela e retorna PNG em base64."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
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
