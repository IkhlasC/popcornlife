import os, io, random, datetime, requests
from PIL import Image

# Œuvres proposées chaque matin : sorties à partir de cette année (change ce chiffre si tu veux plus ou moins récent).
MIN_YEAR = datetime.date.today().year - 8

BASE = "https://api.themoviedb.org/3"; IMG = "https://image.tmdb.org/t/p/"

def get(path, **params):
    params["api_key"] = os.environ["TMDB_API_KEY"]
    r = requests.get(BASE + path, params=params, timeout=30); r.raise_for_status()
    return r.json()

_GENRES = {}
def genres():
    if not _GENRES:
        for t in ("movie", "tv"):
            for g in get(f"/genre/{t}/list", language="fr-FR")["genres"]:
                _GENRES[g["id"]] = g["name"]
    return _GENRES

def _year(d): return (d or "")[:4]

NETFLIX = 8          # identifiant TMDB de Netflix

def _entry(t, it, **flags):
    d = it.get("release_date") or it.get("first_air_date") or ""
    return {"type": t, "id": it["id"], "title": it.get("title") or it.get("name"), "year": _year(d), "date": d,
            "rating": round(it.get("vote_average") or 0, 1), "overview": it.get("overview", ""), "poster_path": it.get("poster_path"),
            "genres": [genres().get(g, "") for g in it.get("genre_ids", [])][:3], "popularity": it.get("popularity", 0), **flags}

def _add(pool, e, exclude, min_year=None):
    key = (e["type"], e["id"])
    if key in exclude or not e["overview"] or not e["poster_path"]:
        return None
    if min_year and not (e["year"].isdigit() and int(e["year"]) >= min_year):
        return None
    if key in pool:
        for k in ("actu",):
            if e.get(k) and not pool[key].get(k): pool[key][k] = e[k]
        pool[key]["trending"] = pool[key].get("trending") or e.get("trending")
        pool[key]["netflix"] = pool[key].get("netflix") or e.get("netflix")
        return pool[key]
    pool[key] = e
    return e

def _flatrate(t, i):
    """(disponible en abonnement en France ?, disponible sur Netflix ?)"""
    try:
        names = platforms(t, i)["flatrate"]
    except Exception:
        return False, False
    return bool(names), "Netflix" in names

def candidates(exclude, n=36, actu=None):
    """Films/séries disponibles en abonnement en France. Priorité : Netflix, ce dont on parle en ce moment (tendances, nouveautés,
    titres de l'actualité). Chaque œuvre porte des indicateurs qui servent à les classer."""
    pool = {}
    def safe(label, fn):
        try: fn()
        except Exception as ex: print(f"[tmdb] {label} ignoré : {ex}", flush=True)
    base = {"vote_average.gte": 6.5, "watch_region": "FR", "with_watch_monetization_types": "flatrate"}
    # 1) Netflix France, les plus populaires du moment (la popularité TMDB suit l'actualité)
    def netflix():
        for t in ("movie", "tv"):
            dk = "primary_release_date.gte" if t == "movie" else "first_air_date.gte"
            for page in random.sample(range(1, 6), 3):
                res = get(f"/discover/{t}", language="fr-FR", sort_by="popularity.desc", page=page, with_watch_providers=NETFLIX,
                          **{**base, "vote_count.gte": 150 if t == "movie" else 100, dk: f"{MIN_YEAR}-01-01"})
                for it in res["results"]: _add(pool, _entry(t, it, netflix=True), exclude, MIN_YEAR)
    safe("netflix", netflix)
    # 2) autres plateformes (pour varier), moins de place
    def autres():
        for t in ("movie", "tv"):
            dk = "primary_release_date.gte" if t == "movie" else "first_air_date.gte"
            res = get(f"/discover/{t}", language="fr-FR", sort_by="popularity.desc", page=random.randint(1, 4),
                      **{**base, "vote_average.gte": 7.0, "vote_count.gte": 700 if t == "movie" else 300, dk: f"{MIN_YEAR}-01-01"})
            for it in res["results"]: _add(pool, _entry(t, it), exclude, MIN_YEAR)
    safe("autres", autres)
    # 3) tendances de la semaine
    def tendances():
        for t in ("movie", "tv"):
            for rank, it in enumerate(get(f"/trending/{t}/week", language="fr-FR")["results"][:12]):
                e = _entry(t, it, trending=rank + 1)
                if (t, it["id"]) not in pool:
                    ok, nf = _flatrate(t, it["id"])
                    if not ok: continue
                    e["netflix"] = nf
                _add(pool, e, exclude, MIN_YEAR)
    safe("tendances", tendances)
    # 4) titres de l'actualité (recherche web faite par l'IA)
    def actualite():
        for a in (actu or [])[:15]:
            found = search(str(a.get("titre") or ""), a.get("annee")) or search(str(a.get("titre") or ""))
            if not found: continue
            t, i = found[0]
            d = get(f"/{t}/{i}", language="fr-FR")
            ok, nf = _flatrate(t, i)
            if not ok: continue
            d["genre_ids"] = [g["id"] for g in d.get("genres", [])]
            _add(pool, _entry(t, d, actu=str(a.get("raison") or "dans l'actualité"), netflix=nf or bool(a.get("netflix") and nf)), exclude, MIN_YEAR - 5)
    safe("actualité", actualite)
    # nouveautés + score de priorité
    today = datetime.date.today()
    out = []
    for e in pool.values():
        try: age = (today - datetime.date.fromisoformat(e["date"])).days
        except Exception: age = 9999
        e["nouveau"] = 0 <= age <= 120
        buzz = []
        if e.get("actu"): buzz.append(f"dans l'actu : {e['actu']}")
        if e.get("trending"): buzz.append(f"en tendance cette semaine (n°{e['trending']})")
        if e["nouveau"]: buzz.append("sorti récemment")
        e["buzz"] = " ; ".join(buzz)
        e["score_prio"] = (3 if e.get("netflix") else 0) + (2 if e.get("actu") else 0) \
                          + (2 if e.get("trending") else 0) + (1 if e["nouveau"] else 0) + random.random() * 1.5
        out.append(e)
    out.sort(key=lambda e: -e["score_prio"])
    return out[:n]

def details(t, i):
    d = get(f"/{t}/{i}", language="fr-FR")
    return {"type": t, "id": i, "title": d.get("title") or d.get("name"),
            "original_title": d.get("original_title") or d.get("original_name"),
            "year": _year(d.get("release_date") or d.get("first_air_date")),
            "overview": d.get("overview", ""), "tagline": d.get("tagline", ""),
            "genres": [g["name"] for g in d.get("genres", [])],
            "rating": round(d["vote_average"], 1) if d.get("vote_count", 0) >= 50 else None,
            "poster_path": d.get("poster_path"),
            "url": f"https://www.themoviedb.org/{t}/{i}"}

def _clean(name):
    for a, b in (("Amazon Prime Video", "Prime Video"), ("Disney Plus", "Disney+"), ("Apple TV Plus", "Apple TV+"),
                 ("Paramount Plus Premium", "Paramount+"), ("Paramount Plus", "Paramount+"), (" Premium", ""), (" Standard with Ads", ""), (" with Ads", ""), (" Amazon Channel", "")):
        name = name.replace(a, b)
    return name.strip()

def platforms(t, i):
    fr = get(f"/{t}/{i}/watch/providers").get("results", {}).get("FR", {})
    out = {}
    for k in ("flatrate", "rent", "buy"):
        names = []
        for p in fr.get(k, []):
            c = _clean(p["provider_name"])
            if c not in names: names.append(c)
        out[k] = names
    return out

def backdrops(t, i, n=24):
    res = get(f"/{t}/{i}/images", include_image_language="null")["backdrops"]
    if len(res) < 4:
        res = get(f"/{t}/{i}/images", include_image_language="null,en,fr")["backdrops"]
    res = [b for b in res if b.get("width", 0) >= 1280]
    res.sort(key=lambda b: b.get("vote_average", 0), reverse=True)
    return [b["file_path"] for b in res[:n]]

def search(query, year=None):
    out = []
    for r in get("/search/multi", query=query, language="fr-FR")["results"]:
        if r.get("media_type") in ("movie", "tv"):
            y = _year(r.get("release_date") or r.get("first_air_date"))
            if year and y != str(year):
                continue
            out.append((r["media_type"], r["id"]))
    return out

def download(path, size="w1280"):
    r = requests.get(f"{IMG}{size}{path}", timeout=60); r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")
