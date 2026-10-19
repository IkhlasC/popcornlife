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
    """Recadre en 9:16 en CENTRANT sur le sujet : fx = position du sujet dans l'image (0 = bord gauche, 1 = bord droit)."""
    r = max(W / im.width, H / im.height)
    im = im.convert("RGB").resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
    x = int(min(max(fx * im.width - W / 2, 0), max(im.width - W, 0)))
    y = int(min(max(fy * im.height - H / 2, 0), max(im.height - H, 0)))
    return im.crop((x, y, x + W, y + H))

def face_focus(im):
    """Position horizontale (0 à 1) du plus grand visage de l'image, ou None si aucun visage n'est détecté."""
    try:
        import cv2, numpy as np
        g = np.array(im.convert("L")); h, w = g.shape; s = 640 / w
        g = cv2.resize(g, (640, max(int(h * s), 1)))
        best = None
        for name in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
            faces = cv2.CascadeClassifier(cv2.data.haarcascades + name).detectMultiScale(g, 1.1, 5, minSize=(40, 40))
            for (x, y, fw, fh) in faces:
                if best is None or fw * fh > best[2] * best[3]:
                    best = (x, y, fw, fh)
            if best is not None:
                break
        return float((best[0] + best[2] / 2) / 640) if best is not None else None
    except Exception:
        return None

def background(im=None, fx=0.5, blur=0, poster=False):
    if im is None:
        return gradient()
    bg = cover(im, fx)
    if blur:
        bg = bg.filter(ImageFilter.GaussianBlur(blur))
    black = Image.new("RGB", (W, H), (6, 4, 6))
    if poster:
        return Image.blend(bg, black, S["poster_dim"])
    bg = Image.blend(bg, black, S["dim"])
    mask = Image.new("L", (W, H), 0); md = ImageDraw.Draw(mask)
    y0 = int(H * S["fade_start"])
    for y in range(y0, H):
        t = (y - y0) / (H - y0)
        md.line([(0, y), (W, y)], fill=int(255 * S["fade_strength"] * min(1, t * 1.6) ** 1.3))
    return Image.composite(black, bg, mask)

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
    y = S["text_bottom"] - len(lines) * lh; cx = sf["left"] + box_w // 2
    for ln in lines:
        d.text((cx + 2, y + 2), ln, font=f, fill=(0, 0, 0), anchor="ma")   # ombre
        d.text((cx, y), ln, font=f, fill=S["text_color"], anchor="ma"); y += lh
    d.rectangle([cx - 40, y + 30, cx + 40, y + 36], fill=S["accent"])
    if index < 3:
        d.text((cx, H - sf["bottom"] + 60), "›››", font=font("font_small", 44), fill=S["accent"], anchor="mm")
    im.save(path, "JPEG", quality=93)

def poster_slide(poster, meta, path):
    im = background(poster, 0.5, blur=40, poster=True); d = ImageDraw.Draw(im); logo(d)
    pw = S["poster_width"]; ph = int(poster.height * pw / poster.width)
    max_h = H - S["safe"]["top"] - S["safe"]["bottom"] - 100
    if ph > max_h:
        ph = max_h; pw = int(poster.width * ph / poster.height)
    p = poster.convert("RGB").resize((pw, ph), Image.LANCZOS)
    mask = Image.new("L", (pw, ph), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], 24, fill=255)
    x, y = (W - pw) // 2, S["safe"]["top"] + 10
    im.paste(p, (x, y), mask)
    infos = " · ".join(v for v in [str(meta.get("year", "")), meta.get("platform", ""), f"{meta['rating']}/10" if meta.get("rating") else ""] if v)
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
