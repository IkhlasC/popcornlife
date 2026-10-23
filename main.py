import sys, os, io, re, json, html, datetime, traceback
from zoneinfo import ZoneInfo
import tmdb, ai, tg, render

DATA = "data"
RECENT_DAYS = 365
SEND_HOUR = 8   # heure (Paris) à partir de laquelle les propositions du jour sont envoyées
HELP = ("🍿 <b>PopcornLife Studio</b>\n\n"
        "• Chaque matin je t'envoie 3 propositions : appuie sur A, B ou C.\n"
        "• Tu peux aussi m'écrire un film : « Gone Girl » ou « Fais-moi un TikTok sur Dark ».\n"
        "• « propositions » : j'envoie 3 nouvelles idées.\n"
        "• « image 2 » : je change l'image de la slide 2 (1, 2 ou 3).\n"
        "• « slide 2 plus choquant » ou « slide 2 : ta phrase » : je change le texte d'une seule slide.\n"
        "• « refais » : j'écris de nouveaux textes pour le dernier film. Tu peux préciser : « refais plus mystérieux ».")

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
def daily():
    """Envoie les propositions une seule fois par jour, à partir de 8 h (heure de Paris), même si GitHub a du retard."""
    now = datetime.datetime.now(ZoneInfo("Europe/Paris")); today = now.date().isoformat()
    force = os.environ.get("FORCE") == "true"
    state = load("state", {"offset": 0})
    if not force and (state.get("last_propose") == today or now.hour < SEND_HOUR):
        return
    state["last_propose"] = today; save("state", state)   # on note d'abord, pour ne jamais envoyer deux fois
    try:
        propose()
    except Exception as ex:
        traceback.print_exc()
        try: tg.send(f"⚠️ Je n'ai pas pu préparer les propositions du jour ({e(ex)}). Écris « propositions » pour réessayer.")
        except Exception: pass

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
def choose_images(meta, paths):
    """L'IA choisit les 3 images les plus accrocheuses (la plus percutante en slide 1), puis on recentre sur le visage."""
    bd = [None, None, None]
    if not paths:
        return [], [], bd
    thumbs = []
    for p in paths:
        im = tmdb.download(p, "w300"); b = io.BytesIO(); im.save(b, "JPEG", quality=80); thumbs.append(b.getvalue())
    choice = ai.pick_images(meta, thumbs)
    cache, focus = {}, []
    for n, c in enumerate(choice):
        if c["idx"] not in cache:
            cache[c["idx"]] = tmdb.download(paths[c["idx"]], "w1280")
        bd[n] = cache[c["idx"]]
        face = render.face_focus(bd[n])   # on affine la position donnée par l'IA avec le vrai visage, s'il est détecté et cohérent
        focus.append(face if face is not None and abs(face - c["focus"]) <= 0.25 else c["focus"])
    return [c["idx"] for c in choice], focus, bd

def rewrite(guidance=""):
    state = load("state", {"offset": 0}); last = state.get("last")
    if not last:
        tg.send("Je n'ai pas de post récent à refaire. Écris d'abord un titre de film."); return
    meta = tmdb.details(last["type"], last["id"])
    tg.send(f"✍️ Je réécris les textes de <b>{e(last['title'])}</b>…" + (f"\nConsigne : {e(guidance)}" if guidance else ""))
    post = ai.write_post(meta, guidance, avoid=last["texts"])
    assign, focus, bd = choose_images(meta, last["candidates"])
    poster = tmdb.download(last["poster_path"], "w780")
    files = render.render_all(post["texts"], bd, focus or [0.5] * 3, poster,
                              {"title": last["title"], "year": last["year"], "platform": last["platform"], "rating": last["rating"]}, "out")
    tg.send_files(files[:-1])
    tg.send("\n".join(f"{k+1}. {e(t)}" for k, t in enumerate(post["texts"])) + "\n\n"
            "L'affiche (dernière slide) ne change pas. Pas encore ça ? Écris « refais » suivi de ce que tu veux, "
            "par exemple « refais plus mystérieux, sans question ».")
    last.update(texts=post["texts"], assign=assign, focus=focus or [0.5] * 3)
    state["last"] = last; save("state", state)

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
    last["assign"], last["focus"], bd = choose_images(meta, paths)
    poster = tmdb.download(meta["poster_path"], "w780")
    files = render.render_all(post["texts"], bd, last["focus"] or [0.5] * 3, poster,
                              {"title": meta["title"], "year": meta["year"], "platform": plat, "rating": meta["rating"]}, "out")
    tg.send_files(files)
    tg.send(f"<code>{e(meta['title'])}</code>")
    tg.send(f"<code>{e(post['hashtags'])}</code>")
    tg.send(f"✅ <b>{e(meta['title'])}</b> est prêt ({len(post['texts'])} slides + l'affiche).\n{e(plat_msg)}\n\n"
            + "\n".join(f"{k+1}. {e(t)}" for k, t in enumerate(post["texts"])) + "\n\n"
            f"Une image ne te plaît pas ? Écris « image 1 », « image 2 »… (une par slide).\n{meta['url']}")
    hist = load("history", []); hist.append({"type": t, "id": i, "title": meta["title"], "date": datetime.date.today().isoformat()})
    save("history", hist)
    state = load("state", {"offset": 0}); state["last"] = last; state["pending"] = []; save("state", state)

def edit_slide(n, instruction):
    state = load("state", {"offset": 0}); last = state.get("last")
    if not last or not last.get("texts"):
        tg.send("Je n'ai pas de post récent à modifier. Écris d'abord un titre de film."); return
    if n > len(last["texts"]):
        tg.send(f"Ce carrousel n'a que {len(last['texts'])} slides de texte."); return
    meta = tmdb.details(last["type"], last["id"])
    tg.send(f"✍️ Je réécris la slide {n}…")
    new = ai.rewrite_slide(meta, last["texts"], n, instruction)
    last["texts"][n - 1] = new
    im = None
    if last.get("candidates") and len(last.get("assign", [])) >= n:
        im = tmdb.download(last["candidates"][last["assign"][n - 1]], "w1280")
    fx = last["focus"][n - 1] if len(last.get("focus", [])) >= n else 0.5
    os.makedirs("out", exist_ok=True); p = f"out/slide{n}.jpg"
    render.text_slide(new, p, n, im, fx, last=(n == len(last["texts"])))
    tg.send_files([p])
    tg.send(f"Slide {n} : {e(new)}\n\nPas encore ça ? Écris par exemple « slide {n} plus choquant » ou « slide {n} : ta phrase exacte ».")
    state["last"] = last; save("state", state)

def redo_image(n):
    state = load("state", {"offset": 0}); last = state.get("last")
    if not last or not last["candidates"]:
        tg.send("Je n'ai pas de post récent avec des images à modifier."); return
    if n > len(last["texts"]):
        tg.send(f"Ce carrousel n'a que {len(last['texts'])} slides de texte."); return
    cands, assign = last["candidates"], last["assign"]
    cur = assign[n - 1]
    nxt = next((k % len(cands) for k in range(cur + 1, cur + 1 + len(cands)) if (k % len(cands)) not in assign), (cur + 1) % len(cands))
    assign[n - 1] = nxt
    im = tmdb.download(cands[nxt], "w1280")
    fx = render.face_focus(im); fx = 0.5 if fx is None else fx; last["focus"][n - 1] = fx
    os.makedirs("out", exist_ok=True); p = f"out/slide{n}.jpg"
    render.text_slide(last["texts"][n - 1], p, n, im, fx, last=(n == len(last["texts"])))
    tg.send_files([p]); tg.send(f"Voilà la slide {n} avec une autre image. Écris « image {n} » pour en essayer une autre.")
    save("state", state)

def parse_request(message):
    """Titre court = utilisé tel quel (avec année facultative). Phrase longue = l'IA extrait le titre."""
    text = message.strip().strip('"«» ').strip()
    title, year = text, None
    mm = re.match(r"^(.*?)[\s,(]+((?:19|20)\d{2})\)?$", text)
    if mm:
        title, year = mm.group(1).strip(), mm.group(2)
    long_request = len(title.split()) > 5 or re.match(r"(?i)^(fais|fait|cr[ée]e|peux|tiktok|un tiktok|je veux)", title)
    if long_request:
        try:
            t, y = ai.extract_title(message)
            if t:
                title, year = t, (str(y) if y else year)
        except Exception:
            traceback.print_exc()
            if " sur " in title:
                title = title.rsplit(" sur ", 1)[1].strip(' .!?"«»')
    return title, year

def manual(message):
    title, year = parse_request(message)
    if not title:
        tg.send(HELP); return
    found = tmdb.search(title, year) or tmdb.search(title)
    if not found:
        tg.send(f"Je ne trouve pas « {e(title)} » sur TMDB. Vérifie l'orthographe, ou ajoute l'année : « {e(title)} 2026 »."); return
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
    elif re.match(r"(?i)^(slide|texte|phrase)\s*([1-3])\b", text):
        mm = re.match(r"(?i)^(?:slide|texte|phrase)\s*([1-3])\b[\s:,\-]*(.*)$", text, re.S)
        edit_slide(int(mm.group(1)), mm.group(2).strip())
    elif low.startswith("image") and low[5:].strip() in ("1", "2", "3"): redo_image(int(low[5:].strip()))
    elif re.match(r"(?i)^(refais|refait|autre hook|nouveau hook|nouveaux textes|change les phrases|change le hook)\b", text):
        rewrite(re.sub(r"(?i)^(refais|refait|autre hook|nouveau hook|nouveaux textes|change les phrases|change le hook)\b[\s:,\-]*", "", text).strip())
    elif low in ("propositions", "proposition", "/propositions", "idées", "idees"): propose()
    else: manual(text)

def poll():
    state = load("state", {"offset": 0, "pending": [], "last": None})
    for u in tg.updates(state["offset"]):
        state = load("state", state); state["offset"] = u["update_id"] + 1; save("state", state)
        try:
            handle(u, load("state", state))
        except Exception as ex:
            traceback.print_exc()
            try: tg.send(f"⚠️ Une erreur est survenue : {e(ex)}\nRéessaie, ou écris-moi le titre directement.")
            except Exception: pass
    daily()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "poll"
    {"propose": propose, "daily": daily, "poll": poll}[cmd]()