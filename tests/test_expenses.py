import io
import unittest
from datetime import date
from app import create_app, db
from app.models import User, Category, Expense
from config import TestConfig


class ExpensesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create and log in a test user
        self.user = User(name="Tester", email="test@example.com", currency="INR")
        self.user.set_password("pass123")
        db.session.add(self.user)
        db.session.commit()

        self.category = Category(name="Groceries", monthly_budget=5000.0, user_id=self.user.id)
        db.session.add(self.category)
        db.session.commit()

        self.client.post("/login", data={"email": "test@example.com", "password": "pass123"})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_add_expense_valid(self):
        response = self.client.post(
            "/expenses/add",
            data={
                "amount": "450.50",
                "category_id": self.category.id,
                "date": date.today().isoformat(),
                "note": "Supermarket veggies",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        expense = Expense.query.filter_by(note="Supermarket veggies").first()
        self.assertIsNotNone(expense)
        self.assertEqual(expense.amount, 450.50)
        self.assertEqual(expense.category_id, self.category.id)

    def test_add_expense_negative_amount_fails(self):
        response = self.client.post(
            "/expenses/add",
            data={
                "amount": "-100",
                "category_id": self.category.id,
                "date": date.today().isoformat(),
                "note": "Invalid",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Expense amount must be greater than 0", response.data)
        self.assertEqual(Expense.query.count(), 0)

    def test_edit_expense(self):
        expense = Expense(
            amount=100.0,
            note="Original Note",
            date=date.today(),
            category_id=self.category.id,
            user_id=self.user.id,
        )
        db.session.add(expense)
        db.session.commit()

        response = self.client.post(
            f"/expenses/{expense.id}/edit",
            data={
                "amount": "250.00",
                "category_id": self.category.id,
                "date": date.today().isoformat(),
                "note": "Updated Note",
                "is_recurring": "on",
                "recurrence_period": "monthly",
                "status": "active",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        db.session.refresh(expense)
        self.assertEqual(expense.amount, 250.00)
        self.assertEqual(expense.note, "Updated Note")
        self.assertTrue(expense.is_recurring)
        self.assertEqual(expense.recurrence_period, "monthly")

    def test_delete_expense(self):
        expense = Expense(
            amount=100.0,
            note="To Delete",
            date=date.today(),
            category_id=self.category.id,
            user_id=self.user.id,
        )
        db.session.add(expense)
        db.session.commit()

        response = self.client.post(f"/expenses/{expense.id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(db.session.get(Expense, expense.id))

    def test_manage_categories(self):
        # Add Category
        response = self.client.post(
            "/categories/add",
            data={"name": "Travel", "monthly_budget": "10000"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        cat = Category.query.filter_by(name="Travel", user_id=self.user.id).first()
        self.assertIsNotNone(cat)
        self.assertEqual(cat.monthly_budget, 10000.0)

        # Edit Category
        response = self.client.post(
            f"/categories/{cat.id}/edit",
            data={"name": "Holiday Travel", "monthly_budget": "15000"},
            follow_redirects=True,
        )
        db.session.refresh(cat)
        self.assertEqual(cat.name, "Holiday Travel")
        self.assertEqual(cat.monthly_budget, 15000.0)

        # Delete Category
        response = self.client.post(f"/categories/{cat.id}/delete", follow_redirects=True)
        self.assertIsNone(db.session.get(Category, cat.id))

    def test_csv_import(self):
        csv_data = """Date,Category,Amount,Note,Recurring,Recurrence Period
2026-08-01,Groceries,1200.00,Weekly fruits,No,
2026-08-05,Streaming,499.00,Disney+ Hotstar,Yes,monthly
"""
        response = self.client.post(
            "/expenses/import",
            data={"file": (io.BytesIO(csv_data.encode("utf-8")), "expenses.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully imported 2 expense", response.data)
        
        # Verify auto-created category
        streaming_cat = Category.query.filter_by(name="Streaming", user_id=self.user.id).first()
        self.assertIsNotNone(streaming_cat)
        
        # Verify recurring expense
        hotstar = Expense.query.filter_by(note="Disney+ Hotstar").first()
        self.assertIsNotNone(hotstar)
        self.assertTrue(hotstar.is_recurring)
        self.assertEqual(hotstar.recurrence_period, "monthly")

    def test_export_json_and_csv(self):
        expense = Expense(
            amount=300.0,
            note="Lunch",
            date=date.today(),
            category_id=self.category.id,
            user_id=self.user.id,
        )
        db.session.add(expense)
        db.session.commit()

        # CSV Export
        res_csv = self.client.get("/export/csv?format=csv")
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn(b"Lunch", res_csv.data)

        # JSON Export
        res_json = self.client.get("/export/csv?format=json")
        self.assertEqual(res_json.status_code, 200)
        self.assertIn(b'"note": "Lunch"', res_json.data)


if __name__ == "__main__":
    unittest.main()
