"""TEMPLATE POPCORNLIFE : tout ce que tu veux changer visuellement est ici.

POLICE : pour changer de police, ajoute un fichier .ttf nommé  title.ttf  (textes des slides)
et éventuellement  small.ttf  (logo et infos) à la racine du dépôt GitHub. Le programme les utilise automatiquement."""
STYLE = {
    "size": (1080, 1920),
    "font_text": ["title.ttf", "fonts/title.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    "font_small": ["small.ttf", "fonts/small.ttf", "title.ttf",
                   "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"],
    "text_max_size": 80, "text_min_size": 50, "line_spacing": 1.18,
    "text_bottom": 1430,         # position du BAS du texte (plus le chiffre est petit, plus le texte monte ; max 1920)
    "dim": 0.20,                 # assombrissement général de l'image (0 = aucun, 1 = noir)
    "fade_start": 0.42,          # où commence le dégradé sombre en bas (0 = haut de l'image, 1 = bas)
    "fade_strength": 0.88,       # force du dégradé sombre derrière le texte
    "poster_dim": 0.58,          # assombrissement du fond flouté de la slide 4
    "bg_top": (14, 10, 12), "bg_bottom": (52, 14, 20),   # fond si aucune image
    "text_color": (255, 255, 255), "accent": (229, 9, 20),
    "logo_text": "POPCORNLIFE",
    # Zones à laisser libres pour l'interface TikTok (en pixels)
    "safe": {"top": 200, "bottom": 420, "left": 90, "right": 150},
    "poster_width": 760,
}
