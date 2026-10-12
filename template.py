"""TEMPLATE POPCORNLIFE : tout ce que tu veux changer visuellement est ici.
Pour une autre police : mets un fichier .ttf dans le dossier fonts/ et nomme-le title.ttf (textes) ou small.ttf (petits textes)."""
STYLE = {
    "size": (1080, 1920),
    "font_text": ["fonts/title.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "C:/Windows/Fonts/georgiab.ttf"],
    "font_small": ["fonts/small.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"],
    "text_max_size": 84, "text_min_size": 52, "line_spacing": 1.25,
    "bg_top": (14, 10, 12), "bg_bottom": (52, 14, 20),   # fond si aucune image
    "dim": 0.58,                                           # assombrissement des images (0 = aucun, 1 = noir)
    "text_color": (245, 240, 232), "accent": (214, 40, 57),
    "logo_text": "POPCORNLIFE",
    # Zones à laisser libres pour l'interface TikTok (en pixels)
    "safe": {"top": 200, "bottom": 420, "left": 90, "right": 150},
    "poster_width": 760,
}
