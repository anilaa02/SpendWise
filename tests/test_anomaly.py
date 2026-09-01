import unittest
from datetime import date
from app import create_app, db
from app.models import User, Category, Expense
from app.anomaly import detect_spending_anomaly
from config import TestConfig


class AnomalyTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(name="Anomaly Tester", email="anomaly@example.com", currency="INR")
        self.user.set_password("pass123")
        db.session.add(self.user)
        db.session.commit()

        self.cat_dining = Category(name="Dining Out", user_id=self.user.id)
        db.session.add(self.cat_dining)
        db.session.commit()

        self.client.post("/login", data={"email": "anomaly@example.com", "password": "pass123"})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_insufficient_history_returns_false(self):
        is_anomaly, reason, _ = detect_spending_anomaly(1500.0, self.cat_dining.id, self.user.id)
        self.assertFalse(is_anomaly)
        self.assertIsNone(reason)

    def test_anomaly_detection_trigger(self):
        # Create baseline history of typical Dining Out: 150, 200, 250, 300, 180
        for amt in [150.0, 200.0, 250.0, 300.0, 180.0]:
            e = Expense(amount=amt, note="Meal", date=date.today(), user_id=self.user.id, category_id=self.cat_dining.id)
            db.session.add(e)
        db.session.commit()

        # Normal purchase: 220 -> False
        is_anom, _, _ = detect_spending_anomaly(220.0, self.cat_dining.id, self.user.id)
        self.assertFalse(is_anom)

        # Huge spike: 4800 -> True
        is_anom, reason, _ = detect_spending_anomaly(4800.0, self.cat_dining.id, self.user.id)
        self.assertTrue(is_anom)
        self.assertIn("significantly higher", reason)

    def test_api_check_anomaly_endpoint(self):
        for amt in [100.0, 120.0, 110.0, 130.0]:
            e = Expense(amount=amt, note="Normal", date=date.today(), user_id=self.user.id, category_id=self.cat_dining.id)
            db.session.add(e)
        db.session.commit()

        res = self.client.post(
            "/api/check-anomaly",
            json={"amount": 3500.0, "category_id": self.cat_dining.id},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["is_anomaly"])
        self.assertIsNotNone(data["reason"])


if __name__ == "__main__":
    unittest.main()
