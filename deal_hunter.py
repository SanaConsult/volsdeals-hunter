"""
VolsDeals -- Deal Hunter
Scrape les sources de deals, filtre avec Claude AI, envoie via Brevo
"""

import feedparser
import json
import requests
from datetime import datetime, timezone
import anthropic
import os

# ============================================================
# CONFIG
# ============================================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BREVO_API_KEY     = os.environ.get("BREVO_API_KEY")
BREVO_LIST_ID     = 3
TON_EMAIL         = "alaouisana0@gmail.com"
# ============================================================

# Sources RSS -- focus Canada/Quebec + sources internationales
FEEDS = [
    # --- Sources specifiques Canada / Quebec ---
    {"name": "Secret Flying Canada",          "url": "https://www.secretflying.com/posts/category/canada/feed/"},
    {"name": "Flytrippers",                   "url": "https://flytrippers.com/feed/"},
    {"name": "Prince of Travel",              "url": "https://princeoftravel.com/feed/"},
    {"name": "Reddit r/airmiles",             "url": "https://www.reddit.com/r/airmiles/.rss"},
    {"name": "Reddit r/CanadaDeals",          "url": "https://www.reddit.com/r/CanadaDeals/.rss"},
    # --- Sources internationales (filtrees par Claude) ---
    {"name": "Secret Flying",                 "url": "https://secretflying.com/feed/"},
    {"name": "The Flight Deal",               "url": "https://www.theflightdeal.com/feed/"},
    {"name": "Reddit r/flightdeals",          "url": "https://www.reddit.com/r/flightdeals/.rss"},
    {"name": "Airfarewatchdog",               "url": "https://www.airfarewatchdog.com/blog/feed/"},
    {"name": "Going (Scotts Cheap Flights)",  "url": "https://going.com/guides/feed"},
    {"name": "Holidaypiraten",                "url": "https://www.holidaypiraten.de/feed/"},
]

# Seuils de prix par destination (en dollars canadiens aller-retour)
SEUILS = {
    "CMN": {"ville": "Casablanca",  "seuil": 600,  "normal": 880},
    "RAK": {"ville": "Marrakech",   "seuil": 620,  "normal": 900},
    "FEZ": {"ville": "Fes",         "seuil": 650,  "normal": 920},
    "AGA": {"ville": "Agadir",      "seuil": 640,  "normal": 910},
    "CDG": {"ville": "Paris",       "seuil": 500,  "normal": 780},
    "LIS": {"ville": "Lisbonne",    "seuil": 520,  "normal": 800},
    "BCN": {"ville": "Barcelone",   "seuil": 530,  "normal": 820},
    "FCO": {"ville": "Rome",        "seuil": 540,  "normal": 830},
    "ATH": {"ville": "Athenes",     "seuil": 560,  "normal": 850},
    "AMS": {"ville": "Amsterdam",   "seuil": 520,  "normal": 790},
    "IST": {"ville": "Istanbul",    "seuil": 580,  "normal": 860},
    "FRA": {"ville": "Francfort",   "seuil": 510,  "normal": 790},
    "MAD": {"ville": "Madrid",      "seuil": 530,  "normal": 820},
    "NCE": {"ville": "Nice",        "seuil": 540,  "normal": 830},
    "MRS": {"ville": "Marseille",   "seuil": 540,  "normal": 830},
}

# ============================================================
# ETAPE 1 -- SCRAPER TOUTES LES SOURCES RSS
# ============================================================
def scraper_sources():
    tous_les_deals = []
    for source in FEEDS:
        print(f"  Scraping {source['name']}...")
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries[:10]:
                tous_les_deals.append({
                    "source":  source["name"],
                    "titre":   entry.get("title", ""),
                    "contenu": entry.get("summary", "")[:1500],
                    "lien":    entry.get("link", ""),
                    "date":    entry.get("published", ""),
                })
        except Exception as e:
            print(f"  Erreur {source['name']}: {e}")
    print(f"\n {len(tous_les_deals)} articles trouves au total\n")
    return tous_les_deals

# ============================================================
# ETAPE 2 -- ANALYSER AVEC CLAUDE AI
# ============================================================
def analyser_deal(deal, client):
    est_canadienne = any(x in deal['source'] for x in ["Canada", "Flytrippers", "Prince of Travel", "airmiles", "CanadaDeals"])

    prompt = f"""Tu es un expert en deals de vols pour le marche quebecois.
Analyse cet article et dis-moi s il contient un vrai deal de vol utilisable depuis Montreal (YUL).

Source: {deal['source']}
Titre: {deal['titre']}
Contenu: {deal['contenu']}
Source canadienne: {est_canadienne}

Reponds UNIQUEMENT en JSON valide, sans texte avant ou apres:
{{
  "contient_deal": true,
  "adaptable_yul": true,
  "code_destination": "CMN",
  "ville_destination": "Casablanca",
  "pays": "Maroc",
  "prix_deal": 389,
  "prix_normal_estime": 850,
  "economie_pct": 54,
  "type_deal": "erreur_tarifaire",
  "duree_validite": "quelques heures",
  "score_urgence": 9,
  "lien_reservation": "https://...",
  "raison_rejet": ""
}}

Regles:
- contient_deal: true seulement si c est un VRAI deal avec un prix precis
- adaptable_yul: true si utilisable depuis Montreal -- directement ou via hub
- Pour les sources canadiennes, sois plus ouvert car elles publient deja des deals YUL
- code_destination: CMN, CDG, LIS, BCN, FCO, ATH, AMS, IST, RAK, FEZ, AGA, FRA, MAD, NCE, MRS
- type_deal: erreur_tarifaire / promo_flash / routage_creatif / reduction_saison
- score_urgence: 1-10
- Si pas pertinent: contient_deal=false et raison_rejet explique pourquoi"""

    try:
        client_anthropic = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client_anthropic.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        texte = response.content[0].text.strip()
        if "json" in texte[:10]:
            texte = texte.split("json", 1)[1]
        texte = texte.strip().strip("`")
        return json.loads(texte)
    except Exception as e:
        return {"contient_deal": False, "raison_rejet": f"Erreur analyse: {e}"}

# ============================================================
# ETAPE 3 -- VERIFIER LE SEUIL DE PRIX
# ============================================================
def verifier_seuil(analyse):
    code = analyse.get("code_destination", "")
    prix = analyse.get("prix_deal", 9999)
    if code in SEUILS:
        seuil = SEUILS[code]["seuil"]
        return (prix <= seuil, seuil)
    return (False, None)

# ============================================================
# ETAPE 4 -- ENVOYER L ALERTE EMAIL VIA BREVO
# ============================================================
def envoyer_alerte(deal_info, liste_emails):
    ville = deal_info.get("ville_destination", "")
    prix  = deal_info.get("prix_deal", "")
    econ  = deal_info.get("economie_pct", "")
    lien  = deal_info.get("lien_reservation", "#")
    type_ = deal_info.get("type_deal", "promo")
    score = deal_info.get("score_urgence", 5)
    norm  = deal_info.get("prix_normal_estime", "")

    if score >= 9:
        badge = "ERREUR TARIFAIRE -- Agis dans l heure !"
    elif score >= 7:
        badge = "DEAL FLASH -- Expire dans quelques heures"
    else:
        badge = "DEAL DU JOUR"

    sujet = f"[VolsDeals] YUL -> {ville} a {prix}$ (-{econ}%) -- {badge}"

    html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#070f1e;color:#fff;padding:40px 32px;border-radius:12px">
  <div style="text-align:center;margin-bottom:32px"><span style="font-size:22px;font-weight:900">VolsDeals</span><span style="color:#ff6b00">&#x25CF;</span></div>
  <div style="background:#ff6b00;color:#fff;text-align:center;padding:10px 20px;border-radius:8px;font-weight:700;font-size:13px;text-transform:uppercase;margin-bottom:24px">{badge}</div>
  <h1 style="font-size:32px;font-weight:900;margin:0 0 8px">YUL &rarr; {ville}</h1>
  <div style="font-size:48px;font-weight:900;color:#ff6b00;margin:16px 0">{prix} $</div>
  <p style="color:#8a9ab5;font-size:15px;margin-bottom:8px">Prix normal : <s>{norm}$</s> &bull; Economie : <strong style="color:#ff6b00">-{econ}%</strong></p>
  <p style="color:#8a9ab5;font-size:14px;margin-bottom:32px">Type : {type_} &bull; Urgence : {score}/10</p>
  <div style="text-align:center;margin:32px 0">
    <a href="{lien}" style="background:#ff6b00;color:#fff;padding:16px 40px;border-radius:8px;font-weight:700;font-size:16px;text-decoration:none;display:inline-block">Voir le deal &rarr;</a>
  </div>
  <hr style="border:none;border-top:1px solid #1e3050;margin:32px 0">
  <p style="color:#4a5a75;font-size:12px;text-align:center">VolsDeals &bull; Laval, Quebec</p>
</div>"""

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

# ============================================================
# ETAPE 5 -- RECUPERER LES ABONNES BREVO
# ============================================================
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

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 55)
    print("  VolsDeals - Deal Hunter")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    deals_bruts   = scraper_sources()
    client        = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    deals_valides = []

    print("Analyse avec Claude AI...\n")

    for i, deal in enumerate(deals_bruts):
        print(f"[{i+1}/{len(deals_bruts)}] {deal['source']} -- {deal['titre'][:70]}...")
        analyse = analyser_deal(deal, client)

        if not analyse.get("contient_deal"):
            print(f"  Non pertinent: {analyse.get('raison_rejet', '')[:120]}")
            continue
        if not analyse.get("adaptable_yul"):
            print("  Non adaptable depuis YUL")
            continue

        ok, seuil = verifier_seuil(analyse)
        if not ok:
            prix = analyse.get("prix_deal", "?")
            print(f"  Prix {prix}$ -- au-dessus du seuil ({seuil}$), ignore")
            continue

        print(f"  DEAL TROUVE ! YUL -> {analyse.get('ville_destination')} a {analyse.get('prix_deal')}$ (-{analyse.get('economie_pct')}%)")
        deals_valides.append(analyse)

    print(f"\n{len(deals_valides)} deal(s) valide(s) trouve(s)\n")

    if deals_valides:
        meilleur = max(deals_valides, key=lambda x: x.get("score_urgence", 0))
        print(f"Meilleur deal : YUL -> {meilleur.get('ville_destination')} a {meilleur.get('prix_deal')}$")
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
