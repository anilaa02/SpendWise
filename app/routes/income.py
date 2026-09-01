"""
Income Management Routes for SpendWise.
Allows users to record, categorize, edit, and delete income streams.
"""
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import extract
from app import db
from app.models import Income

income_bp = Blueprint("income", __name__, url_prefix="/income")


@income_bp.route("")
@login_required
def index():
    today = date.today()
    month = request.args.get("month", today.month, type=int)
    year = request.args.get("year", today.year, type=int)

    incomes = (
        Income.query.filter(
            Income.user_id == current_user.id,
            extract("month", Income.date) == month,
            extract("year", Income.date) == year,
        )
        .order_by(Income.date.desc())
        .all()
    )

    total_month_income = sum(i.amount for i in incomes)
    all_user_incomes = Income.query.filter_by(user_id=current_user.id).all()
    all_time_income = sum(i.amount for i in all_user_incomes)

    sources = ["Salary", "Freelance", "Business", "Investment", "Bonus", "Gift", "Rental", "Other"]

    return render_template(
        "income.html",
        incomes=incomes,
        total_month_income=total_month_income,
        all_time_income=all_time_income,
        selected_month=month,
        selected_year=year,
        sources=sources,
        today=today,
    )


@income_bp.route("/add", methods=["POST"])
@login_required
def add():
    amount_str = request.form.get("amount", "").strip()
    source = request.form.get("source", "Salary").strip()
    date_str = request.form.get("date", "").strip()
    note = request.form.get("note", "").strip()

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Income amount must be greater than 0.", "error")
            return redirect(url_for("income.index"))
    except ValueError:
        flash("Please provide a valid income amount.", "error")
        return redirect(url_for("income.index"))

    try:
        inc_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        inc_date = date.today()

    income = Income(
        amount=amount,
        source=source or "Other",
        date=inc_date,
        note=note,
        user_id=current_user.id,
    )
    db.session.add(income)
    db.session.commit()
    flash(f"Successfully recorded income of {current_user.currency_symbol}{amount:.2f} ({source}).", "success")
    return redirect(url_for("income.index"))


@income_bp.route("/<int:income_id>/edit", methods=["POST"])
@login_required
def edit(income_id):
    income = db.session.get(Income, income_id)
    if not income or income.user_id != current_user.id:
        flash("Income record not found.", "error")
        return redirect(url_for("income.index"))

    amount_str = request.form.get("amount", "").strip()
    source = request.form.get("source", "").strip()
    date_str = request.form.get("date", "").strip()
    note = request.form.get("note", "").strip()

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Income amount must be greater than 0.", "error")
            return redirect(url_for("income.index"))
        income.amount = amount
    except ValueError:
        flash("Invalid income amount.", "error")
        return redirect(url_for("income.index"))

    if date_str:
        try:
            income.date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    if source:
        income.source = source
    income.note = note

    db.session.commit()
    flash("Income entry updated successfully.", "success")
    return redirect(url_for("income.index"))


@income_bp.route("/<int:income_id>/delete", methods=["POST"])
@login_required
def delete(income_id):
    income = db.session.get(Income, income_id)
    if not income or income.user_id != current_user.id:
        flash("Income record not found.", "error")
        return redirect(url_for("income.index"))

    db.session.delete(income)
    db.session.commit()
    flash("Income entry removed.", "info")
    return redirect(url_for("income.index"))
