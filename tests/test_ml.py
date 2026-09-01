import unittest
from app import create_app, db
from app.models import User, Category
from app.ml import predict_expense_category
from config import TestConfig


class MLTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(name="ML Tester", email="ml@example.com")
        self.user.set_password("pass123")
        db.session.add(self.user)
        db.session.commit()

        self.cat_food = Category(name="Food & Dining", user_id=self.user.id)
        self.cat_trans = Category(name="Transportation", user_id=self.user.id)
        self.cat_subs = Category(name="Subscriptions", user_id=self.user.id)
        db.session.add_all([self.cat_food, self.cat_trans, self.cat_subs])
        db.session.commit()

        self.client.post("/login", data={"email": "ml@example.com", "password": "pass123"})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_predict_food(self):
        user_cats = Category.query.filter_by(user_id=self.user.id).all()
        res = predict_expense_category("Swiggy dinner order ₹450", user_cats)
        self.assertEqual(res["predicted_category"], "Food & Dining")
        self.assertEqual(res["category_id"], self.cat_food.id)
        self.assertTrue(res["is_confident"])
        self.assertGreater(res["confidence_pct"], 40)

    def test_predict_transportation(self):
        user_cats = Category.query.filter_by(user_id=self.user.id).all()
        res = predict_expense_category("Uber ride to airport ₹320", user_cats)
        self.assertEqual(res["predicted_category"], "Transportation")
        self.assertEqual(res["category_id"], self.cat_trans.id)
        self.assertTrue(res["is_confident"])

    def test_predict_subscription(self):
        user_cats = Category.query.filter_by(user_id=self.user.id).all()
        res = predict_expense_category("Netflix monthly plan", user_cats)
        self.assertEqual(res["predicted_category"], "Subscriptions")
        self.assertEqual(res["category_id"], self.cat_subs.id)

    def test_empty_string_fallback(self):
        res = predict_expense_category("")
        self.assertIsNone(res["predicted_category"])
        self.assertFalse(res["is_confident"])
        self.assertEqual(res["confidence_pct"], 0)

    def test_api_predict_category_endpoint(self):
        response = self.client.post(
            "/api/predict-category",
            json={"note": "Starbucks latte and coffee"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["predicted_category"], "Food & Dining")
        self.assertTrue(data["is_confident"])


if __name__ == "__main__":
    unittest.main()
