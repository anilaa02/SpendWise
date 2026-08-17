"""
Rule-based insights engine for SpendWise.

Generates human-readable observations about a user's spending by comparing
current data against historical patterns. No ML — just clear, explainable
rules, which keeps the logic transparent and easy to justify in a project
report or viva.
"""
from datetime import date
from calendar import month_name
from sqlalchemy import extract
from app.models import Expense, Category


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
    this_total, this_expenses = _month_total(user_id, today.month, today.year)
    pm, py = _prev_month(today.month, today.year)
    prev_total, prev_expenses = _month_total(user_id, pm, py)

    categories = Category.query.filter_by(user_id=user_id).all()

    # 1. Category-wise month-over-month change
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
                            f"(₹{prev_cat:.0f} → ₹{this_cat:.0f})."
                })

    # 2. Category exceeding personal average
    for cat in categories:
        this_cat = sum(e.amount for e in this_expenses if e.category_id == cat.id)
        all_cat_expenses = [e for e in Expense.query.filter_by(user_id=user_id, category_id=cat.id).all()]
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
                    "text": f"You've spent ₹{this_cat:.0f} on {cat.name} this month, "
                            f"exceeding your average (₹{avg:.0f}) by {pct_over:.0f}%."
                })

    # 3. Highest spending category this month
    if this_expenses:
        cat_totals = {}
        for e in this_expenses:
            cat_totals[e.category_id] = cat_totals.get(e.category_id, 0) + e.amount
        top_cat_id = max(cat_totals, key=cat_totals.get)
        top_cat = next((c for c in categories if c.id == top_cat_id), None)
        if top_cat:
            share = (cat_totals[top_cat_id] / this_total) * 100 if this_total else 0
            insights.append({
                "type": "neutral",
                "text": f"{top_cat.name} is your highest spending category this month "
                        f"(₹{cat_totals[top_cat_id]:.0f}, {share:.0f}% of total spend)."
            })

    # 4. Overall month-over-month change
    if prev_total > 0:
        pct_change = ((this_total - prev_total) / prev_total) * 100
        if abs(pct_change) >= 10:
            direction = "up" if pct_change > 0 else "down"
            insights.append({
                "type": "warning" if pct_change > 0 else "positive",
                "text": f"Total spending is {direction} {abs(pct_change):.0f}% compared to {month_name[pm]} "
                        f"(₹{prev_total:.0f} → ₹{this_total:.0f})."
            })

    # 5. Most expensive month historically
    all_expenses = Expense.query.filter_by(user_id=user_id).all()
    if all_expenses:
        month_totals = {}
        for e in all_expenses:
            key = (e.date.year, e.date.month)
            month_totals[key] = month_totals.get(key, 0) + e.amount
        if len(month_totals) >= 2:
            worst = max(month_totals, key=month_totals.get)
            insights.append({
                "type": "neutral",
                "text": f"Your highest spending month so far was {month_name[worst[1]]} {worst[0]} "
                        f"with ₹{month_totals[worst]:.0f} spent."
            })

    # 6. Unreviewed subscriptions count
    recurring = [e for e in all_expenses if e.is_recurring]
    stale = [e for e in recurring if e.needs_review()]
    if stale:
        insights.append({
            "type": "warning",
            "text": f"{len(stale)} subscription{'s' if len(stale) != 1 else ''} "
                    f"{'have' if len(stale) != 1 else 'has'} not been reviewed for over 60 days."
        })

    if not insights:
        insights.append({
            "type": "neutral",
            "text": "Not enough spending history yet to generate insights. Keep logging expenses!"
        })

    return insights
