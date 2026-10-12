import os, json, requests

def _call(method, data=None, files=None):
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}", data=data, files=files, timeout=90)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"Telegram {method} : {j.get('description')}")
    return j["result"]

def chat_id(): return int(os.environ["TELEGRAM_CHAT_ID"])

def send(text, buttons=None):
    data = {"chat_id": chat_id(), "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if buttons: data["reply_markup"] = json.dumps({"inline_keyboard": buttons})
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
