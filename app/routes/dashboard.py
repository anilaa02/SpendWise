"""
Dashboard and Overview Routes for SpendWise.
Provides financial summaries, savings rates, budget health, financial health scores,
subscription forecasting, and multi-format data exports.
"""
import csv
import io
import json
from datetime import date, timedelta
from calendar import month_name
from flask import Blueprint, render_template, Response, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import extract
from app import db
from app.models import Expense, Category, Income, SavingsGoal, CURRENCY_MAP
from app.insights import generate_insights
from app.health_score import calculate_financial_health

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

    # Current month expenses
    month_expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        extract("month", Expense.date) == today.month,
        extract("year", Expense.date) == today.year,
    ).all()
    total_this_month = sum(e.amount for e in month_expenses)

    # Current month incomes
    month_incomes = Income.query.filter(
        Income.user_id == current_user.id,
        extract("month", Income.date) == today.month,
        extract("year", Income.date) == today.year,
    ).all()
    total_income_this_month = sum(inc.amount for inc in month_incomes)

    net_balance = total_income_this_month - total_this_month
    savings_rate = (net_balance / total_income_this_month * 100) if total_income_this_month > 0 else None

    # Previous month expenses for MoM comparison
    pm = today.month - 1 if today.month > 1 else 12
    py = today.year if today.month > 1 else today.year - 1
    prev_month_expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        extract("month", Expense.date) == pm,
        extract("year", Expense.date) == py,
    ).all()
    total_prev_month = sum(e.amount for e in prev_month_expenses)

    mom_pct = None
    if total_prev_month > 0:
        mom_pct = round(((total_this_month - total_prev_month) / total_prev_month) * 100, 1)

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

    # Budget utilization
    budget_utilization = (total_this_month / total_budget * 100) if total_budget and total_budget > 0 else None

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

    # Subscriptions & Upcoming Renewals
    all_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    active_recurring = [e for e in all_expenses if e.is_recurring and e.status == "active"]
    monthly_subscription_cost = sum(e.monthly_equivalent for e in active_recurring)
    
    upcoming_renewals = []
    renewing_this_month_sum = 0.0
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
            if next_dt.month == today.month and next_dt.year == today.year:
                renewing_this_month_sum += e.amount

    upcoming_renewals.sort(key=lambda x: x["days_left"])

    # Recent transactions
    recent_transactions = (
        Expense.query.filter_by(user_id=current_user.id)
        .order_by(Expense.date.desc(), Expense.id.desc())
        .limit(8)
        .all()
    )

    # Monthly Summary stats
    largest_category = max(category_totals, key=lambda c: c["total"]) if category_totals else None
    remaining_budget = (total_budget - total_this_month) if total_budget else None
    daily_average = (total_this_month / today.day) if today.day > 0 else 0

    # Financial Health Score
    health = calculate_financial_health(current_user.id)

    summary = {
        "total_income": total_income_this_month,
        "total_expenses": total_this_month,
        "net_balance": net_balance,
        "savings_rate": savings_rate,
        "total_budget": total_budget,
        "remaining_budget": remaining_budget,
        "budget_utilization": budget_utilization,
        "daily_average": daily_average,
        "largest_category_name": largest_category["name"] if largest_category else "—",
        "largest_category_amount": largest_category["total"] if largest_category else 0.0,
        "mom_pct": mom_pct,
        "active_subscriptions": len(active_recurring),
        "monthly_subscription_cost": monthly_subscription_cost,
        "renewing_this_month_sum": renewing_this_month_sum,
        "health_score": health["score"],
        "health_grade": health["grade"],
        "health_color": health["color"],
    }

    insights = generate_insights(current_user.id)

    return render_template(
        "dashboard.html",
        summary=summary,
        category_totals=category_totals,
        budget_progress_list=budget_progress_list,
        budget_alerts=budget_alerts,
        trend=trend,
        upcoming_renewals=upcoming_renewals,
        recent_transactions=recent_transactions,
        insights=insights,
        health=health,
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
    renewing_this_month_total = 0.0
    for e in active_recurring:
        next_dt = e.next_renewal_date()
        days_left = (next_dt - today).days if next_dt else None
        if next_dt and next_dt.month == today.month and next_dt.year == today.year:
            renewing_this_month_total += e.amount

        renewals_schedule.append({
            "expense": e,
            "next_date": next_dt,
            "days_left": days_left,
        })
    renewals_schedule.sort(key=lambda x: (x["days_left"] is None, x["days_left"]))

    return render_template(
        "subscriptions.html",
        recurring=active_recurring,
        inactive_recurring=inactive_recurring,
        needs_review=needs_review,
        monthly_burden=monthly_burden,
        annual_burden=annual_burden,
        renewing_this_month_total=renewing_this_month_total,
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
        payment_method=source_expense.payment_method,
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
                "category": e.category.name if e.category else "",
                "amount": e.amount,
                "currency": current_user.currency,
                "payment_method": e.payment_method,
                "note": e.note or "",
                "is_recurring": e.is_recurring,
                "recurrence_period": e.recurrence_period or "",
                "status": e.status,
                "is_anomaly": e.is_anomaly,
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
    writer.writerow(["Date", "Category", "Amount", "Currency", "Payment Method", "Note", "Recurring", "Recurrence Period", "Status", "Is Anomaly"])
    for e in expenses:
        writer.writerow([
            e.date.isoformat(),
            e.category.name if e.category else "",
            e.amount,
            current_user.currency,
            e.payment_method,
            e.note or "",
            "Yes" if e.is_recurring else "No",
            e.recurrence_period or "",
            e.status,
            "Yes" if e.is_anomaly else "No",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename_base}.csv"},
    )
