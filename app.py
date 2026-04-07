from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import os
import secrets
from models import db, AdminUser

# Generate a strong, persistent secret key if one doesn't exist
secret_key_path = 'instance/secret.key'
if os.path.exists(secret_key_path):
    with open(secret_key_path, 'r') as f:
        secret_key = f.read().strip()
else:
    secret_key = secrets.token_hex(32)
    os.makedirs('instance', exist_ok=True)
    with open(secret_key_path, 'w') as f:
        f.write(secret_key)

app = Flask(__name__)
csrf = CSRFProtect(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secret_key)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tpu_manager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# Import routes
import routes_auth
import routes_accounts
import routes_tpu
from apscheduler.schedulers.background import BackgroundScheduler
import scheduler_tasks

# Initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduler_tasks.check_tpu_status, trigger="interval", minutes=5)

# In dev mode with Werkzeug, it runs the app twice. This prevents the scheduler from starting twice.
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler.start()

if __name__ == '__main__':
    try:
        # Debug is set to False to prevent exposing the Werkzeug debugger to the internet
        app.run(debug=False, host='0.0.0.0', port=5000)
    except (KeyboardInterrupt, SystemExit):
        if scheduler.running:
            scheduler.shutdown()
