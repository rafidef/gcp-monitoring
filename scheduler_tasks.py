import datetime
from app import app, db
from models import ManagedTPU, GCPAccount
import gcp_utils
import notifications

def generate_next_name(base_name: str, current_name: str) -> str:
    """
    If current_name is base_name, returns base_name-1.
    If current_name is base_name-1, returns base_name.
    """
    if current_name == base_name:
        return f"{base_name}-1"
    else:
        return base_name

def recreate_tpu(tpu: ManagedTPU, account: GCPAccount):
    print(f"Recreating TPU {tpu.current_name} (base: {tpu.base_name})")

    # 1. Ensure the old one is deleted from GCP
    if tpu.enable_queue:
        gcp_utils.delete_queued_resource(account, tpu.zone, tpu.current_name)
    else:
        gcp_utils.delete_tpu(account, tpu.zone, tpu.current_name)

    # 2. Update name for new creation attempt
    new_name = generate_next_name(tpu.base_name, tpu.current_name)
    tpu.current_name = new_name
    tpu.recreation_count += 1
    tpu.last_known_state = 'RECREATING'
    db.session.commit()

    # 3. Create
    if tpu.enable_queue:
        success, response = gcp_utils.create_queued_tpu(account, tpu)
    else:
        success, response = gcp_utils.create_standard_tpu(account, tpu)

    if success:
        msg = f"Successfully requested recreation. New name: {new_name}"
        print(msg)
        notifications.notify_all("TPU Recreating", f"TPU `{tpu.base_name}` is being recreated as `{new_name}`.", 3066993) # Green
    else:
        msg = f"Failed to recreate: {response}"
        print(msg)
        tpu.last_known_state = 'ERROR'
        db.session.commit()
        notifications.notify_all("TPU Recreation Failed", f"Failed to recreate TPU `{tpu.base_name}`.\nError: {response}", 15158332) # Red

def check_tpu_status():
    with app.app_context():
        tpus = ManagedTPU.query.all()
        for tpu in tpus:
            account = GCPAccount.query.get(tpu.gcp_account_id)
            if not account:
                continue

            old_state = tpu.last_known_state

            if tpu.enable_queue:
                current_state = gcp_utils.get_queued_resource_state(account, tpu.zone, tpu.current_name)
            else:
                current_state = gcp_utils.get_tpu_state(account, tpu.zone, tpu.current_name)

            tpu.last_known_state = current_state
            tpu.last_checked_at = datetime.datetime.utcnow()
            db.session.commit()

            # State transitions & notifications
            if old_state != current_state:
                print(f"TPU {tpu.current_name} changed state from {old_state} to {current_state}")

                # Colors: Info=3447003, Success=3066993, Warning=16776960, Danger=15158332
                color = 3447003
                if current_state == 'ACTIVE':
                    color = 3066993
                elif current_state in ['PREEMPTED', 'STOPPED', 'SUSPENDED', 'DELETED']:
                    color = 16776960

                msg = f"TPU `{tpu.current_name}` (Base: `{tpu.base_name}`) is now **{current_state}**."
                notifications.notify_all("TPU State Changed", msg, color)

                # Check if we need to recreate
                # For queued resources, 'FAILED' might happen if preempted and not queued, or 'SUSPENDED'
                # For standard spot TPUs, 'PREEMPTED', 'STOPPED', 'TERMINATED'
                if current_state in ['PREEMPTED', 'STOPPED', 'SUSPENDED', 'DELETED', 'FAILED']:
                    print(f"Triggering recreation for {tpu.current_name} due to state {current_state}")
                    recreate_tpu(tpu, account)
