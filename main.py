import sys, os, io, json, html, datetime, traceback
import tmdb, ai, tg, render

DATA = "data"
RECENT_DAYS = 365
HELP = ("🍿 <b>PopcornLife Studio</b>\n\n"
        "• Chaque matin je t'envoie 3 propositions : appuie sur A, B ou C.\n"
        "• Tu peux aussi m'écrire un film : « Gone Girl » ou « Fais-moi un TikTok sur Dark ».\n"
        "• « propositions » : j'envoie 3 nouvelles idées.\n"
        "• « image 2 » : je change l'image de la slide 2 (1, 2 ou 3).")

def load(name, default):
    try:
        with open(f"{DATA}/{name}.json", encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError:
        return default

def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(f"{DATA}/{name}.json", "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=1)

def e(s): return html.escape(str(s))

def recent_ids():
    limit = (datetime.date.today() - datetime.timedelta(days=RECENT_DAYS)).isoformat()
    return {(h["type"], h["id"]) for h in load("history", []) if h["date"] >= limit}

def platform_info(t, i):
    p = tmdb.platforms(t, i)
    if p["flatrate"]:
        return " / ".join(p["flatrate"][:2]), f"Disponible en France sur : {', '.join(p['flatrate'])}"
    if p["rent"] or p["buy"]:
        return "", "Pas en abonnement en France d'après TMDB (location/achat seulement). Vérifie avant de publier."
    return "", "Plateforme en France introuvable : je n'en affiche aucune sur la slide 4."

# ---------- propositions ----------
def propose():
    pool = tmdb.candidates(recent_ids())
    if len(pool) < 6:
        tg.send("⚠️ Je n'ai pas trouvé assez de films disponibles pour faire des propositions."); return
    by_ref = {f'{p["type"]}:{p["id"]}': p for p in pool}
    chosen = [c for c in ai.propose(pool) if c.get("ref") in by_ref][:3]
    state = load("state", {"offset": 0}); state["pending"] = []
    lines, buttons = ["🍿 <b>Voici les propositions PopcornLife du jour</b>\n"], []
    for n, c in enumerate(chosen):
        p = by_ref[c["ref"]]; letter = "ABC"[n]
        plat, _ = platform_info(p["type"], p["id"])
        kind = "Série" if p["type"] == "tv" else "Film"
        lines.append(f"<b>{letter} — {e(p['title'])}</b> ({p['year']}) · {kind}{' · ' + e(plat) if plat else ''}\n"
                     f"Angle : {e(c['angle'])}\nHook : {e(c['hook'])}\nPourquoi : {e(c['pourquoi'])}\n")
        buttons.append({"text": f"{letter} — {p['title'][:25]}", "callback_data": f"pick:{p['type']}:{p['id']}"})
        state["pending"].append({"type": p["type"], "id": p["id"], "title": p["title"]})
    save("state", state)
    tg.send("\n".join(lines), [[b] for b in buttons])

# ---------- création d'un post ----------
def produce(t, i):
    meta = tmdb.details(t, i)
    if not meta["overview"] or not meta["poster_path"]:
        tg.send(f"⚠️ TMDB n'a pas de synopsis ou d'affiche pour « {e(meta['title'])} ». Je ne veux pas inventer : choisis-en un autre."); return
    warn = ""
    if (t, i) in recent_ids():
        warn = "\n⚠️ Tu as déjà fait ce titre il y a moins d'un an."
    tg.send(f"⏳ Je prépare <b>{e(meta['title'])}</b> ({meta['year']})…{warn}")
    plat, plat_msg = platform_info(t, i)
    post = ai.write_post(meta)
    paths = tmdb.backdrops(t, i)
    last = {"type": t, "id": i, "title": meta["title"], "year": meta["year"], "rating": meta["rating"], "platform": plat,
            "texts": post["texts"], "poster_path": meta["poster_path"], "candidates": paths, "assign": [], "focus": []}
    thumbs, bd = [], [None, None, None]
    if paths:
        small = [tmdb.download(p, "w300") for p in paths]
        for im in small:
            b = io.BytesIO(); im.save(b, "JPEG", quality=80); thumbs.append(b.getvalue())
        choice = ai.pick_images(meta, post["texts"], thumbs)
        last["assign"] = [c["idx"] for c in choice]; last["focus"] = [c["focus"] for c in choice]
        cache = {}
        for n, c in enumerate(choice):
            if c["idx"] not in cache: cache[c["idx"]] = tmdb.download(paths[c["idx"]], "w1280")
            bd[n] = cache[c["idx"]]
    poster = tmdb.download(meta["poster_path"], "w780")
    files = render.render_all(post["texts"], bd, last["focus"] or [0.5] * 3, poster,
                              {"title": meta["title"], "year": meta["year"], "platform": plat, "rating": meta["rating"]}, "out")
    tg.send_files(files)
    tg.send(f"<b>Caption (touche pour copier) :</b>\n<code>{e(post['caption'])}\n\n{e(post['hashtags'])}</code>")
    tg.send(f"✅ <b>{e(meta['title'])}</b> est prêt.\n{e(plat_msg)}\n\n"
            f"1. {e(post['texts'][0])}\n2. {e(post['texts'][1])}\n3. {e(post['texts'][2])}\n\n"
            f"Une image ne te plaît pas ? Écris « image 1 », « image 2 » ou « image 3 ».\n{meta['url']}")
    hist = load("history", []); hist.append({"type": t, "id": i, "title": meta["title"], "date": datetime.date.today().isoformat()})
    save("history", hist)
    state = load("state", {"offset": 0}); state["last"] = last; state["pending"] = []; save("state", state)

def redo_image(n):
    state = load("state", {"offset": 0}); last = state.get("last")
    if not last or not last["candidates"]:
        tg.send("Je n'ai pas de post récent avec des images à modifier."); return
    cands, assign = last["candidates"], last["assign"]
    cur = assign[n - 1]
    nxt = next((k % len(cands) for k in range(cur + 1, cur + 1 + len(cands)) if (k % len(cands)) not in assign), (cur + 1) % len(cands))
    assign[n - 1] = nxt; last["focus"][n - 1] = 0.5
    im = tmdb.download(cands[nxt], "w1280")
    os.makedirs("out", exist_ok=True); p = f"out/slide{n}.jpg"
    render.text_slide(last["texts"][n - 1], p, n, im, 0.5)
    tg.send_files([p]); tg.send(f"Voilà la slide {n} avec une autre image. Écris « image {n} » pour en essayer une autre.")
    save("state", state)

def manual(message):
    title, year = ai.extract_title(message)
    if not title:
        tg.send(HELP); return
    found = tmdb.search(title, year) or tmdb.search(title)
    if not found:
        tg.send(f"Je ne trouve pas « {e(title)} » sur TMDB. Vérifie l'orthographe ?"); return
    produce(*found[0])

# ---------- lecture des messages Telegram ----------
def handle(u, state):
    if "callback_query" in u:
        cb = u["callback_query"]
        if cb["message"]["chat"]["id"] != tg.chat_id(): return
        tg.answer(cb["id"])
        _, t, i = cb["data"].split(":"); produce(t, int(i)); return
    msg = u.get("message")
    if not msg or msg["chat"]["id"] != tg.chat_id() or "text" not in msg: return
    text = msg["text"].strip(); low = text.lower().strip(" .!")
    if low in ("/start", "aide", "/aide", "help"): tg.send(HELP)
    elif low in ("a", "b", "c") and state.get("pending"):
        k = "abc".index(low)
        if k < len(state["pending"]): p = state["pending"][k]; produce(p["type"], p["id"])
    elif low.startswith("image") and low[5:].strip() in ("1", "2", "3"): redo_image(int(low[5:].strip()))
    elif low in ("propositions", "proposition", "/propositions", "idées", "idees"): propose()
    else: manual(text)

def poll():
    state = load("state", {"offset": 0, "pending": [], "last": None})
    for u in tg.updates(state["offset"]):
        state["offset"] = u["update_id"] + 1; save("state", state)
        try:
            handle(u, load("state", state))
        except Exception as ex:
            traceback.print_exc()
            try: tg.send(f"⚠️ Une erreur est survenue : {e(ex)}\nRéessaie, ou écris-moi le titre directement.")
            except Exception: pass

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "poll"
    {"propose": propose, "poll": poll}[cmd]()
