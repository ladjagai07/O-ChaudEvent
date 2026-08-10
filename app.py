from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import uuid
import json
import os
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = "ochaudeven-secret-key-change-moi"  # Change cette clé !

# Stockage simple (fichier JSON) - pour commencer
DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"invitations": {}, "users": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_id():
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())
    return session["user_id"]

def is_pro(user_id):
    data = load_data()
    user = data["users"].get(user_id, {})
    return user.get("is_pro", False)

def can_create_invitation(user_id):
    if is_pro(user_id):
        return True
    data = load_data()
    user = data["users"].get(user_id, {"created": []})
    # Limite : 2 invitations par mois
    now = datetime.now()
    recent = [d for d in user.get("created", []) if (now - datetime.fromisoformat(d)).days < 30]
    return len(recent) < 2

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/create", methods=["POST"])
def create():
    user_id = get_user_id()
    
    if not can_create_invitation(user_id):
        return redirect(url_for("pro_page"))

    event_type = request.form.get("event_type", "autre")
    titre = request.form.get("titre", "").strip()
    destinataire = request.form.get("destinataire", "").strip()
    date = request.form.get("date", "")
    heure = request.form.get("heure", "")
    lieu = request.form.get("lieu", "").strip()
    details = request.form.get("details", "").strip()
    message = request.form.get("message", "").strip()
    photo_url = request.form.get("photo_url", "").strip()
    musique_url = request.form.get("musique_url", "").strip()
    theme = request.form.get("theme", "classique")

    invite_id = str(uuid.uuid4())[:8]

    invitation = {
        "id": invite_id,
        "event_type": event_type,
        "titre": titre,
        "destinataire": destinataire,
        "date": date,
        "heure": heure,
        "lieu": lieu,
        "details": details,
        "message": message,
        "photo_url": photo_url,
        "musique_url": musique_url,
        "theme": theme,
        "created_at": datetime.now().isoformat(),
        "views": 0,
        "user_id": user_id
    }

    data = load_data()
    data["invitations"][invite_id] = invitation

    # Enregistrer la création pour la limite freemium
    if user_id not in data["users"]:
        data["users"][user_id] = {"created": [], "is_pro": False}
    data["users"][user_id]["created"].append(datetime.now().isoformat())

    save_data(data)

    return redirect(url_for("show_invitation", invite_id=invite_id))

@app.route("/i/<invite_id>")
def show_invitation(invite_id):
    data = load_data()
    invitation = data["invitations"].get(invite_id)

    if not invitation:
        return "Invitation introuvable", 404

    # Incrémenter les vues
    invitation["views"] = invitation.get("views", 0) + 1
    data["invitations"][invite_id] = invitation
    save_data(data)

    return render_template("invitation.html", inv=invitation)

@app.route("/pro")
def pro_page():
    return render_template("pro.html")

@app.route("/activate-pro", methods=["POST"])
def activate_pro():
    # Version manuelle : tu actives toi-même
    code = request.form.get("code", "").strip()
    # Exemple de code simple (tu changes)
    if code == "OCHAUD2026":
        user_id = get_user_id()
        data = load_data()
        if user_id not in data["users"]:
            data["users"][user_id] = {"created": [], "is_pro": False}
        data["users"][user_id]["is_pro"] = True
        save_data(data)
        return "Compte Pro activé avec succès ! Tu peux maintenant créer des invitations illimitées."
    return "Code invalide. Envoie ta capture Mobile Money sur WhatsApp pour recevoir ton code."

if __name__ == "__main__":
    app.run(debug=True)
