from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, User
from services.auth import verify_password, set_password

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity","").strip()
        password = request.form.get("password","")
        user = User.query.filter((User.username==identity)|(User.email==identity)).first()
        if user and user.active and verify_password(user,password):
            session.clear()
            session["user_id"] = user.id
            session["role"] = user.role
            session["username"] = user.username
            return redirect(url_for("dashboard.index"))
        flash("Invalid credentials or disabled account.", "danger")
    return render_template("login.html")

@auth_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/users", methods=["GET","POST"])
def users():
    if session.get("role") != "admin":
        flash("Admin access required.","danger")
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        username=request.form["username"].strip()
        email=request.form["email"].strip().lower()
        password=request.form["password"]
        role=request.form.get("role","sales")
        if User.query.filter((User.username==username)|(User.email==email)).first():
            flash("Username or email already exists.","danger")
        else:
            u=User(username=username,email=email,role=role,active=True)
            set_password(u,password)
            db.session.add(u); db.session.commit()
            flash("User created.","success")
    return render_template("users.html", users=User.query.order_by(User.created_at.desc()).all())

@auth_bp.post("/users/<int:user_id>/toggle")
def toggle_user(user_id):
    if session.get("role") != "admin": return {"error":"forbidden"},403
    u=User.query.get_or_404(user_id)
    u.active=not u.active
    db.session.commit()
    return {"ok":True,"active":u.active}

@auth_bp.post("/users/<int:user_id>/reset-password")
def reset_password(user_id):
    if session.get("role") != "admin": return {"error":"forbidden"},403
    u=User.query.get_or_404(user_id)
    set_password(u, request.form["password"])
    db.session.commit()
    return {"ok":True}
