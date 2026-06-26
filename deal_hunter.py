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

SEUILS = {
"CMN": {"ville": "Casablanca", "seuil": 700, "normal": 880},
"RAK": {"ville": "Marrakech", "seuil": 720, "normal": 900},
"FEZ": {"ville": "Fes", "seuil": 740, "normal": 920},
"AGA": {"ville": "Agadir", "seuil": 730, "normal": 910},
"CDG": {"ville": "Paris", "seuil": 650, "normal": 780},
"LIS": {"ville": "Lisbonne", "seuil": 650, "normal": 800},
"BCN": {"ville": "Barcelone", "seuil": 650, "normal": 820},
"FCO": {"ville": "Rome", "seuil": 660, "normal": 830},
"ATH": {"ville": "Athenes", "seuil": 680, "normal": 850},
"AMS": {"ville": "Amsterdam", "seuil": 640, "normal": 790},
"IST": {"ville": "Istanbul", "seuil": 700, "normal": 860},
"FRA": {"ville": "Francfort", "seuil": 640, "normal": 790},
"MAD": {"ville": "Madrid", "seuil": 650, "normal": 820},
"NCE": {"ville": "Nice", "seuil": 660, "normal": 830},
"MRS": {"ville": "Marseille", "seuil": 660, "normal": 830},
"DXB": {"ville": "Dubai", "seuil": 750, "normal": 1100},
"BKK": {"ville": "Bangkok", "seuil": 800, "normal": 1200},
"MEX": {"ville": "Mexico", "seuil": 500, "normal": 700},
"CUN": {"ville": "Cancun", "seuil": 450, "normal": 650},
"NRT": {"ville": "Tokyo", "seuil": 900, "normal": 1400},
"SIN": {"ville": "Singapore", "seuil": 850, "normal": 1300},
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
              "- code_destination: CMN, CDG, LIS, BCN, FCO, ATH, AMS, IST, RAK, FEZ, AGA, FRA, MAD, NCE, MRS, DXB, BKK, MEX, CUN, NRT, SIN\n"
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
    try:
        economie = float(analyse.get("economie_pct", 0) or 0)
    except (TypeError, ValueError):
        economie = 0
    if economie >= 35:
        print(f"  Destination {code} inconnue mais economie {economie:.0f}% >= 35%, on accepte")
        return (True, None)
    return (False, None)

def mettre_a_jour_site(deals_valides):
    """Met a jour la bande de deals sur index.html via l API GitHub"""
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
    pills_html = ""
    for d in deals_valides[:5]:  # Max 5 deals affiches
        ville = d.get("ville_destination", "")
        code = d.get("code_destination", "")
        prix = d.get("prix_deal_cad", d.get("prix_deal", ""))
        econ = d.get("economie_pct", "")
        lien = d.get("lien_reservation", "#")
        pills_html += (
            f'<a href="{lien}" target="_blank" rel="noopener" class="deal-pill">'
            f'<span class="route">YUL vers {code}</span>'
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
        f'<p class="deals-disclaimer">Deals detectes en temps reel · Mis a jour le {date_maj}</p>\n'
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
    lien = deal_info.get("lien_reservation", "#")
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
