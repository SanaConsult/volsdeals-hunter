"""
VolsDeals — Deal Hunter
Scrape les sources de deals, filtre avec Claude AI, envoie via Brevo
"""

import feedparser
import json
import requests
from datetime import datetime, timezone
import anthropic

# ============================================================
# CONFIG — REMPLACE CES VALEURS
# ============================================================
ANTHROPIC_API_KEY = "sk-ant-REMPLACE_PAR_TA_CLE"   # claude.ai → API Keys
BREVO_API_KEY     = "xkeysib-REMPLACE_PAR_TA_CLE"   # brevo.com → SMTP & API
BREVO_LIST_ID     = 3                                 # ID de ta liste Brevo
TON_EMAIL         = "ton@email.com"                   # Email pour test
# ============================================================

# Sources RSS à scraper
FEEDS = [
    {"name": "Secret Flying",    "url": "https://secretflying.com/feed/"},
    {"name": "The Flight Deal",  "url": "https://www.theflightdeal.com/feed/"},
    {"name": "Reddit Flightdeals","url": "https://www.reddit.com/r/flightdeals/.rss"},
    {"name": "Reddit Airmiles",  "url": "https://www.reddit.com/r/airmiles/.rss"},
    {"name": "Airfarewatchdog",  "url": "https://www.airfarewatchdog.com/blog/feed/"},
]

# Seuils de prix par destination (en dollars canadiens aller-retour)
SEUILS = {
    "CMN": {"ville": "Casablanca",  "seuil": 600, "normal": 880},
    "RAK": {"ville": "Marrakech",   "seuil": 620, "normal": 900},
    "FEZ": {"ville": "Fès",         "seuil": 650, "normal": 920},
    "AGA": {"ville": "Agadir",      "seuil": 640, "normal": 910},
    "CDG": {"ville": "Paris",       "seuil": 500, "normal": 780},
    "LIS": {"ville": "Lisbonne",    "seuil": 520, "normal": 800},
    "BCN": {"ville": "Barcelone",   "seuil": 530, "normal": 820},
    "FCO": {"ville": "Rome",        "seuil": 540, "normal": 830},
    "ATH": {"ville": "Athènes",     "seuil": 560, "normal": 850},
    "AMS": {"ville": "Amsterdam",   "seuil": 520, "normal": 790},
    "IST": {"ville": "Istanbul",    "seuil": 580, "normal": 860},
}


# ============================================================
# ÉTAPE 1 — SCRAPER TOUTES LES SOURCES RSS
# ============================================================
def scraper_sources():
    """Récupère tous les deals bruts depuis les sources RSS"""
    tous_les_deals = []

    for source in FEEDS:
        print(f"📡 Scraping {source['name']}...")
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries[:15]:  # 15 derniers articles max
                tous_les_deals.append({
                    "source": source["name"],
                    "titre":  entry.get("title", ""),
                    "contenu": entry.get("summary", "")[:1500],
                    "lien":   entry.get("link", ""),
                    "date":   entry.get("published", ""),
                })
        except Exception as e:
            print(f"  ⚠️  Erreur {source['name']}: {e}")

    print(f"\n✅ {len(tous_les_deals)} articles trouvés au total\n")
    return tous_les_deals


# ============================================================
# ÉTAPE 2 — ANALYSER AVEC CLAUDE AI
# ============================================================
def analyser_deal(deal, client):
    """Demande à Claude si le deal est pertinent pour YUL → Maroc/Europe"""

    prompt = f"""Tu es un expert en deals de vols pour le marché québécois.

Analyse cet article trouvé en ligne et dis-moi s'il contient un vrai deal de vol.

Source: {deal['source']}
Titre: {deal['titre']}
Contenu: {deal['contenu']}

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après:
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

Règles importantes:
- contient_deal: true seulement si c'est un VRAI deal avec un prix précis
- adaptable_yul: true si le deal peut être utilisé depuis Montréal (YUL)
- code_destination: code IATA de la destination (CMN, CDG, LIS, BCN, FCO, ATH, AMS, IST, RAK, FEZ, AGA)
- type_deal: "erreur_tarifaire", "promo_flash", "routage_creatif", ou "reduction_saison"
- score_urgence: 1-10 (10 = erreur tarifaire qui expire dans 2h)
- Si pas de deal pertinent: contient_deal=false et raison_rejet explique pourquoi"""

    try:
        client_anthropic = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client_anthropic.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        texte = response.content[0].text.strip()
        # Nettoyer si Claude ajoute des backticks
        texte = texte.replace("```json", "").replace("```", "").strip()
        return json.loads(texte)
    except Exception as e:
        print(f"  ⚠️  Erreur analyse: {e}")
        return {"contient_deal": False, "raison_rejet": str(e)}


# ============================================================
# ÉTAPE 3 — RÉDIGER L'EMAIL DEAL AVEC CLAUDE AI
# ============================================================
def rediger_email_deal(analyse, lien_original):
    """Génère l'email newsletter prêt à envoyer"""

    ville     = analyse.get("ville_destination", "")
    pays      = analyse.get("pays", "")
    prix      = analyse.get("prix_deal", 0)
    normal    = analyse.get("prix_normal_estime", 0)
    economie  = analyse.get("economie_pct", 0)
    type_deal = analyse.get("type_deal", "")
    urgence   = analyse.get("score_urgence", 5)
    lien      = analyse.get("lien_reservation") or lien_original

    # Adapter le ton selon l'urgence
    if urgence >= 8:
        ton = "URGENT — ce deal peut disparaître dans les prochaines heures"
    elif urgence >= 6:
        ton = "Deal solide — quelques jours disponibles"
    else:
        ton = "Bonne réduction — prends le temps de vérifier"

    prompt = f"""Tu es la fondatrice de VolsDeals, une Québécoise spécialisée dans les vols vers le Maroc et l'Europe.
Ton style: chaleureux, direct, comme si tu textes une amie. Français québécois naturel.

Écris un email newsletter pour ce deal:
- Destination: YUL → {ville}, {pays}
- Prix deal: {prix}$ aller-retour
- Prix normal: {normal}$
- Économie: {economie}%
- Type: {type_deal}
- Niveau d'urgence: {ton}
- Lien pour réserver: {lien}

Format de réponse (JSON uniquement):
{{
  "objet": "✈️ YUL → {ville} à {prix}$ (prix normal: {normal}$)",
  "corps_html": "<h2>...</h2><p>...</p>"
}}

Le corps HTML doit contenir:
1. Accroche urgente (1 phrase)
2. Les détails du deal (prix, économie, destination)
3. Instructions exactes pour réserver (étapes simples)
4. Avertissement si erreur tarifaire
5. Bouton CTA vers le lien de réservation
6. Signature chaleureuse

Style: 200-300 mots max, phrases courtes, emojis avec modération."""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        texte = response.content[0].text.strip()
        texte = texte.replace("```json", "").replace("```", "").strip()
        return json.loads(texte)
    except Exception as e:
        print(f"  ⚠️  Erreur rédaction: {e}")
        return None


# ============================================================
# ÉTAPE 4 — ENVOYER VIA BREVO
# ============================================================
def envoyer_via_brevo(objet, corps_html, urgence):
    """Envoie l'email à toute la liste Brevo"""

    url = "https://api.brevo.com/v3/emailCampaigns"
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    payload = {
        "name": f"Deal VolsDeals — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "subject": objet,
        "sender": {"name": "VolsDeals", "email": TON_EMAIL},
        "type": "classic",
        "htmlContent": corps_html,
        "recipients": {"listIds": [BREVO_LIST_ID]},
        "scheduledAt": now  # Envoi immédiat
    }

    try:
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code in [200, 201]:
            campaign_id = r.json().get("id")
            print(f"  ✅ Campagne créée (ID: {campaign_id})")

            # Envoyer immédiatement
            send_url = f"https://api.brevo.com/v3/emailCampaigns/{campaign_id}/sendNow"
            r2 = requests.post(send_url, headers={"api-key": BREVO_API_KEY})
            if r2.status_code == 204:
                print(f"  🚀 Email envoyé à toute la liste!")
            return True
        else:
            print(f"  ⚠️  Erreur Brevo: {r.status_code} — {r.text}")
            return False
    except Exception as e:
        print(f"  ⚠️  Erreur envoi: {e}")
        return False


def envoyer_email_test(objet, corps_html):
    """Envoie un email de test à TON_EMAIL seulement"""

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "sender": {"name": "VolsDeals", "email": TON_EMAIL},
        "to": [{"email": TON_EMAIL}],
        "subject": f"[TEST] {objet}",
        "htmlContent": corps_html
    }

    try:
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code == 201:
            print(f"  ✅ Email de test envoyé à {TON_EMAIL}")
            return True
        else:
            print(f"  ⚠️  Erreur test: {r.status_code} — {r.text}")
            return False
    except Exception as e:
        print(f"  ⚠️  Erreur: {e}")
        return False


# ============================================================
# ORCHESTRATION PRINCIPALE
# ============================================================
def main():
    print("=" * 55)
    print("  VolsDeals — Deal Hunter")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # 1. Scraper toutes les sources
    tous_les_deals = scraper_sources()

    deals_trouves = []

    # 2. Analyser chaque article avec Claude
    print("🤖 Analyse avec Claude AI...\n")
    for i, deal in enumerate(tous_les_deals):
        print(f"  [{i+1}/{len(tous_les_deals)}] {deal['source']} — {deal['titre'][:60]}...")

        analyse = analyser_deal(deal, client)

        if not analyse.get("contient_deal"):
            print(f"  ❌ Pas pertinent: {analyse.get('raison_rejet', 'non applicable')}")
            continue

        if not analyse.get("adaptable_yul"):
            print(f"  ❌ Non adaptable depuis YUL")
            continue

        # Vérifier si le prix est sous le seuil
        code = analyse.get("code_destination", "")
        prix = analyse.get("prix_deal", 9999)

        if code in SEUILS and prix < SEUILS[code]["seuil"]:
            print(f"  🔥 DEAL DÉTECTÉ! YUL → {analyse['ville_destination']} à {prix}$")
            analyse["lien_original"] = deal["lien"]
            analyse["source"] = deal["source"]
            deals_trouves.append(analyse)
        else:
            print(f"  💛 Prix {prix}$ — au-dessus du seuil, ignoré")

    # 3. Traiter les deals trouvés
    if not deals_trouves:
        print("\n😴 Aucun deal exceptionnel aujourd'hui. On surveille...")
        return

    print(f"\n🎯 {len(deals_trouves)} deal(s) trouvé(s)!\n")

    # Trier par score d'urgence (les plus urgents en premier)
    deals_trouves.sort(key=lambda x: x.get("score_urgence", 0), reverse=True)

    for deal in deals_trouves:
        ville   = deal.get("ville_destination", "")
        prix    = deal.get("prix_deal", 0)
        urgence = deal.get("score_urgence", 5)

        print(f"\n✍️  Rédaction email: YUL → {ville} à {prix}$...")
        email = rediger_email_deal(deal, deal.get("lien_original", ""))

        if not email:
            print("  ⚠️  Impossible de rédiger l'email")
            continue

        print(f"  📧 Objet: {email['objet']}")

        # Urgence élevée = envoi immédiat à toute la liste
        # Urgence faible = email de test seulement
        if urgence >= 7:
            print(f"  🚨 Urgence {urgence}/10 — envoi à toute la liste!")
            envoyer_via_brevo(email["objet"], email["corps_html"], urgence)
        else:
            print(f"  🧪 Urgence {urgence}/10 — envoi de test à {TON_EMAIL}")
            envoyer_email_test(email["objet"], email["corps_html"])

    print("\n✅ Deal Hunter terminé!")
    print("=" * 55)


if __name__ == "__main__":
    main()
