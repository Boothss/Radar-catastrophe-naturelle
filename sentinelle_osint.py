import requests
import folium
import time
import smtplib
import os

from email.message import EmailMessage
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError
from datetime import datetime, timedelta
from folium.plugins import MarkerCluster

# ==========================================
# ⚙️ CONFIGURATION DU CENTRE DE COMMANDEMENT
# ==========================================
EMAIL_EXPEDITEUR = "alexbailly82@gmail.com" # Remplace par ton adresse
MOT_DE_PASSE_APP = "typa rnce bazv ryyi" # Remplace par tes 16 caractères
FREQUENCE_SCAN = 600 # 10 minutes

FICHIER_MEMOIRE = "sentinelle_db.txt" # Le fichier de sauvegarde "Pro"

# ==========================================
# 🧠 INITIALISATION DES OUTILS & MÉMOIRE PRO
# ==========================================
geolocator = Nominatim(user_agent="radar_crise_osint")

def charger_memoire_permanente():
    """Charge les IDs des catastrophes déjà notifiées depuis le disque dur."""
    if not os.path.exists(FICHIER_MEMOIRE):
        return set()
    with open(FICHIER_MEMOIRE, "r") as f:
        return set(f.read().splitlines())

def sauvegarder_nouvel_id(id_event):
    """Ajoute un ID au fichier texte de manière permanente."""
    with open(FICHIER_MEMOIRE, "a") as f:
        f.write(f"{id_event}\n")

# Au démarrage, le robot lit le fichier pour retrouver ses souvenirs
memoire_alertes = charger_memoire_permanente()
print(f"🧠 Mémoire chargée : {len(memoire_alertes)} événement(s) déjà connu(s).")


def envoyer_alerte_email_pro(sujet, lieu, magnitude, type_alerte, ville_touchee=None):
    """Envoie un e-mail d'alerte avec un design professionnel en HTML."""
    msg = EmailMessage()
    msg['Subject'] = sujet
    msg['From'] = EMAIL_EXPEDITEUR
    msg['To'] = EMAIL_EXPEDITEUR

    couleur_alerte = "#d9534f" if type_alerte == "TSUNAMI" else "#f0ad4e"
    icone = "🌊" if type_alerte == "TSUNAMI" else "🔴"
    
    texte_brut = f"ALERTE {type_alerte} : {lieu}\nMagnitude : {magnitude}"
    msg.set_content(texte_brut)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px; margin: 0;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            <div style="background-color: {couleur_alerte}; color: #ffffff; padding: 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">{icone} ALERTE {type_alerte}</h1>
            </div>
            <div style="padding: 30px;">
                <p style="font-size: 16px; color: #333333; margin-top: 0;">La Sentinelle OSINT a détecté une menace nécessitant votre attention immédiate.</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee; width: 40%;"><strong>📍 Localisation</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee; color: #555555;">{lieu}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee;"><strong>📊 Magnitude</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee; color: #555555; font-size: 18px; font-weight: bold;">{magnitude}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee;"><strong>⏰ Heure (Serveur)</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eeeeee; color: #555555;">{datetime.now().strftime('%H:%M:%S')}</td>
                    </tr>
                </table>
    """

    if ville_touchee:
        html_content += f"""
                <div style="margin-top: 25px; padding: 15px; background-color: #ffeaea; border-left: 5px solid #d9534f;">
                    <h3 style="margin: 0 0 10px 0; color: #d9534f;">🏙️ IMPACT URBAIN DÉTECTÉ</h3>
                    <p style="margin: 0; color: #555;">Ce séisme a été enregistré à proximité immédiate de : <strong>{ville_touchee}</strong>. Risque humanitaire élevé.</p>
                </div>
        """

    html_content += """
            </div>
            <div style="background-color: #333333; color: #ffffff; padding: 15px; text-align: center; font-size: 12px;">
                <p style="margin: 0;">Généré automatiquement par Sentinelle OSINT Python</p>
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
            print(f"   📧 [SUCCÈS] Rapport envoyé pour : {sujet}")
    except Exception as e:
        print(f"   ❌ [ERREUR GMAIL] : {e}")

def verifier_impact_urbain(lat, lon):
    try:
        location = geolocator.reverse((lat, lon), timeout=5)
        if location and 'address' in location.raw:
            return location.raw['address'].get('city') or location.raw['address'].get('town') or location.raw['address'].get('village')
    except GeopyError:
        return None
    return None

def analyser_menaces_usgs(carte):
    print("🌍 Analyse des données sismiques (USGS)...")
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
    
    try:
        donnees = requests.get(url).json()
        evenements = donnees.get('features', [])
    except Exception as e:
        print(f"   ❌ Erreur de connexion à l'USGS : {e}")
        return

    alertes_tsunami = 0
    nouvelles_alertes = 0
    maintenant = datetime.now()

    for event in evenements:
        id_event = event['id']
        prop = event['properties']
        lon, lat, profondeur = event['geometry']['coordinates']
        
        timestamp = prop['time'] / 1000
        heure_seisme = datetime.fromtimestamp(timestamp)
        heure_exacte = heure_seisme.strftime('%d/%m %H:%M')
        
        # --- CALCUL DE L'ÂGE DU SÉISME ---
       # --- CALCUL DE L'ÂGE DU SÉISME ---
        age_heures = (maintenant - heure_seisme).total_seconds() / 3600
        
        # 🛑 NOUVEAU FILTRE : On ignore ce qui a plus de 5 jours (120 heures)
        if age_heures > 120:
            continue # Le mot-clé "continue" fait passer la boucle au séisme suivant !
        
        ressenti = prop.get('felt') or "Non signalé"
        magnitude = prop['mag']
        lieu = prop['place']
        alerte_tsunami = prop['tsunami'] == 1
        
        # --- LOGIQUE DE CARTOGRAPHIE PRO (Couleurs Temporelles) ---
        if alerte_tsunami:
            alertes_tsunami += 1
            couleur_tsunami = "#0056b3"
            
            html_tsunami = f"""
            <div style="width: 350px; font-family: 'Segoe UI', sans-serif; color: #333;">
                <div style="display: flex; align-items: stretch; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; border-left: 4px solid {couleur_tsunami};">
                    <div style="background-color: {couleur_tsunami}; width: 100px; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white; padding: 10px;">
                        <div style="font-size: 32px; margin-bottom: 5px;">🌊</div>
                        <span style="font-size: 14px; font-weight: bold; text-align: center;">DANGER<br>TSUNAMI</span>
                    </div>
                    <div style="flex: 1; padding: 12px; background-color: white;">
                        <h4 style="margin: 0 0 8px 0; font-size: 14px; color: {couleur_tsunami}; border-bottom: 1px solid #eee; padding-bottom: 5px;">🚨 ALERTE VAGUE DÉTECTÉE</h4>
                        <p style="margin: 5px 0; font-size: 12px;"><b>📍 Origine :</b> {lieu}</p>
                        <p style="margin: 5px 0; font-size: 12px;"><b>💥 Mag init :</b> {magnitude}</p>
                        <p style="margin: 5px 0; font-size: 12px;"><b>⏰ Heure :</b> {heure_exacte}</p>
                        <a href="{prop['url']}" target="_blank" style="font-size: 10px; color: #007bff; font-weight: bold;">SUIVI OFFICIEL →</a>
                    </div>
                </div>
            </div>
            """
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
            # Couleurs selon la fraîcheur de l'événement
            if age_heures < 2:
                couleur_marqueur = '#ff0000' # DIRECT (< 2h)
                opacite = 0.9
                titre = "🔴 SÉISME IMMÉDIAT"
            elif age_heures < 24:
                couleur_marqueur = '#ff9900' # RÉCENT (< 24h)
                opacite = 0.7
                titre = "🟠 SÉISME RÉCENT"
            else:
                couleur_marqueur = '#aaaaaa' # HISTORIQUE (Jusqu'à 5 jours)
                opacite = 0.5
                titre = "⚪ HISTORIQUE (5J)" # <-- On change le 7J en 5J ici

            html_popup = f"""
            <div style="width: 320px; font-family: 'Segoe UI', sans-serif; color: #333;">
                <div style="border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
                    <div style="background-color: {couleur_marqueur}; color: white; padding: 10px; text-align: center;">
                        <span style="font-size: 16px; font-weight: bold;">{titre}</span>
                    </div>
                    <div style="padding: 12px; background-color: white;">
                        <p style="margin: 5px 0; font-size: 12px;"><b>📍 Lieu :</b> {lieu}</p>
                        <p style="margin: 5px 0; font-size: 12px;"><b>📊 Magnitude :</b> <span style="font-size:16px; font-weight:bold; color:{couleur_marqueur};">{magnitude}</span></p>
                        <p style="margin: 5px 0; font-size: 12px;"><b>📉 Profondeur :</b> {profondeur} km</p>
                        <p style="margin: 5px 0; font-size: 12px;"><b>⏰ Moment :</b> Il y a {int(age_heures)} heure(s)</p>
                        <a href="{prop['url']}" target="_blank" style="font-size: 10px; color: #007bff; font-weight: bold;">USGS INFO →</a>
                    </div>
                </div>
            </div>
            """
            folium.CircleMarker(
                location=[lat, lon],
                radius=magnitude * 2,
                color=couleur_marqueur,
                fill=True,
                fill_opacity=opacite,
                popup=folium.Popup(html_popup, max_width=400)
            ).add_to(carte)

        # --- LOGIQUE D'ALERTE E-MAIL & MÉMOIRE PERMANENTE ---
        if id_event not in memoire_alertes:
            alerte_requise = False
            sujet_mail = ""
            
            if alerte_tsunami:
                alerte_requise = True
                sujet_mail = f"🌊 ALERTE TSUNAMI : {lieu}"
            elif magnitude >= 6.5: 
                alerte_requise = True
                sujet_mail = f"🔴 SÉISME MAJEUR ({magnitude}) : {lieu}"
            elif magnitude >= 5.5: 
                ville_touchee = verifier_impact_urbain(lat, lon)
                if ville_touchee:
                    alerte_requise = True
                    sujet_mail = f"🏙️ SÉISME URBAIN ({magnitude}) proche de {ville_touchee}"
                    lieu = f"{lieu} (Impact estimé sur : {ville_touchee})"
                time.sleep(1) 

            # Validation de l'alerte
            if alerte_requise:
                type_alerte = "TSUNAMI" if alerte_tsunami else "SÉISME"
                envoyer_alerte_email_pro(
                    sujet=sujet_mail, 
                    lieu=lieu, 
                    magnitude=magnitude, 
                    type_alerte=type_alerte, 
                    ville_touchee=ville_touchee if 'ville_touchee' in locals() else None
                )
                nouvelles_alertes += 1
            
            # 💾 SAUVEGARDE EN MÉMOIRE POUR TOUS LES NOUVEAUX ÉVÉNEMENTS (Même ceux sans mail)
            memoire_alertes.add(id_event)
            sauvegarder_nouvel_id(id_event)

    print(f"   🌊 {alertes_tsunami} zone(s) Tsunami. 📩 {nouvelles_alertes} nouvelle(s) alerte(s) envoyée(s).")


def ajouter_incendies_nasa(carte):
    print("🔥 Connexion aux satellites de la NASA (EONET)...")
    url = "https://eonet.gsfc.nasa.gov/api/v3/categories/wildfires?status=open"
    
    try:
        donnees = requests.get(url).json()
        incendies = donnees.get('events', [])
        
        cluster_incendies = MarkerCluster(name="Incendies Actifs").add_to(carte)
        
        for feu in incendies:
            nom_feu = feu['title']
            coordonnees = feu['geometry'][-1]['coordinates']
            lon, lat = coordonnees[0], coordonnees[1]
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(f"<b>🔥 INCENDIE ACTIF</b><br>{nom_feu}", max_width=300),
                icon=folium.Icon(color='orange', icon='fire', prefix='fa')
            ).add_to(cluster_incendies) 
            
        print(f"   🔥 {len(incendies)} incendies regroupés sur la carte.")
    except Exception as e:
        print(f"   ❌ Erreur de connexion à la NASA : {e}")

# ==========================================
# 🚀 LA BOUCLE PRINCIPALE (LA SENTINELLE)
# ==========================================
def lancer_sentinelle():
    print("🛡️ DÉMARRAGE DE LA SENTINELLE OSINT PRO...")
    print("Appuie sur Ctrl+C pour arrêter le programme.\n")
    
    cycle = 1
    fichier = "radar_automatise.html"

    while True:
        heure_actuelle = datetime.now().strftime("%H:%M:%S")
        print(f"--- [CYCLE {cycle} - {heure_actuelle}] ---")
        
        carte_interactive = folium.Map(location=[20.0, 0.0], zoom_start=2, tiles='CartoDB dark_matter')
        
        analyser_menaces_usgs(carte_interactive)
        ajouter_incendies_nasa(carte_interactive)
        
        carte_interactive.save(fichier)
        if cycle == 1:
            print(f"✅ Carte générée ! Ouvre '{fichier}' dans ton navigateur.")
        
        print(f"⏳ Prochain scan dans {FREQUENCE_SCAN / 60} minutes...\n")
        time.sleep(FREQUENCE_SCAN)
        cycle += 1

if __name__ == "__main__":
    lancer_sentinelle()