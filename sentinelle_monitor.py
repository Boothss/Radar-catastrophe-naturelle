"""
SENTINELLE OSINT — Script de surveillance autonome 24/7
Tourne toutes les 10 minutes via GitHub Actions.
Surveille : Séismes (USGS) + Tsunamis + Incendies (NASA)
Envoie un email si une menace est détectée.
"""

import requests
import smtplib
import json
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError

# ==========================================
# ⚙️  CONFIG (via secrets GitHub)
# ==========================================
EMAIL_EXPEDITEUR = os.environ.get("EMAIL_EXPEDITEUR", "alexbailly82@gmail.com")
EMAIL_PASSWORD   = os.environ.get("EMAIL_PASSWORD",   "")
EMAIL_DESTINATAIRE = EMAIL_EXPEDITEUR   # même adresse

# Seuils d'alerte
SEUIL_SEISME_MAJEUR  = 6.5   # email systématique
SEUIL_SEISME_URBAIN  = 5.5   # email si proche d'une ville
AGE_MAX_HEURES       = 120   # ignore les séismes > 5 jours

# Fichier mémoire (persisté via artifact GitHub Actions)
FICHIER_MEMOIRE = "sentinelle_db.txt"

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
# 🌍  GÉOLOCALISATION INVERSE
# ==========================================
geolocator = Nominatim(user_agent="sentinelle_osint_v2")

def verifier_impact_urbain(lat, lon):
    try:
        location = geolocator.reverse((lat, lon), timeout=8)
        if location and "address" in location.raw:
            addr = location.raw["address"]
            return addr.get("city") or addr.get("town") or addr.get("village")
    except GeopyError:
        pass
    return None

# ==========================================
# 📧  CONSTRUCTION ET ENVOI EMAIL
# ==========================================
def envoyer_email(sujet, alertes):
    """Envoie un email HTML récapitulatif des nouvelles menaces."""
    if not alertes:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = EMAIL_EXPEDITEUR
    msg["To"]      = EMAIL_DESTINATAIRE

    # ── TEXTE PLAIN ──
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
    plain_lines.append("\nSource : USGS Earthquake Hazards Program + NASA EONET")
    plain_text = "\n".join(plain_lines)

    # ── HTML ──
    cards_html = ""
    for a in alertes:
        # --- FIX : magnitude peut être un str "—" pour les incendies ---
        mag = a["magnitude"]
        mag_numerique = mag if isinstance(mag, (int, float)) else None

        if a["type"] == "TSUNAMI":
            accent = "#0056b3"
            bg     = "rgba(0,86,179,0.08)"
            icone  = "🌊"
            badge  = "DANGER TSUNAMI"
        elif mag_numerique is not None and mag_numerique >= SEUIL_SEISME_MAJEUR:
            accent = "#FF3B30"
            bg     = "rgba(255,59,48,0.08)"
            icone  = "🔴"
            badge  = f"SÉISME MAJEUR M{mag}"
        elif a["type"] == "INCENDIE":
            accent = "#FF6B35"
            bg     = "rgba(255,107,53,0.08)"
            icone  = "🔥"
            badge  = "INCENDIE ACTIF"
        else:
            accent = "#F59E0B"
            bg     = "rgba(245,158,11,0.08)"
            icone  = "🟠"
            badge  = f"SÉISME URBAIN M{mag}"

        ville_html = ""
        if a.get("ville"):
            ville_html = f"""
            <div style="margin-top:12px;padding:10px 14px;background:rgba(255,59,48,0.06);
                        border-left:3px solid #FF3B30;border-radius:0 6px 6px 0;">
              <div style="font-size:11px;font-family:monospace;color:#FF6B6B;margin-bottom:4px;">
                IMPACT URBAIN DÉTECTÉ
              </div>
              <div style="font-size:13px;color:#CBD5E1;">
                Proximité immédiate de <strong style="color:#FFFFFF;">{a['ville']}</strong>
              </div>
            </div>"""

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
              <td style="padding:5px 0;font-size:20px;font-weight:700;
                         color:{accent};">{mag}</td>
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
          {ville_html}
          {lien_html}
        </div>"""

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html_body = f"""
    <html>
    <body style="margin:0;padding:0;background:#050810;">
      <div style="max-width:620px;margin:0 auto;padding:32px 24px;
                  font-family:'Segoe UI',Arial,sans-serif;">

        <!-- HEADER -->
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:28px;
                    padding-bottom:20px;border-bottom:1px solid #0F1E38;">
          <div style="background:linear-gradient(135deg,#FF3B30,#F59E0B);
                      border-radius:12px;width:48px;height:48px;
                      display:flex;align-items:center;justify-content:center;
                      font-size:24px;flex-shrink:0;">🛡</div>
          <div>
            <div style="color:#FFFFFF;font-size:20px;font-weight:700;
                        letter-spacing:.15em;">SENTINELLE OSINT</div>
            <div style="color:#4A6FA5;font-size:10px;letter-spacing:.1em;margin-top:2px;">
              SURVEILLANCE SISMIQUE MONDIALE · USGS / NASA
            </div>
          </div>
        </div>

        <!-- BANNER -->
        <div style="background:rgba(255,59,48,0.08);border:1px solid rgba(255,59,48,0.3);
                    border-radius:10px;padding:14px 20px;margin-bottom:24px;">
          <div style="font-size:13px;font-family:monospace;color:#FF6B6B;
                      letter-spacing:.08em;">
            ● {len(alertes)} NOUVELLE(S) MENACE(S) · {now_str}
          </div>
        </div>

        <!-- CARDS -->
        {cards_html}

        <!-- FOOTER -->
        <div style="margin-top:28px;padding-top:20px;border-top:1px solid #0F1E38;
                    font-size:11px;color:#374151;font-family:monospace;line-height:1.8;">
          <div>Sources : USGS Earthquake Hazards Program · NASA EONET</div>
          <div>Scan automatique toutes les 10 minutes via GitHub Actions</div>
        </div>

      </div>
    </body>
    </html>"""

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
def analyser_seismes(memoire):
    print("[USGS] Récupération des données sismiques...")
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        evenements = r.json().get("features", [])
    except Exception as e:
        print(f"[USGS] ❌ Erreur connexion : {e}")
        return []

    maintenant = datetime.now(timezone.utc)
    nouvelles_alertes = []
    nouveaux_ids      = []

    for event in evenements:
        event_id = event["id"]
        prop     = event["properties"]
        coords   = event["geometry"]["coordinates"]
        lon, lat, profondeur = coords[0], coords[1], coords[2]

        # Calcul âge
        ts = prop["time"] / 1000
        heure_seisme = datetime.fromtimestamp(ts, tz=timezone.utc)
        age_heures   = (maintenant - heure_seisme).total_seconds() / 3600

        if age_heures > AGE_MAX_HEURES:
            continue

        # --- FIX : forcer magnitude en float ---
        try:
            magnitude = float(prop.get("mag") or 0)
        except (TypeError, ValueError):
            magnitude = 0.0

        lieu          = prop.get("place", "Lieu inconnu")
        alerte_tsunami = prop.get("tsunami", 0) == 1
        url_usgs      = prop.get("url", "")
        heure_str     = heure_seisme.strftime("%Y-%m-%d %H:%M UTC")

        # Déjà connu ?
        if event_id in memoire:
            continue

        nouveaux_ids.append(event_id)
        alerte_requise = False
        ville = None

        if alerte_tsunami:
            alerte_requise = True
            type_ev = "TSUNAMI"
        elif magnitude >= SEUIL_SEISME_MAJEUR:
            alerte_requise = True
            type_ev = "SÉISME MAJEUR"
        elif magnitude >= SEUIL_SEISME_URBAIN:
            ville = verifier_impact_urbain(lat, lon)
            if ville:
                alerte_requise = True
                type_ev = "SÉISME URBAIN"
            time.sleep(1)  # rate limit géocodage
        else:
            type_ev = "SÉISME"

        if alerte_requise:
            nouvelles_alertes.append({
                "type":       type_ev,
                "lieu":       lieu,
                "magnitude":  magnitude,
                "profondeur": round(profondeur, 1),
                "heure":      heure_str,
                "url":        url_usgs,
                "ville":      ville,
            })

    # Sauvegarde mémoire
    for eid in nouveaux_ids:
        memoire.add(eid)
        sauvegarder_id(eid)

    print(f"[USGS] {len(evenements)} événements · {len(nouvelles_alertes)} nouvelle(s) alerte(s)")
    return nouvelles_alertes

# ==========================================
# 🔥  SURVEILLANCE INCENDIES (NASA EONET)
# ==========================================
def analyser_incendies(memoire):
    print("[NASA] Récupération des incendies actifs...")
    url = "https://eonet.gsfc.nasa.gov/api/v3/categories/wildfires?status=open"

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        incendies = r.json().get("events", [])
    except Exception as e:
        print(f"[NASA] ❌ Erreur connexion : {e}")
        return []

    nouvelles_alertes = []

    for feu in incendies:
        feu_id = feu.get("id", "")
        if feu_id in memoire:
            continue

        nom = feu.get("title", "Incendie inconnu")
        coords = feu["geometry"][-1]["coordinates"] if feu.get("geometry") else None

        memoire.add(feu_id)
        sauvegarder_id(feu_id)

        # On notifie uniquement les grands incendies (titre contenant des mots clés)
        mots_cles = ["complex", "fire", "wildfire", "incendie"]
        if any(m in nom.lower() for m in mots_cles):
            nouvelles_alertes.append({
                "type":      "INCENDIE",
                "lieu":      nom,
                "magnitude": "—",
                "heure":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "url":       feu.get("sources", [{}])[0].get("url", ""),
            })

    print(f"[NASA] {len(incendies)} incendies · {len(nouvelles_alertes)} nouveau(x)")
    return nouvelles_alertes

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

    # Chargement mémoire
    memoire = charger_memoire()

    # Surveillance
    alertes_seismes  = analyser_seismes(memoire)
    alertes_incendies = analyser_incendies(memoire)

    toutes_alertes = alertes_seismes + alertes_incendies

    # Envoi email
    if toutes_alertes:
        # Sujet dynamique selon la menace la plus grave
        tsunamis = [a for a in toutes_alertes if a["type"] == "TSUNAMI"]
        majeurs  = [a for a in toutes_alertes if isinstance(a.get("magnitude"), float)
                    and a["magnitude"] >= SEUIL_SEISME_MAJEUR]

        if tsunamis:
            sujet = f"🌊 ALERTE TSUNAMI — {tsunamis[0]['lieu']}"
        elif majeurs:
            sujet = f"🔴 SÉISME MAJEUR M{majeurs[0]['magnitude']} — {majeurs[0]['lieu']}"
        else:
            sujet = f"⚠️ SENTINELLE — {len(toutes_alertes)} nouvelle(s) menace(s) détectée(s)"

        envoyer_email(sujet, toutes_alertes)
    else:
        print("[OK] Aucune nouvelle menace — pas d'email envoyé")

    print("=" * 52)
    print("[SENTINELLE] Scan terminé")
