import os, json, requests

def _call(method, data=None, files=None):
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}", data=data, files=files, timeout=90)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"Telegram {method} : {j.get('description')}")
    return j["result"]

def chat_id(): return int(os.environ["TELEGRAM_CHAT_ID"])

def lire_url():
    """Lien du bouton « Lire mes réponses » (fichier data/lire_url.txt). Vide : pas de bouton."""
    try:
        with open("data/lire_url.txt", encoding="utf-8") as f:
            u = f.read().strip()
        return u if u.startswith("http") else ""
    except OSError:
        return ""

def send(text, buttons=None):
    data = {"chat_id": chat_id(), "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"}
    rows = list(buttons or [])
    u = lire_url()
    if u: rows.append([{"text": "🔄 Lire mes réponses", "url": u}])      # un clic lance le bot, sans passer par GitHub
    if rows: data["reply_markup"] = json.dumps({"inline_keyboard": rows})
    return _call("sendMessage", data)

def send_files(paths):
    """Envoyées en tant que fichiers pour garder la pleine qualité 1080x1920."""
    if len(paths) == 1:
        with open(paths[0], "rb") as f:
            return _call("sendDocument", {"chat_id": chat_id()}, {"document": f})
    files, media = {}, []
    for i, p in enumerate(paths):
        files[f"f{i}"] = open(p, "rb"); media.append({"type": "document", "media": f"attach://f{i}"})
    try:
        return _call("sendMediaGroup", {"chat_id": chat_id(), "media": json.dumps(media)}, files)
    finally:
        for f in files.values(): f.close()

def updates(offset):
    return _call("getUpdates", {"offset": offset, "timeout": 0, "allowed_updates": json.dumps(["message", "callback_query"])})

def answer(cb_id):
    try: _call("answerCallbackQuery", {"callback_query_id": cb_id})
    except Exception: pass

def download_file(file_id, dest):
    """Télécharge une photo ou un fichier envoyé au bot."""
    info = _call("getFile", {"file_id": file_id})
    r = requests.get(f"https://api.telegram.org/file/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{info['file_path']}", timeout=90)
    r.raise_for_status()
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "wb") as f: f.write(r.content)
    return dest
