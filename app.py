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

    app.register_blueprint(auth_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(settlements_bp)
    app.register_blueprint(comments_bp)

    # Root route redirect to dashboard
    @app.route('/')
    def index():
        return redirect(url_for('groups.dashboard'))

    # Create tables
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"Error during db.create_all(): {e}")

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
