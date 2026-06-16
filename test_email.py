import requests
import os

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
TON_EMAIL = "alaouisana0@gmail.com"

corps_html = """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 10px 10px 0 0; text-align: center;">
<h1 style="margin: 0;">✈️ VolsDeals</h1>
<p style="margin: 5px 0; opacity: 0.8;">Alertes vols Montreal → Maroc et Europe</p>
</div>
<div style="background: #ff4757; color: white; padding: 15px; text-align: center;">
<strong>CECI EST UN EMAIL DE TEST</strong>
</div>
<div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
<h2 style="color: #1a1a2e;">DEAL: YUL → Casablanca a 389$</h2>
<p>Hey! C'est Sana de VolsDeals.</p>
<p>J'ai repere une <strong>erreur tarifaire</strong> sur Air Maroc.</p>
<div style="background: white; border-left: 4px solid #ff4757; padding: 15px; margin: 20px 0;">
<p>Depart: Montreal (YUL)</p>
<p>Arrivee: Casablanca (CMN)</p>
<p>Prix: 389$ aller-retour</p>
<p>Prix normal: 880$</p>
<p>Economie: 56%</p>
</div>
<p>Bonne chance!<br><strong>Sana</strong><br>VolsDeals</p>
</div>
</div>
"""


def envoyer_email_test():
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "sender": {"name": "VolsDeals", "email": TON_EMAIL},
        "to": [{"email": TON_EMAIL}],
        "subject": "[TEST] YUL → Casablanca a 389$ - Erreur tarifaire!",
        "htmlContent": corps_html
    }
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code == 201:
        print("Email de test envoye avec succes a", TON_EMAIL)
    else:
        print("Erreur:", r.status_code, r.text)


if __name__ == "__main__":
    envoyer_email_test()
