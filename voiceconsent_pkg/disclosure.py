"""EU-AI-Act-style disclosure snippet generator (copy-paste HTML or text)."""
from __future__ import annotations

import html

TEXT_TEMPLATE = (
    "AI-generated audio disclosure\n"
    "This audio was generated or modified with artificial intelligence "
    "(voice: {label}).\n"
    "Synthetic content — it does not represent a live recording of the "
    "named speaker."
)

HTML_TEMPLATE = (
    '<div class="ai-voice-disclosure" '
    'style="border:1px solid #ccc;border-radius:8px;padding:12px;'
    'font-size:14px;line-height:1.5;">\n'
    '  <strong>AI-generated audio</strong><br>\n'
    '  This audio was generated or modified with artificial intelligence '
    '(voice: {label}).<br>\n'
    '  <em>Synthetic content &mdash; it does not represent a live recording '
    'of the named speaker.</em>\n'
    '</div>'
)


def render_disclosure(voice_label: str, fmt: str = "text") -> str:
    """Render the disclosure snippet. fmt is 'text' or 'html'."""
    label = (voice_label or "").strip()
    if not label:
        raise ValueError("voice_label must not be empty")
    fmt = (fmt or "text").lower()
    if fmt == "html":
        return HTML_TEMPLATE.format(label=html.escape(label, quote=True))
    if fmt == "text":
        return TEXT_TEMPLATE.format(label=label)
    raise ValueError("format must be 'html' or 'text'")
