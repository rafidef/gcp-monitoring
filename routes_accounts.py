import os
import json
from werkzeug.utils import secure_filename
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import app, db
from models import GCPAccount

UPLOAD_FOLDER = os.path.join(app.root_path, 'service_accounts')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/accounts', methods=['GET', 'POST'])
@login_required
def accounts():
    if request.method == 'POST':
        name = request.form.get('name')
        file = request.files.get('key_file')

        if not name or not file:
            flash('Name and Key File are required', 'error')
            return redirect(url_for('accounts'))

        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(url_for('accounts'))

        if file and file.filename.endswith('.json'):
            filename = secure_filename(file.filename)
            # Ensure unique filename
            base_name, ext = os.path.splitext(filename)
            counter = 1
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            while os.path.exists(file_path):
                filename = f"{base_name}_{counter}{ext}"
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                counter += 1

            file.save(file_path)

            try:
                with open(file_path, 'r') as f:
                    key_data = json.load(f)
                    project_id = key_data.get('project_id')

                if not project_id:
                    os.remove(file_path)
                    flash('Invalid JSON: missing project_id', 'error')
                    return redirect(url_for('accounts'))

                new_account = GCPAccount(
                    name=name,
                    project_id=project_id,
                    key_file_path=file_path
                )
                db.session.add(new_account)
                db.session.commit()
                flash('GCP Account added successfully', 'success')

            except json.JSONDecodeError:
                os.remove(file_path)
                flash('Invalid JSON format', 'error')
            except Exception as e:
                os.remove(file_path)
                flash(f'Error processing file: {str(e)}', 'error')

        else:
            flash('Please upload a .json file', 'error')

        return redirect(url_for('accounts'))

    accounts = GCPAccount.query.all()
    return render_template('accounts.html', accounts=accounts)

@app.route('/accounts/<int:account_id>/delete', methods=['POST'])
@login_required
def delete_account(account_id):
    account = GCPAccount.query.get_or_404(account_id)

    # Try to remove the file
    try:
        if os.path.exists(account.key_file_path):
            os.remove(account.key_file_path)
    except Exception as e:
        print(f"Error removing file {account.key_file_path}: {e}")

    db.session.delete(account)
    db.session.commit()
    flash('Account deleted successfully', 'success')
    return redirect(url_for('accounts'))
