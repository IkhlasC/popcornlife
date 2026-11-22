"""Le classeur « Hooks TikTok à adapter en français » : des posts qui ont très bien marché (surtout en anglais), à reproduire au plus près.
Les données sont dans data/classeur.json (une entrée par film). Un film déjà fait (data/history.json) ou coché « publie » n'est plus proposé."""
import json, random, re, unicodedata

def _n(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)

def fr(n):
    return f"{int(n or 0):,}".replace(",", " ")

def load():
    try:
        with open("data/classeur.json", encoding="utf-8") as f: return [x for x in json.load(f) if x.get("titre")]
    except Exception:
        return []

def mark_published(titre):
    try:
        with open("data/classeur.json", encoding="utf-8") as f: items = json.load(f)
        for x in items:
            if _n(x.get("titre")) == _n(titre): x["publie"] = True
        with open("data/classeur.json", "w", encoding="utf-8") as f: json.dump(items, f, ensure_ascii=False, indent=1)
    except Exception:
        pass

def find_by_title(title, year=None):
    """Retrouve l'entrée du classeur d'après le titre TMDB (pour reproduire le modèle même si elle tape le titre elle-même)."""
    for x in load():
        if _n(x["titre"]) == _n(title) and (not year or not x.get("annee") or abs(int(str(year)[:4]) - int(x["annee"])) <= 1):
            return x
    return None

def pick(exclude, search, flatrate, tries=8):
    """Choisit une entrée non publiée, au hasard pondéré par les likes ; on préfère un film disponible en abonnement en France.
    exclude = {(type, id)} déjà faits récemment ; search(titre, annee) -> [(type, id)] ; flatrate(type, id) -> bool.
    Renvoie (type, id, entrée) ou None."""
    items = [x for x in load() if not x.get("publie")]
    random.shuffle(items)
    items.sort(key=lambda x: -((x.get("likes") or x.get("vues") or 20000) ** 0.5) * random.random())     # tirage pondéré : les gros scores sortent plus souvent
    fallback = None
    for x in items[:tries]:
        try:
            found = search(x["titre"], x.get("annee"))
            if x.get("type") == "tv": found = sorted(found, key=lambda r: r[0] != "tv")
            if not found: continue
            t, i = found[0]
            if (t, i) in exclude: continue
            if flatrate(t, i): return t, i, x
            fallback = fallback or (t, i, x)
        except Exception:
            continue
    return fallback

def model_block(x):
    """Texte ajouté au prompt d'écriture : reproduire au plus près ce qui a marché."""
    if not x: return ""
    score = f"{fr(x['likes'])} likes" if x.get("likes") else (f"{fr(x['vues'])} vues" if x.get("vues") else "un très bon score")
    lignes = [f"POST MODÈLE À REPRODUIRE AU PLUS PRÈS (priorité maximale, il passe avant les autres consignes de style) : un post de {x.get('compte', '?')} sur CE MÊME film a fait {score}. Notre but est de DUPLIQUER ce qui a marché, en l'adaptant à notre style."]
    if x.get("hook_en"): lignes.append(f"- Hook original (anglais) : « {x['hook_en']} »")
    if x.get("hook_fr"): lignes.append(f"- Hook en français déjà préparé : « {x['hook_fr']} »")
    if x.get("slides_fr"): lignes.append("- Slides françaises du modèle (à suivre : même mécanique slide par slide) : " + " / ".join(f"« {t} »" for t in x["slides_fr"]))
    if x.get("legende_fr"): lignes.append(f"- Légende française préparée : « {x['legende_fr']} »")
    if x.get("pourquoi"): lignes.append(f"- Pourquoi ça marche : {x['pourquoi']}")
    if x.get("note"): lignes.append(f"- ATTENTION : {x['note']}")
    how = ("Comment faire : la slide 1 reprend QUASI TEL QUEL le hook français préparé (même mécanique, même construction de phrase, même fin coupée avec « … » ou « mais… » si elle existe, même ordre des informations) ; corrige-la seulement si elle dépasse 20 mots, contient le titre, ou contredit le synopsis. Les slides suivantes prolongent la MÊME mécanique que le modèle (un fait de plus, une aggravation), sans jamais révéler la fin."
           if x.get("hook_fr") else
           "Comment faire : aucun hook n'est préparé pour ce film : écris-le toi-même en reproduisant la mécanique de « Pourquoi ça marche » (le même type d'angle), avec un fait concret et précis que tu connais avec certitude.")
    lignes.append(how + " Pour le champ \"commentaire\" (question d'accroche de la description), pars de la légende française préparée si elle existe, sinon écris-en une dans le même esprit. Adapte à notre sauce seulement ce qui est nécessaire (mots simples, astérisque sur les mots sensibles, phrases courtes, pas de question dans les slides sauf en mode test). N'invente aucun fait réel. Ne dis jamais que c'est un modèle.")
    return "\n" + "\n".join(lignes) + "\n"
