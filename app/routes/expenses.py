"""
Expense and Category Management Routes for SpendWise.
Includes full CRUD operations, payment methods, transaction duplication,
anomaly detection, and 2-step CSV import workflow with preview and duplicate detection.
"""
import csv
import io
import json
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from app import db
from app.models import Expense, Category
from app.anomaly import detect_spending_anomaly

expenses_bp = Blueprint("expenses", __name__)

PAYMENT_METHODS = ["UPI / Online", "Credit Card", "Debit Card", "Cash", "Bank Transfer", "Net Banking"]


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
    payment_method = request.args.get("payment_method")
    anomalies_only = request.args.get("anomalies_only")
    keyword = request.args.get("keyword", "").strip()

    if category_id:
        try:
            query = query.filter_by(category_id=int(category_id))
        except ValueError:
            pass
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
    if payment_method:
        query = query.filter_by(payment_method=payment_method)
    if anomalies_only:
        query = query.filter_by(is_anomaly=True)
    if keyword:
        query = query.filter(Expense.note.ilike(f"%{keyword}%"))

    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    today_str = date.today().strftime("%Y-%m-%d")

    return render_template(
        "expenses.html",
        expenses=expenses,
        categories=categories,
        filters=request.args,
        payment_methods=PAYMENT_METHODS,
        today_str=today_str,
    )


@expenses_bp.route("/expenses/add", methods=["POST"])
@login_required
def add_expense():
    amount_str = request.form.get("amount")
    note = request.form.get("note", "").strip()
    category_id = request.form.get("category_id")
    expense_date = request.form.get("date")
    payment_method = request.form.get("payment_method", "UPI / Online").strip()
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

    # Check for anomaly
    is_anomaly, reason, _ = detect_spending_anomaly(
        amount=amount,
        category_id=cat.id,
        user_id=current_user.id,
    )

    expense = Expense(
        amount=amount,
        note=note,
        date=parsed_date,
        payment_method=payment_method if payment_method in PAYMENT_METHODS else "UPI / Online",
        category_id=cat.id,
        user_id=current_user.id,
        is_recurring=is_recurring,
        recurrence_period=recurrence_period if is_recurring else None,
        status="active",
        is_anomaly=is_anomaly,
        anomaly_reason=reason if is_anomaly else None,
    )
    db.session.add(expense)
    db.session.commit()

    if is_anomaly:
        flash(f"Expense logged. ⚠️ Notice: {reason}", "warning")
    else:
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
    payment_method = request.form.get("payment_method", expense.payment_method).strip()
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

    # Check for anomaly
    is_anomaly, reason, _ = detect_spending_anomaly(
        amount=amount,
        category_id=cat.id,
        user_id=current_user.id,
        exclude_expense_id=expense.id,
    )

    expense.amount = amount
    expense.note = note
    expense.category_id = cat.id
    if payment_method in PAYMENT_METHODS:
        expense.payment_method = payment_method
    expense.is_recurring = is_recurring
    expense.recurrence_period = recurrence_period if is_recurring else None
    if status in ["active", "paused", "cancelled"]:
        expense.status = status
    expense.is_anomaly = is_anomaly
    expense.anomaly_reason = reason if is_anomaly else None

    db.session.commit()
    flash("Expense updated successfully.", "success")
    return redirect(url_for("expenses.list_expenses"))


@expenses_bp.route("/expenses/<int:expense_id>/duplicate", methods=["POST"])
@login_required
def duplicate_expense(expense_id):
    original = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()

    is_anomaly, reason, _ = detect_spending_anomaly(
        amount=original.amount,
        category_id=original.category_id,
        user_id=current_user.id,
    )

    clone = Expense(
        amount=original.amount,
        note=f"{original.note} (Copy)" if original.note else "Copy",
        date=date.today(),
        payment_method=original.payment_method,
        category_id=original.category_id,
        user_id=current_user.id,
        is_recurring=original.is_recurring,
        recurrence_period=original.recurrence_period,
        status="active",
        is_anomaly=is_anomaly,
        anomaly_reason=reason if is_anomaly else None,
    )
    db.session.add(clone)
    db.session.commit()
    flash(f"Duplicated transaction '{clone.note}' to today's ledger.", "success")
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


# ==========================================
# 2-STEP CSV IMPORT & VALIDATION WORKFLOW
# ==========================================

@expenses_bp.route("/expenses/import/preview", methods=["POST"])
@login_required
def preview_csv():
    if "file" not in request.files:
        flash("No file selected for import.", "error")
        return redirect(url_for("expenses.list_expenses"))

    file = request.files["file"]
    if not file.filename or not file.filename.endswith(".csv"):
        flash("Please upload a valid .csv file.", "error")
        return redirect(url_for("expenses.list_expenses"))

    try:
        content = file.stream.read().decode("utf-8-sig")
        stream = io.StringIO(content, newline=None)
        reader = csv.DictReader(stream)

        # Existing user expenses for duplicate detection (lookup by (date_str, amount, note_clean, cat_clean))
        existing_expenses = Expense.query.filter_by(user_id=current_user.id).all()
        existing_set = set(
            (
                e.date.isoformat(),
                round(e.amount, 2),
                (e.note or "").strip().lower(),
                (e.category.name if e.category else "").strip().lower(),
            )
            for e in existing_expenses
        )

        valid_rows = []
        duplicate_rows = []
        invalid_rows = []
        row_num = 1

        for row in reader:
            row_num += 1
            clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            date_val = clean_row.get("date", "")
            cat_name = clean_row.get("category", "")
            amount_val = clean_row.get("amount", "")
            note_val = clean_row.get("note", "")
            rec_val = clean_row.get("recurring", "no").lower()
            period_val = clean_row.get("recurrence period", clean_row.get("recurrence_period", "")).lower()
            pay_val = clean_row.get("payment method", clean_row.get("payment_method", "UPI / Online"))

            # Validate amount
            try:
                amount = float(amount_val)
                if amount <= 0:
                    invalid_rows.append({"row": row_num, "data": row, "error": "Amount must be greater than 0"})
                    continue
            except (ValueError, TypeError):
                invalid_rows.append({"row": row_num, "data": row, "error": f"Invalid amount: '{amount_val}'"})
                continue

            if not cat_name:
                invalid_rows.append({"row": row_num, "data": row, "error": "Missing category name"})
                continue

            # Parse date
            parsed_date = date.today()
            if date_val:
                parsed_ok = False
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                    try:
                        parsed_date = datetime.strptime(date_val, fmt).date()
                        parsed_ok = True
                        break
                    except ValueError:
                        pass
                if not parsed_ok:
                    invalid_rows.append({"row": row_num, "data": row, "error": f"Unparseable date: '{date_val}'"})
                    continue

            is_recurring = rec_val in ["yes", "true", "1", "y"]
            recurrence_period = period_val if period_val in ["weekly", "monthly", "yearly"] else None
            payment_method = pay_val if pay_val in PAYMENT_METHODS else "UPI / Online"

            record = {
                "row_num": row_num,
                "date": parsed_date.isoformat(),
                "category": cat_name.title(),
                "amount": amount,
                "note": note_val,
                "is_recurring": is_recurring,
                "recurrence_period": recurrence_period,
                "payment_method": payment_method,
            }

            key = (parsed_date.isoformat(), round(amount, 2), note_val.lower(), cat_name.lower())
            if key in existing_set:
                record["is_duplicate"] = True
                duplicate_rows.append(record)
            else:
                record["is_duplicate"] = False
                valid_rows.append(record)

        total_detected = len(valid_rows) + len(duplicate_rows) + len(invalid_rows)

        return render_template(
            "expenses/import_preview.html",
            valid_rows=valid_rows,
            duplicate_rows=duplicate_rows,
            invalid_rows=invalid_rows,
            total_detected=total_detected,
            valid_json=json.dumps(valid_rows),
            duplicate_json=json.dumps(duplicate_rows),
        )

    except Exception as ex:
        flash(f"Failed to parse CSV file: {str(ex)}", "error")
        return redirect(url_for("expenses.list_expenses"))


@expenses_bp.route("/expenses/import/confirm", methods=["POST"])
@login_required
def confirm_import():
    valid_json = request.form.get("valid_data", "[]")
    duplicate_json = request.form.get("duplicate_data", "[]")
    include_duplicates = bool(request.form.get("include_duplicates"))

    try:
        rows_to_import = json.loads(valid_json)
        if include_duplicates:
            rows_to_import.extend(json.loads(duplicate_json))
    except Exception:
        flash("Invalid import payload.", "error")
        return redirect(url_for("expenses.list_expenses"))

    if not rows_to_import:
        flash("No records selected for import.", "warning")
        return redirect(url_for("expenses.list_expenses"))

    user_categories = {c.name.lower(): c for c in Category.query.filter_by(user_id=current_user.id).all()}
    count = 0

    for r in rows_to_import:
        cat_key = r["category"].lower()
        if cat_key in user_categories:
            cat = user_categories[cat_key]
        else:
            cat = Category(name=r["category"], user_id=current_user.id)
            db.session.add(cat)
            db.session.flush()
            user_categories[cat_key] = cat

        parsed_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
        expense = Expense(
            amount=float(r["amount"]),
            note=r.get("note", ""),
            date=parsed_date,
            payment_method=r.get("payment_method", "UPI / Online"),
            category_id=cat.id,
            user_id=current_user.id,
            is_recurring=bool(r.get("is_recurring")),
            recurrence_period=r.get("recurrence_period"),
            status="active",
        )
        db.session.add(expense)
        count += 1

    db.session.commit()
    flash(f"Successfully imported {count} transaction(s) into your ledger.", "success")
    return redirect(url_for("expenses.list_expenses"))


# Fallback direct import for automated tests / single-step form
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

        user_categories = {c.name.lower(): c for c in Category.query.filter_by(user_id=current_user.id).all()}

        for row in reader:
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
    writer.writerow(["Date", "Category", "Amount", "Note", "Recurring", "Recurrence Period", "Payment Method"])
    today = date.today().isoformat()
    writer.writerow([today, "Groceries", "1250.00", "Weekly supermarket provisions", "No", "", "UPI / Online"])
    writer.writerow([today, "Subscriptions", "499.00", "Netflix Standard Plan", "Yes", "monthly", "Credit Card"])
    writer.writerow([today, "Dining Out", "820.50", "Dinner with team", "No", "", "Debit Card"])
    writer.writerow([today, "Transportation", "320.00", "Uber ride to office", "No", "", "UPI / Online"])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=spendwise_template.csv"},
    )
