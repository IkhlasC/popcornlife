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

def as_list(r):
    """Renvoie toujours une liste d'objets, même si l'IA a enveloppé la liste dans un objet ou renvoyé du texte."""
    if isinstance(r, dict):
        r = next((v for v in r.values() if isinstance(v, list)), [r] if "ref" in r else [])
    return [x for x in r if isinstance(x, dict)] if isinstance(r, list) else []

def propose(pool):
    lines = "\n".join(f'{p["type"]}:{p["id"]} | {p["title"]} ({p["year"]}) | note {p["rating"]} | {", ".join(p["genres"])} | {p["overview"][:220]}' for p in pool)
    prompt = f"""Voici une liste d'œuvres disponibles en streaming en France :
{lines}

Choisis les 3 œuvres qui vont FAIRE LE PLUS RÉAGIR sur TikTok, c'est-à-dire celles dont une seule phrase provoque une émotion forte (peur, choc, indignation, « c'est quoi ce film ? », « je dois le voir »). Note chaque œuvre de 1 à 10 sur son potentiel de réaction (score_reaction) et ne garde que les 3 meilleures scores, classées de la plus forte à la moins forte. Ne retiens qu'une œuvre à plus de 7 si tu peux la défendre avec une phrase choc ; refuse les œuvres tièdes même si elles sont bien notées.
Ce qui fait le plus réagir : une MENACE VENUE DU CERCLE FAMILIER (un père, une mère, un frère, un enfant, un proche qui n'est pas ce qu'il semble), une INJUSTICE ou un dilemme moral (jusqu'où irais-tu ?), un enfant ou un proche en danger, un piège dans un lieu du quotidien (airbnb, concert, tunnel, aéroport, vacances en famille), un retournement, une situation où le lecteur se dit « et si c'était moi ? ». Privilégie les œuvres où le lecteur peut se mettre à la place d'un personnage.
Varie (pas 3 films du même genre ; 1 série maximum ; varie les pays si possible), privilégie les sorties récentes et les films de découverte plutôt que les blockbusters vus partout. Évite les décors lointains ou fantastiques (apocalypse, western, dystopie, monstres), les clichés de genre (cimetière, village maudit) et les concepts qu'il faut expliquer.
Pour chacune : un angle éditorial, une idée de hook (une phrase), et pourquoi ça peut faire réagir sur TikTok (une phrase).
JSON : [{{"ref":"movie:123","score_reaction":8,"angle":"","hook":"","pourquoi":""}}, ...]"""
    out = as_list(ask_json(prompt, max_tokens=3000))
    out.sort(key=lambda c: -float(c.get("score_reaction", 0) or 0) if str(c.get("score_reaction", "0")).replace(".", "").isdigit() else 0)
    return out

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

B) Idées d'un très grand compte du même concept (@alorsonregardequoi, jusqu'à 2,7 M de vues) : phrases coupées qui obligent à swiper, MAIS seulement quand ce qui est coupé est CONCRET. Une phrase coupée vague échoue (leur version de Carry-On : « sous la menace d'un passager mystérieux… / forcé de laisser passer une valise dangereuse » = 15 200 vues ; celle de la rédactrice, avec l'oreillette et la petite amie en danger = 361 000).
- « la nuit tombe, alors le chef d'une station de ski décide d'arrêter les télésièges pendant 1 semaine, mais… » / « sans le savoir, il oublie 3 amis, suspendus en hauteur, la nuit dans le froid… » (2,7 M)
- « imaginez louer un airbnb, et vous trouvez un sous-sol caché… » (2,6 M) : un lieu du quotidien + un objet précis
- « un homme assiste à un procès pour m*urtre en tant que membre du jury » / « mais, en écoutant les preuves, il comprend qu'il est lui-même responsable du crime » (2,3 M)
- « une femme se retrouve seule sur une surface glissante avec un trou sans fin… » / « un mouvement de travers, elle tombe… elle bouge, elle tombe… »

CE QUE MONTRENT LES VRAIES STATISTIQUES (467 publications relevées) :
- Les textes de la rédactrice qui ont le plus marché (3,3 M, 2,1 M, 950 K, 895 K, 823 K) ont presque tous 2 slides de texte : un fait de la vie de tous les jours qui dérape, puis un RETOURNEMENT net ou une INJUSTICE. Trois slides marchent aussi (From, 747 K) quand chaque slide apporte un fait nouveau. Jamais plus de 3 slides de texte.
- Un CHIFFRE ou un OBJET précis dans la slide 1 aide (médiane x1,5 à x1,8) : 13 ans, 30 000 spectateurs, 2h17, une oreillette, un bunker.
- La slide 2 qui commence par « Très vite… », « Plus le temps passe… », « Il se rend compte que… » ou « Mais… » fait presque 2 fois mieux.
- Mettre le lecteur dans la situation (« Imagine… ») marche SEULEMENT avec un danger précis et un lieu du quotidien (un airbnb, un concert, la chambre de ton enfant). « Imagine que tu es piégé dans un couloir sans fin » est trop vague, « Imagine que ton mari est retrouvé m*rt dans la neige » aussi.
- Les mots génériques sont mauvais : « cauchemar », « mystérieux », « tout bascule », « quelque chose cloche ». Les mots concrets sont bons : un objet, un lieu, un chiffre, un lien familial.
- Les commentaires explosent avec : une injustice (« personne ne le croit »), une question morale qui donne envie de répondre « moi à sa place je… » (« Jusqu'où irais-tu ? », « qui mérite de survivre ? »), ou une zone d'ombre qui pousse à demander « pourquoi ? ». Termine donc sur un dilemme, une injustice ou un détail qui demande une explication.

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

REFERENCES_REDACTRICE = [
    ("À l'ouest, rien de nouveau",
     ["Un jeune soldat allemand part au front avec ses camarades, euphorique", "Mais au fond des tranchées, ils ne se battent plus que pour survivre"],
     ["Cet adolescent a menti à ses parents pour pouvoir partir à la guerre avec ses copains", "Il pensait qu'ils allaient tous s'amuser pendant quelques semaines avant de gagner la guerre...", "L'histoire en a décidé autrement"]),
    ("Reconnu coupable",
     ["Un détective accusé d'avoir t*é sa femme est jugé par une IA", "Ce tribunal expéditif, c'est lui qui a grandement aidé à le créer", "Il a 90 minutes pour se défendre sinon l'IA le condamne à m*rt"],
     ["Un homme accusé d'avoir t*é sa femme est jugé par une IA.", "C'est lui qui a créé ce tribunal.", "Il a 90 minutes pour se défendre, sinon l'IA le t*e."]),
    ("Si tu m'écoutes",
     ["Imagine que tu envoies tes confessions en vocal à ta sœur décédée", "Mais ses vocaux finissent chez un inconnu, qui tombe sous son charme"],
     ["Imagine que ta sœur est morte. Mais elle te manque tellement que tu continues de lui laisser des messages vocaux.", "Le truc, c'est que maintenant, ils arrivent sur le répondeur d'un inconnu", "Par curiosité, il écoute tous tes messages et tombe amoureux de toi.", "Il force carrément le destin et décide de te rencontrer sans te dire qui il est."]),
    ("Nobody",
     ["Un père ne réagit pas quand deux cambrioleurs entrent chez lui", "Son fils le prend pour un lâche, mais lui sait t*er"],
     ["Cet homme ne réagit pas quand deux cambrioleurs rentrent chez lui.", "Du coup, son fils le prend pour un lâche.", "Il ne sait pas que son père est un a*sassin redoutable."]),
    ("Exit 8",
     ["Imagine que tu es piégé dans un couloir de métro sans fin", "Si tu rates une seule anomalie, tu reviens au point de départ"],
     ["Imagine que tu prends le métro, mais après quelques minutes, tu te rends compte que la station est vide.", "Tu te rends compte que tu es dans un jeu. Et qu'à chaque intersection, il faut faire un choix.", "Si tu te trompes, tu reviens au point de départ."]),
    ("Nuremberg",
     ["Un psychiatre américain doit examiner 22 nazis avant leur procès", "Mais Göring, le plus haut gradé, joue au chat et à la souris"],
     ["Imagine que tu dois examiner psychologiquement le bras droit d'Hitler avant son procès.", "Mais tu te rends compte que psychologiquement, il est tout à fait normal.", "Tu te demandes s'il mérite vraiment la peine de mort."]),
    ("Trap (3,3 M de vues)",
     ["Un père emmène sa fille ado à un concert avec 30 000 spectateurs", "Ils se rendent compte que 300 policiers traquent 1 t*eur en série"],
     ["Ce t*eur en série se rend à un concert avec sa fille", "Il se rend compte que le concert tout entier est un piège pour lui"]),
    ("Le Monde de John (2,1 M de vues ; elle préfère sa version)",
     ["Imagine que ton frère de 13 ans dr*gue toute ta famille", "Puis il vous laisse tomber dans un bunker découvert chez vous, sans explication"],
     ["Un garçon de 13 ans découvre un bunker à côté de sa maison", "Il décide de dr*guer toute sa famille et les enferme dedans"]),
    ("Omar m'a tuer (952 K de vues)",
     ["Imagine que ta patronne est retrouvée morte avec ton nom écrit en sang", "Tu comprends mal le français, alors pour tout le monde tu es le coupable", "Tu sors 7 ans plus tard, gracié, mais toujours coupable pour la justice"],
     ["Une vieille dame écrit le nom de son meurtrier avant de mourir", "Omar, son jardinier, est jugé coupable, pourtant aucune preuve ne prouve sa culpabilité"]),
    ("Carry-On (361 K de vues)",
     ["La veille de Noël, un agent de sécurité est forcé par un inconnu…", "de laisser passer un objet dangereux, alors qu'il court pour l'arrêter"],
     ["Un agent de sécurité à l'aéroport trouve une oreillette à côté d'une valise", "Pour sauver sa petite amie, il va devoir faire tout ce que lui dit la voix"]),
    ("Gone Girl",
     ["Le jour de leurs 5 ans de mariage, sa femme disparaît", "Tout l'accuse, alors il enquête et découvre qu'elle lui cachait beaucoup de choses"],
     ["Une femme disparaît dans d'étranges circonstances et son mari est le suspect n°1", "Il n'imagine pas le vaste piège qui va se refermer sur lui"]),
    ("Speak No Evil",
     ["Imagine que tu passes le week-end chez une famille rencontrée en vacances", "Leur maison est parfaite, mais très vite le week-end devient un cauchemar"],
     ["2 couples d'inconnus sympathisent et l'un invite l'autre pour le week-end", "Pendant le week-end les hôtes commencent à être très malséants"]),
    ("Downsizing (241 K de vues)",
     ["Pour fuir son stress à Omaha, Paul accepte de mesurer 12 cm", "Sa femme et lui quittent tout, convaincus d'avoir une vie meilleure"],
     ["Il voulait une meilleure vie… il ne savait pas ce qui l'attendait", "Il décide de se faire rétrécir pour faire 12 cm"]),
    ("Évanouis",
     None,
     ["Imagine que tu te lèves et que tu te rends compte que ton enfant de 8 ans n'est plus dans son lit.", "Quand tu regardes les caméras, tu te rends compte qu'il s'est enfui en courant à 2h17.", "Et la police t'annonce que tous les enfants de sa classe ont fait exactement la même chose à la même heure."]),
]

def references_block():
    """Les textes que la rédactrice aurait écrits à la place du bot : c'est sa vraie voix (à imiter dans le rythme, pas à recopier)."""
    out = ["\nTEXTES DE RÉFÉRENCE DE LA RÉDACTRICE (PRIORITÉ MAXIMALE : c'est EXACTEMENT ce qu'elle veut. Pour certains films, tu vois ce que le bot avait écrit (À ÉVITER) puis sa version (À IMITER). Observe la différence et reproduis-la : "
           "le fait précis et un peu choquant dès la slide 1 (il a MENTI à ses parents, il ne réagit PAS, ta sœur est MORTE), une seule information nouvelle par slide, des liens parlés (« Du coup », « Le truc, c'est que », « Par curiosité », « Quand tu regardes… »), "
           "des détails chiffrés (2h17, 8 ans, 90 minutes), souvent le « tu » du début à la fin, et une DERNIÈRE SLIDE qui touche (menace, ironie, dilemme moral ou conséquence) au lieu d'expliquer) :"]
    for film, bot, her in REFERENCES_REDACTRICE:
        out.append(f"* {film}")
        if bot: out.append("   ❌ bot : " + " / ".join(bot))
        out.append("   ✅ elle : " + " / ".join(her))
    return "\n".join(out) + "\n"

def corrections_block(limit=8):
    """Les corrections que la rédactrice a faites elle-même (« slide 2 : sa phrase ») : ce sont ses meilleurs exemples."""
    try:
        with open("data/corrections.json", encoding="utf-8") as f: items = json.load(f)
    except Exception:
        return ""
    items = [c for c in items if c.get("avant") and c.get("apres")][-limit:]
    if not items: return ""
    lines = [f"- {c.get('film','?')} : le bot avait écrit « {c['avant']} » → elle a écrit « {c['apres']} »" for c in items]
    return ("\nCORRECTIONS DE LA RÉDACTRICE (PRIORITÉ MAXIMALE : elle a réécrit elle-même ces phrases, c'est EXACTEMENT sa voix. Compare l'avant et l'après : "
            "longueur, choix des mots, fait concret, ordre de l'information, façon de couper la phrase. Applique la même différence à ta nouvelle écriture, sans recopier) :\n" + "\n".join(lines) + "\n")

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
{references_block()}{corrections_block()}
Écris un carrousel TikTok de 2 OU 3 slides (une phrase chacune). Le nombre de slides dépend de l'intrigue :
- 2 slides si l'histoire tient en deux coups (situation + retournement). C'est souvent le mieux : DEUX slides bien faites valent mieux que TROIS moyennes. Ne rajoute JAMAIS une 3e slide pour remplir.
- 3 slides seulement si la 3e apporte un vrai coup de plus (un enjeu, un choix impossible, un détail glaçant). Sinon, 2.
Le but : stopper le scroll dès la slide 1, puis finir sur une ÉMOTION FORTE qui donne envie de savoir la suite. La dernière slide doit laisser le lecteur avec : de la PEUR, de la TRISTESSE, de la SURPRISE, ou une CURIOSITÉ qui brûle (une question qu'il ne peut pas laisser sans réponse). Jamais de conclusion tiède, jamais d'explication, jamais de morale. On s'arrête juste avant la réponse.
- slide 1 : UNE PERSONNE dans une situation du quotidien, avec le vrai hook dès cette slide (ou l'inversion : le héros est en fait le méchant) ;
- slide 2 (ou 3 s'il y en a 3) : le coup qui fait mal ou qui surprend, le fait précis qui glace ou qui serre la gorge, jamais la fin.

STYLE DES MOTS (très important) :
- Les mots les plus SIMPLES, courts et durs, comme on parle à un ami. Jamais de mot soutenu ou littéraire : écris « inutile » (pas « désuet »), « peur » (pas « appréhension »), « tuer » (masqué : t*er), « piège » (pas « stratagème »), « mentir » (pas « dissimuler »), « se rend compte » (pas « prend conscience »), « riche » (pas « fortuné »), « cacher » (pas « dissimuler »).
- CONTEXTE D'ABORD : quelqu'un qui ne connaît PAS le film doit comprendre la situation : qui (un père, un employé…), où, et la règle ou l'enjeu. Si c'est un jeu ou un mécanisme, explique-le en quelques mots (« un jeu où il faut repérer les anomalies pour sortir d'un couloir sans fin »). Une slide trop vague (« une anomalie », « un objet magique » sans dire quoi) est mauvaise.
- HÉROS SOUS-ESTIMÉ : joue le CONTRASTE entre ce que les autres croient de lui (lâche, bête, inutile, raté) et ce qu'il est vraiment, puis le DÉCLIC (l'événement qui va tout changer : cambrioleurs, accident, menace), sans dire ce qu'il fait ensuite.
- Phrases courtes mais CLAIRES : 8 à 14 mots. Le contexte passe avant la brièveté, mais chaque mot doit servir. Coupe tout le reste.
- ZÉRO phrase bateau : pas de « tout bascule », « rien ne sera plus comme avant », « un secret terrible », « une histoire incroyable », « un destin hors du commun ». Si la phrase pourrait s'appliquer à 10 autres films, elle est mauvaise : remplace-la par un fait précis (chiffre, objet, lien familial, lieu).
- N'hésite pas à employer des mots forts et directs (tuer, mourir, enfermer, disparaître, mentir, trahir), masqués par un astérisque quand ils sont sensibles.

ÉTAPE 0, L'INTRIGUE (la plus importante, à faire avant d'écrire) : avant toute phrase, identifie ce qui rend cette œuvre EXTRAORDINAIRE et pousse la curiosité : le fait singulier, le contraste ou le destin hors norme qu'on ne voit pas ailleurs (ex. pour un film : un homme moqué pour sa bêtise qui devient, grâce à un don unique, une star nationale). Ce n'est PAS le simple résumé ni le point de départ banal : c'est le « comment est-ce possible ? » qui donne envie de voir. Remplis "contexte_cle" (ce que le lecteur doit absolument savoir pour comprendre : la règle du jeu, le lien familial, le lieu, ce que les autres pensent du héros), "intrigue_principale" (ce qui fait l'œuvre), "element_extraordinaire" (le fait le plus percutant, concret) et "question_curiosite" (la question que le lecteur se pose). Les 3 slides doivent TOUTES jouer sur cet élément : slide 1 = la personne + le contraste de départ, slide 2 = le fait extraordinaire qui intrigue, slide 3 = l'enjeu ou ce qui reste inexpliqué. N'écris jamais une slide sur un détail secondaire. Tu peux t'appuyer sur ta connaissance de l'œuvre pour repérer cet élément si tu en es certain ; sinon reste fidèle au synopsis.

MÉTHODE (c'est ce qui décide de la qualité) :
1. "brouillons_s1" : 6 versions DIFFÉRENTES de la slide 1 : (a) une personne + une situation du quotidien (airbnb, vacances, trajet, concert, travail), (b) l'inversion : le héros est en réalité le méchant ou le piège est pour lui, (c) la menace vient d'un proche (père, mère, enfant, voisin), (d) une proposition coupée (« Après… », « Alors que… ») que la slide 2 terminera, (e) une injustice, (f) un objet ou un fait chiffré qui déclenche l'intrigue, (g) si le synopsis s'y prête, une accroche « Imagine ton frère… » ou « Imagine que tu es… » suivie d'un fait choquant et concret.
2. "brouillons_s2" : 5 versions de la slide 2 : (a) la prise de conscience (« se rend compte que… »), (b) un retournement ou une ironie, (c) « plus le temps passe, plus… » ou « très vite… », (d) « il va devoir… », (e) l'injustice (« pourtant personne ne le croit »). Toutes basées sur un FAIT PRÉCIS du synopsis, qui laissent volontairement une zone d'ombre.
3. Garde pour chaque slide la plus concrète, la plus choquante et la plus intrigante. Si la version (g) « Imagine… » est la plus forte pour cette œuvre (et que ce n'est pas forcé), prends-la.
Test final pour chaque phrase : (1) peut-on la coller telle quelle sur un autre film ? Alors elle est trop vague, recommence. (2) la slide 1 commence-t-elle par un décor ou un contexte (« Dans un monde… », « En pleine… ») ? Réécris-la avec une personne. (3) contient-elle un jugement ou une conclusion ? Supprime-le. (4) donne-t-elle envie de connaître la suite ? Sinon, recommence.
INTERDIT : « quelque chose cloche », « tout bascule », « personne ne s'y attend », « tu vas adorer », « d'un côté… de l'autre », « impossible de lâcher », « leurs vacances tournent au drame » et autres formules vagues, les points d'exclamation, les emojis, les superlatifs vides, un nom d'acteur. Une question n'est autorisée qu'en slide 2 (« Jusqu'où irais-tu… ? »), jamais en slide 1 ni 3.

CE QUI DÉRANGE, À PETITES GOUTTES (règle de la rédactrice) : n'écris JAMAIS « il cache un secret », « elle cache des choses », « un secret terrible », « quelque chose de dérangeant », « un passé sombre », « un truc qu'on ne devrait pas savoir ». Ces formules ne disent rien et n'intriguent pas. À la place, NOMME le fait dérangeant, précis et concret, mais UN SEUL par slide, sans jamais révéler la fin. Exemples de la différence : « sa femme lui cachait beaucoup de choses » ❌ → « il découvre qu'elle a ouvert un compte à son nom sans le lui dire » ✅ ; « ce père a un passé sombre » ❌ → « ce père de famille tranquille a déjà t*é des hommes » ✅ ; « ce voisin si gentil cache un secret » ❌ → « ce voisin si gentil garde les clés de toutes les maisons du quartier » ✅ (ces exemples sont inventés pour montrer la méthode : ne les réutilise pas ; n'invente jamais un fait, prends le plus précis du synopsis ou de ce que tu connais avec certitude).
Chaque slide apporte UNE information nouvelle, plus dérangeante que la précédente.

RÈGLE SPOILER : tu peux raconter le point de départ et la première grande bascule de l'histoire (ce que dirait le résumé au dos du film), mais JAMAIS le retournement final, la fin, qui meurt à la fin, ni l'identité d'un personnage caché.
Reste fidèle au synopsis fourni : n'invente aucun fait.

Ajoute 6 hashtags : #film (ou #serie), #cinema, #quoiregarder, un hashtag du genre (#thriller, #suspense, #horreur, #psychologique…), le hashtag du titre (sans espaces ni accents) et un hashtag lié à l'intrigue.
Mets nb_slides à 2 ou 3 ; si nb_slides = 2, laisse s3 vide.
TEST DE COMPRÉHENSION avant de répondre : un inconnu qui ne sait rien du film comprend-il, avec tes slides seules, QUI est le héros, OÙ il est, quelle est la RÈGLE ou l'enjeu, et ce qui l'attend ? Sinon, ajoute le contexte manquant.
JSON : {{"contexte_cle":"","intrigue_principale":"","element_extraordinaire":"","question_curiosite":"","brouillons_s1":["","","","","",""],"brouillons_s2":["","","","",""],"emotion_finale":"peur|tristesse|surprise|curiosité","nb_slides":2,"s1":"","s2":"","s3":"","hashtags":["#..."],"spoiler_risk":false}}
Mets spoiler_risk à true seulement si une phrase révèle la fin ou un retournement."""
    note = ""
    for _ in range(3):
        r = as_dict(ask_json(base + note, max_tokens=3000))
        s = [str(r.get("s1", "")).strip(), str(r.get("s2", "")).strip(), str(r.get("s3", "")).strip()]
        if not s[2] or int(r.get("nb_slides") or 3) == 2: s = s[:2]
        problems = []
        if any(not x.strip() for x in s): problems.append("une slide est vide")
        if any(len(x.split()) > 15 for x in s): problems.append("une phrase dépasse 14 mots : raccourcis sans perdre le contexte")
        if r.get("spoiler_risk"): problems.append("risque de spoiler sur la fin ou un retournement")
        if len(set(s)) < len(s): problems.append("phrases identiques")
        if any("?" in x for x in s[:-1]) or (len(s) == 3 and "?" in s[0]): problems.append("une question hors dernière slide")
        if any("!" in x for x in s): problems.append("une phrase contient un point d'exclamation")
        hard = [w for x in s for w in re.findall(r"[A-Za-zÀ-ÿ'-]+", x) if len(w) >= 13 or re.fullmatch(r"(?i)d[ée]su[eè]t[es]*|stratag[èe]mes?|dissimul\w*|appr[ée]hension|incontournables?|insoutenables?|tumultueu\w+|fallacieu\w+|machiav[ée]li\w+|inextricables?|inexorables?|ind[ée]niables?|abyssal\w*|vertigineu\w+", w)]
        if hard: problems.append("mots trop soutenus ou trop longs (" + ", ".join(sorted(set(hard))) + ") : remplace-les par des mots simples et courts")
        vague = re.compile(r"impossible de (le |la |les |s'en )?(l[âa]cher|quitter|d[ée]crocher)|d'un c[ôo]t[ée]|de l'autre|tout (bascule|change)|rien ne sera plus|plus jamais comme|quelque chose cloche|personne ne s'y attend|tu vas adorer|tournent? au drame", re.I)
        if re.match(r"(?i)^(dans un (monde|futur|univers)|en pleine|dans un pays|dans une soci[ée]t[ée])", s[0].strip()): problems.append("la slide 1 commence par un décor : commence par une personne dans une situation")
        secret = re.compile(r"cach(e|ent|er|ait|aient|é|ée|és|ées) (un|une|des|plein|beaucoup|quelque|tout|bien|de) ?(de )?(secrets?|choses?|trucs?|chose|dérangeant|lourd|sombre|terrible|mensonges?)|un secret (terrible|sombre|inavouable|dérangeant|lourd)|secrets? (terribles?|sombres?|inavouables?|dérangeants?)|quelque chose de (terrible|dérangeant|sombre|inquiétant|louche|étrange)|passé sombre|\bcauchemar|myst[ée]rieu[xs]e?s?\b|ne devrait pas (savoir|voir)", re.I)
        bad_s = [x for x in s if secret.search(x)]
        if bad_s: problems.append("formule floue (« cache un secret », « cauchemar », « mystérieux », « quelque chose de dérangeant ») dans : " + " / ".join(bad_s) + ". NOMME le fait précis et concret qui dérange (un objet, un geste, un chiffre), sans révéler la fin")
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
- 8 à 14 mots, une seule phrase claire pour quelqu'un qui ne connaît pas le film, mots très simples et courts (jamais de mot soutenu), aucune phrase bateau, en cohérence avec les deux autres slides (la suite doit rester logique), sans spoiler la fin, sans emoji, sans point d'exclamation. Mots sensibles masqués par un astérisque (t*er, m*urtre…).
- Ne reprends pas la version actuelle.
JSON : {{"texte":""}}"""
    for _ in range(3):
        raw = ask(prompt, max_tokens=400)
        r = parse_json(raw)
        if isinstance(r, dict) and r.get("texte"):
            t = str(r["texte"])
        else:                                          # l'IA a répondu en texte simple ou en JSON cassé : on récupère la phrase
            m = re.search(r'"texte"\s*:\s*"(.+?)"\s*[,}]', raw, re.S)
            t = m.group(1) if m else raw.strip().splitlines()[-1] if raw.strip() else ""
        t = oral(re.sub(r'^(?:texte|slide\s*\d)\s*:\s*', '', t.strip().strip('"«» ').strip(), flags=re.I).strip('"«» '))
        if t and t != texts[n - 1] and len(t.split()) <= 16:
            return t
        prompt += "\n\nPropose une phrase différente de l'actuelle et de 14 mots maximum. Réponds avec le JSON demandé."
    raise RuntimeError("Impossible de réécrire cette slide")

def pick_images(meta, thumbs, texts=None):
    """Mélange des deux méthodes : chaque image est notée sur le CHOC et sur sa COHÉRENCE avec chaque texte.
    Slide 1 = surtout le choc (c'est elle qui arrête le scroll). Slides suivantes = cohérence et choc à parts égales."""
    texts = [t for t in (texts or []) if t] or ["", "", ""]
    k = len(texts)
    liste = "\n".join(f"Slide {i+1} : « {t} »" for i, t in enumerate(texts) if t)
    prompt = f"""Voici {len(thumbs)} images du {'film' if meta['type']=='movie' else 'la série'} « {meta['title']} ».
Textes du carrousel TikTok :
{liste or '(pas encore de texte)'}
Note CHAQUE image :
- choc (0 à 10) : intensité émotionnelle ou visuelle. 9-10 = visage en gros plan avec peur, colère, larmes, regard glaçant ou tension extrême, ou image spectaculaire immédiatement compréhensible. 5-6 = plan correct mais neutre. 0-3 = plan large, personnages minuscules, scène calme, décor vide, foule.
- lisible (0 à 10) : un sujet principal net et grand, plutôt dans la moitié haute, BIEN ÉCLAIRÉ (une image sombre où l'on distingue mal le visage vaut moins de 4), couleurs contrastées.
- coherence : une liste de {k} notes (0 à 10), une par slide : à quel point l'image illustre la phrase de cette slide (le bon personnage, la situation, le lieu, l'ambiance décrits). 8-10 = on voit exactement ce que dit la phrase ; 4-6 = même univers ; 0-2 = rien à voir.
- texte (true/false) : texte, logo ou sous-titre visible.
- spoil (true/false) : montre la fin, une mort décisive ou un retournement.
- groupe : un entier ; le MÊME pour les images quasi identiques.
- focus_x : position horizontale du visage ou sujet principal (0 = gauche, 1 = droite).
Sois sévère : peu d'images méritent plus de 7.
JSON : [{{"image":1,"choc":0,"lisible":0,"coherence":{[0]*k},"texte":false,"spoil":false,"groupe":1,"focus_x":0.5}}, ...] (une entrée par image)"""
    rows = []
    for x in as_list(ask_json(prompt, images=thumbs, max_tokens=4500)):
        try:
            idx = int(x["image"]) - 1
            if not 0 <= idx < len(thumbs): continue
            coh = [float(c) for c in (x.get("coherence") or [])][:k]; coh += [5.0] * (k - len(coh))
            pen = (4 if x.get("texte") else 0) + (6 if x.get("spoil") else 0) + _penalty(thumbs[idx])
            rows.append({"idx": idx, "choc": float(x.get("choc", 0)), "lis": float(x.get("lisible", 0)), "coh": coh, "pen": pen,
                         "groupe": x.get("groupe", idx), "focus": min(max(float(x.get("focus_x", 0.5)), 0.0), 1.0)})
        except Exception:
            continue
    out, used, groups = [], set(), set()
    for s in range(k):
        w = (0.55, 0.15, 0.30) if s == 0 else (0.35, 0.15, 0.50)
        pool = [z for z in rows if z["idx"] not in used and z["groupe"] not in groups] or [z for z in rows if z["idx"] not in used]
        if not pool: break
        z = max(pool, key=lambda z: w[0] * z["choc"] + w[1] * z["lis"] + w[2] * z["coh"][s] - z["pen"])
        out.append({"idx": z["idx"], "focus": z["focus"]}); used.add(z["idx"]); groups.add(z["groupe"])
    for n in range(len(thumbs)):
        if len(out) >= k: break
        if n not in used: out.append({"idx": n, "focus": 0.5}); used.add(n)
    return out

def pick_image_hint(meta, thumbs, hint, text, exclude):
    """Choisit l'image qui correspond à la demande de la rédactrice (hors images déjà utilisées sur les autres slides)."""
    ban = ", ".join(str(i + 1) for i in exclude)
    prompt = f"""Voici {len(thumbs)} images du {'film' if meta['type']=='movie' else 'la série'} « {meta['title']} ».
La slide affiche : « {text} ».
La rédactrice veut cette image : « {hint} ».
Choisis l'image qui correspond le mieux à sa demande, tout en restant accrocheuse, nette et lumineuse. {('Interdit : les images ' + ban + ' (déjà utilisées).') if ban else ''}
focus_x : position horizontale du visage ou sujet principal (0 = gauche, 1 = droite).
JSON : {{"image":1,"focus_x":0.5}}"""
    raw = ask(prompt, images=thumbs, model=MODEL, max_tokens=300)
    r = parse_json(raw)
    try:
        if isinstance(r, list): r = next((x for x in r if isinstance(x, dict)), {})
        if isinstance(r, dict) and "image" in r:
            idx, fx = int(r["image"]) - 1, float(r.get("focus_x", 0.5))
        else:                                          # réponse en texte simple : on récupère les chiffres
            m = re.search(r'"?image"?\s*[:=]?\s*(\d+)', raw, re.I) or re.search(r"(\d+)", raw)
            f = re.search(r'focus_x"?\s*[:=]\s*([0-9.]+)', raw)
            idx, fx = int(m.group(1)) - 1, float(f.group(1)) if f else 0.5
        if not 0 <= idx < len(thumbs) or idx in exclude: raise ValueError
        return {"idx": idx, "focus": min(max(fx, 0.0), 1.0)}
    except Exception:
        return None

def route(message, texts, title):
    """Comprend une demande libre (plusieurs actions possibles, dans l'ordre) sur le dernier carrousel."""
    cur = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    prompt = f"""Un bot crée des carrousels TikTok. Dernier film traité : « {title} ». Slides de texte actuelles (la dernière slide, l'affiche, ne change pas) :
{cur}

La rédactrice écrit : « {message} »

Traduis sa demande en actions, dans l'ordre où elle les demande. Actions possibles :
- {{"action":"text","slide":N,"instruction":"...","exact":false}} : changer le texte de la slide N. Si elle DONNE elle-même la phrase à afficher (une phrase complète rédigée, avec ou sans guillemets), mets exact à true et recopie la phrase TELLE QUELLE dans instruction. Sinon instruction = sa consigne (ex. « plus dur »), ou "" si elle veut juste une autre version, et exact à false.
- {{"action":"image","slide":N,"hint":"..."}} : changer l'image de la slide N. hint = ce qu'elle veut voir (ex. « plus de gros plan sur son visage »), ou "" pour simplement une autre image.
- {{"action":"zoom","slide":N,"direction":"in"}} : agrandir l'image de la slide N (« zoom + », « zoome », « plus près », « plus gros »). direction = "in" ; "out" pour réduire (« zoom - », « dézoome », « on voit plus de décor ») ; "fill" pour qu'elle remplisse tout le cadre (« plein cadre », « plein écran », « enlève le noir ») ; "reset" pour revenir à la taille de départ.
- {{"action":"rewrite_all","instruction":"..."}} : refaire tous les textes.
- {{"action":"new_film","title":"...","year":null}} : elle demande un AUTRE film ou série (elle cite un titre différent du dernier).
- {{"action":"propositions"}} : elle veut de nouvelles idées de films.
- {{"action":"unknown"}} : tu ne comprends pas.
Règles : « la 1 », « la première », « la couverture » = slide 1. « l'image », « la photo » = image. « le texte », « la phrase », « le hook » = text. « change la slide 2 » sans précision = text ET image. Elle peut enchaîner (« change l'image 1, puis le texte 2 »). Ignore une slide qui n'existe pas. Un message qui n'est qu'un titre de film différent = new_film.
JSON : {{"actions":[...]}}"""
    r = ask_json(prompt, model=MODEL_FAST, max_tokens=600)
    acts = as_list(r.get("actions") if isinstance(r, dict) else r)
    return acts

def extract_title(message):
    r = as_dict(ask_json(f'Message : « {message} »\nQuel film ou quelle série la personne demande-t-elle ? JSON : {{"titre":"","annee":null}} (titre vide si ce n\'est pas une demande de film/série).', model=MODEL_FAST, max_tokens=200))
    return (r.get("titre") or "").strip(), r.get("annee")
