import csv
import io
import json
from datetime import date, timedelta
from calendar import month_name
from flask import Blueprint, render_template, Response, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import extract
from app import db
from app.models import Expense, Category, User, CURRENCY_MAP
from app.insights import generate_insights

dashboard_bp = Blueprint("dashboard", __name__)


def _budget_status(spent, budget):
    """Returns a warning level: 'ok', 'notice' (50%+), 'warning' (75%+), 'danger' (90%+), 'over' (100%+)."""
    if not budget or budget <= 0:
        return "none", 0
    pct = (spent / budget) * 100
    if pct >= 100:
        level = "over"
    elif pct >= 90:
        level = "danger"
    elif pct >= 75:
        level = "warning"
    elif pct >= 50:
        level = "notice"
    else:
        level = "ok"
    return level, pct


@dashboard_bp.route("/")
@login_required
def index():
    today = date.today()

    month_expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        extract("month", Expense.date) == today.month,
        extract("year", Expense.date) == today.year,
    ).all()

    total_this_month = sum(e.amount for e in month_expenses)

    categories = Category.query.filter_by(user_id=current_user.id).all()
    category_totals = []
    budget_progress_list = []
    budget_alerts = []
    total_budget = sum(c.monthly_budget for c in categories if c.monthly_budget)

    for cat in categories:
        cat_total = sum(e.amount for e in month_expenses if e.category_id == cat.id)
        if cat_total > 0:
            category_totals.append({"name": cat.name, "total": cat_total})
        
        if cat.monthly_budget:
            level, pct = _budget_status(cat_total, cat.monthly_budget)
            progress_item = {
                "id": cat.id,
                "name": cat.name,
                "spent": cat_total,
                "budget": cat.monthly_budget,
                "pct": min(pct, 100),
                "actual_pct": pct,
                "level": level,
            }
            budget_progress_list.append(progress_item)
            if level in ["warning", "danger", "over"]:
                budget_alerts.append(progress_item)

    # Last 6 months trend
    trend = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_total = sum(
            e.amount
            for e in Expense.query.filter(
                Expense.user_id == current_user.id,
                extract("month", Expense.date) == m,
                extract("year", Expense.date) == y,
            ).all()
        )
        trend.append({"label": f"{month_name[m][:3]} {y}", "total": month_total})

    # Budget vs Spending (per category with a budget)
    budget_vs_spend = []
    for cat in categories:
        if cat.monthly_budget:
            cat_total = sum(e.amount for e in month_expenses if e.category_id == cat.id)
            budget_vs_spend.append({"name": cat.name, "spent": cat_total, "budget": cat.monthly_budget})

    # Top spending categories (all-time, top 5)
    all_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    all_time_cat_totals = {}
    for e in all_expenses:
        all_time_cat_totals[e.category_id] = all_time_cat_totals.get(e.category_id, 0) + e.amount
    top_categories = sorted(
        [{"name": c.name, "total": all_time_cat_totals.get(c.id, 0)} for c in categories],
        key=lambda x: x["total"], reverse=True
    )[:5]
    top_categories = [c for c in top_categories if c["total"] > 0]

    # Subscriptions & Upcoming Renewals
    active_recurring = [e for e in all_expenses if e.is_recurring and e.status == "active"]
    monthly_subscription_cost = sum(e.monthly_equivalent for e in active_recurring)
    
    upcoming_renewals = []
    for e in active_recurring:
        next_dt = e.next_renewal_date()
        if next_dt:
            days_left = (next_dt - today).days
            if 0 <= days_left <= 30:
                upcoming_renewals.append({
                    "expense": e,
                    "renewal_date": next_dt,
                    "days_left": days_left,
                    "is_urgent": days_left <= 7,
                })
    upcoming_renewals.sort(key=lambda x: x["days_left"])

    # Monthly Summary stats
    largest_category = max(category_totals, key=lambda c: c["total"])["name"] if category_totals else "—"
    remaining_budget = (total_budget - total_this_month) if total_budget else None
    daily_average = (total_this_month / today.day) if today.day > 0 else 0

    summary = {
        "total_expenses": total_this_month,
        "total_budget": total_budget,
        "remaining_budget": remaining_budget,
        "daily_average": daily_average,
        "largest_category": largest_category,
        "active_subscriptions": len(active_recurring),
        "monthly_subscription_cost": monthly_subscription_cost,
    }

    insights = generate_insights(current_user.id)

    return render_template(
        "dashboard.html",
        summary=summary,
        category_totals=category_totals,
        budget_progress_list=budget_progress_list,
        budget_alerts=budget_alerts,
        trend=trend,
        budget_vs_spend=budget_vs_spend,
        top_categories=top_categories,
        upcoming_renewals=upcoming_renewals,
        insights=insights,
        currency_map=CURRENCY_MAP,
    )


@dashboard_bp.route("/subscriptions")
@login_required
def subscriptions():
    today = date.today()
    all_recurring = Expense.query.filter_by(user_id=current_user.id, is_recurring=True).all()
    active_recurring = [e for e in all_recurring if e.status == "active"]
    inactive_recurring = [e for e in all_recurring if e.status in ["paused", "cancelled"]]
    
    needs_review = [e for e in active_recurring if e.needs_review()]

    monthly_burden = sum(e.monthly_equivalent for e in active_recurring)
    annual_burden = sum(e.annual_equivalent for e in active_recurring)

    categories = Category.query.filter_by(user_id=current_user.id).all()
    total_budget = sum(c.monthly_budget for c in categories if c.monthly_budget)
    subscription_pct_of_budget = (monthly_burden / total_budget * 100) if total_budget else None

    ranked = sorted(active_recurring, key=lambda e: e.monthly_equivalent, reverse=True)

    oldest_unreviewed = None
    if needs_review:
        oldest_unreviewed = min(
            needs_review,
            key=lambda e: e.last_reviewed_date or e.date
        )

    # Calculate next renewal dates
    renewals_schedule = []
    for e in active_recurring:
        next_dt = e.next_renewal_date()
        renewals_schedule.append({
            "expense": e,
            "next_date": next_dt,
            "days_left": (next_dt - today).days if next_dt else None,
        })
    renewals_schedule.sort(key=lambda x: (x["days_left"] is None, x["days_left"]))

    return render_template(
        "subscriptions.html",
        recurring=active_recurring,
        inactive_recurring=inactive_recurring,
        needs_review=needs_review,
        monthly_burden=monthly_burden,
        annual_burden=annual_burden,
        subscription_pct_of_budget=subscription_pct_of_budget,
        ranked=ranked,
        oldest_unreviewed=oldest_unreviewed,
        renewals_schedule=renewals_schedule,
    )


@dashboard_bp.route("/subscriptions/<int:expense_id>/renew", methods=["POST"])
@login_required
def renew_subscription(expense_id):
    """Logs an actual new expense entry for the current renewal cycle."""
    source_expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    
    today = date.today()
    renewal_expense = Expense(
        amount=source_expense.amount,
        note=f"{source_expense.note or source_expense.category.name} (Renewal)",
        date=today,
        category_id=source_expense.category_id,
        user_id=current_user.id,
        is_recurring=False,
        status="active",
    )
    source_expense.last_reviewed_date = today
    db.session.add(renewal_expense)
    db.session.commit()

    flash(f'Logged renewal expense of {current_user.currency_symbol}{source_expense.amount:.2f} for "{source_expense.note or source_expense.category.name}".', "success")
    return redirect(url_for("dashboard.subscriptions"))


@dashboard_bp.route("/settings/preferences", methods=["POST"])
@login_required
def update_preferences():
    currency = request.form.get("currency", "INR").upper()
    name = request.form.get("name", "").strip()

    if currency in CURRENCY_MAP:
        current_user.currency = currency
    if name:
        current_user.name = name

    db.session.commit()
    flash("Preferences saved.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))


@dashboard_bp.route("/export/csv")
@login_required
def export_csv():
    """Supports optional filters: ?scope=month|year|category&format=csv|json"""
    scope = request.args.get("scope", "all")
    export_format = request.args.get("format", "csv").lower()
    query = Expense.query.filter_by(user_id=current_user.id)

    today = date.today()
    filename_base = "spendwise_export"

    if scope == "month":
        month = int(request.args.get("month", today.month))
        year = int(request.args.get("year", today.year))
        query = query.filter(extract("month", Expense.date) == month, extract("year", Expense.date) == year)
        filename_base = f"spendwise_{month_name[month]}_{year}"
    elif scope == "year":
        year = int(request.args.get("year", today.year))
        query = query.filter(extract("year", Expense.date) == year)
        filename_base = f"spendwise_{year}"
    elif scope == "category":
        category_id = request.args.get("category_id")
        if category_id:
            query = query.filter_by(category_id=int(category_id))
            cat = db.session.get(Category, int(category_id))
            if cat:
                filename_base = f"spendwise_{cat.name.replace(' ', '_')}"

    expenses = query.order_by(Expense.date.desc()).all()

    if export_format == "json":
        data = [
            {
                "id": e.id,
                "date": e.date.isoformat(),
                "category": e.category.name,
                "amount": e.amount,
                "currency": current_user.currency,
                "note": e.note or "",
                "is_recurring": e.is_recurring,
                "recurrence_period": e.recurrence_period or "",
                "status": e.status,
            }
            for e in expenses
        ]
        return Response(
            json.dumps(data, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.json"},
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Category", "Amount", "Currency", "Note", "Recurring", "Recurrence Period", "Status"])
    for e in expenses:
        writer.writerow([
            e.date.isoformat(),
            e.category.name,
            e.amount,
            current_user.currency,
            e.note or "",
            "Yes" if e.is_recurring else "No",
            e.recurrence_period or "",
            e.status,
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename_base}.csv"},
    )

