import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from template import STYLE as S

W, H = S["size"]

def font(kind, size):
    for p in S[kind]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def gradient():
    img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(S["bg_top"][i] + (S["bg_bottom"][i] - S["bg_top"][i]) * t) for i in range(3)))
    return img

def cover(im, fx=0.5, fy=0.5):
    r = max(W / im.width, H / im.height)
    im = im.convert("RGB").resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
    x = int((im.width - W) * min(max(fx, 0), 1)); y = int((im.height - H) * min(max(fy, 0), 1))
    return im.crop((x, y, x + W, y + H))

def background(im=None, fx=0.5, blur=0):
    if im is None:
        return gradient()
    bg = cover(im, fx)
    if blur:
        bg = bg.filter(ImageFilter.GaussianBlur(blur))
    return Image.blend(bg, Image.new("RGB", (W, H), (8, 6, 8)), S["dim"])

def logo(d):
    d.text((W // 2, S["safe"]["top"] - 50), S["logo_text"], font=font("font_small", 30), fill=S["accent"], anchor="mm")

def wrap(d, text, f, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=f) <= max_w:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines

def text_slide(text, path, index, img=None, fx=0.5):
    im = background(img, fx); d = ImageDraw.Draw(im); logo(d)
    sf = S["safe"]; box_w = W - sf["left"] - sf["right"]; box_h = H - sf["top"] - sf["bottom"]
    size = S["text_max_size"]
    while True:
        f = font("font_text", size); lines = wrap(d, text, f, box_w); lh = int(size * S["line_spacing"])
        if len(lines) * lh <= box_h or size <= S["text_min_size"]:
            break
        size -= 4
    if len(lines) * lh > box_h:
        raise ValueError(f"Texte trop long pour la slide {index}")
    y = sf["top"] + (box_h - len(lines) * lh) // 2; cx = sf["left"] + box_w // 2
    for ln in lines:
        d.text((cx + 3, y + 3), ln, font=f, fill=(0, 0, 0), anchor="ma")   # ombre
        d.text((cx, y), ln, font=f, fill=S["text_color"], anchor="ma"); y += lh
    d.rectangle([cx - 40, y + 30, cx + 40, y + 36], fill=S["accent"])
    if index < 3:
        d.text((cx, H - sf["bottom"] + 60), "›››", font=font("font_small", 44), fill=S["accent"], anchor="mm")
    im.save(path, "JPEG", quality=93)

def poster_slide(poster, meta, path):
    im = background(poster, 0.5, blur=40); d = ImageDraw.Draw(im); logo(d)
    pw = S["poster_width"]; ph = int(poster.height * pw / poster.width)
    max_h = H - S["safe"]["top"] - S["safe"]["bottom"] - 100
    if ph > max_h:
        ph = max_h; pw = int(poster.width * ph / poster.height)
    p = poster.convert("RGB").resize((pw, ph), Image.LANCZOS)
    mask = Image.new("L", (pw, ph), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], 24, fill=255)
    x, y = (W - pw) // 2, S["safe"]["top"] + 10
    im.paste(p, (x, y), mask)
    infos = " · ".join(v for v in [str(meta.get("year", "")), meta.get("platform", ""), f"★ {meta['rating']}" if meta.get("rating") else ""] if v)
    d.text((W // 2, y + ph + 45), meta["title"], font=font("font_small", 36), fill=S["text_color"], anchor="mm")
    d.text((W // 2, y + ph + 95), infos, font=font("font_small", 28), fill=S["accent"], anchor="mm")
    im.save(path, "JPEG", quality=93)

def render_all(texts, backdrops, focus, poster, meta, out_dir):
    os.makedirs(out_dir, exist_ok=True); paths = []
    for i in range(3):
        p = f"{out_dir}/slide{i+1}.jpg"
        text_slide(texts[i], p, i + 1, backdrops[i], focus[i]); paths.append(p)
    p = f"{out_dir}/slide4.jpg"; poster_slide(poster, meta, p)
    return paths + [p]
