from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Category

auth_bp = Blueprint("auth", __name__)

DEFAULT_CATEGORIES = [
    "Groceries",
    "Housing & Rent",
    "Utilities & Bills",
    "Dining Out",
    "Subscriptions",
    "Transport",
    "Entertainment",
]


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        currency = request.form.get("currency", "INR").upper()

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("auth.signup"))

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return redirect(url_for("auth.signup"))

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return redirect(url_for("auth.signup"))

        user = User(name=name, email=email, currency=currency)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Seed standard categories without forced budgets (user can set them optionally)
        for cat_name in DEFAULT_CATEGORIES:
            db.session.add(Category(name=cat_name, monthly_budget=None, user_id=user.id))

        db.session.commit()

        login_user(user)
        flash(f"Welcome to SpendWise, {user.name}! We've set up starter categories for you.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard.index"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("auth.login"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))

