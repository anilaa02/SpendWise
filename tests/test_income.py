import unittest
from datetime import date
from app import create_app, db
from app.models import User, Income
from config import TestConfig


class IncomeTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(name="Income User", email="income@example.com", currency="INR")
        self.user.set_password("pass123")
        db.session.add(self.user)
        db.session.commit()

        self.client.post("/login", data={"email": "income@example.com", "password": "pass123"})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_add_income(self):
        response = self.client.post(
            "/income/add",
            data={
                "amount": "65000",
                "source": "Salary",
                "date": date.today().isoformat(),
                "note": "Monthly Tech Salary",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        inc = Income.query.filter_by(user_id=self.user.id, source="Salary").first()
        self.assertIsNotNone(inc)
        self.assertEqual(inc.amount, 65000.0)
        self.assertEqual(inc.note, "Monthly Tech Salary")

    def test_add_income_invalid_amount_fails(self):
        response = self.client.post(
            "/income/add",
            data={
                "amount": "-500",
                "source": "Salary",
                "date": date.today().isoformat(),
            },
            follow_redirects=True,
        )
        self.assertIn(b"Income amount must be greater than 0", response.data)
        self.assertEqual(Income.query.filter_by(user_id=self.user.id).count(), 0)

    def test_edit_income(self):
        inc = Income(amount=5000.0, source="Freelance", date=date.today(), user_id=self.user.id)
        db.session.add(inc)
        db.session.commit()

        response = self.client.post(
            f"/income/{inc.id}/edit",
            data={
                "amount": "7500.00",
                "source": "Consulting",
                "date": date.today().isoformat(),
                "note": "Updated Consulting payout",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        db.session.refresh(inc)
        self.assertEqual(inc.amount, 7500.00)
        self.assertEqual(inc.source, "Consulting")

    def test_delete_income(self):
        inc = Income(amount=2000.0, source="Gift", date=date.today(), user_id=self.user.id)
        db.session.add(inc)
        db.session.commit()

        response = self.client.post(f"/income/{inc.id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(db.session.get(Income, inc.id))


if __name__ == "__main__":
    unittest.main()
