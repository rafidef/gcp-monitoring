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
    combined_tpus = []

    if account_id:
        selected_account = GCPAccount.query.get(account_id)
        if selected_account:
            db_managed_tpus = ManagedTPU.query.filter_by(gcp_account_id=selected_account.id).all()
            remote_tpus = gcp_utils.list_all_tpus(selected_account)

            db_tpus_by_name = {f"{tpu.zone}/{tpu.current_name}": tpu for tpu in db_managed_tpus}

            remote_tpus_by_name = {f"{r_tpu['zone']}/{r_tpu['short_name']}": r_tpu for r_tpu in remote_tpus}
            processed_remote_names = set()

            # First iterate DB managed TPUs (ensuring offline/queued ones still show up)
            for db_tpu in db_managed_tpus:
                key = f"{db_tpu.zone}/{db_tpu.current_name}"
                r_tpu = remote_tpus_by_name.get(key)

                if r_tpu:
                    processed_remote_names.add(key)

                    is_spot = False
                    if 'schedulingConfig' in r_tpu and r_tpu['schedulingConfig'].get('spot'):
                        is_spot = True
                    elif r_tpu.get('labels', {}).get('spot') == 'true':
                        is_spot = True

                    combined_tpu = {
                        'id': db_tpu.id,
                        'current_name': db_tpu.current_name,
                        'base_name': db_tpu.base_name,
                        'zone': db_tpu.zone,
                        'tpu_type': r_tpu.get('acceleratorType', db_tpu.tpu_type),
                        'software_version': r_tpu.get('runtimeVersion', db_tpu.software_version),
                        'is_spot': is_spot,
                        'last_known_state': r_tpu.get('state', db_tpu.last_known_state),
                        'recreation_count': db_tpu.recreation_count,
                        'is_managed': True, # Overrides GCP label if it exists in DB
                        'last_checked_at': db_tpu.last_checked_at
                    }
                else:
                    # Offline/Missing from GCP but in DB
                    combined_tpu = {
                        'id': db_tpu.id,
                        'current_name': db_tpu.current_name,
                        'base_name': db_tpu.base_name,
                        'zone': db_tpu.zone,
                        'tpu_type': db_tpu.tpu_type,
                        'software_version': db_tpu.software_version,
                        'is_spot': db_tpu.is_spot,
                        'last_known_state': db_tpu.last_known_state,
                        'recreation_count': db_tpu.recreation_count,
                        'is_managed': True,
                        'last_checked_at': db_tpu.last_checked_at
                    }

                combined_tpus.append(combined_tpu)

            # Then append purely unmanaged/remote-only TPUs
            for r_tpu in remote_tpus:
                key = f"{r_tpu['zone']}/{r_tpu['short_name']}"
                if key not in processed_remote_names:
                    # Even if it's missing from DB, could it be an orphaned managed TPU?
                    # Yes, we look at the label. But since it's not in DB, we can't fully manage it (no DB ID).
                    # It will still show as unmanaged (or managed without an ID)

                    is_spot = False
                    if 'schedulingConfig' in r_tpu and r_tpu['schedulingConfig'].get('spot'):
                        is_spot = True
                    elif r_tpu.get('labels', {}).get('spot') == 'true':
                        is_spot = True

                    combined_tpu = {
                        'id': None,
                        'current_name': r_tpu['short_name'],
                        'base_name': r_tpu['short_name'],
                        'zone': r_tpu['zone'],
                        'tpu_type': r_tpu.get('acceleratorType', 'UNKNOWN'),
                        'software_version': r_tpu.get('runtimeVersion', 'UNKNOWN'),
                        'is_spot': is_spot,
                        'last_known_state': r_tpu.get('state', 'UNKNOWN'),
                        'recreation_count': 0,
                        'is_managed': r_tpu['is_managed'],
                        'last_checked_at': None
                    }
                    combined_tpus.append(combined_tpu)

    return render_template('tpus.html',
                           accounts=accounts,
                           selected_account=selected_account,
                           managed_tpus=combined_tpus)

@app.route('/tpus/<int:account_id>/<zone>/<tpu_name>/monitoring', methods=['GET'])
@login_required
def tpu_monitoring(account_id, zone, tpu_name):
    account = GCPAccount.query.get_or_404(account_id)
    return render_template('tpu_monitoring.html', account=account, zone=zone, tpu_name=tpu_name)

@app.route('/api/tpu/<int:account_id>/<zone>/<tpu_name>/metrics', methods=['GET'])
@login_required
def api_tpu_metrics(account_id, zone, tpu_name):
    account = GCPAccount.query.get_or_404(account_id)
    time_range_hours = int(request.args.get('hours', 1))

    cpu_data = gcp_utils.get_tpu_metrics(
        account=account,
        zone=zone,
        tpu_name=tpu_name,
        metric_type="tpu.googleapis.com/cpu/utilization",
        time_range_hours=time_range_hours
    )

    memory_data = gcp_utils.get_tpu_metrics(
        account=account,
        zone=zone,
        tpu_name=tpu_name,
        metric_type="tpu.googleapis.com/memory/usage",
        time_range_hours=time_range_hours
    )

    return jsonify({
        'cpu': cpu_data,
        'memory': memory_data
    })

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

        # Trigger creation via GCP API FIRST
        if enable_queue:
            success, response = gcp_utils.create_queued_tpu(account, new_tpu)
        else:
            success, response = gcp_utils.create_standard_tpu(account, new_tpu)

        if success:
            # ONLY save to database if GCP API creation was successful
            db.session.add(new_tpu)
            db.session.commit()
            flash(f"Successfully requested creation of TPU {base_name}", "success")
        else:
            flash(f"Error requesting TPU creation: {response}", "error")
            # Do NOT save to db if initial creation fails, preventing infinite loop

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
