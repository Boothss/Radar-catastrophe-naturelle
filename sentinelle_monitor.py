"""
SENTINELLE OSINT — Script de surveillance autonome 24/7
Tourne toutes les 10 minutes via GitHub Actions.
Surveille : Séismes (USGS) + Tsunamis
Envoie un email uniquement pour : séismes M6.0+ et alertes tsunami
Génère une carte HTML publiée sur GitHub Pages
"""

import requests
import smtplib
import os
import time
import folium

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from folium.plugins import MarkerCluster

# ==========================================
# ⚙️  CONFIG (via secrets GitHub)
# ==========================================
EMAIL_EXPEDITEUR   = os.environ.get("EMAIL_EXPEDITEUR", "alexbailly82@gmail.com")
EMAIL_PASSWORD     = os.environ.get("EMAIL_PASSWORD",   "")
EMAIL_DESTINATAIRE = EMAIL_EXPEDITEUR

# Seuils d'alerte
SEUIL_SEISME_MAJEUR = 6.0
AGE_MAX_HEURES      = 120   # ignore les séismes > 5 jours

# Fichier mémoire
FICHIER_MEMOIRE = "sentinelle_db.txt"

# Dossier de sortie pour la carte (publié sur GitHub Pages)
DOSSIER_CARTE = "map_output"
FICHIER_CARTE = f"{DOSSIER_CARTE}/index.html"

# ==========================================
# 💾  MÉMOIRE PERSISTANTE
# ==========================================
def charger_memoire():
    if not os.path.exists(FICHIER_MEMOIRE):
        return set()
    with open(FICHIER_MEMOIRE, "r") as f:
        ids = set(line.strip() for line in f if line.strip())
    print(f"[MÉMOIRE] {len(ids)} événement(s) déjà connu(s)")
    return ids

def sauvegarder_id(event_id):
    with open(FICHIER_MEMOIRE, "a") as f:
        f.write(f"{event_id}\n")

# ==========================================
# 📧  ENVOI EMAIL
# ==========================================
def envoyer_email(sujet, alertes):
    if not alertes:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = EMAIL_EXPEDITEUR
    msg["To"]      = EMAIL_DESTINATAIRE

    plain_lines = [
        "SENTINELLE OSINT · Surveillance Sismique Mondiale",
        "=" * 52,
        f"  {len(alertes)} NOUVELLE(S) MENACE(S) DÉTECTÉE(S)",
        "=" * 52,
    ]
    for a in alertes:
        plain_lines += [
            "",
            f"  TYPE       : {a['type']}",
            f"  LIEU       : {a['lieu']}",
            f"  MAGNITUDE  : {a['magnitude']}",
            f"  PROFONDEUR : {a.get('profondeur', '—')} km",
            f"  HEURE UTC  : {a['heure']}",
            f"  LIEN USGS  : {a.get('url', '—')}",
            "",
            "  " + "-" * 50,
        ]
    plain_lines.append("\nSource : USGS Earthquake Hazards Program")
    plain_text = "\n".join(plain_lines)

    cards_html = ""
    for a in alertes:
        mag = a["magnitude"]

        if a["type"] == "TSUNAMI":
            accent = "#0056b3"
            bg     = "rgba(0,86,179,0.08)"
            icone  = "🌊"
            badge  = "DANGER TSUNAMI"
        else:
            accent = "#FF3B30"
            bg     = "rgba(255,59,48,0.08)"
            icone  = "🔴"
            badge  = f"SÉISME MAJEUR M{mag}"

        lien_html = ""
        if a.get("url"):
            lien_html = f"""
            <a href="{a['url']}" style="display:inline-block;margin-top:14px;font-size:11px;
               font-family:monospace;color:{accent};text-decoration:none;
               border:1px solid {accent}40;padding:4px 12px;border-radius:4px;">
              SUIVI OFFICIEL USGS →
            </a>"""

        cards_html += f"""
        <div style="background:{bg};border:1px solid {accent}40;border-left:4px solid {accent};
                    border-radius:10px;padding:20px 24px;margin-bottom:20px;">
          <div style="font-size:10px;font-family:monospace;color:{accent};
                      letter-spacing:.12em;text-transform:uppercase;margin-bottom:10px;">
            {icone} {badge}
          </div>
          <div style="font-size:18px;font-weight:700;color:#FFFFFF;margin-bottom:16px;
                      line-height:1.3;">{a['lieu']}</div>
          <table style="width:100%;border-collapse:collapse;margin-bottom:4px;">
            <tr>
              <td style="padding:5px 12px 5px 0;font-size:11px;color:#64748B;
                         font-family:monospace;white-space:nowrap;">MAGNITUDE</td>
              <td style="padding:5px 0;font-size:20px;font-weight:700;color:{accent};">{mag}</td>
            </tr>
            <tr>
              <td style="padding:5px 12px 5px 0;font-size:11px;color:#64748B;
                         font-family:monospace;">PROFONDEUR</td>
              <td style="padding:5px 0;font-size:13px;color:#E2E8F0;">
                {a.get('profondeur', '—')} km</td>
            </tr>
            <tr>
              <td style="padding:5px 12px 5px 0;font-size:11px;color:#64748B;
                         font-family:monospace;">HEURE UTC</td>
              <td style="padding:5px 0;font-size:13px;color:#E2E8F0;
                         font-family:monospace;">{a['heure']}</td>
            </tr>
          </table>
          {lien_html}
        </div>"""

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html_body = f"""
    <html><body style="margin:0;padding:0;background:#050810;">
      <div style="max-width:620px;margin:0 auto;padding:32px 24px;
                  font-family:'Segoe UI',Arial,sans-serif;">
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:28px;
                    padding-bottom:20px;border-bottom:1px solid #0F1E38;">
          <div style="background:linear-gradient(135deg,#FF3B30,#F59E0B);
                      border-radius:12px;width:48px;height:48px;font-size:24px;
                      display:flex;align-items:center;justify-content:center;">🛡</div>
          <div>
            <div style="color:#FFFFFF;font-size:20px;font-weight:700;
                        letter-spacing:.15em;">SENTINELLE OSINT</div>
            <div style="color:#4A6FA5;font-size:10px;letter-spacing:.1em;margin-top:2px;">
              SURVEILLANCE SISMIQUE MONDIALE · USGS</div>
          </div>
        </div>
        <div style="background:rgba(255,59,48,0.08);border:1px solid rgba(255,59,48,0.3);
                    border-radius:10px;padding:14px 20px;margin-bottom:24px;">
          <div style="font-size:13px;font-family:monospace;color:#FF6B6B;">
            ● {len(alertes)} NOUVELLE(S) MENACE(S) · {now_str}</div>
        </div>
        {cards_html}
        <div style="margin-top:28px;padding-top:20px;border-top:1px solid #0F1E38;
                    font-size:11px;color:#374151;font-family:monospace;line-height:1.8;">
          <div>Source : USGS Earthquake Hazards Program</div>
          <div>Alertes : Séismes M6.0+ et tsunamis uniquement</div>
          <div>Scan automatique toutes les 10 minutes via GitHub Actions</div>
        </div>
      </div>
    </body></html>"""

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_EXPEDITEUR, EMAIL_PASSWORD)
            server.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
        print(f"[EMAIL] ✅ Envoyé : {sujet}")
        return True
    except Exception as e:
        print(f"[EMAIL] ❌ Erreur : {e}")
        return False

# ==========================================
# 🌍  SURVEILLANCE SÉISMES (USGS)
# ==========================================
def analyser_seismes(memoire, carte):
    print("[USGS] Récupération des données sismiques...")
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        evenements = r.json().get("features", [])
    except Exception as e:
        print(f"[USGS] ❌ Erreur connexion : {e}")
        return []

    maintenant    = datetime.now(timezone.utc)
    nouvelles_alertes = []
    nouveaux_ids  = []

    for event in evenements:
        event_id         = event["id"]
        prop             = event["properties"]
        coords           = event["geometry"]["coordinates"]
        lon, lat, profondeur = coords[0], coords[1], coords[2]

        ts           = prop["time"] / 1000
        heure_seisme = datetime.fromtimestamp(ts, tz=timezone.utc)
        age_heures   = (maintenant - heure_seisme).total_seconds() / 3600
        heure_str    = heure_seisme.strftime("%Y-%m-%d %H:%M UTC")

        if age_heures > AGE_MAX_HEURES:
            continue

        try:
            magnitude = float(prop.get("mag") or 0)
        except (TypeError, ValueError):
            magnitude = 0.0

        lieu           = prop.get("place", "Lieu inconnu")
        alerte_tsunami = prop.get("tsunami", 0) == 1
        url_usgs       = prop.get("url", "")

        # ── CARTE ──
        if alerte_tsunami:
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(
                    f"<b>🌊 DANGER TSUNAMI</b><br>{lieu}<br>M{magnitude}<br>"
                    f"{heure_str}<br><a href='{url_usgs}' target='_blank'>USGS →</a>",
                    max_width=300
                ),
                icon=folium.Icon(color='darkblue', icon='tint')
            ).add_to(carte)
            folium.Circle(
                location=[lat, lon], radius=magnitude * 30000,
                color='#0056b3', fill=True, fill_opacity=0.3
            ).add_to(carte)
        else:
            if age_heures < 2:
                couleur = '#ff0000'; opacite = 0.9; titre = "🔴 SÉISME IMMÉDIAT"
            elif age_heures < 24:
                couleur = '#ff9900'; opacite = 0.7; titre = "🟠 SÉISME RÉCENT"
            else:
                couleur = '#aaaaaa'; opacite = 0.5; titre = "⚪ HISTORIQUE (5J)"

            folium.CircleMarker(
                location=[lat, lon],
                radius=magnitude * 2,
                color=couleur,
                fill=True,
                fill_opacity=opacite,
                popup=folium.Popup(
                    f"<b>{titre}</b><br>{lieu}<br>M{magnitude} · {round(profondeur,1)} km<br>"
                    f"{heure_str}<br><a href='{url_usgs}' target='_blank'>USGS →</a>",
                    max_width=300
                )
            ).add_to(carte)

        # ── EMAIL ──
        if event_id not in memoire:
            nouveaux_ids.append(event_id)
            if alerte_tsunami:
                nouvelles_alertes.append({
                    "type": "TSUNAMI", "lieu": lieu, "magnitude": magnitude,
                    "profondeur": round(profondeur, 1), "heure": heure_str, "url": url_usgs,
                })
            elif magnitude >= SEUIL_SEISME_MAJEUR:
                nouvelles_alertes.append({
                    "type": "SÉISME MAJEUR", "lieu": lieu, "magnitude": magnitude,
                    "profondeur": round(profondeur, 1), "heure": heure_str, "url": url_usgs,
                })

    for eid in nouveaux_ids:
        memoire.add(eid)
        sauvegarder_id(eid)

    print(f"[USGS] {len(evenements)} événements · {len(nouvelles_alertes)} nouvelle(s) alerte(s)")
    return nouvelles_alertes

# ==========================================
# 🔥  INCENDIES NASA (carte seulement)
# ==========================================
def ajouter_incendies_nasa(memoire, carte):
    print("[NASA] Récupération des incendies (carte seulement)...")
    url = "https://eonet.gsfc.nasa.gov/api/v3/categories/wildfires?status=open"

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        incendies = r.json().get("events", [])
    except Exception as e:
        print(f"[NASA] ❌ Erreur connexion : {e}")
        return

    cluster = MarkerCluster(name="Incendies Actifs").add_to(carte)

    for feu in incendies:
        feu_id = feu.get("id", "")
        nom    = feu.get("title", "Incendie inconnu")
        coords = feu.get("geometry", [])
        if not coords:
            continue
        lon, lat = coords[-1]["coordinates"][0], coords[-1]["coordinates"][1]

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(f"<b>🔥 INCENDIE ACTIF</b><br>{nom}", max_width=300),
            icon=folium.Icon(color='orange', icon='fire', prefix='fa')
        ).add_to(cluster)

        if feu_id not in memoire:
            memoire.add(feu_id)
            sauvegarder_id(feu_id)

    print(f"[NASA] {len(incendies)} incendies sur la carte · aucun email")

# ==========================================
# 🗺️  GÉNÉRATION DE LA CARTE HTML
# ==========================================
def generer_carte():
    """Crée la carte Folium et la sauvegarde dans map_output/index.html."""
    os.makedirs(DOSSIER_CARTE, exist_ok=True)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    carte = folium.Map(location=[20.0, 0.0], zoom_start=2, tiles='CartoDB dark_matter')

    # Légende en bas à droite
    legende_html = f"""
    <div style="position:fixed;bottom:30px;right:15px;z-index:1000;
                background:rgba(5,8,16,0.92);border:1px solid #1e3a5f;
                border-radius:10px;padding:14px 18px;font-family:monospace;
                font-size:12px;color:#CBD5E1;min-width:220px;">
      <div style="color:#FFFFFF;font-weight:700;font-size:13px;
                  margin-bottom:10px;letter-spacing:.08em;">🛡 SENTINELLE OSINT</div>
      <div style="margin-bottom:6px;">
        <span style="color:#FF3B30;">●</span> Séisme &lt; 2h
      </div>
      <div style="margin-bottom:6px;">
        <span style="color:#FF9900;">●</span> Séisme &lt; 24h
      </div>
      <div style="margin-bottom:6px;">
        <span style="color:#AAAAAA;">●</span> Historique (5j)
      </div>
      <div style="margin-bottom:6px;">
        <span style="color:#0056b3;">●</span> Alerte Tsunami
      </div>
      <div style="margin-bottom:10px;">
        <span style="color:#FF6B35;">●</span> Incendie NASA
      </div>
      <div style="border-top:1px solid #1e3a5f;padding-top:8px;
                  font-size:10px;color:#4A6FA5;">
        Mis à jour : {now_str}<br>
        Alertes email : M6.0+ · Tsunamis
      </div>
    </div>"""

    carte.get_root().html.add_child(folium.Element(legende_html))
    return carte

# ==========================================
# 🚀  MAIN
# ==========================================
if __name__ == "__main__":
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[SENTINELLE] Scan démarré · {now}")
    print("=" * 52)

    if not EMAIL_PASSWORD:
        print("[ERREUR] EMAIL_PASSWORD non défini dans les secrets GitHub")
        exit(1)

    memoire = charger_memoire()
    carte   = generer_carte()

    alertes_seismes = analyser_seismes(memoire, carte)
    ajouter_incendies_nasa(memoire, carte)

    # Sauvegarde de la carte dans map_output/index.html
    os.makedirs(DOSSIER_CARTE, exist_ok=True)
    carte.save(FICHIER_CARTE)
    print(f"[CARTE] ✅ Générée → {FICHIER_CARTE}")

    # Email si menace critique
    if alertes_seismes:
        tsunamis = [a for a in alertes_seismes if a["type"] == "TSUNAMI"]
        majeurs  = [a for a in alertes_seismes if a["magnitude"] >= SEUIL_SEISME_MAJEUR]

        if tsunamis:
            sujet = f"🌊 ALERTE TSUNAMI — {tsunamis[0]['lieu']}"
        elif majeurs:
            sujet = f"🔴 SÉISME MAJEUR M{majeurs[0]['magnitude']} — {majeurs[0]['lieu']}"
        else:
            sujet = f"⚠️ SENTINELLE — {len(alertes_seismes)} menace(s) détectée(s)"

        envoyer_email(sujet, alertes_seismes)
    else:
        print("[OK] Aucune nouvelle menace critique — pas d'email envoyé")

    print("=" * 52)
    print("[SENTINELLE] Scan terminé")
