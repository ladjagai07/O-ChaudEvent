from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import uuid
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ochaudeven-secret-key-2026")

basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "ochaudeven.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ======================
# MODÈLES
# ======================

class User(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_pro = db.Column(db.Boolean, default=False)
    pro_until = db.Column(db.DateTime, nullable=True)

class Invitation(db.Model):
    id = db.Column(db.String(12), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    
    event_type = db.Column(db.String(50), nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    destinataire = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(20))
    heure = db.Column(db.String(10))
    lieu = db.Column(db.String(200))
    details = db.Column(db.Text)
    message = db.Column(db.Text)
    photo_url = db.Column(db.String(500))
    musique_url = db.Column(db.String(500))
    theme = db.Column(db.String(50), default="royal")
    
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String(50))
    reference = db.Column(db.String(100))
    status = db.Column(db.String(20), default="pending")
    plan = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    validated_at = db.Column(db.DateTime, nullable=True)

# ======================
# FONCTIONS
# ======================

def get_or_create_user():
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())
    
    user_id = session["user_id"]
    user = User.query.get(user_id)
    
    if not user:
        user = User(id=user_id)
        db.session.add(user)
        db.session.commit()
    
    return user

def is_user_pro(user):
    if not user.is_pro:
        return False
    if user.pro_until and user.pro_until < datetime.utcnow():
        user.is_pro = False
        db.session.commit()
        return False
    return True

def can_create_invitation(user):
    if is_user_pro(user):
        return True
    
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    count = Invitation.query.filter(
        Invitation.user_id == user.id,
        Invitation.created_at >= thirty_days_ago
    ).count()
    
    return count < 2

# ======================
# ROUTES
# ======================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/create", methods=["POST"])
def create():
    try:
        user = get_or_create_user()
        
        if not can_create_invitation(user):
            return redirect(url_for("pro_page"))

        # Récupérer les données du formulaire
        event_type = request.form.get("event_type", "autre").strip()
        titre = request.form.get("titre", "Invitation").strip()
        destinataire = request.form.get("destinataire", "").strip()
        date = request.form.get("date", "")
        heure = request.form.get("heure", "")
        lieu = request.form.get("lieu", "").strip()
        details = request.form.get("details", "").strip()
        message = request.form.get("message", "").strip()
        photo_url = request.form.get("photo_url", "").strip()
        musique_url = request.form.get("musique_url", "").strip()
        theme = request.form.get("theme", "royal")

        if not destinataire:
            destinataire = "Invité"

        invite_id = str(uuid.uuid4())[:8]

        invitation = Invitation(
            id=invite_id,
            user_id=user.id,
            event_type=event_type,
            titre=titre,
            destinataire=destinataire,
            date=date,
            heure=heure,
            lieu=lieu,
            details=details,
            message=message,
            photo_url=photo_url,
            musique_url=musique_url,
            theme=theme
        )

        db.session.add(invitation)
        db.session.commit()

        return redirect(url_for("show_invitation", invite_id=invite_id))

    except Exception as e:
        print("ERREUR CREATE:", str(e))
        return f"<h2>Erreur lors de la création</h2><p>{str(e)}</p><a href='/'>Retour</a>", 500

@app.route("/i/<invite_id>")
def show_invitation(invite_id):
    invitation = Invitation.query.get(invite_id)
    
    if not invitation:
        return "<h2>Invitation introuvable</h2><a href='/'>Retour</a>", 404

    invitation.views += 1
    db.session.commit()

    return render_template("invitation.html", inv=invitation)

@app.route("/pro")
def pro_page():
    return render_template("pro.html")

@app.route("/activate-pro", methods=["POST"])
def activate_pro():
    user = get_or_create_user()
    code = request.form.get("code", "").strip().upper()

    valid_codes = {
        "OCHAUD2026": {"days": 30, "plan": "pro_mensuel", "amount": 2000},
    }

    if code in valid_codes:
        info = valid_codes[code]
        
        transaction = Transaction(
            user_id=user.id,
            amount=info["amount"],
            method="Mobile Money",
            reference=code,
            status="validated",
            plan=info["plan"],
            validated_at=datetime.utcnow()
        )
        db.session.add(transaction)

        user.is_pro = True
        user.pro_until = datetime.utcnow() + timedelta(days=info["days"])
        db.session.commit()
        
        return "<h2>✅ Compte Pro activé avec succès !</h2><a href='/'>Retour à l'accueil</a>"
    
    return "<h2>❌ Code invalide</h2><a href='/pro'>Réessayer</a>"

@app.route("/admin/stats")
def admin_stats():
    users_count = User.query.count()
    invitations_count = Invitation.query.count()
    return f"""
    <h1>Stats Ochaud Even.ci</h1>
    <p>Utilisateurs : {users_count}</p>
    <p>Invitations créées : {invitations_count}</p>
    """

# ======================
# INITIALISATION
# ======================

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
