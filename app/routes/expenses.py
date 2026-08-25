import csv
import io
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
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
        try:
            query = query.filter(Expense.date >= datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Expense.date <= datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass
    if min_amount:
        try:
            query = query.filter(Expense.amount >= float(min_amount))
        except ValueError:
            pass
    if max_amount:
        try:
            query = query.filter(Expense.amount <= float(max_amount))
        except ValueError:
            pass
    if recurring_only:
        query = query.filter_by(is_recurring=True)
    if keyword:
        query = query.filter(Expense.note.ilike(f"%{keyword}%"))

    expenses = query.order_by(Expense.date.desc()).all()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    today_str = date.today().strftime("%Y-%m-%d")

    return render_template(
        "expenses.html",
        expenses=expenses,
        categories=categories,
        filters=request.args,
        today_str=today_str,
    )


@expenses_bp.route("/expenses/add", methods=["POST"])
@login_required
def add_expense():
    amount_str = request.form.get("amount")
    note = request.form.get("note", "").strip()
    category_id = request.form.get("category_id")
    expense_date = request.form.get("date")
    is_recurring = bool(request.form.get("is_recurring"))
    recurrence_period = request.form.get("recurrence_period") or None

    if not amount_str or not category_id:
        flash("Amount and category are required.", "error")
        return redirect(url_for("expenses.list_expenses"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Expense amount must be greater than 0.", "error")
            return redirect(url_for("expenses.list_expenses"))
    except ValueError:
        flash("Invalid amount entered.", "error")
        return redirect(url_for("expenses.list_expenses"))

    cat = Category.query.filter_by(id=int(category_id), user_id=current_user.id).first()
    if not cat:
        flash("Selected category does not exist.", "error")
        return redirect(url_for("expenses.list_expenses"))

    try:
        parsed_date = (
            datetime.strptime(expense_date, "%Y-%m-%d").date() if expense_date else date.today()
        )
    except ValueError:
        parsed_date = date.today()

    expense = Expense(
        amount=amount,
        note=note,
        date=parsed_date,
        category_id=cat.id,
        user_id=current_user.id,
        is_recurring=is_recurring,
        recurrence_period=recurrence_period if is_recurring else None,
        status="active",
    )
    db.session.add(expense)
    db.session.commit()
    flash("Expense added successfully.", "success")
    return redirect(url_for("expenses.list_expenses"))


@expenses_bp.route("/expenses/<int:expense_id>/edit", methods=["POST"])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()

    amount_str = request.form.get("amount")
    note = request.form.get("note", "").strip()
    category_id = request.form.get("category_id")
    expense_date = request.form.get("date")
    is_recurring = bool(request.form.get("is_recurring"))
    recurrence_period = request.form.get("recurrence_period") or None
    status = request.form.get("status", "active")

    if not amount_str or not category_id:
        flash("Amount and category are required.", "error")
        return redirect(url_for("expenses.list_expenses"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Expense amount must be greater than 0.", "error")
            return redirect(url_for("expenses.list_expenses"))
    except ValueError:
        flash("Invalid amount entered.", "error")
        return redirect(url_for("expenses.list_expenses"))

    cat = Category.query.filter_by(id=int(category_id), user_id=current_user.id).first()
    if not cat:
        flash("Selected category does not exist.", "error")
        return redirect(url_for("expenses.list_expenses"))

    if expense_date:
        try:
            expense.date = datetime.strptime(expense_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    expense.amount = amount
    expense.note = note
    expense.category_id = cat.id
    expense.is_recurring = is_recurring
    expense.recurrence_period = recurrence_period if is_recurring else None
    if status in ["active", "paused", "cancelled"]:
        expense.status = status

    db.session.commit()
    flash("Expense updated successfully.", "success")
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


@expenses_bp.route("/expenses/<int:expense_id>/toggle-status", methods=["POST"])
@login_required
def toggle_status(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    new_status = request.form.get("status")
    if new_status in ["active", "paused", "cancelled"]:
        expense.status = new_status
        db.session.commit()
        flash(f'Updated "{expense.note or expense.category.name}" status to {new_status.capitalize()}.', "success")
    return redirect(url_for("dashboard.subscriptions"))


@expenses_bp.route("/categories/add", methods=["POST"])
@login_required
def add_category():
    name = request.form.get("name", "").strip()
    budget_str = request.form.get("monthly_budget", "").strip()

    if not name:
        flash("Category name is required.", "error")
        return redirect(url_for("expenses.list_expenses"))

    existing = Category.query.filter_by(user_id=current_user.id, name=name).first()
    if existing:
        flash(f'Category "{name}" already exists.', "error")
        return redirect(url_for("expenses.list_expenses"))

    budget = None
    if budget_str:
        try:
            budget = float(budget_str)
            if budget < 0:
                budget = None
        except ValueError:
            budget = None

    category = Category(
        name=name,
        monthly_budget=budget,
        user_id=current_user.id,
    )
    db.session.add(category)
    db.session.commit()
    flash(f'Category "{name}" created.', "success")
    return redirect(url_for("expenses.list_expenses"))


@expenses_bp.route("/categories/<int:category_id>/edit", methods=["POST"])
@login_required
def edit_category(category_id):
    category = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    name = request.form.get("name", "").strip()
    budget_str = request.form.get("monthly_budget", "").strip()

    if not name:
        flash("Category name cannot be empty.", "error")
        return redirect(url_for("expenses.list_expenses"))

    duplicate = Category.query.filter(
        Category.user_id == current_user.id,
        Category.name == name,
        Category.id != category.id,
    ).first()
    if duplicate:
        flash(f'A category named "{name}" already exists.', "error")
        return redirect(url_for("expenses.list_expenses"))

    category.name = name
    if budget_str:
        try:
            budget = float(budget_str)
            category.monthly_budget = budget if budget >= 0 else None
        except ValueError:
            pass
    else:
        category.monthly_budget = None

    db.session.commit()
    flash(f'Category "{category.name}" updated.', "success")
    return redirect(url_for("expenses.list_expenses"))


@expenses_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    category = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    cat_name = category.name
    db.session.delete(category)
    db.session.commit()
    flash(f'Category "{cat_name}" and its associated expenses have been deleted.', "success")
    return redirect(url_for("expenses.list_expenses"))


@expenses_bp.route("/expenses/import", methods=["POST"])
@login_required
def import_csv():
    if "file" not in request.files:
        flash("No file selected for import.", "error")
        return redirect(url_for("expenses.list_expenses"))

    file = request.files["file"]
    if not file.filename or not file.filename.endswith(".csv"):
        flash("Please upload a valid .csv file.", "error")
        return redirect(url_for("expenses.list_expenses"))

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        reader = csv.DictReader(stream)
        
        imported_count = 0
        errors = 0

        # Preload categories map {lower_name: Category}
        user_categories = {c.name.lower(): c for c in Category.query.filter_by(user_id=current_user.id).all()}

        for row in reader:
            # normalize keys
            clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            date_val = clean_row.get("date")
            cat_name = clean_row.get("category")
            amount_val = clean_row.get("amount")
            note_val = clean_row.get("note", "")
            rec_val = clean_row.get("recurring", "no").lower()
            period_val = clean_row.get("recurrence period", clean_row.get("recurrence_period", "")).lower()

            if not cat_name or not amount_val:
                errors += 1
                continue

            try:
                amount = float(amount_val)
                if amount <= 0:
                    errors += 1
                    continue
            except ValueError:
                errors += 1
                continue

            parsed_date = date.today()
            if date_val:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                    try:
                        parsed_date = datetime.strptime(date_val, fmt).date()
                        break
                    except ValueError:
                        pass

            # Find or auto-create category
            cat_key = cat_name.lower()
            if cat_key in user_categories:
                category = user_categories[cat_key]
            else:
                category = Category(name=cat_name.title(), user_id=current_user.id)
                db.session.add(category)
                db.session.flush()
                user_categories[cat_key] = category

            is_recurring = rec_val in ["yes", "true", "1", "y"]
            recurrence_period = period_val if period_val in ["weekly", "monthly", "yearly"] else None

            expense = Expense(
                amount=amount,
                note=note_val,
                date=parsed_date,
                category_id=category.id,
                user_id=current_user.id,
                is_recurring=is_recurring,
                recurrence_period=recurrence_period if is_recurring else None,
                status="active",
            )
            db.session.add(expense)
            imported_count += 1

        db.session.commit()
        if imported_count > 0:
            flash(f"Successfully imported {imported_count} expense(s)." + (f" ({errors} rows skipped due to invalid data)" if errors else ""), "success")
        else:
            flash("No valid rows could be imported from the CSV.", "warning")

    except Exception as ex:
        db.session.rollback()
        flash(f"Error processing CSV: {str(ex)}", "error")

    return redirect(url_for("expenses.list_expenses"))


@expenses_bp.route("/expenses/sample-csv")
@login_required
def sample_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Category", "Amount", "Note", "Recurring", "Recurrence Period"])
    today = date.today().isoformat()
    writer.writerow([today, "Groceries", "1250.00", "Weekly supermarket shopping", "No", ""])
    writer.writerow([today, "Subscriptions", "499.00", "Netflix Standard Plan", "Yes", "monthly"])
    writer.writerow([today, "Dining", "820.50", "Dinner with team", "No", ""])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=spendwise_template.csv"},
    )

