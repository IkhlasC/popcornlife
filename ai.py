import os, io, re, json, base64
from anthropic import Anthropic

MODEL = os.environ.get("MODEL_WRITE", "claude-sonnet-5-5")
MODEL_FAST = os.environ.get("MODEL_FAST", "claude-haiku-5-5")
_client = None

# Style des slides. False = ta voix PopcornLife (majuscule au début). True = style « tout en minuscules, sans point final » du compte @alorsonregardequoi.
STYLE_ORAL = False

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

def parse_json(txt):
    """Extrait le JSON d'une réponse, même entourée de texte ou de ```. Renvoie None si illisible."""
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt.strip(), flags=re.M).strip()
    cands = [clean]
    for pat in (r"\{.*\}", r"\[.*\]"):
        m = re.search(pat, clean, re.S)
        if m: cands.append(m.group(0))
    for c in cands:
        try:
            return json.loads(c)
        except Exception:
            pass
    return None

def ask_json(prompt, **kw):
    for attempt in range(2):
        r = parse_json(ask(prompt, **kw))
        if r is not None:
            return r
        prompt += "\n\nRéponds UNIQUEMENT avec du JSON valide."
    raise RuntimeError("Réponse IA illisible")

def as_dict(r):
    """Si l'IA a renvoyé une liste contenant l'objet attendu, on prend l'objet."""
    if isinstance(r, list):
        r = next((x for x in r if isinstance(x, dict)), {})
    return r if isinstance(r, dict) else {}

def propose(pool):
    lines = "\n".join(f'{p["type"]}:{p["id"]} | {p["title"]} ({p["year"]}) | note {p["rating"]} | {", ".join(p["genres"])} | {p["overview"][:220]}' for p in pool)
    prompt = f"""Voici une liste d'œuvres disponibles en streaming en France :
{lines}

Choisis les 3 œuvres qui vont FAIRE LE PLUS RÉAGIR sur TikTok, c'est-à-dire celles dont une seule phrase provoque une émotion forte (peur, choc, indignation, « c'est quoi ce film ? », « je dois le voir »). Note chaque œuvre de 1 à 10 sur son potentiel de réaction (score_reaction) et ne garde que les 3 meilleures scores, classées de la plus forte à la moins forte. Ne retiens qu'une œuvre à plus de 7 si tu peux la défendre avec une phrase choc ; refuse les œuvres tièdes même si elles sont bien notées.
Ce qui fait le plus réagir : une MENACE VENUE DU CERCLE FAMILIER (un père, une mère, un frère, un enfant, un proche qui n'est pas ce qu'il semble), une INJUSTICE ou un dilemme moral (jusqu'où irais-tu ?), un enfant ou un proche en danger, un piège dans un lieu du quotidien (airbnb, concert, tunnel, aéroport, vacances en famille), un retournement, une situation où le lecteur se dit « et si c'était moi ? ». Privilégie les œuvres où le lecteur peut se mettre à la place d'un personnage.
Varie (pas 3 films du même genre ; 1 série maximum ; varie les pays si possible), privilégie les sorties récentes et les films de découverte plutôt que les blockbusters vus partout. Évite les décors lointains ou fantastiques (apocalypse, western, dystopie, monstres), les clichés de genre (cimetière, village maudit) et les concepts qu'il faut expliquer.
Pour chacune : un angle éditorial, une idée de hook (une phrase), et pourquoi ça peut faire réagir sur TikTok (une phrase).
JSON : [{{"ref":"movie:123","score_reaction":8,"angle":"","hook":"","pourquoi":""}}, ...]"""
    return ask_json(prompt)

EXEMPLES = """RÉFÉRENCES DE STYLE. Ne recopie jamais ces phrases ni ces idées : inspire-toi du RYTHME, de la STRUCTURE et du niveau de précision.

A) TA VOIX PopcornLife (priorité : c'est le style du compte, majuscule au début, 9 à 12 mots par slide) :
- Trap, 3,3 M de vues : « Ce t*eur en série se rend à un concert avec sa fille » / « Il se rend compte que le concert tout entier est un piège pour lui »
- Le Monde de John, 2,1 M : « Un garçon de 13 ans découvre un bunker à côté de sa maison » / « Il décide de dr*guer toute sa famille et les enferme dedans »
- Omar m'a tuer, 952 K : « Une vieille dame écrit le nom de son meurtrier avant de mourir » / « Omar, son jardinier, est jugé coupable, pourtant aucune preuve ne prouve sa culpabilité »
- Prisoners, 895 K : « Et si ton enfant disparaissait… et que le seul suspect était intouchable » / « Jusqu'où irais-tu pour le faire parler ? »
- Au nom de ma fille, 823 K : « Un père laisse sa fille partir en vacances chez une copine » / « Elle se fait t*er, son père accuse le père de sa copine mais personne ne le croit »
- Goodnight Mommy, 647 K : « En rentrant, 2 jumeaux se rendent compte que leur mère a le visage bandé » / « Plus le temps passe, plus ils doutent de l'identité de cette femme »
- Carry-On, 361 K : « Un agent de sécurité à l'aéroport trouve une oreillette à côté d'une valise » / « Pour sauver sa petite amie, il va devoir faire tout ce que lui dit la voix »
- The Rental, 394 K : « Un couple loue un airbnb dans une maison isolée » / « Très vite, ils se rendent compte que la maison est truffée de caméras »

B) Idées à reprendre d'un très grand compte du même concept (@alorsonregardequoi, jusqu'à 2,7 M de vues) : des détails encore plus concrets, des phrases coupées qui obligent à swiper.
- « la nuit tombe, alors le chef d'une station de ski décide d'arrêter les télésièges pendant 1 semaine, mais… » / « sans le savoir, il oublie 3 amis, suspendus en hauteur, la nuit dans le froid… »
- « une femme se retrouve seule sur une surface glissante avec un trou sans fin… » / « un mouvement de travers, elle tombe… elle bouge, elle tombe… » (le même film reste à 309 K quand le texte dit seulement « dans cette position » : le détail concret gagne)
- « un homme assiste à un procès pour m*urtre en tant que membre du jury » / « mais, en écoutant les preuves, il comprend qu'il est lui-même responsable du crime »

C) ACCROCHE « IMAGINE… » (pour que le lecteur se sente concerné ; à utiliser quand l'occasion s'y prête) :
- « Imagine que ton frère t'enferme dans sa cave pour 3 jours » / « Alors que ta famille te cherche, tu entends ses pas au-dessus de toi »
- « Imagine que tu es père et que ta fille de 6 ans a disparu au supermarché » / « Le seul suspect est le voisin que tout le monde adore »
- « Imagine ta mère qui change de visage du jour au lendemain » / « Plus le temps passe, plus tu doutes que ce soit vraiment elle »
- « Imagine que tu es juré dans un procès pour m*urtre » / « Mais en écoutant les preuves, tu comprends que le coupable, c'est toi »
Règles de l'accroche « Imagine » : elle ouvre la slide 1 (« Imagine que tu es… » ou « Imagine ton frère / ta mère / ton père / ta meilleure amie… »), suivie d'un FAIT CHOQUANT et concret du synopsis, jamais flou ; la slide 2 enchaîne au tutoiement ou à la 3e personne ; elle n'est pas une question. À utiliser dans environ 1 carrousel sur 3, uniquement quand le synopsis s'y prête (un proche, un enfant, une situation du quotidien qu'on peut se représenter). Pour une histoire lointaine ou fantastique, ne la force pas.

CE QUI FAIT LA DIFFÉRENCE (à reproduire) :
- UNE phrase par slide, 7 à 12 mots (environ 10), en langage parlé, peu de virgules. Parfois une seule phrase coupée sur deux slides : la slide 1 est une proposition incomplète (« Après une dispute dans les bouchons », « Alors que… ») que la slide 2 termine.
- La slide 1 met UNE PERSONNE DANS UNE SITUATION du quotidien (un père, une famille, un couple, un agent de sécurité), au présent. Elle ne commence JAMAIS par un décor ou un contexte (« Dans un monde où… », « En pleine apocalypse », « Alors qu'un tueur rôde en Amérique ») : le vrai hook doit être dans la slide 1.
- Variantes qui marchent : l'inversion dès la slide 1 (le héros est en réalité le méchant : « Ce t*eur en série se rend à un concert avec sa fille »), le tutoiement « Et si ton… » (rarement), une phrase coupée par « mais… » ou « alors… ».
- La MENACE VIENT DU CERCLE FAMILIER OU FAMILIER : un père, une mère qui n'est peut-être pas la mère, un enfant qui enferme sa famille, un logement loué. Pas un décor lointain.
- La slide 2 montre la PRISE DE CONSCIENCE ou le retournement, jamais la fin : « se rend compte que… », « très vite… », « plus le temps passe, plus… », « il va devoir… ». Le meilleur : un retournement ou une ironie (le concert entier est un piège, le juré est le coupable).
- Un sentiment d'INJUSTICE ou un dilemme moral fait réagir (on accuse le mauvais coupable, personne ne le croit, jusqu'où irait-on).
- Détails utiles : un chiffre (13 ans, 2 jumeaux, 30 000 spectateurs, 1 semaine), un lieu clos du quotidien (airbnb, tunnel, aéroport, vacances), un objet qui déclenche l'intrigue (oreillette, valise, visage bandé, caméras), un lien familial (père, fille, mère, jumeaux).
- Mots sensibles TOUJOURS masqués par un astérisque : t*eur, t*er, vi*ler, dr*guer, m*urtre, s*icide, m*rt.
- Aucun jugement (« incroyable », « impossible de lâcher »), pas de point d'exclamation, pas d'emoji.

CE QUI MARCHE MOINS (à éviter) : une slide 1 qui commence par un décor (« Alors qu'un t*eur rôde en Amérique ») ; une menace lointaine ou fantastique (apocalypse, dystopie, western, cimetière, monstres la nuit) ; une slide 2 qui EXPLIQUE au lieu de retourner (« en effet… », « le chemin va être périlleux ») ; une slide 2 vague (« leurs vacances tournent au drame ») ; un texte vague au lieu d'un détail précis (« dans cette position »).

STRUCTURES RÉUTILISABLES (varie) :
1. Proposition coupée : « Après [événement banal]… » puis « [Personnage] se rend compte que [menace] »
2. Méchant en héros : « Ce [rôle inquiétant] fait [activité familiale banale] avec [proche] »
3. Découverte + chiffre : « Un [enfant] de [N] ans découvre [lieu ou objet] près de chez lui »
4. Prise de conscience progressive : « Plus le temps passe, plus [ils] doutent de [chose ou personne] »
5. Objet déclencheur : « [Métier] trouve [petit objet] à côté de [lieu] » puis « Pour sauver [proche], il va devoir [obéir / faire] »
6. Injustice : « [Personne] est accusé(e), pourtant [aucune preuve / personne ne la croit] »
7. Cadre idyllique qui bascule : « Un couple loue [logement] [isolé] » puis « Très vite, ils se rendent compte que [détail inquiétant] »
8. Chiffre repris : la slide 1 pose un nombre, la slide 2 le reprend (« et parmi ces 30 000, il y a… »)
9. Imagine : « Imagine ton frère / Imagine que tu es [situation choquante et concrète] » puis la conséquence qui laisse une zone d'ombre
"""

def oral(t):
    """Met la phrase au style oral : points de suspension propres, minuscule au début, pas de point final."""
    t = re.sub(r"\.{3,}", "…", t.strip())
    if not STYLE_ORAL:
        return t
    t = t.rstrip(". ")
    if len(t) > 1 and t[0].isupper() and t[1].islower():
        t = t[0].lower() + t[1:]
    return t

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
Écris un carrousel TikTok de 2 OU 3 slides (une phrase chacune). Le nombre de slides dépend de l'intrigue :
- 2 slides si l'histoire tient en deux coups (situation + retournement). C'est souvent le mieux : DEUX slides bien faites valent mieux que TROIS moyennes. Ne rajoute JAMAIS une 3e slide pour remplir.
- 3 slides seulement si la 3e apporte un vrai coup de plus (un enjeu, un choix impossible, un détail glaçant). Sinon, 2.
Le but : stopper le scroll dès la slide 1, puis finir sur une ÉMOTION FORTE qui donne envie de savoir la suite. La dernière slide doit laisser le lecteur avec : de la PEUR, de la TRISTESSE, de la SURPRISE, ou une CURIOSITÉ qui brûle (une question qu'il ne peut pas laisser sans réponse). Jamais de conclusion tiède, jamais d'explication, jamais de morale. On s'arrête juste avant la réponse.
- slide 1 : UNE PERSONNE dans une situation du quotidien, avec le vrai hook dès cette slide (ou l'inversion : le héros est en fait le méchant) ;
- slide 2 (ou 3 s'il y en a 3) : le coup qui fait mal ou qui surprend, le fait précis qui glace ou qui serre la gorge, jamais la fin.

STYLE DES MOTS (très important) :
- Les mots les plus SIMPLES, courts et durs, comme on parle à un ami. Jamais de mot soutenu ou littéraire : écris « inutile » (pas « désuet »), « peur » (pas « appréhension »), « tuer » (masqué : t*er), « piège » (pas « stratagème »), « mentir » (pas « dissimuler »), « se rend compte » (pas « prend conscience »), « riche » (pas « fortuné »), « cacher » (pas « dissimuler »).
- Phrases COURTES : 6 à 11 mots. On coupe tout ce qui ne sert pas. Un fait, un détail précis, c'est tout.
- ZÉRO phrase bateau : pas de « tout bascule », « rien ne sera plus comme avant », « un secret terrible », « une histoire incroyable », « un destin hors du commun ». Si la phrase pourrait s'appliquer à 10 autres films, elle est mauvaise : remplace-la par un fait précis (chiffre, objet, lien familial, lieu).
- N'hésite pas à employer des mots forts et directs (tuer, mourir, enfermer, disparaître, mentir, trahir), masqués par un astérisque quand ils sont sensibles.

ÉTAPE 0, L'INTRIGUE (la plus importante, à faire avant d'écrire) : avant toute phrase, identifie ce qui rend cette œuvre EXTRAORDINAIRE et pousse la curiosité : le fait singulier, le contraste ou le destin hors norme qu'on ne voit pas ailleurs (ex. pour un film : un homme moqué pour sa bêtise qui devient, grâce à un don unique, une star nationale). Ce n'est PAS le simple résumé ni le point de départ banal : c'est le « comment est-ce possible ? » qui donne envie de voir. Remplis "intrigue_principale" (ce qui fait l'œuvre), "element_extraordinaire" (le fait le plus percutant, concret) et "question_curiosite" (la question que le lecteur se pose). Les 3 slides doivent TOUTES jouer sur cet élément : slide 1 = la personne + le contraste de départ, slide 2 = le fait extraordinaire qui intrigue, slide 3 = l'enjeu ou ce qui reste inexpliqué. N'écris jamais une slide sur un détail secondaire. Tu peux t'appuyer sur ta connaissance de l'œuvre pour repérer cet élément si tu en es certain ; sinon reste fidèle au synopsis.

MÉTHODE (c'est ce qui décide de la qualité) :
1. "brouillons_s1" : 6 versions DIFFÉRENTES de la slide 1 : (a) une personne + une situation du quotidien (airbnb, vacances, trajet, concert, travail), (b) l'inversion : le héros est en réalité le méchant ou le piège est pour lui, (c) la menace vient d'un proche (père, mère, enfant, voisin), (d) une proposition coupée (« Après… », « Alors que… ») que la slide 2 terminera, (e) une injustice, (f) un objet ou un fait chiffré qui déclenche l'intrigue, (g) si le synopsis s'y prête, une accroche « Imagine ton frère… » ou « Imagine que tu es… » suivie d'un fait choquant et concret.
2. "brouillons_s2" : 5 versions de la slide 2 : (a) la prise de conscience (« se rend compte que… »), (b) un retournement ou une ironie, (c) « plus le temps passe, plus… » ou « très vite… », (d) « il va devoir… », (e) l'injustice (« pourtant personne ne le croit »). Toutes basées sur un FAIT PRÉCIS du synopsis, qui laissent volontairement une zone d'ombre.
3. Garde pour chaque slide la plus concrète, la plus choquante et la plus intrigante. Si la version (g) « Imagine… » est la plus forte pour cette œuvre (et que ce n'est pas forcé), prends-la.
Test final pour chaque phrase : (1) peut-on la coller telle quelle sur un autre film ? Alors elle est trop vague, recommence. (2) la slide 1 commence-t-elle par un décor ou un contexte (« Dans un monde… », « En pleine… ») ? Réécris-la avec une personne. (3) contient-elle un jugement ou une conclusion ? Supprime-le. (4) donne-t-elle envie de connaître la suite ? Sinon, recommence.
INTERDIT : « quelque chose cloche », « tout bascule », « personne ne s'y attend », « tu vas adorer », « d'un côté… de l'autre », « impossible de lâcher », « leurs vacances tournent au drame » et autres formules vagues, les points d'exclamation, les emojis, les superlatifs vides, un nom d'acteur. Une question n'est autorisée qu'en slide 2 (« Jusqu'où irais-tu… ? »), jamais en slide 1 ni 3.

RÈGLE SPOILER : tu peux raconter le point de départ et la première grande bascule de l'histoire (ce que dirait le résumé au dos du film), mais JAMAIS le retournement final, la fin, qui meurt à la fin, ni l'identité d'un personnage caché.
Reste fidèle au synopsis fourni : n'invente aucun fait.

Ajoute 6 hashtags : #film (ou #serie), #cinema, #quoiregarder, un hashtag du genre (#thriller, #suspense, #horreur, #psychologique…), le hashtag du titre (sans espaces ni accents) et un hashtag lié à l'intrigue.
Mets nb_slides à 2 ou 3 ; si nb_slides = 2, laisse s3 vide.
JSON : {{"intrigue_principale":"","element_extraordinaire":"","question_curiosite":"","brouillons_s1":["","","","","",""],"brouillons_s2":["","","","",""],"emotion_finale":"peur|tristesse|surprise|curiosité","nb_slides":2,"s1":"","s2":"","s3":"","hashtags":["#..."],"spoiler_risk":false}}
Mets spoiler_risk à true seulement si une phrase révèle la fin ou un retournement."""
    note = ""
    for _ in range(3):
        r = as_dict(ask_json(base + note, max_tokens=3000))
        s = [str(r.get("s1", "")).strip(), str(r.get("s2", "")).strip(), str(r.get("s3", "")).strip()]
        if not s[2] or int(r.get("nb_slides") or 3) == 2: s = s[:2]
        problems = []
        if any(not x.strip() for x in s): problems.append("une slide est vide")
        if any(len(x.split()) > 12 for x in s): problems.append("une phrase dépasse 11 mots : raccourcis, garde seulement le fait choquant")
        if r.get("spoiler_risk"): problems.append("risque de spoiler sur la fin ou un retournement")
        if len(set(s)) < len(s): problems.append("phrases identiques")
        if any("?" in x for x in s[:-1]) or (len(s) == 3 and "?" in s[0]): problems.append("une question hors dernière slide")
        if any("!" in x for x in s): problems.append("une phrase contient un point d'exclamation")
        hard = [w for x in s for w in re.findall(r"[A-Za-zÀ-ÿ'-]+", x) if len(w) >= 13 or re.fullmatch(r"(?i)d[ée]su[eè]t[es]*|stratag[èe]mes?|dissimul\w*|appr[ée]hension|incontournables?|insoutenables?|tumultueu\w+|fallacieu\w+|machiav[ée]li\w+|inextricables?|inexorables?|ind[ée]niables?|abyssal\w*|vertigineu\w+", w)]
        if hard: problems.append("mots trop soutenus ou trop longs (" + ", ".join(sorted(set(hard))) + ") : remplace-les par des mots simples et courts")
        vague = re.compile(r"impossible de (le |la |les |s'en )?(l[âa]cher|quitter|d[ée]crocher)|d'un c[ôo]t[ée]|de l'autre|tout (bascule|change)|rien ne sera plus|plus jamais comme|quelque chose cloche|personne ne s'y attend|tu vas adorer|tournent? au drame", re.I)
        if re.match(r"(?i)^(dans un (monde|futur|univers)|en pleine|dans un pays|dans une soci[ée]t[ée])", s[0].strip()): problems.append("la slide 1 commence par un décor : commence par une personne dans une situation")
        bad = [x for x in s if vague.search(x)]
        if bad: problems.append("formule vague ou conclusion interdite dans : " + " / ".join(bad) + " (raconte un fait précis à la place)")
        if avoid and oral(s[0]) in [x.strip() for x in avoid]: problems.append("la slide 1 reprend un texte refusé")
        if not problems:
            tags = r.get("hashtags", [])
            tags = [t if t.startswith("#") else "#" + t for t in tags]
            return {"texts": [oral(x) for x in s], "caption": "", "hashtags": " ".join(tags)}
        note = "\n\nCorrige ce problème : " + ", ".join(problems) + "."
    raise RuntimeError("Impossible d'obtenir des textes valides")

def _penalty(b):
    """Pénalité pour une image sombre ou floue (mesurée avec Pillow, indépendante de l'IA)."""
    try:
        from PIL import Image, ImageFilter, ImageStat
        im = Image.open(io.BytesIO(b)).convert("L")
        lum = ImageStat.Stat(im).mean[0]
        sharp = ImageStat.Stat(im.filter(ImageFilter.FIND_EDGES)).var[0]
        p = max(0.0, (75 - lum) / 8)             # sombre : jusqu'à -9 si presque noire
        if sharp < 60: p += 2                    # floue
        return p
    except Exception:
        return 0.0

def rewrite_slide(meta, texts, n, instruction):
    """Réécrit UNE seule slide (n = 1, 2 ou 3) selon la demande, en gardant les deux autres."""
    kind = "série" if meta["type"] == "tv" else "film"
    prompt = f"""Œuvre : {meta['title']} ({meta['year']}), {kind}. Synopsis : {meta['overview']}
Carrousel actuel :
{chr(10).join(f"{k+1}. {t}" for k, t in enumerate(texts))}

Réécris UNIQUEMENT la slide {n}. Demande de la rédactrice : « {instruction or 'propose une autre version plus percutante'} ».
- Si sa demande est déjà une phrase complète prête à afficher (entre guillemets ou clairement rédigée), reprends-la presque telle quelle (corrige seulement les fautes).
- Sinon, applique sa consigne (ton, angle, élément à mettre en avant).
- 6 à 11 mots, une seule phrase, mots très simples et courts (jamais de mot soutenu), aucune phrase bateau, en cohérence avec les deux autres slides (la suite doit rester logique), sans spoiler la fin, sans emoji, sans point d'exclamation. Mots sensibles masqués par un astérisque (t*er, m*urtre…).
- Ne reprends pas la version actuelle.
JSON : {{"texte":""}}"""
    for _ in range(3):
        r = as_dict(ask_json(prompt, max_tokens=400))
        t = oral(str(r.get("texte", "")).strip().strip('"«» '))
        if t and t != texts[n - 1] and len(t.split()) <= 13:
            return t
        prompt += "\n\nPropose une phrase différente de l'actuelle et de 12 mots maximum."
    raise RuntimeError("Impossible de réécrire cette slide")

def pick_images(meta, thumbs):
    """Chaque image reçoit une note de CHOC ; on prend les 3 meilleures, la plus choquante en slide 1."""
    prompt = f"""Voici {len(thumbs)} images du {'film' if meta['type']=='movie' else 'la série'} « {meta['title']} ».
Note CHAQUE image pour un carrousel TikTok vertical. Le but n'est pas d'illustrer un texte : c'est d'ARRÊTER LE SCROLL.
- choc (0 à 10) : intensité émotionnelle ou visuelle. 9-10 = visage en gros plan avec peur, colère, larmes, regard glaçant ou tension extrême, ou image spectaculaire et immédiatement compréhensible. 5-6 = plan correct mais neutre. 0-3 = plan large, personnages minuscules, scène calme, décor vide, foule.
- lisible (0 à 10) : un sujet principal net, grand, plutôt dans la moitié haute de l'image, BIEN ÉCLAIRÉ et lumineux (une image sombre où l'on distingue mal le visage vaut moins de 4), couleurs contrastées.
- texte (true/false) : vrai s'il y a un texte, un logo ou un sous-titre visible.
- spoil (true/false) : vrai si l'image montre la fin, une mort décisive ou un retournement.
- groupe : un entier ; donne le MÊME entier aux images quasi identiques (même scène, même plan).
- focus_x : position horizontale du visage ou du sujet principal (0 = bord gauche, 1 = bord droit).
Sois sévère : peu d'images méritent plus de 7.
JSON : [{{"image":1,"choc":0,"lisible":0,"texte":false,"spoil":false,"groupe":1,"focus_x":0.5}}, ...] (une entrée par image)"""
    r = ask_json(prompt, images=thumbs, max_tokens=3500)
    if isinstance(r, dict):
        r = next((v for v in r.values() if isinstance(v, list)), [])
    while r and isinstance(r, list) and isinstance(r[0], list):
        r = r[0]
    rows = []
    for x in (r if isinstance(r, list) else []):
        try:
            if not isinstance(x, dict): continue
            idx = int(x["image"]) - 1
            if not 0 <= idx < len(thumbs): continue
            score = float(x.get("choc", 0)) * 0.7 + float(x.get("lisible", 0)) * 0.3
            if x.get("texte"): score -= 4
            if x.get("spoil"): score -= 6
            rows.append({"idx": idx, "score": score, "groupe": x.get("groupe", idx), "focus": min(max(float(x.get("focus_x", 0.5)), 0.0), 1.0)})
        except Exception:
            continue
    for z in rows:                                   # pénalités mesurées : image trop sombre ou floue
        z["score"] -= _penalty(thumbs[z["idx"]])
    rows.sort(key=lambda z: z["score"], reverse=True)
    out, used, groups = [], set(), set()
    for z in rows:                                   # d'abord : 3 images de scènes différentes
        if z["idx"] in used or z["groupe"] in groups: continue
        out.append({"idx": z["idx"], "focus": z["focus"]}); used.add(z["idx"]); groups.add(z["groupe"])
        if len(out) == 3: break
    for z in rows:                                   # si besoin : on complète
        if len(out) == 3: break
        if z["idx"] not in used:
            out.append({"idx": z["idx"], "focus": z["focus"]}); used.add(z["idx"])
    for k in range(len(thumbs)):                     # dernier recours
        if len(out) == 3: break
        if k not in used:
            out.append({"idx": k, "focus": 0.5}); used.add(k)
    return out

def extract_title(message):
    r = as_dict(ask_json(f'Message : « {message} »\nQuel film ou quelle série la personne demande-t-elle ? JSON : {{"titre":"","annee":null}} (titre vide si ce n\'est pas une demande de film/série).', model=MODEL_FAST, max_tokens=200))
    return (r.get("titre") or "").strip(), r.get("annee")