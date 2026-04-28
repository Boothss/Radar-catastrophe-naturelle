"""
SENTINELLE OSINT — Script local avec carte interactive
Lance une surveillance en boucle toutes les 10 minutes.
Surveille : Séismes (USGS) + Tsunamis + Incendies NASA (carte seulement)
Envoie un email uniquement pour : séismes M6.0+ et alertes tsunami
"""

import requests
import folium
import time
import smtplib
import os

from email.message import EmailMessage
from datetime import datetime, timedelta
from folium.plugins import MarkerCluster

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
EMAIL_EXPEDITEUR  = "alexbailly82@gmail.com"
MOT_DE_PASSE_APP  = "typa rnce bazv ryyi"   # ← tes 16 caractères Gmail
FREQUENCE_SCAN    = 600                      # 10 minutes

SEUIL_SEISME_MAJEUR = 6.0   # email pour M6.0+
AGE_MAX_HEURES      = 120   # ignore les séismes > 5 jours

FICHIER_MEMOIRE = "sentinelle_db.txt"

# ==========================================
# 🧠 MÉMOIRE PERSISTANTE
# ==========================================
def charger_memoire_permanente():
    if not os.path.exists(FICHIER_MEMOIRE):
        return set()
    with open(FICHIER_MEMOIRE, "r") as f:
        return set(f.read().splitlines())

def sauvegarder_nouvel_id(id_event):
    with open(FICHIER_MEMOIRE, "a") as f:
        f.write(f"{id_event}\n")

memoire_alertes = charger_memoire_permanente()
print(f"🧠 Mémoire chargée : {len(memoire_alertes)} événement(s) déjà connu(s).")
print(f"📋 Alertes email actives : Tsunami + Séismes M{SEUIL_SEISME_MAJEUR}+")
print(f"🔕 Silencieux : incendies et séismes < M{SEUIL_SEISME_MAJEUR}\n")


# ==========================================
# 📧  ENVOI EMAIL
# ==========================================
def envoyer_alerte_email(sujet, lieu, magnitude, type_alerte):
    """Envoie un email HTML pour les séismes M6.0+ et tsunamis."""
    msg = EmailMessage()
    msg['Subject'] = sujet
    msg['From']    = EMAIL_EXPEDITEUR
    msg['To']      = EMAIL_EXPEDITEUR

    couleur_alerte = "#0056b3" if type_alerte == "TSUNAMI" else "#d9534f"
    icone          = "🌊" if type_alerte == "TSUNAMI" else "🔴"

    msg.set_content(f"ALERTE {type_alerte} : {lieu}\nMagnitude : {magnitude}")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px; margin: 0;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff;
                    border-radius: 8px; overflow: hidden;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);">

            <div style="background-color: {couleur_alerte}; color: #ffffff;
                        padding: 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">{icone} ALERTE {type_alerte}</h1>
            </div>

            <div style="padding: 30px;">
                <p style="font-size: 16px; color: #333333; margin-top: 0;">
                    La Sentinelle OSINT a détecté une menace critique.
                </p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee;
                                   width: 40%;"><strong>📍 Localisation</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee;
                                   color: #555555;">{lieu}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee;">
                            <strong>📊 Magnitude</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee;
                                   color: #555555; font-size: 18px;
                                   font-weight: bold;">{magnitude}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee;">
                            <strong>⏰ Heure (UTC)</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee;
                                   color: #555555;">
                            {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
                    </tr>
                </table>
            </div>

            <div style="background-color: #333333; color: #ffffff; padding: 15px;
                        text-align: center; font-size: 12px;">
                <p style="margin: 0;">
                    Sentinelle OSINT · Alertes : Tsunami + Séismes M{SEUIL_SEISME_MAJEUR}+ uniquement
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_EXPEDITEUR, MOT_DE_PASSE_APP)
            smtp.send_message(msg)
            print(f"   📧 [SUCCÈS] Email envoyé : {sujet}")
    except Exception as e:
        print(f"   ❌ [ERREUR GMAIL] : {e}")


# ==========================================
# 🌍  ANALYSE SÉISMES (USGS)
# ==========================================
def analyser_menaces_usgs(carte):
    print("🌍 Analyse des données sismiques (USGS)...")
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"

    try:
        donnees = requests.get(url, timeout=15).json()
        evenements = donnees.get('features', [])
    except Exception as e:
        print(f"   ❌ Erreur de connexion à l'USGS : {e}")
        return

    alertes_tsunami   = 0
    nouvelles_alertes = 0
    maintenant        = datetime.utcnow()

    for event in evenements:
        id_event         = event['id']
        prop             = event['properties']
        lon, lat, profondeur = event['geometry']['coordinates']

        timestamp    = prop['time'] / 1000
        heure_seisme = datetime.utcfromtimestamp(timestamp)
        heure_exacte = heure_seisme.strftime('%d/%m %H:%M UTC')
        age_heures   = (maintenant - heure_seisme).total_seconds() / 3600

        # Ignorer les séismes trop anciens
        if age_heures > AGE_MAX_HEURES:
            continue

        magnitude      = prop.get('mag') or 0.0
        lieu           = prop.get('place', 'Lieu inconnu')
        alerte_tsunami = prop.get('tsunami', 0) == 1
        url_usgs       = prop.get('url', '#')

        # ── CARTE : couleurs selon fraîcheur ──
        if alerte_tsunami:
            alertes_tsunami += 1
            couleur_tsunami  = "#0056b3"
            html_tsunami = f"""
            <div style="width:350px;font-family:'Segoe UI',sans-serif;color:#333;">
                <div style="display:flex;align-items:stretch;border:1px solid #ddd;
                            border-radius:8px;overflow:hidden;
                            border-left:4px solid {couleur_tsunami};">
                    <div style="background-color:{couleur_tsunami};width:100px;
                                display:flex;flex-direction:column;justify-content:center;
                                align-items:center;color:white;padding:10px;">
                        <div style="font-size:32px;margin-bottom:5px;">🌊</div>
                        <span style="font-size:14px;font-weight:bold;
                                     text-align:center;">DANGER<br>TSUNAMI</span>
                    </div>
                    <div style="flex:1;padding:12px;background-color:white;">
                        <h4 style="margin:0 0 8px 0;font-size:14px;
                                   color:{couleur_tsunami};border-bottom:1px solid #eee;
                                   padding-bottom:5px;">🚨 ALERTE VAGUE DÉTECTÉE</h4>
                        <p style="margin:5px 0;font-size:12px;"><b>📍 Origine :</b> {lieu}</p>
                        <p style="margin:5px 0;font-size:12px;"><b>💥 Magnitude :</b> {magnitude}</p>
                        <p style="margin:5px 0;font-size:12px;"><b>⏰ Heure :</b> {heure_exacte}</p>
                        <a href="{url_usgs}" target="_blank"
                           style="font-size:10px;color:#007bff;font-weight:bold;">
                           SUIVI OFFICIEL USGS →</a>
                    </div>
                </div>
            </div>"""
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(html_tsunami, max_width=400),
                icon=folium.Icon(color='darkblue', icon='tint')
            ).add_to(carte)
            folium.Circle(
                location=[lat, lon], radius=magnitude * 30000,
                color='#0056b3', fill=True, fill_opacity=0.3
            ).add_to(carte)

        else:
            if age_heures < 2:
                couleur_marqueur = '#ff0000'
                opacite          = 0.9
                titre            = "🔴 SÉISME IMMÉDIAT"
            elif age_heures < 24:
                couleur_marqueur = '#ff9900'
                opacite          = 0.7
                titre            = "🟠 SÉISME RÉCENT"
            else:
                couleur_marqueur = '#aaaaaa'
                opacite          = 0.5
                titre            = "⚪ HISTORIQUE (5J)"

            html_popup = f"""
            <div style="width:320px;font-family:'Segoe UI',sans-serif;color:#333;">
                <div style="border:1px solid #ddd;border-radius:8px;overflow:hidden;">
                    <div style="background-color:{couleur_marqueur};color:white;
                                padding:10px;text-align:center;">
                        <span style="font-size:16px;font-weight:bold;">{titre}</span>
                    </div>
                    <div style="padding:12px;background-color:white;">
                        <p style="margin:5px 0;font-size:12px;"><b>📍 Lieu :</b> {lieu}</p>
                        <p style="margin:5px 0;font-size:12px;">
                            <b>📊 Magnitude :</b>
                            <span style="font-size:16px;font-weight:bold;
                                         color:{couleur_marqueur};">{magnitude}</span></p>
                        <p style="margin:5px 0;font-size:12px;">
                            <b>📉 Profondeur :</b> {profondeur} km</p>
                        <p style="margin:5px 0;font-size:12px;">
                            <b>⏰ Il y a :</b> {int(age_heures)}h</p>
                        <a href="{url_usgs}" target="_blank"
                           style="font-size:10px;color:#007bff;font-weight:bold;">
                           USGS INFO →</a>
                    </div>
                </div>
            </div>"""
            folium.CircleMarker(
                location=[lat, lon],
                radius=magnitude * 2,
                color=couleur_marqueur,
                fill=True,
                fill_opacity=opacite,
                popup=folium.Popup(html_popup, max_width=400)
            ).add_to(carte)

        # ── EMAIL : uniquement tsunami ou M6.0+ ──
        if id_event not in memoire_alertes:
            alerte_requise = False

            if alerte_tsunami:
                alerte_requise = True
                type_alerte    = "TSUNAMI"
                sujet_mail     = f"🌊 ALERTE TSUNAMI : {lieu}"
            elif magnitude >= SEUIL_SEISME_MAJEUR:
                alerte_requise = True
                type_alerte    = "SÉISME"
                sujet_mail     = f"🔴 SÉISME MAJEUR M{magnitude} : {lieu}"
            # Pas d'email pour les séismes < M6.0

            if alerte_requise:
                envoyer_alerte_email(
                    sujet=sujet_mail,
                    lieu=lieu,
                    magnitude=magnitude,
                    type_alerte=type_alerte
                )
                nouvelles_alertes += 1

            # Mémoire pour tous les événements vus
            memoire_alertes.add(id_event)
            sauvegarder_nouvel_id(id_event)

    print(f"   🌊 {alertes_tsunami} zone(s) Tsunami. 📩 {nouvelles_alertes} nouvelle(s) alerte(s) envoyée(s).")


# ==========================================
# 🔥  INCENDIES NASA (CARTE SEULEMENT, PAS D'EMAIL)
# ==========================================
def ajouter_incendies_nasa(carte):
    print("🔥 Connexion NASA EONET (carte seulement, aucun email)...")
    url = "https://eonet.gsfc.nasa.gov/api/v3/categories/wildfires?status=open"

    try:
        donnees  = requests.get(url, timeout=15).json()
        incendies = donnees.get('events', [])

        cluster_incendies = MarkerCluster(name="Incendies Actifs").add_to(carte)

        for feu in incendies:
            nom_feu     = feu['title']
            coordonnees = feu['geometry'][-1]['coordinates']
            lon, lat    = coordonnees[0], coordonnees[1]

            # Mémoire sans email
            feu_id = feu.get("id", "")
            if feu_id not in memoire_alertes:
                memoire_alertes.add(feu_id)
                sauvegarder_nouvel_id(feu_id)

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(
                    f"<b>🔥 INCENDIE ACTIF</b><br>{nom_feu}<br>"
                    f"<small style='color:#888'>Affiché sur carte · pas d'email</small>",
                    max_width=300
                ),
                icon=folium.Icon(color='orange', icon='fire', prefix='fa')
            ).add_to(cluster_incendies)

        print(f"   🔥 {len(incendies)} incendies affichés sur la carte · aucun email envoyé.")
    except Exception as e:
        print(f"   ❌ Erreur NASA : {e}")


# ==========================================
# 🚀  BOUCLE PRINCIPALE
# ==========================================
def lancer_sentinelle():
    print("🛡️  DÉMARRAGE SENTINELLE OSINT")
    print(f"   Alertes email → Tsunami + M{SEUIL_SEISME_MAJEUR}+ uniquement")
    print("   Appuie sur Ctrl+C pour arrêter.\n")

    cycle   = 1
    fichier = "radar_automatise.html"

    while True:
        heure_actuelle = datetime.utcnow().strftime("%H:%M:%S UTC")
        print(f"--- [CYCLE {cycle} · {heure_actuelle}] ---")

        carte_interactive = folium.Map(
            location=[20.0, 0.0], zoom_start=2, tiles='CartoDB dark_matter'
        )

        analyser_menaces_usgs(carte_interactive)
        ajouter_incendies_nasa(carte_interactive)

        carte_interactive.save(fichier)
        if cycle == 1:
            print(f"✅ Carte générée → ouvre '{fichier}' dans ton navigateur.")

        print(f"⏳ Prochain scan dans {FREQUENCE_SCAN // 60} minutes...\n")
        time.sleep(FREQUENCE_SCAN)
        cycle += 1


if __name__ == "__main__":
    lancer_sentinelle()
