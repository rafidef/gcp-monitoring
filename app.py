from flask import Flask
from flask_login import LoginManager
import os
from models import db, AdminUser

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-secret-key-change-in-prod')
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
        app.run(debug=True, host='0.0.0.0')
    except (KeyboardInterrupt, SystemExit):
        if scheduler.running:
            scheduler.shutdown()
