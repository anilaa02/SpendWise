"""
Rule-Based Insights Engine for SpendWise.
Generates human-readable observations from real user data.
Covers category changes, budget projections, subscription renewals, income/savings rate, and goal progress.
"""
from datetime import date
from calendar import month_name, monthrange
from sqlalchemy import extract
from app import db
from app.models import Expense, Category, User, Income, SavingsGoal


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

    # 1. Income & Savings Rate Insight
    month_incomes = Income.query.filter(
        Income.user_id == user_id,
        extract("month", Income.date) == today.month,
        extract("year", Income.date) == today.year,
    ).all()
    this_income = sum(inc.amount for inc in month_incomes)

    if this_income > 0:
        net_balance = this_income - this_total
        savings_rate = (net_balance / this_income) * 100
        if net_balance >= 0:
            insights.append({
                "type": "positive",
                "text": f"Income this month is {sym}{this_income:.0f}, with {sym}{net_balance:.0f} saved "
                        f"({savings_rate:.0f}% savings rate)."
            })
        else:
            deficit = abs(net_balance)
            insights.append({
                "type": "warning",
                "text": f"Monthly spending ({sym}{this_total:.0f}) exceeds income ({sym}{this_income:.0f}) "
                        f"by {sym}{deficit:.0f}."
            })

    # 2. Spending Velocity & End-of-Month Pace
    days_in_month = monthrange(today.year, today.month)[1]
    if today.day > 3 and this_total > 0:
        daily_pace = this_total / today.day
        projected_spend = daily_pace * days_in_month
        if total_budget and total_budget > 0:
            if projected_spend > total_budget * 1.05:
                overrun = projected_spend - total_budget
                insights.append({
                    "type": "warning",
                    "text": f"Pacing Alert: At your current rate of {sym}{daily_pace:.0f}/day, "
                            f"you are projected to exceed your monthly budget by {sym}{overrun:.0f}."
                })
            elif projected_spend <= total_budget * 0.85 and today.day >= 12:
                savings = total_budget - projected_spend
                insights.append({
                    "type": "positive",
                    "text": f"Great budget control! On track to stay {sym}{savings:.0f} under your monthly budget."
                })

    # 3. Category-wise month-over-month change
    for cat in categories:
        this_cat = sum(e.amount for e in this_expenses if e.category_id == cat.id)
        prev_cat = sum(e.amount for e in prev_expenses if e.category_id == cat.id)
        if prev_cat > 0 and this_cat > 0:
            pct_change = ((this_cat - prev_cat) / prev_cat) * 100
            if abs(pct_change) >= 15:
                direction = "increased" if pct_change > 0 else "decreased"
                insights.append({
                    "type": "warning" if pct_change > 0 else "positive",
                    "text": f"Your {cat.name} spending {direction} by {abs(pct_change):.0f}% compared with last month "
                            f"({sym}{prev_cat:.0f} → {sym}{this_cat:.0f})."
                })

    # 4. Overall month-over-month change
    if prev_total > 0 and this_total > 0:
        pct_change = ((this_total - prev_total) / prev_total) * 100
        if abs(pct_change) >= 10:
            direction = "higher" if pct_change > 0 else "lower"
            insights.append({
                "type": "warning" if pct_change > 0 else "positive",
                "text": f"Your spending is {direction} than {month_name[pm]} by {abs(pct_change):.0f}% "
                        f"({sym}{prev_total:.0f} → {sym}{this_total:.0f})."
            })

    # 5. Subscriptions Renewing This Month
    all_expenses = Expense.query.filter_by(user_id=user_id).all()
    active_recurring = [e for e in all_expenses if e.is_recurring and e.status == "active"]
    renewing_this_month = []
    for sub in active_recurring:
        next_dt = sub.next_renewal_date()
        if next_dt and next_dt.month == today.month and next_dt.year == today.year:
            renewing_this_month.append(sub)

    if renewing_this_month:
        renewal_sum = sum(s.amount for s in renewing_this_month)
        insights.append({
            "type": "neutral",
            "text": f"You have {sym}{renewal_sum:.0f} in subscriptions scheduled for renewal this month."
        })

    # 6. Savings Goal Milestone
    active_goals = SavingsGoal.query.filter_by(user_id=user_id, status="in_progress").all()
    for g in active_goals:
        if g.progress_pct >= 80 and not g.is_completed:
            rem = g.remaining_amount
            insights.append({
                "type": "positive",
                "text": f"You are {sym}{rem:.0f} away from completing your '{g.name}' savings goal ({g.progress_pct:.0f}% reached)!"
            })
            break

    # 7. Unreviewed subscriptions count
    stale = [e for e in active_recurring if e.needs_review()]
    if stale:
        insights.append({
            "type": "warning",
            "text": f"{len(stale)} active subscription{'s' if len(stale) != 1 else ''} "
                    f"{'have' if len(stale) != 1 else 'has'} not been reviewed in over 60 days."
        })

    # 8. Single Large Transaction Anomaly / Spike Detection
    for cat in categories:
        cat_expenses = [e for e in this_expenses if e.category_id == cat.id]
        if len(cat_expenses) >= 3:
            avg_spend = sum(e.amount for e in cat_expenses) / len(cat_expenses)
            for e in cat_expenses:
                if (e.amount >= 2.5 * avg_spend and e.amount >= 100) or e.is_anomaly:
                    insights.append({
                        "type": "warning",
                        "text": f"Unusual spend detected: {sym}{e.amount:.2f} on '{e.note or cat.name}' is significantly higher than your typical {cat.name} expenses."
                    })
                    break

    if not insights:
        insights.append({
            "type": "neutral",
            "text": "Not enough spending history yet to generate deep insights. Keep logging expenses & income!"
        })

    return insights
