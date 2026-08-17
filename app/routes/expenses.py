from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Expense, Category

expenses_bp = Blueprint("expenses", __name__)


@expenses_bp.route("/expenses")
@login_required
def list_expenses():
    query = Expense.query.filter_by(user_id=current_user.id)

    category_id = request.args.get("category_id")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    min_amount = request.args.get("min_amount")
    max_amount = request.args.get("max_amount")
    recurring_only = request.args.get("recurring_only")
    keyword = request.args.get("keyword", "").strip()

    if category_id:
        query = query.filter_by(category_id=int(category_id))
    if date_from:
        query = query.filter(Expense.date >= datetime.strptime(date_from, "%Y-%m-%d").date())
    if date_to:
        query = query.filter(Expense.date <= datetime.strptime(date_to, "%Y-%m-%d").date())
    if min_amount:
        query = query.filter(Expense.amount >= float(min_amount))
    if max_amount:
        query = query.filter(Expense.amount <= float(max_amount))
    if recurring_only:
        query = query.filter_by(is_recurring=True)
    if keyword:
        query = query.filter(Expense.note.ilike(f"%{keyword}%"))

    expenses = query.order_by(Expense.date.desc()).all()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    return render_template(
        "expenses.html",
        expenses=expenses,
        categories=categories,
        filters=request.args,
    )


@expenses_bp.route("/expenses/add", methods=["POST"])
@login_required
def add_expense():
    amount = request.form.get("amount")
    note = request.form.get("note", "")
    category_id = request.form.get("category_id")
    expense_date = request.form.get("date")
    is_recurring = bool(request.form.get("is_recurring"))
    recurrence_period = request.form.get("recurrence_period") or None

    if not amount or not category_id:
        flash("Amount and category are required.", "error")
        return redirect(url_for("expenses.list_expenses"))

    parsed_date = (
        datetime.strptime(expense_date, "%Y-%m-%d").date() if expense_date else date.today()
    )

    expense = Expense(
        amount=float(amount),
        note=note,
        date=parsed_date,
        category_id=int(category_id),
        user_id=current_user.id,
        is_recurring=is_recurring,
        recurrence_period=recurrence_period if is_recurring else None,
    )
    db.session.add(expense)
    db.session.commit()
    flash("Expense added.", "success")
    return redirect(url_for("expenses.list_expenses"))


@expenses_bp.route("/expenses/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    flash("Expense deleted.", "success")
    return redirect(url_for("expenses.list_expenses"))


@expenses_bp.route("/expenses/<int:expense_id>/mark-reviewed", methods=["POST"])
@login_required
def mark_reviewed(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    expense.last_reviewed_date = date.today()
    db.session.commit()
    flash(f'Marked "{expense.note or expense.category.name}" as reviewed.', "success")
    return redirect(url_for("dashboard.subscriptions"))


@expenses_bp.route("/categories/add", methods=["POST"])
@login_required
def add_category():
    name = request.form.get("name", "").strip()
    budget = request.form.get("monthly_budget")

    if not name:
        flash("Category name is required.", "error")
        return redirect(url_for("expenses.list_expenses"))

    category = Category(
        name=name,
        monthly_budget=float(budget) if budget else None,
        user_id=current_user.id,
    )
    db.session.add(category)
    db.session.commit()
    flash("Category added.", "success")
    return redirect(url_for("expenses.list_expenses"))
