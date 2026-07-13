"""
Generate a 1200x675 X/Twitter card thumbnail from a Jekyll post front-matter dict.
Shared across the three It's Already * blogs.

Usage:
    from x_thumbnail import render
    png_path = render("when", fm)   # returns temp file path; caller removes it
"""
import re
import tempfile
from pathlib import Path

STYLES = {
    "when": {
        "bg": (8, 10, 13),
        "accent": (226, 75, 74),
        "headline": (240, 240, 238),
        "label": (226, 75, 74),
        "footer_bg": (13, 17, 23),
        "footer_text": (61, 61, 58),
        "blog_name": "IT'S ALREADY WHEN",
        "blog_tag": "CYBER DIGEST",
    },
    "written": {
        "bg": (17, 14, 5),
        "accent": (186, 117, 23),
        "headline": (250, 238, 218),
        "label": (186, 117, 23),
        "footer_bg": (11, 9, 1),
        "footer_text": (65, 36, 2),
        "blog_name": "IT'S ALREADY WRITTEN",
        "blog_tag": "TTRPG WEEKLY DIGEST",
    },
    "priced": {
        "bg": (2, 13, 8),
        "accent": (29, 158, 117),
        "headline": (225, 245, 238),
        "label": (29, 158, 117),
        "footer_bg": (1, 9, 5),
        "footer_text": (4, 52, 44),
        "blog_name": "IT'S ALREADY PRICED",
        "blog_tag": "CRYPTO SECURITY & MARKETS",
    },
}

W, H = 1200, 675
FOOTER_H = 52
PAD = 64
_FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def _load_font(name, size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(f"{_FONT_DIR}/{name}", size)
    except Exception:
        return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if draw.textlength(test, font=font) > max_w and cur:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


def _dollar_figures(text):
    return re.findall(r"\$[\d,.]+\s*[MBKmb]", str(text))


def render(blog: str, fm: dict, out_path: str | None = None) -> str:
    """Render a 1200x675 PNG and return its file path.

    If *out_path* is None a NamedTemporaryFile is created; the caller is
    responsible for deleting it when done.
    """
    from PIL import Image, ImageDraw

    s = STYLES[blog]
    issue = fm.get("issue", "?")
    summary = str(fm.get("summary", "") or "").strip()
    date_str = str(fm.get("date", "") or "")[:10]

    f_label = _load_font("DejaVuSansMono.ttf", 22)
    f_bold = _load_font("DejaVuSans-Bold.ttf", 54)
    f_bold_sm = _load_font("DejaVuSans-Bold.ttf", 38)
    f_footer = _load_font("DejaVuSansMono.ttf", 19)
    f_fig = _load_font("DejaVuSansMono-Bold.ttf", 36)

    img = Image.new("RGB", (W, H), s["bg"])
    d = ImageDraw.Draw(img)

    # footer bar
    fy = H - FOOTER_H
    d.rectangle([0, fy, W, H], fill=s["footer_bg"])
    d.line([0, fy, W, fy], fill=(*s["accent"], 30), width=1)
    d.text((PAD, fy + 17),
           f"{s['blog_tag']}  ·  ISSUE #{issue}  ·  {date_str}",
           font=f_footer, fill=s["footer_text"])

    # label dot + blog name
    dr = 6
    d.ellipse([PAD, PAD + dr - dr, PAD + dr * 2, PAD + dr + dr], fill=s["accent"])
    d.text((PAD + dr * 2 + 12, PAD),
           f"{s['blog_name']}  —  ISSUE #{issue}",
           font=f_label, fill=s["label"])

    # priced: pull dollar figures into right column
    content_w = W - PAD * 2
    figures = []
    if blog == "priced":
        figures = _dollar_figures(summary)[:3]
        if figures:
            content_w = W - PAD * 2 - 220

    # headline
    lines = _wrap(d, summary, f_bold, content_w)
    if len(lines) > 3:
        lines = _wrap(d, summary, f_bold_sm, content_w)
        hfont, lh = f_bold_sm, 52
    else:
        hfont, lh = f_bold, 70

    total_h = len(lines) * lh
    ty = PAD + 60 + (fy - PAD - 60 - total_h) // 2
    for line in lines:
        d.text((PAD, ty), line, font=hfont, fill=s["headline"])
        ty += lh

    # priced right column
    if figures:
        sx = W - PAD - 180
        d.line([sx, PAD + 60, sx, fy - 20], fill=(*s["accent"], 50), width=1)
        gy = PAD + 80
        for fig in figures:
            d.text((sx + 20, gy), fig, font=f_fig, fill=(226, 75, 74))
            gy += 90

    if out_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        out_path = tmp.name
        tmp.close()

    img.save(out_path, "PNG", optimize=True)
    print(f"[x_thumbnail] {blog} issue #{issue} → {out_path} ({Path(out_path).stat().st_size} B)")
    return out_path
