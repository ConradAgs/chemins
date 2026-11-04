#!/usr/bin/env python3
"""Une vérification de https://voyage.benin.bj, alerte si changement."""

import difflib
import hashlib
import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://voyage.benin.bj"
ETAT = Path("etat_page.json")

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")          # alerte push téléphone
SMTP_USER = os.environ.get("SMTP_USER")            # alerte e-mail (optionnel)
SMTP_PASS = os.environ.get("SMTP_PASS")
EMAIL_DEST = os.environ.get("EMAIL_DEST")


def extraire_contenu(html):
    soup = BeautifulSoup(html, "html.parser")
    for b in soup(["script", "style"]):
        b.decompose()
    texte = soup.get_text("\n", strip=True)
    liens = sorted(a["href"] for a in soup.find_all("a", href=True))
    return texte + "\n--LIENS--\n" + "\n".join(liens)


def notifier(diff):
    if NTFY_TOPIC:
        try:
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=f"La page a change : {URL}\n\n{diff[:1500]}".encode("utf-8"),
                headers={"Title": "Billets Paris-Cotonou", "Priority": "urgent",
                         "Tags": "airplane", "Click": URL},
                timeout=20,
            )
        except Exception as e:
            print(f"Échec ntfy : {e}")
    if SMTP_USER and SMTP_PASS and EMAIL_DEST:
        try:
            msg = EmailMessage()
            msg["Subject"] = "La page voyage.benin.bj a changé !"
            msg["From"], msg["To"] = SMTP_USER, EMAIL_DEST
            msg.set_content(f"{URL}\n\n{diff}")
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        except Exception as e:
            print(f"Échec e-mail : {e}")


def main():
    try:
        r = requests.get(URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"Page injoignable, réessai au prochain cycle : {e}")
        return

    contenu = extraire_contenu(r.text)
    h = hashlib.sha256(contenu.encode()).hexdigest()
    ancien = json.loads(ETAT.read_text()) if ETAT.exists() else None

    if ancien is None:
        print("État initial enregistré.")
    elif ancien["hash"] != h:
        diff = "\n".join(difflib.unified_diff(
            ancien["contenu"].splitlines(), contenu.splitlines(), lineterm="", n=1))
        print("CHANGEMENT DÉTECTÉ\n", diff)
        notifier(diff)
    else:
        print("Aucun changement.")
        return  # rien à sauvegarder

    ETAT.write_text(json.dumps({"hash": h, "contenu": contenu}))


if __name__ == "__main__":
    main()
