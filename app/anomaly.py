"""
Statistical Spending Anomaly Detection Engine for SpendWise.
Analyzes category-specific spending distribution using IQR (Interquartile Range)
and Z-score thresholds to identify unusually large purchases without excessive false alarms.
"""
import numpy as np
from app.models import Expense, Category, User
from app import db


def detect_spending_anomaly(amount, category_id, user_id, exclude_expense_id=None):
    """
    Evaluates whether an expense amount represents a spending anomaly in its category.
    Returns:
      (is_anomaly: bool, reason: str or None, typical_range: str or None)
    """
    if not amount or amount <= 0 or not category_id or not user_id:
        return False, None, None

    query = Expense.query.filter_by(user_id=user_id, category_id=category_id)
    if exclude_expense_id:
        query = query.filter(Expense.id != exclude_expense_id)

    historical_expenses = query.all()
    if len(historical_expenses) < 3:
        return False, None, None

    amounts = [e.amount for e in historical_expenses]
    user = db.session.get(User, user_id)
    sym = user.currency_symbol if user else "₹"
    cat = db.session.get(Category, category_id)
    cat_name = cat.name if cat else "this category"

    # Calculate IQR and descriptive percentiles
    q25 = float(np.percentile(amounts, 25))
    q50 = float(np.median(amounts))
    q75 = float(np.percentile(amounts, 75))
    iqr = q75 - q25

    mean = float(np.mean(amounts))
    std = float(np.std(amounts)) if len(amounts) > 1 else 0.0

    # Upper bound: Q3 + 1.5 * IQR or Mean + 2.2 * Std
    iqr_upper = q75 + 1.5 * iqr
    std_upper = mean + 2.2 * std if std > 0 else mean * 2.5
    threshold = max(iqr_upper, std_upper, q50 * 2.2)

    # Minimum absolute noise floor (to avoid flagging ₹30 vs ₹10)
    noise_floor = 300.0

    is_anomaly = (amount >= threshold) and (amount >= noise_floor)

    if is_anomaly:
        ratio = amount / q50 if q50 > 0 else (amount / mean if mean > 0 else 2.5)
        reason = (
            f"This transaction of {sym}{amount:.2f} is significantly higher ({ratio:.1f}x) than your typical "
            f"{sym}{q25:.0f}–{sym}{q75:.0f} spending range in {cat_name}."
        )
        typical_range = f"{sym}{q25:.0f} – {sym}{q75:.0f}"
        return True, reason, typical_range

    return False, None, f"{sym}{q25:.0f} – {sym}{q75:.0f}"
