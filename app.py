import os
from flask import Flask, redirect, url_for
from dotenv import load_dotenv
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from models import db, User

# Load environment variables
load_dotenv()

bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app(config_override=None):
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-splitwise-clone')
    
    # Retrieve and sanitize database URL
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        # Fallback to local PostgreSQL (assuming default postgres credentials)
        database_url = 'postgresql://postgres:postgres@localhost:5432/splitwise'
    
    # Handle Render/Heroku postgres prefix issue
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
    # Strip pgbouncer query parameter to avoid psycopg2 ProgrammingError
    if database_url and '?' in database_url:
        database_url = database_url.split('?')[0]
        
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Apply overrides if any
    if config_override:
        app.config.update(config_override)

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Import and register Blueprints
    from routes.auth import auth_bp
    from routes.groups import groups_bp
    from routes.expenses import expenses_bp
    from routes.settlements import settlements_bp
    from routes.comments import comments_bp
    from routes.importer import importer_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(settlements_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(importer_bp)

    # Root route redirect to dashboard
    @app.route('/')
    def index():
        return redirect(url_for('groups.dashboard'))

    # Create tables & run migrations
    with app.app_context():
        try:
            db.create_all()
            
            # Auto-migrations using SQLAlchemy inspect
            from sqlalchemy import inspect, text
            from decimal import Decimal
            
            inspector = inspect(db.engine)
            
            # Check group_members columns
            gm_cols = [c['name'] for c in inspector.get_columns('group_members')]
            if 'joined_at' not in gm_cols:
                db.session.execute(text("ALTER TABLE group_members ADD COLUMN joined_at DATE NOT NULL DEFAULT CURRENT_DATE"))
            if 'left_at' not in gm_cols:
                db.session.execute(text("ALTER TABLE group_members ADD COLUMN left_at DATE"))
            db.session.commit()
                
            # Drop unique constraint on group_members if in postgres
            if db.engine.dialect.name == 'postgresql':
                try:
                    db.session.execute(text("ALTER TABLE group_members DROP CONSTRAINT IF EXISTS uq_group_user"))
                    db.session.commit()
                except Exception as ex:
                    db.session.rollback()
                    print(f"Warning: could not drop uq_group_user constraint: {ex}")
                
            # Check expenses columns
            exp_cols = [c['name'] for c in inspector.get_columns('expenses')]
            if 'original_amount' not in exp_cols:
                db.session.execute(text("ALTER TABLE expenses ADD COLUMN original_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00"))
            if 'currency' not in exp_cols:
                db.session.execute(text("ALTER TABLE expenses ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'INR'"))
            if 'exchange_rate' not in exp_cols:
                db.session.execute(text("ALTER TABLE expenses ADD COLUMN exchange_rate NUMERIC(10, 6) NOT NULL DEFAULT 1.0"))
            if 'date' not in exp_cols:
                db.session.execute(text("ALTER TABLE expenses ADD COLUMN date DATE NOT NULL DEFAULT CURRENT_DATE"))
            db.session.commit()

            # Check settlements columns
            set_cols = [c['name'] for c in inspector.get_columns('settlements')]
            if 'original_amount' not in set_cols:
                db.session.execute(text("ALTER TABLE settlements ADD COLUMN original_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00"))
            if 'currency' not in set_cols:
                db.session.execute(text("ALTER TABLE settlements ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'INR'"))
            if 'exchange_rate' not in set_cols:
                db.session.execute(text("ALTER TABLE settlements ADD COLUMN exchange_rate NUMERIC(10, 6) NOT NULL DEFAULT 1.0"))
            if 'date' not in set_cols:
                db.session.execute(text("ALTER TABLE settlements ADD COLUMN date DATE NOT NULL DEFAULT CURRENT_DATE"))
            db.session.commit()
            
            # Update existing records to ensure original_amount is populated
            db.session.execute(text("UPDATE expenses SET original_amount = total_amount WHERE original_amount = 0.00"))
            db.session.execute(text("UPDATE settlements SET original_amount = amount WHERE original_amount = 0.00"))
            db.session.commit()
            
            # Seed default exchange rates
            from models import ExchangeRate
            if not ExchangeRate.query.first():
                rate1 = ExchangeRate(from_currency='USD', to_currency='INR', rate=Decimal('83.00'))
                rate2 = ExchangeRate(from_currency='INR', to_currency='USD', rate=Decimal('0.012048'))
                db.session.add_all([rate1, rate2])
                db.session.commit()
                
        except Exception as e:
            db.session.rollback()
            print(f"Error during db.create_all() or migrations: {e}")

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
