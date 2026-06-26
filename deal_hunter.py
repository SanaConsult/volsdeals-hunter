"""
VolsDeals -- Deal Hunter
Scrape les sources de deals, filtre avec Claude AI, envoie via Brevo
Met a jour index.html avec les vrais deals trouves
"""

import feedparser
import json
import requests
from datetime import datetime, timezone, timedelta
import anthropic
import os
import re
import base64

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "SanaConsult/volsdeals-hunter"
BREVO_LIST_ID = 3
TON_EMAIL = "alaouisana0@gmail.com"
USD_TO_CAD = 1.37

FEEDS = [
{"name": "Secret Flying Canada", "url": "https://www.secretflying.com/posts/category/canada/feed/"},
{"name": "Flytrippers", "url": "https://flytrippers.com/feed/"},
{"name": "Prince of Travel", "url": "https://princeoftravel.com/feed/"},
{"name": "Reddit r/airmiles", "url": "https://www.reddit.com/r/airmiles/.rss"},
{"name": "Reddit r/CanadaDeals", "url": "https://www.reddit.com/r/CanadaDeals/.rss"},
{"name": "Secret Flying", "url": "https://secretflying.com/feed/"},
{"name": "The Flight Deal", "url": "https://www.theflightdeal.com/feed/"},
{"name": "Reddit r/flightdeals", "url": "https://www.reddit.com/r/flightdeals/.rss"},
{"name": "Airfarewatchdog", "url": "https://www.airfarewatchdog.com/blog/feed/"},
{"name": "Going (Scotts Cheap)", "url": "https://going.com/guides/feed"},
{"name": "Holidaypiraten", "url": "https://www.holidaypiraten.de/feed/"},
]

# Destinations mondiales avec seuils de prix CAD depuis YUL
SEUILS = {
# Europe de l Ouest
"CDG": {"ville": "Paris", "seuil": 650, "normal": 780},
"LIS": {"ville": "Lisbonne", "seuil": 650, "normal": 800},
"BCN": {"ville": "Barcelone", "seuil": 650, "normal": 820},
"FCO": {"ville": "Rome", "seuil": 660, "normal": 830},
"ATH": {"ville": "Athenes", "seuil": 680, "normal": 850},
"AMS": {"ville": "Amsterdam", "seuil": 640, "normal": 790},
"FRA": {"ville": "Francfort", "seuil": 640, "normal": 790},
"MAD": {"ville": "Madrid", "seuil": 650, "normal": 820},
"NCE": {"ville": "Nice", "seuil": 660, "normal": 830},
"MRS": {"ville": "Marseille", "seuil": 660, "normal": 830},
"LHR": {"ville": "Londres", "seuil": 600, "normal": 750},
"LGW": {"ville": "Londres Gatwick", "seuil": 600, "normal": 750},
"DUB": {"ville": "Dublin", "seuil": 620, "normal": 780},
"MAN": {"ville": "Manchester", "seuil": 620, "normal": 780},
"ZRH": {"ville": "Zurich", "seuil": 680, "normal": 850},
"VIE": {"ville": "Vienne", "seuil": 660, "normal": 830},
"BRU": {"ville": "Bruxelles", "seuil": 640, "normal": 790},
"CPH": {"ville": "Copenhague", "seuil": 660, "normal": 830},
"OSL": {"ville": "Oslo", "seuil": 660, "normal": 840},
"ARN": {"ville": "Stockholm", "seuil": 660, "normal": 840},
"HEL": {"ville": "Helsinki", "seuil": 680, "normal": 860},
"MXP": {"ville": "Milan", "seuil": 650, "normal": 820},
"PMI": {"ville": "Palma de Majorque", "seuil": 700, "normal": 870},
# Europe de l Est
"WAW": {"ville": "Varsovie", "seuil": 680, "normal": 850},
"PRG": {"ville": "Prague", "seuil": 670, "normal": 840},
"BUD": {"ville": "Budapest", "seuil": 680, "normal": 850},
"OTP": {"ville": "Bucarest", "seuil": 700, "normal": 880},
"SOF": {"ville": "Sofia", "seuil": 700, "normal": 880},
"KRK": {"ville": "Cracovie", "seuil": 690, "normal": 860},
"VNO": {"ville": "Vilnius", "seuil": 700, "normal": 880},
"TLL": {"ville": "Tallinn", "seuil": 700, "normal": 880},
# Afrique du Nord et Maroc
"CMN": {"ville": "Casablanca", "seuil": 700, "normal": 880},
"RAK": {"ville": "Marrakech", "seuil": 720, "normal": 900},
"FEZ": {"ville": "Fes", "seuil": 740, "normal": 920},
"AGA": {"ville": "Agadir", "seuil": 730, "normal": 910},
"TNG": {"ville": "Tanger", "seuil": 750, "normal": 930},
"CAI": {"ville": "Le Caire", "seuil": 780, "normal": 1000},
"TUN": {"ville": "Tunis", "seuil": 760, "normal": 950},
"ALG": {"ville": "Alger", "seuil": 780, "normal": 980},
# Afrique subsaharienne
"NBO": {"ville": "Nairobi", "seuil": 900, "normal": 1300},
"ACC": {"ville": "Accra", "seuil": 900, "normal": 1300},
"LOS": {"ville": "Lagos", "seuil": 950, "normal": 1400},
"DAK": {"ville": "Dakar", "seuil": 850, "normal": 1200},
"CPT": {"ville": "Le Cap", "seuil": 1000, "normal": 1500},
"JNB": {"ville": "Johannesburg", "seuil": 1000, "normal": 1500},
"ADD": {"ville": "Addis-Abeba", "seuil": 950, "normal": 1400},
"KMG": {"ville": "Kumasi", "seuil": 920, "normal": 1350},
# Moyen-Orient
"DXB": {"ville": "Dubai", "seuil": 750, "normal": 1100},
"IST": {"ville": "Istanbul", "seuil": 700, "normal": 860},
"DOH": {"ville": "Doha", "seuil": 800, "normal": 1150},
"AUH": {"ville": "Abu Dhabi", "seuil": 780, "normal": 1120},
"AMM": {"ville": "Amman", "seuil": 820, "normal": 1100},
"BEY": {"ville": "Beyrouth", "seuil": 800, "normal": 1100},
"TLV": {"ville": "Tel Aviv", "seuil": 780, "normal": 1050},
"KWI": {"ville": "Koweit", "seuil": 820, "normal": 1150},
"MCT": {"ville": "Muscat", "seuil": 830, "normal": 1200},
# Asie du Sud-Est
"BKK": {"ville": "Bangkok", "seuil": 800, "normal": 1200},
"SIN": {"ville": "Singapore", "seuil": 850, "normal": 1300},
"KUL": {"ville": "Kuala Lumpur", "seuil": 820, "normal": 1250},
"MNL": {"ville": "Manille", "seuil": 830, "normal": 1300},
"CGK": {"ville": "Jakarta", "seuil": 880, "normal": 1350},
"SGN": {"ville": "Ho Chi Minh Ville", "seuil": 850, "normal": 1300},
"HAN": {"ville": "Hanoi", "seuil": 860, "normal": 1320},
"DPS": {"ville": "Bali", "seuil": 900, "normal": 1380},
"BKI": {"ville": "Kota Kinabalu", "seuil": 900, "normal": 1380},
"NAN": {"ville": "Nadi Fiji", "seuil": 950, "normal": 1500},
# Asie de l Est
"NRT": {"ville": "Tokyo Narita", "seuil": 900, "normal": 1400},
"HND": {"ville": "Tokyo Haneda", "seuil": 900, "normal": 1400},
"ICN": {"ville": "Seoul", "seuil": 880, "normal": 1380},
"PEK": {"ville": "Pekin", "seuil": 860, "normal": 1350},
"PVG": {"ville": "Shanghai", "seuil": 860, "normal": 1350},
"HKG": {"ville": "Hong Kong", "seuil": 850, "normal": 1330},
"TPE": {"ville": "Taipei", "seuil": 870, "normal": 1360},
# Asie du Sud
"DEL": {"ville": "Delhi", "seuil": 800, "normal": 1200},
"BOM": {"ville": "Mumbai", "seuil": 810, "normal": 1220},
"CMB": {"ville": "Colombo", "seuil": 850, "normal": 1300},
"DAC": {"ville": "Dhaka", "seuil": 870, "normal": 1330},
"KTM": {"ville": "Katmandou", "seuil": 880, "normal": 1350},
# Ameriques
"MEX": {"ville": "Mexico", "seuil": 500, "normal": 700},
"CUN": {"ville": "Cancun", "seuil": 450, "normal": 650},
"BOG": {"ville": "Bogota", "seuil": 550, "normal": 750},
"GRU": {"ville": "Sao Paulo", "seuil": 650, "normal": 950},
"EZE": {"ville": "Buenos Aires", "seuil": 700, "normal": 1050},
"SCL": {"ville": "Santiago", "seuil": 680, "normal": 1000},
"LIM": {"ville": "Lima", "seuil": 600, "normal": 850},
"GIG": {"ville": "Rio de Janeiro", "seuil": 650, "normal": 950},
"UIO": {"ville": "Quito", "seuil": 580, "normal": 820},
"PTY": {"ville": "Panama", "seuil": 450, "normal": 620},
"HAV": {"ville": "La Havane", "seuil": 400, "normal": 580},
"SDQ": {"ville": "Saint-Domingue", "seuil": 380, "normal": 550},
"MBJ": {"ville": "Montego Bay", "seuil": 350, "normal": 500},
"SJU": {"ville": "San Juan", "seuil": 350, "normal": 500},
"NAS": {"ville": "Nassau", "seuil": 350, "normal": 500},
"GEO": {"ville": "Georgetown", "seuil": 500, "normal": 720},
# Oceanie
"SYD": {"ville": "Sydney", "seuil": 1100, "normal": 1700},
"MEL": {"ville": "Melbourne", "seuil": 1100, "normal": 1700},
"AKL": {"ville": "Auckland", "seuil": 1150, "normal": 1800},
"PPT": {"ville": "Papeete", "seuil": 900, "normal": 1400},
}

def scraper_sources():
    tous_les_deals = []
    for source in FEEDS:
        print(f"  Scraping {source['name']}...")
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries[:10]:
                tous_les_deals.append({
                    "source": source["name"],
                    "titre": entry.get("title", ""),
                    "contenu": entry.get("summary", "")[:2000],
                    "lien": entry.get("link", ""),
                    "date": entry.get("published", ""),
                })
        except Exception as e:
            print(f"  Erreur {source['name']}: {e}")
    print(f"\n  {len(tous_les_deals)} articles trouves au total\n")
    return tous_les_deals

def analyser_deal(deal, client):
    est_canadienne = any(x in deal["source"] for x in [
        "Canada", "Flytrippers", "Prince of Travel", "airmiles", "CanadaDeals"
    ])
    prompt = ("Tu es un expert en bons plans de vols pour les voyageurs de Montreal (YUL), Quebec, Canada.\n"
              "Analyse cet article et reponds en JSON.\n\n"
              "Source: " + deal["source"] + "\n"
              "Titre: " + deal["titre"] + "\n"
              "Contenu: " + deal["contenu"] + "\n"
              "Source canadienne: " + str(est_canadienne) + "\n\n"
              'Reponds UNIQUEMENT en JSON valide, sans texte avant ou apres:\n'
              '{\n'
              '  "contient_deal": true,\n'
              '  "adaptable_yul": true,\n'
              '  "code_destination": "CMN",\n'
              '  "ville_destination": "Casablanca",\n'
              '  "pays": "Maroc",\n'
              '  "prix_deal": 389,\n'
              '  "devise": "CAD",\n'
              '  "prix_normal_estime": 850,\n'
              '  "economie_pct": 54,\n'
              '  "type_deal": "erreur_tarifaire",\n'
              '  "duree_validite": "quelques heures",\n'
              '  "score_urgence": 9,\n'
              '  "lien_reservation": "https://...",\n'
              '  "raison_rejet": ""\n'
              '}\n\n'
              "Regles IMPORTANTES:\n"
              "- contient_deal: true UNIQUEMENT si prix de vol numerique precis mentionne. Sinon false\n"
              "- prix_deal: entier positif. Si pas de prix precis -> 0 et contient_deal=false\n"
              "- adaptable_yul: true si vol possible depuis Montreal (YUL) directement ou via hub\n"
              "- code_destination: utilise le code IATA exact de la destination (ex: CDG, NRT, SYD, GRU, DXB, BKK, CMN, JNB, etc.) - TOUTE destination mondiale acceptee\n"
              "- ville_destination: nom de la ville en francais\n"
              "- Si prix en USD: mets devise=USD (on convertira en CAD)\n"
              "- type_deal: erreur_tarifaire / promo_flash / routage_creatif / reduction_saison / miles_points\n"
              "- score_urgence: 1-10\n"
              "- Si pas un deal de vol avec prix: contient_deal=false et raison_rejet explique")
    try:
        client_anthropic = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client_anthropic.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        texte = response.content[0].text.strip()
        if "```" in texte:
            parties = texte.split("```")
            for p in parties:
                p2 = p.strip()
                if p2.startswith("json"):
                    p2 = p2[4:].strip()
                if p2.startswith("{"):
                    texte = p2
                    break
        texte = texte.strip()
        result = json.loads(texte)
        prix = result.get("prix_deal", 0)
        if not isinstance(prix, (int, float)) or prix <= 0:
            result["contient_deal"] = False
            result["raison_rejet"] = "Prix invalide ou absent: " + str(prix)
        return result
    except Exception as e:
        return {"contient_deal": False, "raison_rejet": "Erreur analyse: " + str(e)}

def verifier_seuil(analyse):
    code = analyse.get("code_destination", "")
    prix = analyse.get("prix_deal", 0)
    devise = analyse.get("devise", "CAD")
    try:
        prix = float(prix)
    except (TypeError, ValueError):
        return (False, None)
    if prix <= 0:
        return (False, None)
    if devise == "USD":
        prix_cad = round(prix * USD_TO_CAD)
        print(f"  Conversion: {prix:.0f} USD -> {prix_cad} CAD")
        analyse["prix_deal_cad"] = prix_cad
    else:
        prix_cad = int(prix)
        analyse["prix_deal_cad"] = prix_cad
    if code in SEUILS:
        seuil = SEUILS[code]["seuil"]
        return (prix_cad <= seuil, seuil)
    # Destination inconnue: accepter si economie >= 30% ou si prix < 800 CAD
    try:
        economie = float(analyse.get("economie_pct", 0) or 0)
    except (TypeError, ValueError):
        economie = 0
    if economie >= 30:
        print(f"  Destination {code} inconnue mais economie {economie:.0f}% >= 30%, on accepte")
        return (True, None)
    if prix_cad < 800:
        print(f"  Destination {code} inconnue mais prix {prix_cad}$ CAD < 800$, on accepte")
        return (True, None)
    return (False, None)

def mettre_a_jour_site(deals_valides):
    """Met a jour la bande de deals et les route-cards sur index.html via l API GitHub"""
    if not GITHUB_TOKEN:
        print("  GITHUB_TOKEN absent, mise a jour du site ignoree")
        return
    if not deals_valides:
        print("  Aucun deal a afficher sur le site")
        return

    # Recuperer le fichier actuel
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/index.html"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"  Erreur recuperation index.html: {r.status_code}")
        return
    data = r.json()
    sha = data["sha"]
    html_content = base64.b64decode(data["content"]).decode("utf-8")

    # Generer les nouvelles deal-pills avec les vrais deals
    depart = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y%m%d")
    retour = (datetime.now(timezone.utc) + timedelta(days=37)).strftime("%Y%m%d")
    pills_html = ""
    for d in deals_valides[:5]:  # Max 5 deals affiches
        ville = d.get("ville_destination", "")
        code = d.get("code_destination", "").lower()
        prix = d.get("prix_deal_cad", d.get("prix_deal", ""))
        econ = d.get("economie_pct", "")
        lien_sky = (
            f"https://www.skyscanner.ca/transport/flights/yul/{code}/"
            f"{depart}/{retour}/?adults=1&currency=CAD&locale=fr-CA&market=CA"
        )
        pills_html += (
            f'<a href="{lien_sky}" target="_blank" rel="noopener" class="deal-pill">'
            f'<span class="route">YUL \u2192 {ville}</span>'
            f'<span class="sep"></span>'
            f'<span class="price">{prix} $</span>'
            f'<span class="saving">-{econ}%</span>'
            f'</a>'
        )

    date_maj = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    nouveau_bloc = (
        '<div class="deals-strip-section">\n'
        '<div class="deals-strip">\n'
        + pills_html + '\n'
        '</div>\n'
        f'<p class="deals-disclaimer">Deals detectes en temps reel \u00b7 Mis a jour le {date_maj}</p>\n'
        '</div>'
    )

    # Remplacer le bloc deals-strip-section dans le HTML
    pattern = r'<div class="deals-strip-section">.*?</div>\s*</div>\s*<p class="deals-disclaimer">.*?</p>\s*</div>'
    nouveau_html = re.sub(pattern, nouveau_bloc, html_content, flags=re.DOTALL)

    if nouveau_html == html_content:
        print("  Pattern non trouve, tentative alternative...")
        start = html_content.find('<div class="deals-strip-section">')
        end = html_content.find('</div>', html_content.find('</div>', html_content.find('</div>', start) + 1) + 1) + 6
        if start != -1:
            nouveau_html = html_content[:start] + nouveau_bloc + html_content[end:]

    # ----------------------------------------------------------------
    # Mettre a jour les route-cards avec les prix des deals trouves
    # ----------------------------------------------------------------
    deals_par_code = {}
    for d in deals_valides:
        code_up = d.get("code_destination", "").upper()
        if code_up:
            deals_par_code[code_up] = d

    def remplacer_route_card(m):
        inner = m.group(0)
        # Chercher l attribut data-iata dans la carte
        iata_match = re.search(r'data-iata="([A-Z]{2,4})"', inner)
        if not iata_match:
            return inner
        code = iata_match.group(1)
        if code not in deals_par_code:
            return inner
        d = deals_par_code[code]
        prix_c = d.get("prix_deal_cad", d.get("prix_deal", ""))
        econ_c = d.get("economie_pct", "")
        code_low = code.lower()
        lien_c = (
            f"https://www.skyscanner.ca/transport/flights/yul/{code_low}/"
            f"{depart}/{retour}/?adults=1&currency=CAD&locale=fr-CA&market=CA"
        )
        # Extraire le contenu interne de la route-card (tout sauf la div exterieure)
        # La structure est: <div class="route-card" data-iata="XXX">...<div>...</div></div>
        # On reconstruit: <a class="route-card has-deal" href="...">...<div class="deal-badge">PRIX</div></div></a>
        # Remplacer l ouverture <div class="route-card" ...> par <a ...>
        new_card = re.sub(
            r'<div class="route-card"([^>]*)>',
            f'<a href="{lien_c}" target="_blank" rel="noopener" class="route-card has-deal"\1 style="text-decoration:none;display:flex;align-items:center;">',
            inner,
            count=1
        )
        # Ajouter le badge prix avant la fermeture de la card
        # La route-card se ferme par </div></div> (inner-div puis outer-div)
        # On insere le badge prix juste avant le dernier </div>
        badge = (
            f'<div style="margin-left:auto;text-align:right;">'
            f'<div style="font-size:13px;font-weight:700;color:#ff6b00;">{prix_c}$</div>'
            f'<div style="font-size:10px;color:#ff6b00;background:rgba(255,107,0,0.18);'
            f'padding:1px 5px;border-radius:3px;">-{econ_c}%</div>'
            f'</div>'
        )
        # Trouver la position du dernier </div> et inserer le badge avant
        last_div_pos = new_card.rfind('</div>')
        if last_div_pos != -1:
            new_card = new_card[:last_div_pos] + badge + '</div>'
        else:
            new_card += badge
        # Remplacer la fermeture </div> finale par </a>
        last_div_pos2 = new_card.rfind('</div>')
        if last_div_pos2 != -1:
            new_card = new_card[:last_div_pos2] + '</a>'
        print(f"  Route-card {code} mise a jour avec {prix_c}$ CAD (-{econ_c}%)")
        return new_card

    # PATTERN CORRIGE: accepte les route-cards avec OU sans attributs (data-iata etc.)
    route_pattern = r'<div class="route-card"[^>]*>.*?</div>\s*</div>'
    nouveau_html = re.sub(route_pattern, remplacer_route_card, nouveau_html, flags=re.DOTALL)

    # Commiter via API GitHub
    contenu_b64 = base64.b64encode(nouveau_html.encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"Auto: mise a jour deals du {date_maj}",
        "content": contenu_b64,
        "sha": sha,
        "committer": {
            "name": "VolsDeals Bot",
            "email": "alaouisana0@gmail.com"
        }
    }
    r2 = requests.put(url, headers=headers, json=payload)
    if r2.status_code in (200, 201):
        print(f"  Site mis a jour avec {len(deals_valides)} deal(s) !")
    else:
        print(f"  Erreur mise a jour site: {r2.status_code} {r2.text[:200]}")

def envoyer_alerte(deal_info, liste_emails):
    ville = deal_info.get("ville_destination", "")
    prix = deal_info.get("prix_deal_cad", deal_info.get("prix_deal", ""))
    econ = deal_info.get("economie_pct", "")
    code_dest = deal_info.get("code_destination", "").lower()
    depart_sky = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y%m%d")
    retour_sky = (datetime.now(timezone.utc) + timedelta(days=37)).strftime("%Y%m%d")
    lien = (
        f"https://www.skyscanner.ca/transport/flights/yul/{code_dest}/"
        f"{depart_sky}/{retour_sky}/?adults=1&currency=CAD&locale=fr-CA&market=CA"
    ) if code_dest else deal_info.get("lien_reservation", "#")
    type_ = deal_info.get("type_deal", "promo")
    norm = deal_info.get("prix_normal_estime", "")
    pays = deal_info.get("pays", "")
    try:
        score = int(deal_info.get("score_urgence", 5) or 5)
    except (TypeError, ValueError):
        score = 5
    if score >= 9:
        badge = "ERREUR TARIFAIRE -- Agis dans l heure !"
    elif score >= 7:
        badge = "DEAL FLASH -- Expire dans quelques heures"
    else:
        badge = "DEAL DU JOUR"
    sujet = f"[VolsDeals] YUL -> {ville} a {prix}$ CAD (-{econ}%) -- {badge}"
    html = ('<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#070f1e;color:#fff;padding:40px 32px;border-radius:12px">'
            '<div style="text-align:center;margin-bottom:32px"><span style="font-size:22px;font-weight:900">VolsDeals</span><span style="color:#ff6b00">&#x25CF;</span></div>'
            f'<div style="background:#ff6b00;color:#fff;text-align:center;padding:10px 20px;border-radius:8px;font-weight:700;font-size:13px;text-transform:uppercase;margin-bottom:24px">{badge}</div>'
            f'<h1 style="font-size:32px;font-weight:900;margin:0 0 8px">YUL &rarr; {ville} ({pays})</h1>'
            f'<div style="font-size:48px;font-weight:900;color:#ff6b00;margin:16px 0">{prix} $ CAD</div>'
            f'<p style="color:#8a9ab5;font-size:15px;margin-bottom:8px">Prix normal : <s>{norm}$</s> &bull; Economie : <strong style="color:#ff6b00">-{econ}%</strong></p>'
            f'<p style="color:#8a9ab5;font-size:14px;margin-bottom:32px">Type : {type_} &bull; Urgence : {score}/10</p>'
            '<div style="text-align:center;margin:32px 0">'
            f'<a href="{lien}" style="background:#ff6b00;color:#fff;padding:16px 40px;border-radius:8px;font-weight:700;font-size:16px;text-decoration:none;display:inline-block">Voir le deal &rarr;</a>'
            '</div>'
            '<hr style="border:none;border-top:1px solid #1e3050;margin:32px 0">'
            '<p style="color:#4a5a75;font-size:12px;text-align:center">VolsDeals &bull; Laval, Quebec</p>'
            '</div>')
    payload = {
        "sender": {"name": "VolsDeals", "email": "alaouisana0@gmail.com"},
        "to": [{"email": e} for e in liste_emails],
        "subject": sujet,
        "htmlContent": html,
    }
    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    if r.status_code in (200, 201):
        print(f"  Email envoye a {len(liste_emails)} abonne(s) !")
    else:
        print(f"  Erreur envoi email: {r.status_code} {r.text}")

def get_abonnes():
    emails = []
    offset = 0
    while True:
        r = requests.get(
            f"https://api.brevo.com/v3/contacts?listId={BREVO_LIST_ID}&limit=500&offset={offset}",
            headers={"api-key": BREVO_API_KEY}
        )
        if r.status_code != 200:
            break
        contacts = r.json().get("contacts", [])
        if not contacts:
            break
        emails += [c["email"] for c in contacts]
        offset += 500
        if len(contacts) < 500:
            break
    return emails

def main():
    print("=" * 55)
    print("  VolsDeals - Deal Hunter")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 55)
    deals_bruts = scraper_sources()
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    deals_valides = []
    print("Analyse avec Claude AI...\n")
    for i, deal in enumerate(deals_bruts):
        print(f"[{i+1}/{len(deals_bruts)}] {deal['source']} -- {deal['titre'][:70]}...")
        analyse = analyser_deal(deal, client)
        if not analyse.get("contient_deal"):
            print(f"  Non pertinent: {analyse.get('raison_rejet', '')[:120]}")
            continue
        if not analyse.get("adaptable_yul"):
            print(f"  Non adaptable depuis YUL")
            continue
        ok, seuil = verifier_seuil(analyse)
        if not ok:
            prix_cad = analyse.get("prix_deal_cad", analyse.get("prix_deal", "?"))
            print(f"  Prix {prix_cad}$ CAD -- au-dessus du seuil ({seuil}$), ignore")
            continue
        prix_affiche = analyse.get("prix_deal_cad", analyse.get("prix_deal", "?"))
        print(f"  DEAL TROUVE ! YUL -> {analyse.get('ville_destination')} a {prix_affiche}$ CAD (-{analyse.get('economie_pct')}%)")
        deals_valides.append(analyse)
    print(f"\n{len(deals_valides)} deal(s) valide(s) trouve(s)\n")
    if deals_valides:
        # Trier par score d urgence (meilleurs en premier)
        deals_valides.sort(key=lambda x: x.get("score_urgence", 0) or 0, reverse=True)
        meilleur = deals_valides[0]
        prix_affiche = meilleur.get("prix_deal_cad", meilleur.get("prix_deal"))
        print(f"Meilleur deal : YUL -> {meilleur.get('ville_destination')} a {prix_affiche}$ CAD")
        # Mettre a jour le site avec tous les deals trouves
        print("\nMise a jour du site web...")
        mettre_a_jour_site(deals_valides)
        # Envoyer l alerte email
        abonnes = get_abonnes()
        if not abonnes:
            abonnes = [TON_EMAIL]
            print(f"  Aucun abonne, envoi a {TON_EMAIL} uniquement")
        else:
            print(f"  {len(abonnes)} abonne(s)")
        envoyer_alerte(meilleur, abonnes)
    else:
        print("Aucun deal exceptionnel aujourd hui. On surveille...")

if __name__ == "__main__":
    main()
