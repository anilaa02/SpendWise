import csv
import io
from datetime import date
from calendar import month_name
from flask import Blueprint, render_template, Response, request
from flask_login import login_required, current_user
from sqlalchemy import extract
from app.models import Expense, Category
from app.insights import generate_insights

dashboard_bp = Blueprint("dashboard", __name__)


def _budget_status(spent, budget):
    """Returns a warning level: 'ok', 'notice' (50%+), 'warning' (75%+), 'danger' (90%+), 'over' (100%+)."""
    if not budget or budget <= 0:
        return "ok", 0
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


def _recurring_monthly_equivalent(expense):
    if expense.recurrence_period == "monthly":
        return expense.amount
    if expense.recurrence_period == "yearly":
        return expense.amount / 12
    if expense.recurrence_period == "weekly":
        return expense.amount * 4.33
    return 0


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
    budget_alerts = []
    total_budget = sum(c.monthly_budget for c in categories if c.monthly_budget)

    for cat in categories:
        cat_total = sum(e.amount for e in month_expenses if e.category_id == cat.id)
        if cat_total > 0:
            category_totals.append({"name": cat.name, "total": cat_total})
        if cat.monthly_budget:
            level, pct = _budget_status(cat_total, cat.monthly_budget)
            if level != "ok":
                budget_alerts.append({
                    "name": cat.name,
                    "spent": cat_total,
                    "budget": cat.monthly_budget,
                    "level": level,
                    "pct": pct,
                })

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

    # Budget vs Spending (per category, this month)
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

    # Monthly Financial Summary
    recurring = [e for e in all_expenses if e.is_recurring]
    monthly_subscription_cost = sum(_recurring_monthly_equivalent(e) for e in recurring)
    largest_category = max(category_totals, key=lambda c: c["total"])["name"] if category_totals else "—"
    remaining_budget = (total_budget - total_this_month) if total_budget else None

    summary = {
        "total_expenses": total_this_month,
        "total_budget": total_budget,
        "remaining_budget": remaining_budget,
        "largest_category": largest_category,
        "active_subscriptions": len(recurring),
        "monthly_subscription_cost": monthly_subscription_cost,
    }

    insights = generate_insights(current_user.id)

    return render_template(
        "dashboard.html",
        summary=summary,
        category_totals=category_totals,
        budget_alerts=budget_alerts,
        trend=trend,
        budget_vs_spend=budget_vs_spend,
        top_categories=top_categories,
        insights=insights,
    )


@dashboard_bp.route("/subscriptions")
@login_required
def subscriptions():
    recurring = Expense.query.filter_by(user_id=current_user.id, is_recurring=True).all()
    needs_review = [e for e in recurring if e.needs_review()]

    for e in recurring:
        e.monthly_equivalent = _recurring_monthly_equivalent(e)

    monthly_burden = sum(e.monthly_equivalent for e in recurring)

    categories = Category.query.filter_by(user_id=current_user.id).all()
    total_budget = sum(c.monthly_budget for c in categories if c.monthly_budget)
    subscription_pct_of_budget = (monthly_burden / total_budget * 100) if total_budget else None

    ranked = sorted(recurring, key=lambda e: e.monthly_equivalent, reverse=True)

    oldest_unreviewed = None
    if needs_review:
        oldest_unreviewed = min(
            needs_review,
            key=lambda e: e.last_reviewed_date or e.date
        )

    calendar_entries = sorted(
        [{"expense": e, "day": e.date.day} for e in recurring],
        key=lambda x: x["day"]
    )

    return render_template(
        "subscriptions.html",
        recurring=recurring,
        needs_review=needs_review,
        monthly_burden=monthly_burden,
        subscription_pct_of_budget=subscription_pct_of_budget,
        ranked=ranked,
        oldest_unreviewed=oldest_unreviewed,
        calendar_entries=calendar_entries,
    )


@dashboard_bp.route("/export/csv")
@login_required
def export_csv():
    """Supports optional filters: ?scope=month|year|category&category_id=&month=&year="""
    scope = request.args.get("scope", "all")
    query = Expense.query.filter_by(user_id=current_user.id)

    today = date.today()
    filename = "spendwise_export.csv"

    if scope == "month":
        month = int(request.args.get("month", today.month))
        year = int(request.args.get("year", today.year))
        query = query.filter(extract("month", Expense.date) == month, extract("year", Expense.date) == year)
        filename = f"spendwise_{month_name[month]}_{year}.csv"
    elif scope == "year":
        year = int(request.args.get("year", today.year))
        query = query.filter(extract("year", Expense.date) == year)
        filename = f"spendwise_{year}.csv"
    elif scope == "category":
        category_id = request.args.get("category_id")
        if category_id:
            query = query.filter_by(category_id=int(category_id))
            cat = Category.query.get(int(category_id))
            if cat:
                filename = f"spendwise_{cat.name}.csv"

    expenses = query.order_by(Expense.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Category", "Amount", "Note", "Recurring", "Recurrence Period"])
    for e in expenses:
        writer.writerow([
            e.date.isoformat(),
            e.category.name,
            e.amount,
            e.note or "",
            "Yes" if e.is_recurring else "No",
            e.recurrence_period or "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
