"""
JSON API Endpoints for SpendWise.
Provides asynchronous ML category prediction and real-time spending anomaly detection.
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.ml import predict_expense_category
from app.anomaly import detect_spending_anomaly
from app.models import Category

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/predict-category", methods=["POST"])
@login_required
def predict_category():
    data = request.get_json(silent=True) or request.form
    text = (data.get("text") or data.get("note") or "").strip()

    if not text:
        return jsonify({
            "predicted_category": None,
            "matched_category_name": None,
            "category_id": None,
            "confidence": 0.0,
            "confidence_pct": 0,
            "is_confident": False,
        })

    user_categories = Category.query.filter_by(user_id=current_user.id).all()
    result = predict_expense_category(text, user_categories)
    return jsonify(result)


@api_bp.route("/check-anomaly", methods=["POST"])
@login_required
def check_anomaly():
    data = request.get_json(silent=True) or request.form
    try:
        amount = float(data.get("amount", 0))
        category_id = int(data.get("category_id", 0))
    except (ValueError, TypeError):
        return jsonify({"is_anomaly": False, "reason": None, "typical_range": None})

    expense_id = data.get("expense_id")
    if expense_id:
        try:
            expense_id = int(expense_id)
        except (ValueError, TypeError):
            expense_id = None

    is_anomaly, reason, typical_range = detect_spending_anomaly(
        amount=amount,
        category_id=category_id,
        user_id=current_user.id,
        exclude_expense_id=expense_id,
    )

    return jsonify({
        "is_anomaly": is_anomaly,
        "reason": reason,
        "typical_range": typical_range,
    })
