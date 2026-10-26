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
        "• Tu peux m'envoyer ta propre image : envoie-la avec la légende « 1 » (ou 2, 3). Si elle n'est pas verticale, je la centre avec du noir en haut et en bas.\n"
        "• « zoom + » / « zoom - » : j'agrandis ou je réduis l'image de la dernière slide modifiée (« zoom + 2 » pour la slide 2). « plein cadre » : l'image remplit toute la slide.\n"
        "• Après un post, dis-moi librement ce que tu veux changer, autant de fois que tu veux : « image 1 avec son visage en gros plan », « texte 2 plus dur », « change l'image 2 puis le texte 1 », « slide 2 : ta phrase exacte ».\n"
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
    if not chosen:
        tg.send("⚠️ L'IA n'a pas renvoyé de proposition utilisable. Écris « propositions » pour réessayer."); return
    state = load("state", {"offset": 0}); state["pending"] = []
    lines, buttons = ["🍿 <b>Voici les propositions PopcornLife du jour</b>\n"], []
    for n, c in enumerate(chosen):
        p = by_ref[c["ref"]]; letter = "ABC"[n]
        plat, _ = platform_info(p["type"], p["id"])
        kind = "Série" if p["type"] == "tv" else "Film"
        lines.append(f"<b>{letter} — {e(p['title'])}</b> ({p['year']}) · {kind}{' · ' + e(plat) if plat else ''}\n"
                     f"Angle : {e(c.get('angle', ''))}\nHook : {e(c.get('hook', ''))}\nPourquoi : {e(c.get('pourquoi', ''))}\n")
        buttons.append({"text": f"{letter} — {p['title'][:25]}", "callback_data": f"pick:{p['type']}:{p['id']}"})
        state["pending"].append({"type": p["type"], "id": p["id"], "title": p["title"]})
    save("state", state)
    tg.send("\n".join(lines), [[b] for b in buttons])

# ---------- création d'un post ----------
def choose_images(meta, paths, texts=None):
    """Mélange choc + cohérence avec les textes ; la plus percutante en slide 1 ; recentrage sur le visage."""
    if not paths:
        return [], [], [None] * max(len(texts or []), 2)
    thumbs = []
    for p in paths:
        im = tmdb.download(p, "w300"); b = io.BytesIO(); im.save(b, "JPEG", quality=80); thumbs.append(b.getvalue())
    choice = ai.pick_images(meta, thumbs, texts)
    cache, focus, bd = {}, [], []
    for c in choice:
        if c["idx"] not in cache:
            cache[c["idx"]] = tmdb.download(paths[c["idx"]], "w1280")
        im = cache[c["idx"]]; bd.append(im)
        face = render.face_focus(im)   # on affine la position donnée par l'IA avec le vrai visage, s'il est détecté et cohérent
        focus.append(face if face is not None and abs(face - c["focus"]) <= 0.25 else c["focus"])
    return [c["idx"] for c in choice], focus, bd

def rewrite(guidance=""):
    state = load("state", {"offset": 0}); last = state.get("last")
    if not last:
        tg.send("Je n'ai pas de post récent à refaire. Écris d'abord un titre de film."); return
    meta = tmdb.details(last["type"], last["id"])
    tg.send(f"✍️ Je réécris les textes de <b>{e(last['title'])}</b>…" + (f"\nConsigne : {e(guidance)}" if guidance else ""))
    post = ai.write_post(meta, guidance, avoid=last["texts"])
    assign, focus, bd = choose_images(meta, last["candidates"], post["texts"])
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
    last["assign"], last["focus"], bd = choose_images(meta, paths, post["texts"])
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

# ---------- modifications libres du dernier carrousel ----------
def _ensure(last):
    n = len(last["texts"])
    last.setdefault("assign", []); last.setdefault("focus", [])
    while len(last["focus"]) < n: last["focus"].append(0.5)

def _slide_image(last, n):
    im, custom = None, False
    cp = (last.get("custom") or {}).get(str(n))
    if cp and os.path.exists(cp):                    # image envoyée par la rédactrice
        from PIL import Image
        im, custom = Image.open(cp), True
    elif last.get("candidates") and len(last["assign"]) >= n:
        im = tmdb.download(last["candidates"][last["assign"][n - 1]], "w1280")
    return im, custom

def _render_slide(last, n):
    im, custom = _slide_image(last, n)
    zoom = float((last.get("zoom") or {}).get(str(n), 1.0))
    os.makedirs("out", exist_ok=True); p = f"out/slide{n}.jpg"
    render.text_slide(last["texts"][n - 1], p, n, im, last["focus"][n - 1], last=(n == len(last["texts"])), custom=custom, zoom=zoom)
    return p

def _do_zoom(last, n, direction):
    im, custom = _slide_image(last, n)
    if im is None:
        raise ValueError("cette slide n'a pas d'image à zoomer")
    k = str(n); zs = last.setdefault("zoom", {}); cur = float(zs.get(k, 1.0))
    fill = render.fill_factor(im, custom); step = 1.4
    if direction == "fill": new = fill
    elif direction == "reset": new = 1.0
    elif direction == "out":
        new = cur / step
        if cur > fill * 1.02 and new < fill: new = fill      # on s'arrête d'abord sur « plein cadre »
    else:
        new = cur * step
        if cur < fill * 0.98 and new > fill: new = fill
    zs[k] = round(min(max(new, 0.4), fill * 2.5), 3)

def _do_image(last, n, hint=""):
    (last.get("custom") or {}).pop(str(n), None)     # on remplace l'image envoyée par une image du film
    (last.get("zoom") or {}).pop(str(n), None)       # et le zoom repart à zéro
    cands, assign = last["candidates"], last["assign"]
    if not cands or len(assign) < n:
        raise ValueError("pas d'images disponibles pour ce film")
    meta = tmdb.details(last["type"], last["id"])
    if hint:
        thumbs = []
        for p in cands:
            im = tmdb.download(p, "w300"); b = io.BytesIO(); im.save(b, "JPEG", quality=80); thumbs.append(b.getvalue())
        r = ai.pick_image_hint(meta, thumbs, hint, last["texts"][n - 1], list(assign))
    else:
        cur = assign[n - 1]
        nxt = next((k % len(cands) for k in range(cur + 1, cur + 1 + len(cands)) if (k % len(cands)) not in assign), (cur + 1) % len(cands))
        r = {"idx": nxt, "focus": 0.5}
    if r is None:
        raise ValueError("je n'ai pas trouvé d'image qui correspond")
    im = tmdb.download(cands[r["idx"]], "w1280")
    face = render.face_focus(im)
    if hint: focus = face if face is not None and abs(face - r["focus"]) <= 0.25 else r["focus"]
    else: focus = face if face is not None else 0.5
    assign[n - 1] = r["idx"]; last["focus"][n - 1] = focus

def apply_actions(actions):
    """Exécute dans l'ordre une ou plusieurs modifications, puis renvoie toutes les slides touchées."""
    state = load("state", {"offset": 0}); last = state.get("last")
    if not last or not last.get("texts"):
        tg.send("Je n'ai pas de post récent à modifier. Écris d'abord un titre de film."); return
    _ensure(last); total = len(last["texts"]); touched, notes = [], []
    for a in actions:
        kind = a.get("action")
        try: n = int(a.get("slide") or 0)
        except Exception: n = 0
        if kind in ("text", "image", "custom", "zoom") and not 1 <= n <= total:
            notes.append(f"Slide {n or '?'} : ce carrousel n'a que {total} slides de texte."); continue
        try:
            if kind == "text":
                meta = tmdb.details(last["type"], last["id"])
                ins = str(a.get("instruction") or "").strip()
                if a.get("exact") and ins:                  # sa propre phrase : on l'affiche telle quelle
                    last["texts"][n - 1] = ai.oral(ins.strip('"«» '))
                else:
                    last["texts"][n - 1] = ai.rewrite_slide(meta, last["texts"], n, ins)
                touched.append(n)
            elif kind == "image":
                _do_image(last, n, str(a.get("hint") or "")); touched.append(n)
            elif kind == "custom":
                from PIL import Image, ImageOps
                os.makedirs(f"{DATA}/custom", exist_ok=True); dst = f"{DATA}/custom/{last['id']}_slide{n}.jpg"
                ImageOps.exif_transpose(Image.open(a["path"])).convert("RGB").save(dst, "JPEG", quality=92)
                last.setdefault("custom", {})[str(n)] = dst; (last.get("zoom") or {}).pop(str(n), None); touched.append(n)
            elif kind == "zoom":
                d = str(a.get("direction") or "in")
                _do_zoom(last, n, d if d in ("in", "out", "fill", "reset") else "in"); touched.append(n)
            elif kind == "rewrite_all":
                state["last"] = last; save("state", state)
                rewrite(str(a.get("instruction") or "")); return
            elif kind == "new_film":
                state["last"] = last; save("state", state)
                t = str(a.get("title") or "").strip()
                found = tmdb.search(t, a.get("year")) or tmdb.search(t) if t else None
                if not found: tg.send(f"Je ne trouve pas « {e(t)} » sur TMDB."); return
                produce(*found[0]); return
            elif kind == "propositions":
                state["last"] = last; save("state", state); propose(); return
            else:
                notes.append("Je n'ai pas compris cette partie de ta demande.")
        except Exception as ex:
            traceback.print_exc(); notes.append(f"Slide {n or '?'} : {e(ex)}")
    if touched: last["last_slide"] = touched[-1]
    state["last"] = last; save("state", state)
    slides = sorted(set(touched))
    if slides:
        tg.send_files([_render_slide(last, n) for n in slides])
    tg.send(("\n".join(notes) + "\n\n" if notes else "") + "\n".join(f"{k+1}. {e(t)}" for k, t in enumerate(last["texts"])) + "\n\n"
            "Tu peux continuer : « zoom + », « zoom - », « image 1 avec son visage en gros plan », « texte 2 plus dur », « change l'image 2 puis le texte 1 »… "
            "Dis-moi tout ce que tu veux, dans l'ordre.")

def edit_slide(n, instruction):
    apply_actions([{"action": "text", "slide": n, "instruction": instruction}])

def redo_image(n, hint=""):
    apply_actions([{"action": "image", "slide": n, "hint": hint}])

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
def photo_received(file_id, caption):
    state = load("state", {"offset": 0}); last = state.get("last")
    if not last or not last.get("texts"):
        tg.send("J'ai reçu ton image, mais je n'ai pas de carrousel en cours. Écris d'abord un titre de film."); return
    os.makedirs(f"{DATA}/custom", exist_ok=True)
    path = tg.download_file(file_id, f"{DATA}/custom/_waiting.jpg")
    mm = re.search(r"([1-3])", caption)
    if mm:
        apply_actions([{"action": "custom", "slide": int(mm.group(1)), "path": path}])
    else:
        state["photo"] = path; save("state", state)
        tg.send(f"📷 Image reçue. Pour quelle slide ? Réponds simplement 1, 2 ou 3 (le carrousel a {len(last['texts'])} slides de texte).")

def handle(u, state):
    if "callback_query" in u:
        cb = u["callback_query"]
        if cb["message"]["chat"]["id"] != tg.chat_id(): return
        tg.answer(cb["id"])
        _, t, i = cb["data"].split(":"); produce(t, int(i)); return
    msg = u.get("message")
    if not msg or msg["chat"]["id"] != tg.chat_id(): return
    fid = None
    if msg.get("photo"): fid = msg["photo"][-1]["file_id"]
    elif (msg.get("document") or {}).get("mime_type", "").startswith("image/"): fid = msg["document"]["file_id"]
    if fid:                                          # une image envoyée par la rédactrice
        photo_received(fid, (msg.get("caption") or "").strip()); return
    if "text" not in msg: return
    text = msg["text"].strip(); low = text.lower().strip(" .!")
    ph = state.get("photo")
    if ph and os.path.exists(ph) and re.search(r"(?i)\b(image|photo|slide|la|numéro)\s*([1-3])\b|^\s*([1-3])\s*$", text):
        mm = re.search(r"([1-3])", text)
        st = load("state", {"offset": 0}); st["photo"] = None; save("state", st)
        apply_actions([{"action": "custom", "slide": int(mm.group(1)), "path": ph}]); return
    elif ph:                                         # autre message : l'image en attente est abandonnée
        st = load("state", {"offset": 0}); st["photo"] = None; save("state", st)
    zm = re.match(r"^(zoom|d[eé]zoom|plein (?:cadre|[eé]cran)|remplis?(?: tout)?)\b(.*)$", low)
    if zm and state.get("last") and state["last"].get("texts") and len(low.split()) <= 5:
        rest = zm.group(2); sl = re.search(r"\b([1-3])\b", rest)
        n = int(sl.group(1)) if sl else int(state["last"].get("last_slide") or 1)
        w = zm.group(1)
        if w.startswith(("plein", "rempli")): d = "fill"
        elif w.startswith("d") or re.search(r"(-|moins|\bmoin\b)", rest): d = "out"
        elif "reset" in rest or "normal" in rest: d = "reset"
        else: d = "in"
        apply_actions([{"action": "zoom", "slide": n, "direction": d}]); return
    ex = re.match(r"(?is)^\s*(?:slide|texte|phrase|la)\s*([1-3])\s*[:：]\s*(.{4,})$", text)
    if ex and state.get("last") and state["last"].get("texts"):    # « slide 2 : ta phrase » : sa phrase telle quelle, sans passer par l'IA
        apply_actions([{"action": "text", "slide": int(ex.group(1)), "instruction": ex.group(2).strip(), "exact": True}]); return
    if low in ("/start", "aide", "/aide", "help"): tg.send(HELP)
    elif low in ("a", "b", "c") and state.get("pending"):
        k = "abc".index(low)
        if k < len(state["pending"]): p = state["pending"][k]; produce(p["type"], p["id"])
    elif low.startswith("image") and low[5:].strip() in ("1", "2", "3"): redo_image(int(low[5:].strip()))
    elif re.match(r"(?i)^(refais|refait|autre hook|nouveau hook|nouveaux textes|change les phrases|change le hook)\b", text):
        rewrite(re.sub(r"(?i)^(refais|refait|autre hook|nouveau hook|nouveaux textes|change les phrases|change le hook)\b[\s:,\-]*", "", text).strip())
    elif low in ("propositions", "proposition", "/propositions", "idées", "idees"): propose()
    else:
        last = state.get("last")
        if last and last.get("texts"):               # un carrousel est en cours : on comprend la demande libre
            try: acts = [a for a in ai.route(text, last["texts"], last["title"]) if a.get("action") != "unknown"]
            except Exception: traceback.print_exc(); acts = []
            if acts:
                apply_actions(acts); return
            if len(text.split()) > 6:
                tg.send("Je n'ai pas compris. Exemples : « image 1 avec son visage en gros plan », « texte 2 plus dur », « change l'image 2 puis le texte 1 », ou un autre titre de film."); return
        manual(text)

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
