"""
backend/tools/builtin/vision_tools.py
Ferramentas de visão computacional: leitura de texto na tela (OCR via LLM de visão).
"""
from backend.tools.base import Tool, ToolParam

_OCR_PROMPT = (
    "Transcreva TODO o texto visível nesta captura de tela, na ordem de leitura "
    "(esquerda→direita, cima→baixo). Preserve títulos, menus, botões e conteúdo. "
    "Não descreva imagens nem layout — retorne APENAS o texto transcrito. "
    "Se não houver texto, responda: [sem texto visível]"
)


def make_read_screen(router) -> Tool:
    """OCR da tela inteira via task 'ocr' do router (phi-4-multimodal → gemma3)."""

    async def _read_screen(monitor: int = 1) -> str:
        try:
            from backend.vision.capture import capture_screen
            image_b64 = capture_screen(monitor=int(monitor))
        except Exception as e:
            return f"[Erro] Falha ao capturar a tela: {e}"

        text = await router.complete(
            "ocr",
            [{"role": "user", "content": _OCR_PROMPT, "images": [image_b64]}],
            temperature=0.0,
            max_tokens=1500,
        )
        text = (text or "").strip()
        if not text:
            return "[Erro] O modelo de visão não retornou texto."
        return f"Texto lido da tela:\n\n{text}"

    return Tool(
        name="read_screen",
        description=(
            "Lê e transcreve todo o texto visível na tela do usuário (OCR). "
            "Use quando o usuário pedir para ler, verificar ou copiar algo que está na tela."
        ),
        params=[
            ToolParam("monitor", "Qual monitor capturar (1=primário, 2=secundário)", "int",
                      required=False, default=1),
        ],
        func=_read_screen,
        timeout=60,  # visão é lenta — upload de imagem + inferência
    )
