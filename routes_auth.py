from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db
from models import AdminUser, Settings

# Initialize database and default admin if no users exist
with app.app_context():
    db.create_all()
    if AdminUser.query.count() == 0:
        default_admin = AdminUser(
            username='admin',
            password_hash=generate_password_hash('admin') # Default password
        )
        db.session.add(default_admin)
        db.session.commit()
        print("Created default admin user (admin/admin). Please change this immediately upon login.")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = AdminUser.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    settings_obj = Settings.query.first()
    if not settings_obj:
        settings_obj = Settings()
        db.session.add(settings_obj)
        db.session.commit()

    if request.method == 'POST':
        # Update settings
        settings_obj.discord_webhook_url = request.form.get('discord_webhook_url', '').strip()
        settings_obj.telegram_bot_token = request.form.get('telegram_bot_token', '').strip()
        settings_obj.telegram_chat_id = request.form.get('telegram_chat_id', '').strip()

        # Change password if provided
        new_password = request.form.get('new_password')
        if new_password:
            current_user.password_hash = generate_password_hash(new_password)

        db.session.commit()
        flash('Settings updated successfully', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', settings=settings_obj)

@app.route('/')
@login_required
def index():
    return redirect(url_for('list_tpus_view'))
