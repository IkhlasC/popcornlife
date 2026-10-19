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

Choisis 3 œuvres DIFFÉRENTES (pas 3 films du même genre ; 1 série maximum ; varie les pays si possible) qui ont le plus de potentiel pour un TikTok de recommandation qui fait swiper. Privilégie les sorties récentes, les univers visuellement forts (décors, ambiance, acteurs connus) et ceux dont on a envie de voir les images. Évite les titres trop vus partout si un titre plus surprenant est aussi bon.
Pour chacune : un angle éditorial, une idée de hook (une phrase), et pourquoi ça peut fonctionner sur TikTok (une phrase).
JSON : [{{"ref":"movie:123","angle":"","hook":"","pourquoi":""}}, ...]"""
    return ask_json(prompt)

EXEMPLES = """CE QUI MARCHE SUR LE COMPTE PopcornLife (vrais posts, du plus vu au moins vu) :
- Le Monde de John, 2,1 M de vues : 1) « Un garçon de 13 ans découvre un bunker à côté de sa maison. » 2) « Il décide de dr*guer toute sa famille et les enferme dedans. »
- Curve (court-métrage), 309 K : 1) « Une femme se retrouve seule dans cette position. » 2) « Au moindre mouvement, la chute est assurée. »
- Dans leur regard, 57 K : 1) « Un groupe d'amis passent la soirée à s'amuser dans Central Park. » 2) « Quand ils se retrouvent accusés à tort d'un v*ol et d'un m*eurtre. »
- The Rain, 12 K (le plus faible) : 1) « Dans un monde apocalyptique, une seule goutte de pluie peut te t*er. » 2) « Une fille va tout faire pour protéger son petit frère. » La 2e phrase est la plus générique : c'est elle qui freine.
Ce que ces textes ont en commun, et que tu dois reproduire :
- phrases simples, concrètes, au présent, 8 à 12 mots, en langage parlé ;
- un DÉTAIL PRÉCIS dans CHAQUE phrase (un âge, un chiffre, un lieu, un objet, une durée, un lien entre deux personnes) : si on peut remplacer le détail sans changer la phrase, il est trop vague ;
- on RACONTE ce qui se passe, on ne dit jamais quoi ressentir : aucun jugement ni conclusion (« impossible de lâcher », « incroyable », « bouleversant », « tout bascule ») ;
- la slide 1 pose une situation (normale ou étrange) ; la slide 2 donne la BASCULE et s'arrête JUSTE AVANT la réponse : on connaît le déclencheur, mais on retient la conséquence, l'identité ou le « pourquoi » ; c'est ce qui donne envie de voir la suite ;
- aucune question, pas de « tu » dans les slides 1 et 2 ;
- les mots sensibles sont masqués par un astérisque, comme sur le compte : t*er, m*eurtre, v*ol, dr*guer, s*icide, etc.

COMPARE (style uniquement, ne reprends pas ces faits) :
MAUVAIS (vague, bateau, il conclut au lieu de raconter) : « Des braqueurs expérimentés d'un côté, un inconnu trop précis de l'autre, impossible de lâcher. » / « Dans ce fourgon blindé, le petit nouveau ne rate aucune cible. »
BON (un fait précis, et on veut la suite) : « Un convoyeur engagé il y a trois jours abat seul quatre braqueurs armés. » puis « Personne dans l'équipe ne sait d'où il sort, et il refuse de dire son nom. »
Le BON donne un chiffre, une durée, un fait qu'on ne peut pas deviner, et laisse une zone d'ombre ; le MAUVAIS pourrait se coller sur n'importe quel film.

"""

def write_post(meta, guidance="", avoid=None):
    kind = "série" if meta["type"] == "tv" else "film"
    extra = ""
    if guidance:
        extra += f"\nINSTRUCTION DE LA RÉDACTRICE (à respecter en priorité absolue) : {guidance}\n"
    if avoid:
        extra += "\nTextes déjà proposés et REFUSÉS (ne les reprends pas, change d'angle) :\n" + "\n".join(f"- {x}" for x in avoid) + "\n"
    base = f"""Œuvre : {meta['title']} ({meta['year']}), {kind}. Genres : {', '.join(meta['genres'])}.
Accroche officielle : {meta['tagline'] or '-'}
Synopsis : {meta['overview']}
{extra}
{EXEMPLES}
Écris un carrousel TikTok de 3 phrases (une par slide), UNE phrase chacune, 12 mots maximum. Le but : retenir l'attention dès la slide 1 et créer du SUSPENSE à chaque slide, pour qu'on ait envie de swiper.
- slide 1 : une situation concrète et précise (détail chiffré ou visuel) qui arrête le scroll ;
- slide 2 : la bascule, racontée avec un fait précis, qui s'arrête juste avant la réponse (on retient la conséquence, l'identité ou le « pourquoi ») ;
- slide 3 : l'enjeu ou le dilemme final, concret (un délai, un danger, un choix impossible), sans dire comment ça finit.
Les trois forment une progression : chacune donne envie de voir la suivante.

MÉTHODE (c'est ce qui décide de la qualité) :
1. "brouillons_s1" : 6 versions DIFFÉRENTES de la slide 1 : (a) une personne précise (âge, métier) + un objet ou un lieu inhabituel, (b) une situation normale sur le point de dérailler, (c) une contrainte physique ou une règle impossible, (d) un piège ou une injustice, (e) un choix extrême, (f) un fait chiffré.
2. "brouillons_s2" : 5 versions de la slide 2, chacune basée sur un FAIT PRÉCIS du synopsis et qui laisse volontairement une zone d'ombre.
3. Garde pour chaque slide la plus concrète et la plus intrigante.
Test final pour chaque phrase : (1) peut-on la coller telle quelle sur un autre film ? Alors elle est trop vague, recommence. (2) contient-elle un jugement ou une conclusion (« impossible de lâcher », « tout change ») ? Supprime-le. (3) donne-t-elle envie de connaître la suite ? Sinon, recommence.
INTERDIT : « Et si… », « Imagine… », « quelque chose cloche », « tout bascule », « personne ne s'y attend », « tu vas adorer », « d'un côté… de l'autre », « impossible de lâcher », les questions, les superlatifs vides.

RÈGLE SPOILER : tu peux raconter le point de départ et la première grande bascule de l'histoire (ce que dirait le résumé au dos du film), mais JAMAIS le retournement final, la fin, qui meurt à la fin, ni l'identité d'un personnage caché.
Reste fidèle au synopsis fourni : n'invente aucun fait.

Ajoute 6 hashtags : généraux (#film #cinema ou #serie) et spécifiques au titre, à l'acteur principal ou au genre ; pas de hashtags vagues comme #drame.
JSON : {{"brouillons_s1":["","","","","",""],"brouillons_s2":["","","","",""],"s1":"","s2":"","s3":"","hashtags":["#..."],"spoiler_risk":false}}
Mets spoiler_risk à true seulement si une phrase révèle la fin ou un retournement."""
    note = ""
    for _ in range(3):
        r = ask_json(base + note, max_tokens=3000)
        s = [r.get("s1", ""), r.get("s2", ""), r.get("s3", "")]
        problems = []
        if any(not x.strip() for x in s): problems.append("une slide est vide")
        if any(len(x.split()) > 16 for x in s): problems.append("une phrase dépasse 12 mots")
        if r.get("spoiler_risk"): problems.append("risque de spoiler sur la fin ou un retournement")
        if len(set(s)) < 3: problems.append("phrases identiques")
        if any("?" in x for x in s): problems.append("une phrase contient une question")
        vague = re.compile(r"impossible de (le |la |les |s'en )?(l[âa]cher|quitter|d[ée]crocher)|d'un c[ôo]t[ée]|de l'autre|tout (bascule|change)|rien ne sera plus|plus jamais comme|quelque chose cloche|personne ne s'y attend|tu vas adorer", re.I)
        bad = [x for x in s if vague.search(x)]
        if bad: problems.append("formule vague ou conclusion interdite dans : " + " / ".join(bad) + " (raconte un fait précis à la place)")
        if avoid and s[0].strip() in [x.strip() for x in avoid]: problems.append("la slide 1 reprend un texte refusé")
        if not problems:
            tags = r.get("hashtags", [])
            tags = [t if t.startswith("#") else "#" + t for t in tags]
            return {"texts": s, "caption": "", "hashtags": " ".join(tags)}
        note = "\n\nCorrige ce problème : " + ", ".join(problems) + "."
    raise RuntimeError("Impossible d'obtenir des textes valides")

def pick_images(meta, thumbs):
    prompt = f"""Voici {len(thumbs)} images du {'film' if meta['type']=='movie' else 'la série'} « {meta['title']} ».
Choisis les 3 images les plus ACCROCHEUSES visuellement pour un carrousel TikTok vertical. Ne cherche PAS à illustrer un texte : cherche les images qui arrêtent le scroll et donnent envie de voir l'œuvre.
Critères, par ordre d'importance :
- un visage en gros plan ou plan rapproché, avec une émotion ou une intensité forte (regard, tension, peur, colère, sourire marquant), ou une image spectaculaire (décor, action) très lisible ;
- UN sujet principal net, placé plutôt dans la moitié HAUTE de l'image (le texte occupera le bas) ;
- couleurs et contrastes marqués, image nette et lumineuse ;
- fuis : plans larges où les personnages sont minuscules, foule, flou, image sombre ou terne, texte ou logo visible, visage coupé, scène qui spoile la fin.
L'image placée en n°1 doit être LA plus percutante de toutes (c'est elle qui décide si on continue). Utilise 3 images différentes.
Pour chaque image choisie, donne focus_x : la position horizontale du visage ou du sujet principal (0 = bord gauche, 1 = bord droit), pour recadrer en vertical autour de lui.
JSON : [{{"image":1,"focus_x":0.5}}, {{"image":2,"focus_x":0.5}}, {{"image":3,"focus_x":0.5}}] (dans l'ordre des slides 1, 2, 3)"""
    r = ask_json(prompt, images=thumbs)
    out, used = [], set()
    for i in range(3):
        try:
            idx = int(r[i]["image"]) - 1
            if not 0 <= idx < len(thumbs) or idx in used: raise ValueError
            out.append({"idx": idx, "focus": float(r[i].get("focus_x", 0.5))})
        except Exception:
            idx = next(k for k in range(len(thumbs)) if k not in used)
            out.append({"idx": idx, "focus": 0.5})
        used.add(out[-1]["idx"])
    return out

def extract_title(message):
    r = ask_json(f'Message : « {message} »\nQuel film ou quelle série la personne demande-t-elle ? JSON : {{"titre":"","annee":null}} (titre vide si ce n\'est pas une demande de film/série).', model=MODEL_FAST, max_tokens=200)
    return (r.get("titre") or "").strip(), r.get("annee")
