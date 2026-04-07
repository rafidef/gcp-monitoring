from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import datetime

db = SQLAlchemy()

class AdminUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class GCPAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    project_id = db.Column(db.String(100), nullable=False)
    # Store path to the local JSON file
    key_file_path = db.Column(db.String(255), nullable=False)

    tpus = db.relationship('ManagedTPU', backref='gcp_account', lazy=True, cascade='all, delete-orphan')

class ManagedTPU(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gcp_account_id = db.Column(db.Integer, db.ForeignKey('gcp_account.id'), nullable=False)

    # User provided settings
    base_name = db.Column(db.String(100), nullable=False) # e.g. "my-tpu"
    current_name = db.Column(db.String(150), nullable=False) # e.g. "my-tpu-1"
    zone = db.Column(db.String(50), nullable=False)
    tpu_type = db.Column(db.String(50), nullable=False)
    software_version = db.Column(db.String(50), nullable=False)

    # Advanced settings
    use_public_ip = db.Column(db.Boolean, default=False)
    network = db.Column(db.String(100), default='default')
    subnetwork = db.Column(db.String(100), nullable=True) # e.g. "default" or "usc1"
    is_spot = db.Column(db.Boolean, default=True)
    enable_queue = db.Column(db.Boolean, default=True)
    metadata_json = db.Column(db.Text, nullable=True) # Stored as JSON string
    labels_json = db.Column(db.Text, nullable=True) # Stored as JSON string

    # State tracking
    last_known_state = db.Column(db.String(50), default='UNKNOWN')
    recreation_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_checked_at = db.Column(db.DateTime, nullable=True)

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discord_webhook_url = db.Column(db.String(500), nullable=True)
    telegram_bot_token = db.Column(db.String(200), nullable=True)
    telegram_chat_id = db.Column(db.String(100), nullable=True)
