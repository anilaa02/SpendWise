from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
from sqlalchemy import text

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_user_preferences():
        from flask_login import current_user
        currency_sym = "₹"
        if current_user.is_authenticated and hasattr(current_user, "currency_symbol"):
            currency_sym = current_user.currency_symbol
        return dict(currency_sym=currency_sym)

    from app.routes.auth import auth_bp
    from app.routes.expenses import expenses_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.income import income_bp
    from app.routes.goals import goals_bp
    from app.routes.analytics import analytics_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(income_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(api_bp)

    # Allow JSON API endpoints to be invoked via frontend fetch/XHR
    csrf.exempt(api_bp)

    # Custom HTTP error handlers
    @app.errorhandler(400)
    def bad_request_error(e):
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    with app.app_context():
        db.create_all()

        # Automatic SQLite schema migration for older database files:
        try:
            with db.engine.connect() as conn:
                # User table migration
                user_cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(user)").fetchall()]
                if "currency" not in user_cols:
                    conn.exec_driver_sql("ALTER TABLE user ADD COLUMN currency VARCHAR(10) DEFAULT 'INR' NOT NULL")

                # Expense table migration
                expense_cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(expense)").fetchall()]
                if "status" not in expense_cols:
                    conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN status VARCHAR(20) DEFAULT 'active' NOT NULL")
                if "payment_method" not in expense_cols:
                    conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN payment_method VARCHAR(50) DEFAULT 'UPI / Online' NOT NULL")
                if "is_anomaly" not in expense_cols:
                    conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN is_anomaly BOOLEAN DEFAULT 0 NOT NULL")
                if "anomaly_reason" not in expense_cols:
                    conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN anomaly_reason VARCHAR(255)")

                conn.commit()
        except Exception as e:
            app.logger.warning(f"Database schema auto-migration notice: {e}")

    return app



