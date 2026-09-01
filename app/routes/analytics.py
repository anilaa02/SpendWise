"""
Analytics and Visualizations Routes for SpendWise.
Provides Chart.js datasets for cashflow trends, category distributions,
budget variance, and financial health diagnostics.
"""
from datetime import date
from calendar import month_abbr
from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import extract
from app.models import Expense, Category, Income, SavingsGoal
from app.health_score import calculate_financial_health

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")


@analytics_bp.route("")
@login_required
def index():
    today = date.today()

    # 1. 6-Month Income & Expense Trend
    months_labels = []
    expense_trend = []
    income_trend = []
    net_savings_trend = []

    for i in range(5, -1, -1):
        target_dt = today - relativedelta(months=i)
        m = target_dt.month
        y = target_dt.year
        label = f"{month_abbr[m]} {y}"
        months_labels.append(label)

        m_expenses = Expense.query.filter(
            Expense.user_id == current_user.id,
            extract("month", Expense.date) == m,
            extract("year", Expense.date) == y,
        ).all()
        m_expense_sum = sum(e.amount for e in m_expenses)
        expense_trend.append(round(m_expense_sum, 2))

        m_incomes = Income.query.filter(
            Income.user_id == current_user.id,
            extract("month", Income.date) == m,
            extract("year", Income.date) == y,
        ).all()
        m_income_sum = sum(inc.amount for inc in m_incomes)
        income_trend.append(round(m_income_sum, 2))

        net_savings_trend.append(round(m_income_sum - m_expense_sum, 2))

    # 2. Category Distribution (Current Month)
    categories = Category.query.filter_by(user_id=current_user.id).all()
    current_month_expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        extract("month", Expense.date) == today.month,
        extract("year", Expense.date) == today.year,
    ).all()

    total_current_expense = sum(e.amount for e in current_month_expenses)
    category_breakdown = []
    for cat in categories:
        spent = sum(e.amount for e in current_month_expenses if e.category_id == cat.id)
        if spent > 0:
            pct = (spent / total_current_expense * 100) if total_current_expense > 0 else 0
            category_breakdown.append({
                "name": cat.name,
                "amount": round(spent, 2),
                "pct": round(pct, 1),
                "budget": cat.monthly_budget or 0.0,
            })
    category_breakdown.sort(key=lambda x: x["amount"], reverse=True)

    # 3. Budget vs Actual
    budget_comparison = []
    for cat in categories:
        spent = sum(e.amount for e in current_month_expenses if e.category_id == cat.id)
        budget = cat.monthly_budget or 0.0
        variance = budget - spent if budget > 0 else 0.0
        budget_comparison.append({
            "name": cat.name,
            "spent": round(spent, 2),
            "budget": round(budget, 2),
            "variance": round(variance, 2),
            "is_over": spent > budget and budget > 0,
        })

    # 4. Financial Health Score
    health = calculate_financial_health(current_user.id)

    # 5. Savings Goals
    goals = SavingsGoal.query.filter_by(user_id=current_user.id).all()

    return render_template(
        "analytics.html",
        months_labels=months_labels,
        expense_trend=expense_trend,
        income_trend=income_trend,
        net_savings_trend=net_savings_trend,
        category_breakdown=category_breakdown,
        budget_comparison=budget_comparison,
        health=health,
        goals=goals,
        total_current_expense=total_current_expense,
    )
