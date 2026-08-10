from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import uuid
import os

app = Flask(__name__)
app.secret_key = "change-cette-cle-secrete-tres-longue-et-aleatoire"

# Configuration de la base de données
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "ochaudeven.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ======================
# MODÈLES (Tables)
# ======================

class User(db.Model):
    id = db.Column(db.String(36), primary_key=True)  # UUID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_pro = db.Column(db.Boolean, default=False)
    pro_until = db.Column(db.DateTime, nullable=True)  # Date d'expiration du Pro
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)

    invitations = db.relationship("Invitation", backref="user", lazy=True)
    transactions = db.relationship("Transaction", backref="user", lazy=True)

class Invitation(db.Model):
    id = db.Column(db.String(12), primary_key=True)  # ID court
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
    theme = db.Column(db.String(50), default="classique")
    
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    
    amount = db.Column(db.Integer, nullable=False)          # Montant en FCFA
    method = db.Column(db.String(50))                       # Orange Money / Wave
    reference = db.Column(db.String(100))                   # Référence du paiement
    status = db.Column(db.String(20), default="pending")    # pending / validated / rejected
    plan = db.Column(db.String(50))                         # pro_mensuel / pro_10_invitations...
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    validated_at = db.Column(db.DateTime, nullable=True)
    note = db.Column(db.Text)                               # Note interne

# ======================
# FONCTIONS UTILES
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
    
    # Limite gratuite : 2 invitations sur les 30 derniers jours
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
    user = get_or_create_user()
    
    if not can_create_invitation(user):
        return redirect(url_for("pro_page"))

    invite_id = str(uuid.uuid4())[:8]

    invitation = Invitation(
        id=invite_id,
        user_id=user.id,
        event_type=request.form.get("event_type", "autre"),
        titre=request.form.get("titre", "").strip(),
        destinataire=request.form.get("destinataire", "").strip(),
        date=request.form.get("date", ""),
        heure=request.form.get("heure", ""),
        lieu=request.form.get("lieu", "").strip(),
        details=request.form.get("details", "").strip(),
        message=request.form.get("message", "").strip(),
        photo_url=request.form.get("photo_url", "").strip(),
        musique_url=request.form.get("musique_url", "").strip(),
        theme=request.form.get("theme", "classique")
    )

    db.session.add(invitation)
    db.session.commit()

    return redirect(url_for("show_invitation", invite_id=invite_id))

@app.route("/i/<invite_id>")
def show_invitation(invite_id):
    invitation = Invitation.query.get_or_404(invite_id)
    
    # Incrémenter les vues
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

    # Codes d'activation (tu peux en générer d'autres)
    valid_codes = {
        "OCHAUD2026": {"days": 30, "plan": "pro_mensuel", "amount": 2000},
        "OCHAUD10": {"days": 0, "plan": "pro_10_invitations", "amount": 1500},  # illimité 10 invitations (à gérer différemment si tu veux)
    }

    if code in valid_codes:
        info = valid_codes[code]
        
        # Créer la transaction
        transaction = Transaction(
            user_id=user.id,
            amount=info["amount"],
            method="Mobile Money",
            reference=code,
            status="validated",
            plan=info["plan"],
            validated_at=datetime.utcnow(),
            note="Activation manuelle via code"
        )
        db.session.add(transaction)

        # Activer le Pro
        user.is_pro = True
        if info["days"] > 0:
            user.pro_until = datetime.utcnow() + timedelta(days=info["days"])
        else:
            user.pro_until = None  # Illimité ou autre logique

        db.session.commit()
        return f"✅ Compte Pro activé avec succès ! Plan : {info['plan']}"
    
    return "❌ Code invalide. Envoie ta capture Mobile Money sur WhatsApp pour recevoir ton code d'activation."

# Route admin simple pour voir les données (protège-la plus tard)
@app.route("/admin/stats")
def admin_stats():
    # Attention : à protéger avec un mot de passe plus tard
    users_count = User.query.count()
    invitations_count = Invitation.query.count()
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(50).all()
    
    return f"""
    <h1>Stats Ochaud Even.ci</h1>
    <p>Utilisateurs : {users_count}</p>
    <p>Invitations créées : {invitations_count}</p>
    <h3>Dernières transactions</h3>
    <ul>
    {''.join([f"<li>{t.created_at} - {t.amount} FCFA - {t.status} - {t.plan}</li>" for t in transactions])}
    </ul>
    """

# ======================
# INITIALISATION
# ======================

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
