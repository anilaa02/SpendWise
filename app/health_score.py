"""
Transparent Financial Health Score Engine for SpendWise.
Calculates a 0–100 score based on 6 core financial indicators with transparent,
explainable component deductions and recommendations.
"""
from datetime import date
from sqlalchemy import extract
from app.models import User, Expense, Category, Income, SavingsGoal
from app import db


def calculate_financial_health(user_id):
    """
    Computes a comprehensive financial health score (0-100).
    Returns a dict with score, grade, color, pillar scores, strengths, and recommendations.
    """
    today = date.today()
    user = db.session.get(User, user_id)
    sym = user.currency_symbol if user else "₹"

    month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        extract("month", Expense.date) == today.month,
        extract("year", Expense.date) == today.year,
    ).all()
    total_expense = sum(e.amount for e in month_expenses)

    month_incomes = Income.query.filter(
        Income.user_id == user_id,
        extract("month", Income.date) == today.month,
        extract("year", Income.date) == today.year,
    ).all()
    total_income = sum(inc.amount for inc in month_incomes)

    categories = Category.query.filter_by(user_id=user_id).all()
    goals = SavingsGoal.query.filter_by(user_id=user_id).all()
    all_expenses = Expense.query.filter_by(user_id=user_id).all()

    strengths = []
    recommendations = []

    # 1. Budget Adherence (Max 25 pts)
    budget_cats = [c for c in categories if c.monthly_budget and c.monthly_budget > 0]
    if budget_cats:
        under_budget_count = 0
        for c in budget_cats:
            cat_spent = sum(e.amount for e in month_expenses if e.category_id == c.id)
            if cat_spent <= c.monthly_budget:
                under_budget_count += 1
            else:
                over = cat_spent - c.monthly_budget
                recommendations.append(f"Over budget in {c.name} by {sym}{over:.0f}.")
        
        adherence_ratio = under_budget_count / len(budget_cats)
        budget_pts = round(adherence_ratio * 25)
        if adherence_ratio == 1.0:
            strengths.append(f"All {len(budget_cats)} category budgets are under control.")
        elif adherence_ratio >= 0.7:
            strengths.append(f"{under_budget_count} of {len(budget_cats)} categories within budget limits.")
    else:
        budget_pts = 16  # Neutral baseline
        recommendations.append("Set monthly budgets on categories to improve your score.")

    # 2. Savings Rate & Cashflow (Max 20 pts)
    if total_income > 0:
        net_savings = total_income - total_expense
        savings_rate = (net_savings / total_income) * 100.0
        if savings_rate >= 30:
            savings_pts = 20
            strengths.append(f"Outstanding savings rate: {savings_rate:.0f}% of income saved this month.")
        elif savings_rate >= 20:
            savings_pts = 17
            strengths.append(f"Healthy savings rate: {savings_rate:.0f}% of income saved.")
        elif savings_rate >= 10:
            savings_pts = 13
            recommendations.append(f"Savings rate is {savings_rate:.0f}%. Aim for at least 20% savings.")
        elif savings_rate >= 0:
            savings_pts = 8
            recommendations.append("Expenses nearly equal income this month. Build a buffer.")
        else:
            savings_pts = 3
            overspent = abs(net_savings)
            recommendations.append(f"Monthly expenses exceed income by {sym}{overspent:.0f}.")
    else:
        savings_pts = 12  # Neutral baseline
        savings_rate = None
        recommendations.append("Log your monthly income to track your exact savings rate.")

    # 3. Cashflow Ratio (Max 20 pts)
    if total_income > 0:
        ratio = total_income / total_expense if total_expense > 0 else 2.0
        if ratio >= 1.3:
            cashflow_pts = 20
            strengths.append("Positive cashflow: Income comfortably exceeds expenses.")
        elif ratio >= 1.0:
            cashflow_pts = 14
        else:
            cashflow_pts = 5
    else:
        cashflow_pts = 12

    # 4. Subscription Burden (Max 15 pts)
    active_subs = [e for e in all_expenses if e.is_recurring and e.status == "active"]
    monthly_sub_cost = sum(e.monthly_equivalent for e in active_subs)
    if total_expense > 0 and monthly_sub_cost > 0:
        sub_ratio = (monthly_sub_cost / total_expense) * 100.0
        if sub_ratio <= 12:
            sub_pts = 15
            strengths.append(f"Low subscription overhead ({sub_ratio:.0f}% of monthly spending).")
        elif sub_ratio <= 22:
            sub_pts = 12
        elif sub_ratio <= 32:
            sub_pts = 8
            recommendations.append(f"Subscriptions consume {sub_ratio:.0f}% of expenses ({sym}{monthly_sub_cost:.0f}/mo).")
        else:
            sub_pts = 4
            recommendations.append(f"High subscription burden: {sub_ratio:.0f}% of spending ({sym}{monthly_sub_cost:.0f}/mo).")
    else:
        sub_pts = 15
        if not active_subs:
            strengths.append("No active subscription drain detected.")

    # 5. Spending Stability & Anomalies (Max 10 pts)
    anomalies_this_month = [e for e in month_expenses if e.is_anomaly]
    if not anomalies_this_month:
        anomaly_pts = 10
        strengths.append("Stable transaction history with no unusual spending spikes.")
    elif len(anomalies_this_month) == 1:
        anomaly_pts = 6
        recommendations.append(f"1 spending anomaly detected ({anomalies_this_month[0].note or 'large purchase'}).")
    else:
        anomaly_pts = 3
        recommendations.append(f"{len(anomalies_this_month)} unusual spending spikes detected this month.")

    # 6. Savings Goals Momentum (Max 10 pts)
    if goals:
        completed = [g for g in goals if g.is_completed]
        overdue = [g for g in goals if g.is_overdue]
        active = [g for g in goals if not g.is_completed and not g.is_overdue]
        
        if completed:
            strengths.append(f"{len(completed)} savings goal{'s' if len(completed) > 1 else ''} achieved!")
        if overdue:
            recommendations.append(f"{len(overdue)} savings goal{'s are' if len(overdue) > 1 else ' is'} past target date.")
        
        if completed and not overdue:
            goals_pts = 10
        elif active and not overdue:
            goals_pts = 8
            strengths.append("Active savings goals in progress.")
        elif overdue:
            goals_pts = 4
        else:
            goals_pts = 6
    else:
        goals_pts = 5
        recommendations.append("Create a savings goal to boost your financial roadmap.")

    total_score = min(100, max(10, budget_pts + savings_pts + cashflow_pts + sub_pts + anomaly_pts + goals_pts))

    if total_score >= 85:
        grade = "Excellent"
        color = "emerald"
    elif total_score >= 70:
        grade = "Good"
        color = "emerald"
    elif total_score >= 50:
        grade = "Fair"
        color = "amber"
    else:
        grade = "Needs Attention"
        color = "brick"

    return {
        "score": total_score,
        "grade": grade,
        "color": color,
        "pillar_scores": {
            "budget": budget_pts,
            "savings": savings_pts,
            "cashflow": cashflow_pts,
            "subscriptions": sub_pts,
            "stability": anomaly_pts,
            "goals": goals_pts,
        },
        "strengths": strengths[:4],
        "recommendations": recommendations[:4],
        "savings_rate": savings_rate,
        "total_income": total_income,
        "total_expense": total_expense,
    }
