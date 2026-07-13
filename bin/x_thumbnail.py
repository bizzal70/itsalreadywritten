#!/usr/bin/env python3
"""Generate a 1200x675 X/Twitter card thumbnail for a Jekyll blog post."""
import argparse
import re
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

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
FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def load_font(name, size):
    try:
        return ImageFont.truetype(f"{FONT_DIR}/{name}", size)
    except Exception:
        return ImageFont.load_default()


def parse_frontmatter(md_path):
    text = Path(md_path).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(m.group(1)) if m else {}


def extract_dollar_figures(text):
    return re.findall(r"\$[\d,.]+\s*[MBKmb]", str(text))


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        if draw.textlength(test, font=font) > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def render(blog, md_path, out_path):
    s = STYLES[blog]
    fm = parse_frontmatter(md_path)
    issue_num = fm.get("issue", "?")
    summary = str(fm.get("summary", "")).strip()
    date_str = str(fm.get("date", ""))[:10]

    f_label = load_font("DejaVuSansMono.ttf", 22)
    f_bold = load_font("DejaVuSans-Bold.ttf", 54)
    f_bold_sm = load_font("DejaVuSans-Bold.ttf", 38)
    f_footer = load_font("DejaVuSansMono.ttf", 19)

    img = Image.new("RGB", (W, H), s["bg"])
    d = ImageDraw.Draw(img)

    # Footer bar
    footer_y = H - FOOTER_H
    d.rectangle([0, footer_y, W, H], fill=s["footer_bg"])
    d.line([0, footer_y, W, footer_y], fill=(*s["accent"], 30), width=1)
    footer_str = f"{s['blog_tag']}  ·  ISSUE #{issue_num}  ·  {date_str}"
    d.text((PAD, footer_y + 17), footer_str, font=f_footer, fill=s["footer_text"])

    # Label row (top)
    dot_r = 6
    dot_y = PAD + dot_r
    d.ellipse([PAD, dot_y - dot_r, PAD + dot_r * 2, dot_y + dot_r], fill=s["accent"])
    label = f"{s['blog_name']}  —  ISSUE #{issue_num}"
    d.text((PAD + dot_r * 2 + 12, PAD), label, font=f_label, fill=s["label"])

    # For priced: extract dollar figures and show right column
    content_w = W - PAD * 2
    figures = []
    if blog == "priced":
        figures = extract_dollar_figures(summary)[:3]
        if figures:
            content_w = W - PAD * 2 - 220

    # Wrap + draw headline
    lines = wrap_text(d, summary, f_bold, content_w)
    if len(lines) > 3:
        lines = wrap_text(d, summary, f_bold_sm, content_w)
        headline_font = f_bold_sm
        line_h = 52
    else:
        headline_font = f_bold
        line_h = 70

    total_h = len(lines) * line_h
    text_y = PAD + 60 + (footer_y - PAD - 60 - total_h) // 2

    for line in lines:
        d.text((PAD, text_y), line, font=headline_font, fill=s["headline"])
        text_y += line_h

    # Priced: dollar figures in right column
    if figures:
        sep_x = W - PAD - 180
        d.line([sep_x, PAD + 60, sep_x, footer_y - 20], fill=(*s["accent"], 50), width=1)
        fig_y = PAD + 80
        f_fig = load_font("DejaVuSansMono-Bold.ttf", 36)
        for fig in figures:
            d.text((sep_x + 20, fig_y), fig, font=f_fig, fill=(226, 75, 74))
            fig_y += 90

    img.save(out_path, "PNG", optimize=True)
    print(f"[x_thumbnail] saved {out_path} ({Path(out_path).stat().st_size} bytes)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--blog", required=True, choices=["when", "written", "priced"])
    p.add_argument("--post", required=True)
    p.add_argument("--out", default="thumbnail.png")
    args = p.parse_args()
    render(args.blog, args.post, args.out)


if __name__ == "__main__":
    main()
