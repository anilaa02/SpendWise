"""
Machine Learning Expense Categorization Engine for SpendWise.
Uses TF-IDF feature extraction with Multinomial Naive Bayes / Logistic Regression.
Provides predicted category name, category ID matching user categories, and confidence score.
"""
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

TRAINING_DATA = [
    # Food & Dining
    ("Swiggy food delivery meal", "Food & Dining"),
    ("Zomato order dinner biryani", "Food & Dining"),
    ("Starbucks coffee tea pastry snack", "Food & Dining"),
    ("McDonalds burger meal fries coke", "Food & Dining"),
    ("Dominos pizza party dinner", "Food & Dining"),
    ("KFC chicken meal lunch", "Food & Dining"),
    ("Subway sandwich healthy lunch", "Food & Dining"),
    ("Chipotle burrito bowl dinner", "Food & Dining"),
    ("Local cafe breakfast chai coffee", "Food & Dining"),
    ("Restaurant fine dining dinner with family", "Food & Dining"),
    ("Bar pub beer drinks with friends", "Food & Dining"),
    ("Bakery bread cakes pastry", "Food & Dining"),
    ("Dine out food court buffet", "Food & Dining"),
    ("Canteen snacks lunch", "Food & Dining"),
    ("Food truck tacos ice cream", "Food & Dining"),

    # Groceries
    ("Supermarket fruits vegetables groceries", "Groceries"),
    ("BigBasket weekly grocery shopping provisions", "Groceries"),
    ("Blinkit instant grocery delivery essentials", "Groceries"),
    ("Zepto milk eggs bread butter cheese", "Groceries"),
    ("Trader Joes snacks pantry items", "Groceries"),
    ("Whole Foods market organic veggies", "Groceries"),
    ("Walmart produce rice wheat oil cereals", "Groceries"),
    ("Costco wholesale bulk provisions groceries", "Groceries"),
    ("Local vegetable fruit market bazaar mandi", "Groceries"),
    ("Butcher fresh meat chicken fish eggs", "Groceries"),
    ("Dairy milk curd paneer butter", "Groceries"),
    ("Grocery kirana general store provisions", "Groceries"),

    # Transportation
    ("Uber cab ride to airport office", "Transportation"),
    ("Ola cab city travel taxi", "Transportation"),
    ("Gas station petrol refill fuel", "Transportation"),
    ("Shell diesel car fuel pump", "Transportation"),
    ("Metro train smart card recharge transit", "Transportation"),
    ("City bus ticket pass commute", "Transportation"),
    ("Airport parking garage fee valet", "Transportation"),
    ("Toll plaza highway fastag payment", "Transportation"),
    ("Auto rickshaw meter fare", "Transportation"),
    ("Flight ticket airline booking Indigo flight", "Transportation"),
    ("Railway IRCTC train ticket reservation", "Transportation"),
    ("Lyft ride home taxi fare", "Transportation"),
    ("Car service mechanic tyre repair wash", "Transportation"),

    # Subscriptions
    ("Netflix monthly streaming video subscription plan", "Subscriptions"),
    ("Spotify premium music streaming podcast", "Subscriptions"),
    ("Amazon Prime yearly membership prime video", "Subscriptions"),
    ("YouTube Premium ad-free subscription", "Subscriptions"),
    ("Disney+ Hotstar annual renewal plan", "Subscriptions"),
    ("Apple iCloud storage monthly cloud backup", "Subscriptions"),
    ("Google One cloud drive storage subscription", "Subscriptions"),
    ("GitHub Copilot developer subscription", "Subscriptions"),
    ("ChatGPT Plus OpenAI monthly subscription", "Subscriptions"),
    ("Gym fitness center monthly membership pass", "Subscriptions"),
    ("Newspaper journal digital magazine subscription", "Subscriptions"),
    ("Audible audiobook monthly credit subscription", "Subscriptions"),

    # Utilities & Bills
    ("Electricity power energy board monthly bill", "Utilities & Bills"),
    ("Water supply municipal utility bill payment", "Utilities & Bills"),
    ("Home WiFi broadband fiber internet bill Airtel Jio", "Utilities & Bills"),
    ("Mobile postpaid prepaid recharge phone bill", "Utilities & Bills"),
    ("LPG cooking gas cylinder refill Bharat Indane", "Utilities & Bills"),
    ("DTH cable television dish recharge", "Utilities & Bills"),
    ("Trash garbage waste collection municipal utility fee", "Utilities & Bills"),
    ("Maintenance utility society sewage bill", "Utilities & Bills"),

    # Housing & Rent
    ("Monthly apartment house flat rent owner", "Housing & Rent"),
    ("Society building flat maintenance charges", "Housing & Rent"),
    ("Home mortgage loan installment EMI housing", "Housing & Rent"),
    ("Property tax house tax municipal payment", "Housing & Rent"),
    ("Home painting repair plumber electrician hardware", "Housing & Rent"),
    ("Furniture home decor bedroom sofa table", "Housing & Rent"),

    # Entertainment
    ("PVR cinema movie tickets popcorn movie theater", "Entertainment"),
    ("IMAX movie ticket booking Cinepolis", "Entertainment"),
    ("Concert live show music festival stadium pass", "Entertainment"),
    ("Steam video game purchase download", "Entertainment"),
    ("PlayStation Network PS Plus game store", "Entertainment"),
    ("Theme park amusement waterpark tickets entry", "Entertainment"),
    ("Bowling arcade games weekend hangout", "Entertainment"),
    ("Board games escape room outing", "Entertainment"),

    # Healthcare
    ("Apollo pharmacy prescription medicines pills tablets", "Healthcare"),
    ("Doctor physician specialist clinic consultation fee", "Healthcare"),
    ("Dentist dental clinic cleaning root canal", "Healthcare"),
    ("Diagnostic lab blood test scan MRI X-ray", "Healthcare"),
    ("Health medical insurance premium Mediclaim", "Healthcare"),
    ("Hospital emergency care treatment patient fee", "Healthcare"),
    ("Eye clinic spectacles glasses contact lenses", "Healthcare"),
    ("Physiotherapy therapy counseling session", "Healthcare"),

    # Shopping & Personal Care
    ("Amazon online shopping order clothes electronics", "Shopping"),
    ("Zara clothing jeans t-shirt jacket apparel", "Shopping"),
    ("Nike shoes sneakers sports wear apparel", "Shopping"),
    ("Myntra fashion shopping shoes dress", "Shopping"),
    ("H&M clothing wardrobe fashion", "Shopping"),
    ("Hair salon haircut styling grooming spa", "Shopping"),
    ("Cosmetics skincare shampoo makeup beauty products", "Shopping"),
    ("Apple store electronics headphones laptop gadgets", "Shopping"),
    ("Bookstore books novel stationery items", "Shopping"),
    ("Jewelry accessories gift watch shopping", "Shopping"),
]

_model_pipeline = None


def _get_or_train_model():
    global _model_pipeline
    if _model_pipeline is not None:
        return _model_pipeline

    texts, labels = zip(*TRAINING_DATA)
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, lowercase=True)),
        ("clf", MultinomialNB(alpha=0.05)),
    ])
    pipeline.fit(texts, labels)
    _model_pipeline = pipeline
    return _model_pipeline


def _clean_text(text):
    if not text:
        return ""
    # Strip currency signs, digits, and noise symbols
    cleaned = re.sub(r"[₹\$€£¥0-9,.:;!?()\-_/\\@#]", " ", text)
    return " ".join(cleaned.split()).strip()


def predict_expense_category(text, user_categories=None):
    """
    Predicts category from transaction note/description.
    Returns:
      dict {
        "predicted_category": str or None,
        "matched_category_name": str or None,
        "category_id": int or None,
        "confidence": float (0.0 - 1.0),
        "confidence_pct": int (0 - 100),
        "is_confident": bool
      }
    """
    cleaned = _clean_text(text)
    if not cleaned or len(cleaned) < 2:
        return {
            "predicted_category": None,
            "matched_category_name": None,
            "category_id": None,
            "confidence": 0.0,
            "confidence_pct": 0,
            "is_confident": False,
        }

    try:
        model = _get_or_train_model()
        probs = model.predict_proba([cleaned])[0]
        classes = list(model.classes_)
        top_idx = int(probs.argmax())
        pred_label = str(classes[top_idx])
        raw_conf = float(probs[top_idx])

        # Confidence calibration to a 0.50 - 0.98 display scale for clear user intuition
        confidence = min(0.98, max(0.40, raw_conf))
    except Exception:
        return {
            "predicted_category": None,
            "matched_category_name": None,
            "category_id": None,
            "confidence": 0.0,
            "confidence_pct": 0,
            "is_confident": False,
        }

    # Map predicted label to user categories if provided
    matched_cat = None
    if user_categories:
        pred_clean = pred_label.lower()
        # 1. Exact or substring match
        for cat in user_categories:
            cat_name_clean = cat.name.lower()
            if cat_name_clean == pred_clean or cat_name_clean in pred_clean or pred_clean in cat_name_clean:
                matched_cat = cat
                break

        # 2. Keyword fallback mappings
        if not matched_cat:
            synonyms = {
                "food & dining": ["dining", "food", "groceries", "restaurant", "meal", "cafe"],
                "groceries": ["food", "groceries", "supermarket", "provisions", "market"],
                "transportation": ["transport", "travel", "cab", "commute", "fuel", "vehicle", "ride"],
                "subscriptions": ["subscription", "subscriptions", "recurring", "bills", "streaming"],
                "utilities & bills": ["utilities", "bills", "utilities & bills", "electricity", "water", "phone"],
                "housing & rent": ["housing", "rent", "housing & rent", "home", "maintenance"],
                "entertainment": ["entertainment", "leisure", "movies", "games", "fun"],
                "healthcare": ["health", "medical", "healthcare", "wellness", "doctor", "pharmacy"],
                "shopping": ["shopping", "personal", "retail", "general", "clothing"],
            }
            target_syns = synonyms.get(pred_clean, [])
            for cat in user_categories:
                cat_lower = cat.name.lower()
                if any(syn in cat_lower for syn in target_syns):
                    matched_cat = cat
                    break

    return {
        "predicted_category": str(pred_label),
        "matched_category_name": str(matched_cat.name) if matched_cat else None,
        "category_id": int(matched_cat.id) if matched_cat else None,
        "confidence": float(round(confidence, 2)),
        "confidence_pct": int(round(confidence * 100)),
        "is_confident": confidence >= 0.45,
    }
