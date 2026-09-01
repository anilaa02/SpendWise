"""
Savings Goals Routes for SpendWise.
Allows users to create financial targets, log contributions, track progress,
and view automated monthly savings recommendations.
"""
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import SavingsGoal, GoalContribution

goals_bp = Blueprint("goals", __name__, url_prefix="/goals")


@goals_bp.route("")
@login_required
def index():
    goals = SavingsGoal.query.filter_by(user_id=current_user.id).order_by(SavingsGoal.created_at.desc()).all()
    
    total_target = sum(g.target_amount for g in goals if not g.status == "cancelled")
    total_saved = sum(g.current_amount for g in goals if not g.status == "cancelled")
    overall_progress = (total_saved / total_target * 100) if total_target > 0 else 0.0

    active_goals = [g for g in goals if not g.is_completed and g.status == "in_progress"]
    completed_goals = [g for g in goals if g.is_completed or g.status == "completed"]
    overdue_goals = [g for g in goals if g.is_overdue]

    monthly_savings_needed = sum(
        g.required_monthly_savings for g in active_goals if g.required_monthly_savings is not None
    )

    return render_template(
        "goals.html",
        goals=goals,
        active_goals=active_goals,
        completed_goals=completed_goals,
        overdue_goals=overdue_goals,
        total_target=total_target,
        total_saved=total_saved,
        overall_progress=round(overall_progress, 1),
        monthly_savings_needed=round(monthly_savings_needed, 2),
        today=date.today(),
    )


@goals_bp.route("/add", methods=["POST"])
@login_required
def add():
    name = request.form.get("name", "").strip()
    target_str = request.form.get("target_amount", "").strip()
    current_str = request.form.get("current_amount", "0").strip()
    target_date_str = request.form.get("target_date", "").strip()

    if not name:
        flash("Please provide a name for your savings goal.", "error")
        return redirect(url_for("goals.index"))

    try:
        target_amount = float(target_str)
        if target_amount <= 0:
            flash("Target amount must be greater than 0.", "error")
            return redirect(url_for("goals.index"))
    except ValueError:
        flash("Invalid target amount.", "error")
        return redirect(url_for("goals.index"))

    try:
        current_amount = float(current_str) if current_str else 0.0
        if current_amount < 0:
            current_amount = 0.0
    except ValueError:
        current_amount = 0.0

    target_date = None
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = None

    status = "completed" if current_amount >= target_amount else "in_progress"

    goal = SavingsGoal(
        name=name,
        target_amount=target_amount,
        current_amount=current_amount,
        target_date=target_date,
        status=status,
        user_id=current_user.id,
    )
    db.session.add(goal)
    db.session.commit()

    # Log initial contribution if current_amount > 0
    if current_amount > 0:
        contribution = GoalContribution(
            goal_id=goal.id,
            amount=current_amount,
            date=date.today(),
            note="Initial deposit",
        )
        db.session.add(contribution)
        db.session.commit()

    flash(f"Savings goal '{name}' created successfully!", "success")
    return redirect(url_for("goals.index"))


@goals_bp.route("/<int:goal_id>/contribute", methods=["POST"])
@login_required
def contribute(goal_id):
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != current_user.id:
        flash("Savings goal not found.", "error")
        return redirect(url_for("goals.index"))

    amount_str = request.form.get("amount", "").strip()
    note = request.form.get("note", "").strip()
    date_str = request.form.get("date", "").strip()

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Contribution amount must be greater than 0.", "error")
            return redirect(url_for("goals.index"))
    except ValueError:
        flash("Invalid contribution amount.", "error")
        return redirect(url_for("goals.index"))

    try:
        contrib_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        contrib_date = date.today()

    goal.current_amount += amount
    if goal.current_amount >= goal.target_amount:
        goal.status = "completed"
        flash(f"🎉 Milestone reached! You have fully funded '{goal.name}'!", "success")
    else:
        flash(f"Added {current_user.currency_symbol}{amount:.2f} toward '{goal.name}'.", "success")

    contribution = GoalContribution(
        goal_id=goal.id,
        amount=amount,
        date=contrib_date,
        note=note or "Deposit",
    )
    db.session.add(contribution)
    db.session.commit()

    return redirect(url_for("goals.index"))


@goals_bp.route("/<int:goal_id>/edit", methods=["POST"])
@login_required
def edit(goal_id):
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != current_user.id:
        flash("Savings goal not found.", "error")
        return redirect(url_for("goals.index"))

    name = request.form.get("name", "").strip()
    target_str = request.form.get("target_amount", "").strip()
    target_date_str = request.form.get("target_date", "").strip()
    status = request.form.get("status", goal.status).strip()

    if name:
        goal.name = name

    if target_str:
        try:
            target_amount = float(target_str)
            if target_amount > 0:
                goal.target_amount = target_amount
        except ValueError:
            pass

    if target_date_str:
        try:
            goal.target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    elif "clear_target_date" in request.form:
        goal.target_date = None

    if status in ["in_progress", "completed", "cancelled"]:
        goal.status = status

    db.session.commit()
    flash(f"Updated goal '{goal.name}'.", "success")
    return redirect(url_for("goals.index"))


@goals_bp.route("/<int:goal_id>/delete", methods=["POST"])
@login_required
def delete(goal_id):
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != current_user.id:
        flash("Savings goal not found.", "error")
        return redirect(url_for("goals.index"))

    db.session.delete(goal)
    db.session.commit()
    flash(f"Deleted savings goal '{goal.name}'.", "info")
    return redirect(url_for("goals.index"))
