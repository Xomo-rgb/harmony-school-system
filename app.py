from flask import Flask, redirect, url_for
from config import Config
from routes.auth import auth_bp
from routes.student import student_bp
from routes.teacher import teacher_bp
from routes.admin import admin_bp
from routes.user import user_bp
from routes.assignment import assignment_bp
from routes.profile import profile_bp
from routes.curriculum import curriculum_bp
from db import close_db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config) # A more robust way to load config
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix='/students')
    app.register_blueprint(teacher_bp, url_prefix='/teachers')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(user_bp, url_prefix='/users')
    app.register_blueprint(assignment_bp, url_prefix='/assignments')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(curriculum_bp, url_prefix='/curriculum')

    # Register the teardown function
    app.teardown_appcontext(close_db)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app

# --- THE FIX IS HERE ---
# We create the app instance in the global scope
app = create_app()

if __name__ == "__main__":
    # This part is now only used for local development
    app.run(debug=True)