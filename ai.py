import os, io, re, json, base64
from anthropic import Anthropic

MODEL = os.environ.get("MODEL_WRITE", "claude-sonnet-5-5")
MODEL_FAST = os.environ.get("MODEL_FAST", "claude-haiku-5-5")
_client = None

SYSTEM = """Tu écris pour PopcornLife, compte TikTok de recommandations de films et séries. Tu écris comme une vraie cinéphile qui recommande personnellement une œuvre à une amie : naturel, direct, jamais pompeux.
Interdits : les clichés d'IA (« plongez dans », « incontournable », « chef-d'œuvre », « préparez-vous », « embarquez », « voyage »...), les emojis dans les slides, les paragraphes, les spoilers (ne révèle jamais un retournement, une mort, la fin, une identité cachée), et toute information sur l'intrigue qui ne figure pas dans le synopsis fourni."""

def _c():
    global _client
    if _client is None: _client = Anthropic()
    return _client

def ask(prompt, images=None, model=None, max_tokens=2500):
    content = []
    for i, b in enumerate(images or []):
        content += [{"type": "text", "text": f"Image {i+1} :"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(b).decode()}}]
    content.append({"type": "text", "text": prompt})
    r = _c().messages.create(model=model or MODEL, max_tokens=max_tokens, system=SYSTEM,
                             messages=[{"role": "user", "content": content}])
    return "".join(b.text for b in r.content if b.type == "text")

def ask_json(prompt, **kw):
    for attempt in range(2):
        txt = ask(prompt, **kw)
        m = re.search(r"(\{.*\}|\[.*\])", txt, re.S)
        try:
            return json.loads(m.group(1))
        except Exception:
            prompt += "\n\nRéponds UNIQUEMENT avec du JSON valide."
    raise RuntimeError("Réponse IA illisible")

def propose(pool):
    lines = "\n".join(f'{p["type"]}:{p["id"]} | {p["title"]} ({p["year"]}) | note {p["rating"]} | {", ".join(p["genres"])} | {p["overview"][:220]}' for p in pool)
    prompt = f"""Voici une liste d'œuvres disponibles en streaming en France :
{lines}

Choisis 3 œuvres DIFFÉRENTES (pas 3 films du même genre ; 1 série maximum ; varie les pays et les époques si possible) qui ont le plus de potentiel pour un TikTok de recommandation qui fait swiper. Évite les titres trop vus partout si un titre plus surprenant est aussi bon.
Pour chacune : un angle éditorial, une idée de hook (une phrase), et pourquoi ça peut fonctionner sur TikTok (une phrase).
JSON : [{{"ref":"movie:123","angle":"","hook":"","pourquoi":""}}, ...]"""
    return ask_json(prompt)

def write_post(meta):
    kind = "série" if meta["type"] == "tv" else "film"
    base = f"""Œuvre : {meta['title']} ({meta['year']}), {kind}. Genres : {', '.join(meta['genres'])}.
Accroche officielle : {meta['tagline'] or '-'}
Synopsis : {meta['overview']}

Écris un carrousel TikTok de 3 phrases (une par slide), UNE phrase chacune, 14 mots maximum :
- slide 1 : une phrase qui arrête le scroll, intrigue sans rien révéler ;
- slide 2 : augmente la curiosité (situation étrange, tension, dilemme, détail mystérieux, ambiance ou promesse), sans spoiler ;
- slide 3 : donne définitivement envie de regarder, un peu plus précise mais sans révéler l'important.
Les trois forment une progression logique, chacune donne envie de voir la suivante. Exemples de TON (ne les réutilise pas) : « Ce film commence presque normalement… puis tout bascule. » / « Tu crois avoir compris l'histoire. Tu n'as encore rien vu. »
Ajoute une caption TikTok (1 à 2 phrases courtes, avec éventuellement un CTA naturel comme « Tu l'as déjà vu ? »), et 6 hashtags (mélange de généraux #film #cinema et de spécifiques au titre/genre).
JSON : {{"s1":"","s2":"","s3":"","caption":"","hashtags":["#..."],"spoiler_risk":false}}
Mets spoiler_risk à true si tu as un doute sur un spoiler."""
    note = ""
    for _ in range(3):
        r = ask_json(base + note)
        s = [r.get("s1", ""), r.get("s2", ""), r.get("s3", "")]
        problems = []
        if any(not x.strip() for x in s): problems.append("une slide est vide")
        if any(len(x.split()) > 18 for x in s): problems.append("une phrase dépasse 14 mots")
        if r.get("spoiler_risk"): problems.append("risque de spoiler")
        if len(set(s)) < 3: problems.append("phrases identiques")
        if not problems:
            tags = r.get("hashtags", [])
            tags = [t if t.startswith("#") else "#" + t for t in tags]
            return {"texts": s, "caption": r.get("caption", "").strip(), "hashtags": " ".join(tags)}
        note = "\n\nCorrige ce problème : " + ", ".join(problems) + "."
    raise RuntimeError("Impossible d'obtenir des textes valides sans spoiler")

def pick_images(meta, texts, thumbs):
    prompt = f"""Voici {len(thumbs)} images du {'film' if meta['type']=='movie' else 'la série'} « {meta['title']} ».
Pour chacune de ces 3 phrases de slide, choisis l'image la plus cohérente avec son sens ou son ambiance :
1. {texts[0]}
2. {texts[1]}
3. {texts[2]}
Évite les images floues, celles avec du texte ou un logo visible, et celles qui pourraient spoiler (révélation, fin). Utilise 3 images différentes si possible. Donne aussi focus_x (0 = gauche, 1 = droite) : où se trouve le sujet principal, pour le recadrage vertical.
JSON : [{{"image":1,"focus_x":0.5}}, {{"image":2,"focus_x":0.5}}, {{"image":3,"focus_x":0.5}}]"""
    r = ask_json(prompt, images=thumbs)
    out = []
    for i in range(3):
        try:
            idx = int(r[i]["image"]) - 1
            if not 0 <= idx < len(thumbs): raise ValueError
            out.append({"idx": idx, "focus": float(r[i].get("focus_x", 0.5))})
        except Exception:
            out.append({"idx": i % len(thumbs), "focus": 0.5})
    return out

def extract_title(message):
    r = ask_json(f'Message : « {message} »\nQuel film ou quelle série la personne demande-t-elle ? JSON : {{"titre":"","annee":null}} (titre vide si ce n\'est pas une demande de film/série).', model=MODEL_FAST, max_tokens=200)
    return (r.get("titre") or "").strip(), r.get("annee")
