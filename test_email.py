"""
VolsDeals — Test Email
Envoie un faux deal de test pour vérifier que Brevo fonctionne
"""
import requests
import os

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
TON_EMAIL = "alaouisana0@gmail.com"

corps_html = """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 10px 10px 0 0; text-align: center;">
      <h1 style="margin: 0;">✈️ VolsDeals</h1>
          <p style="margin: 5px 0; opacity: 0.8;">Alertes vols Montréal → Maroc & Europe</p>
            </div>

              <div style="background: #ff4757; color: white; padding: 15px; text-align: center;">
                  <strong>🚨 CECI EST UN EMAIL DE TEST 🚨</strong>
                    </div>

                      <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
                          <h2 style="color: #1a1a2e;">🔥 DEAL: YUL → Casablanca à 389$ !</h2>

                              <p>Hey ! C'est Sana de VolsDeals 👋</p>

                                  <p>J'ai repéré une <strong>erreur tarifaire</strong> sur Air Maroc — des billets Montréal (YUL) → Casablanca (CMN) à seulement <strong>389$ aller-retour</strong> en classe économique !</p>

                                      <div style="background: white; border-left: 4px solid #ff4757; padding: 15px; margin: 20px 0; border-radius: 5px;">
                                            <p style="margin: 5px 0;">🛫 <strong>Départ :</strong> Montréal (YUL)</p>
                                                  <p style="margin: 5px 0;">🛬 <strong>Arrivée :</strong> Casablanca (CMN)</p>
                                                        <p style="margin: 5px 0;">💰 <strong>Prix :</strong> 389$ aller-retour</p>
                                                              <p style="margin: 5px 0;">📉 <strong>Prix normal :</strong> 880$</p>
                                                                    <p style="margin: 5px 0;">🎯 <strong>Économie :</strong> 56% (491$ de rabais !)</p>
                                                                          <p style="margin: 5px 0;">⏰ <strong>Urgence :</strong> Expire dans ~2h</p>
                                                                              </div>

                                                                                  <p><strong>Comment réserver :</strong></p>
                                                                                      <ol>
                                                                                            <li>Clique sur le bouton ci-dessous</li>
                                                                                                  <li>Sélectionne tes dates (flexible = meilleures chances)</li>
                                                                                                        <li>Réserve AVANT que le prix remonte !</li>
                                                                                                            </ol>
                                                                                                            
                                                                                                                <div style="text-align: center; margin: 30px 0;">
                                                                                                                      <a href="https://www.airmaroc.com" style="background: #ff4757; color: white; padding: 15px 30px; border-radius: 25px; text-decoration: none; font-weight: bold; font-size: 16px;">
                                                                                                                              🛒 RÉSERVER MAINTENANT
                                                                                                                                    </a>
                                                                                                                                        </div>
                                                                                                                                        
                                                                                                                                            <p style="color: #666; font-size: 12px;">⚠️ Erreur tarifaire — peut disparaître à tout moment. VolsDeals n'est pas responsable si le prix change.</p>
                                                                                                                                            
                                                                                                                                                <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">
                                                                                                                                                
                                                                                                                                                    <p>Bonne chance ! ✈️<br>
                                                                                                                                                        <strong>Sana</strong><br>
                                                                                                                                                            <em>VolsDeals — Des vols pas chers depuis Montréal</em></p>
                                                                                                                                                              </div>
                                                                                                                                                              
                                                                                                                                                                <p style="text-align: center; color: #999; font-size: 11px; margin-top: 15px;">
                                                                                                                                                                    [EMAIL DE TEST — Le vrai système est opérationnel !]
                                                                                                                                                                      </p>
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
                                                                                                                                                                                                                              "subject": "[TEST] ✈️ YUL → Casablanca à 389$ — Erreur tarifaire !",
                                                                                                                                                                                                                                      "htmlContent": corps_html
                                                                                                                                                                                                                                          }
                                                                                                                                                                                                                                              r = requests.post(url, headers=headers, json=payload)
                                                                                                                                                                                                                                                  if r.status_code == 201:
                                                                                                                                                                                                                                                          print("✅ Email de test envoyé avec succès à", TON_EMAIL)
                                                                                                                                                                                                                                                              else:
                                                                                                                                                                                                                                                                      print(f"❌ Erreur: {r.status_code} — {r.text}")
                                                                                                                                                                                                                                                                      
                                                                                                                                                                                                                                                                      if __name__ == "__main__":
                                                                                                                                                                                                                                                                          envoyer_email_test()
