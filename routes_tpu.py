from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app import app, db
from models import GCPAccount, ManagedTPU
import gcp_utils
import json
import datetime

@app.route('/tpus', methods=['GET'])
@login_required
def list_tpus_view():
    account_id = request.args.get('account_id')
    accounts = GCPAccount.query.all()

    selected_account = None
    managed_tpus = []

    if account_id:
        selected_account = GCPAccount.query.get(account_id)
        if selected_account:
            managed_tpus = ManagedTPU.query.filter_by(gcp_account_id=selected_account.id).all()

    return render_template('tpus.html',
                           accounts=accounts,
                           selected_account=selected_account,
                           managed_tpus=managed_tpus)

@app.route('/api/subnetworks', methods=['GET'])
@login_required
def api_subnetworks():
    account_id = request.args.get('account_id')
    zone = request.args.get('zone')

    if not account_id or not zone:
        return jsonify([])

    account = GCPAccount.query.get(account_id)
    if not account:
        return jsonify([])

    region = gcp_utils.extract_region_from_zone(zone)
    subnets = gcp_utils.list_subnetworks(account, region)
    return jsonify(subnets)

@app.route('/tpus/create', methods=['GET', 'POST'])
@login_required
def create_tpu():
    account_id = request.args.get('account_id')
    account = GCPAccount.query.get_or_404(account_id)

    if request.method == 'POST':
        base_name = request.form.get('name')
        zone = request.form.get('zone')
        tpu_type = request.form.get('tpu_type')
        software_version = request.form.get('software_version')
        network = request.form.get('network', 'default')
        subnetwork = request.form.get('subnetwork')
        use_public_ip = request.form.get('use_public_ip') == 'on'
        is_spot = request.form.get('is_spot') == 'on'
        enable_queue = request.form.get('enable_queue') == 'on'

        # Parse metadata
        metadata = {}
        metadata_keys = request.form.getlist('metadata_key[]')
        metadata_values = request.form.getlist('metadata_value[]')
        for k, v in zip(metadata_keys, metadata_values):
            if k and k.strip():
                metadata[k.strip()] = v.strip()

        # Parse labels
        labels = {}
        label_keys = request.form.getlist('label_key[]')
        label_values = request.form.getlist('label_value[]')
        for k, v in zip(label_keys, label_values):
            if k and k.strip():
                labels[k.strip()] = v.strip()

        new_tpu = ManagedTPU(
            gcp_account_id=account.id,
            base_name=base_name,
            current_name=base_name, # Initially same as base name
            zone=zone,
            tpu_type=tpu_type,
            software_version=software_version,
            use_public_ip=use_public_ip,
            network=network,
            subnetwork=subnetwork,
            is_spot=is_spot,
            enable_queue=enable_queue,
            metadata_json=json.dumps(metadata) if metadata else None,
            labels_json=json.dumps(labels) if labels else None,
            last_known_state='CREATING'
        )

        db.session.add(new_tpu)
        db.session.commit()

        # Trigger creation via GCP API
        if enable_queue:
            success, response = gcp_utils.create_queued_tpu(account, new_tpu)
        else:
            success, response = gcp_utils.create_standard_tpu(account, new_tpu)

        if success:
            flash(f"Successfully requested creation of TPU {base_name}", "success")
        else:
            flash(f"Error requesting TPU creation: {response}", "error")
            new_tpu.last_known_state = 'ERROR'
            db.session.commit()

        return redirect(url_for('list_tpus_view', account_id=account.id))

    return render_template('create_tpu.html', account=account)

@app.route('/tpus/<int:tpu_id>/delete', methods=['POST'])
@login_required
def delete_managed_tpu(tpu_id):
    tpu = ManagedTPU.query.get_or_404(tpu_id)
    account = GCPAccount.query.get(tpu.gcp_account_id)

    # Attempt to delete from GCP
    if tpu.enable_queue:
        gcp_utils.delete_queued_resource(account, tpu.zone, tpu.current_name)
    else:
        gcp_utils.delete_tpu(account, tpu.zone, tpu.current_name)

    db.session.delete(tpu)
    db.session.commit()
    flash('TPU tracking removed and deletion requested on GCP.', 'success')

    return redirect(url_for('list_tpus_view', account_id=account.id))
