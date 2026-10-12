import os, io, random, requests
from PIL import Image

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

def candidates(exclude, n=30):
    """Films/séries bien notés, disponibles en abonnement en France, jamais utilisés récemment."""
    pool = []
    for t in ("movie", "tv"):
        for page in random.sample(range(1, 9), 3):
            res = get(f"/discover/{t}", language="fr-FR", sort_by="popularity.desc", page=page,
                      **{"vote_average.gte": 7.0, "vote_count.gte": 1500 if t == "movie" else 600},
                      watch_region="FR", with_watch_monetization_types="flatrate")
            for it in res["results"]:
                if (t, it["id"]) in exclude or not it.get("overview") or not it.get("poster_path"):
                    continue
                pool.append({"type": t, "id": it["id"], "title": it.get("title") or it.get("name"),
                             "year": _year(it.get("release_date") or it.get("first_air_date")),
                             "rating": round(it["vote_average"], 1), "overview": it["overview"],
                             "genres": [genres().get(g, "") for g in it.get("genre_ids", [])][:3]})
    seen, out = set(), []
    for it in pool:
        if (it["type"], it["id"]) not in seen:
            seen.add((it["type"], it["id"])); out.append(it)
    random.shuffle(out)
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
                 (" Standard with Ads", ""), (" with Ads", ""), (" Amazon Channel", "")):
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

def backdrops(t, i, n=10):
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
