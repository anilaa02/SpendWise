"""
Rule-based insights engine for SpendWise.

Generates human-readable observations about a user's spending by comparing
current data against historical patterns. No ML — just clear, explainable
rules, which keeps the logic transparent and easy to justify.
"""
from datetime import date
from calendar import month_name, monthrange
from sqlalchemy import extract
from app import db
from app.models import Expense, Category, User


def _month_total(user_id, month, year):
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        extract("month", Expense.date) == month,
        extract("year", Expense.date) == year,
    ).all()
    return sum(e.amount for e in expenses), expenses


def _prev_month(month, year):
    if month == 1:
        return 12, year - 1
    return month - 1, year


def generate_insights(user_id):
    """Returns a list of insight dicts: {type, text} where type is
    'positive', 'warning', or 'neutral' (used for styling)."""
    insights = []
    today = date.today()
    user = db.session.get(User, user_id)
    sym = user.currency_symbol if user else "₹"

    this_total, this_expenses = _month_total(user_id, today.month, today.year)
    pm, py = _prev_month(today.month, today.year)
    prev_total, prev_expenses = _month_total(user_id, pm, py)

    categories = Category.query.filter_by(user_id=user_id).all()
    total_budget = sum(c.monthly_budget for c in categories if c.monthly_budget)

    # 1. Spending Velocity & End-of-Month Pace
    days_in_month = monthrange(today.year, today.month)[1]
    if today.day > 3 and this_total > 0:
        daily_pace = this_total / today.day
        projected_spend = daily_pace * days_in_month
        if total_budget and total_budget > 0:
            if projected_spend > total_budget * 1.1:
                overrun = projected_spend - total_budget
                insights.append({
                    "type": "warning",
                    "text": f"Pacing Alert: At your current rate of {sym}{daily_pace:.0f}/day, "
                            f"projected spend is {sym}{projected_spend:.0f}, which exceeds your {sym}{total_budget:.0f} budget by {sym}{overrun:.0f}."
                })
            elif projected_spend <= total_budget * 0.85 and today.day >= 15:
                savings = total_budget - projected_spend
                insights.append({
                    "type": "positive",
                    "text": f"Great pacing! You are on track to spend {sym}{projected_spend:.0f} this month, "
                            f"leaving {sym}{savings:.0f} in savings under your budget."
                })

    # 2. Category-wise month-over-month change
    for cat in categories:
        this_cat = sum(e.amount for e in this_expenses if e.category_id == cat.id)
        prev_cat = sum(e.amount for e in prev_expenses if e.category_id == cat.id)
        if prev_cat > 0 and this_cat > 0:
            pct_change = ((this_cat - prev_cat) / prev_cat) * 100
            if abs(pct_change) >= 15:
                direction = "increased" if pct_change > 0 else "decreased"
                insights.append({
                    "type": "warning" if pct_change > 0 else "positive",
                    "text": f"{cat.name} expenses {direction} by {abs(pct_change):.0f}% compared to last month "
                            f"({sym}{prev_cat:.0f} → {sym}{this_cat:.0f})."
                })

    # 3. Category exceeding personal average
    for cat in categories:
        this_cat = sum(e.amount for e in this_expenses if e.category_id == cat.id)
        all_cat_expenses = Expense.query.filter_by(user_id=user_id, category_id=cat.id).all()
        if not all_cat_expenses:
            continue
        months_seen = {(e.date.month, e.date.year) for e in all_cat_expenses}
        months_seen.discard((today.month, today.year))
        if len(months_seen) >= 1:
            avg = sum(e.amount for e in all_cat_expenses if (e.date.month, e.date.year) != (today.month, today.year)) / len(months_seen)
            if avg > 0 and this_cat > avg * 1.2:
                pct_over = ((this_cat - avg) / avg) * 100
                insights.append({
                    "type": "warning",
                    "text": f"You've spent {sym}{this_cat:.0f} on {cat.name} this month, "
                            f"exceeding your historical monthly average ({sym}{avg:.0f}) by {pct_over:.0f}%."
                })

    # 4. Unusual single transaction spike detection
    for cat in categories:
        cat_expenses = [e for e in this_expenses if e.category_id == cat.id]
        if len(cat_expenses) >= 2:
            avg_txn = sum(e.amount for e in cat_expenses) / len(cat_expenses)
            for e in cat_expenses:
                if e.amount >= 300 and e.amount > avg_txn * 2.5:
                    insights.append({
                        "type": "warning",
                        "text": f"Unusual spend detected: {e.note or cat.name} ({sym}{e.amount:.0f}) "
                                f"is over 2.5x your typical transaction size in {cat.name}."
                    })
                    break

    # 5. Highest spending category this month
    if this_expenses:
        cat_totals = {}
        for e in this_expenses:
            cat_totals[e.category_id] = cat_totals.get(e.category_id, 0) + e.amount
        top_cat_id = max(cat_totals, key=cat_totals.get)
        top_cat = next((c for c in categories if c.id == top_cat_id), None)
        if top_cat and this_total > 0:
            share = (cat_totals[top_cat_id] / this_total) * 100
            insights.append({
                "type": "neutral",
                "text": f"{top_cat.name} is your top expense category this month "
                        f"({sym}{cat_totals[top_cat_id]:.0f}, {share:.0f}% of total spend)."
            })

    # 6. Overall month-over-month change
    if prev_total > 0:
        pct_change = ((this_total - prev_total) / prev_total) * 100
        if abs(pct_change) >= 10:
            direction = "up" if pct_change > 0 else "down"
            insights.append({
                "type": "warning" if pct_change > 0 else "positive",
                "text": f"Total spending is {direction} {abs(pct_change):.0f}% compared to {month_name[pm]} "
                        f"({sym}{prev_total:.0f} → {sym}{this_total:.0f})."
            })

    # 7. Unreviewed subscriptions count
    all_expenses = Expense.query.filter_by(user_id=user_id).all()
    recurring = [e for e in all_expenses if e.is_recurring and e.status == "active"]
    stale = [e for e in recurring if e.needs_review()]
    if stale:
        insights.append({
            "type": "warning",
            "text": f"{len(stale)} active subscription{'s' if len(stale) != 1 else ''} "
                    f"{'have' if len(stale) != 1 else 'has'} not been reviewed in over 60 days."
        })

    # 8. Subscription Creep Indicator (>30% of monthly budget or expenses)
    monthly_recurring_burden = sum(e.monthly_equivalent for e in recurring)
    if this_total > 0 and monthly_recurring_burden > 0:
        sub_ratio = (monthly_recurring_burden / this_total) * 100
        if sub_ratio >= 30:
            insights.append({
                "type": "warning",
                "text": f"Subscription Creep: Recurring subscriptions represent {sub_ratio:.0f}% of your monthly expenses "
                        f"({sym}{monthly_recurring_burden:.0f}/month)."
            })

    if not insights:
        insights.append({
            "type": "neutral",
            "text": "Not enough spending history yet to generate deep insights. Keep logging expenses!"
        })

    return insights

