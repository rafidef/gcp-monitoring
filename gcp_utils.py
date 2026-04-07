import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from models import GCPAccount
import requests

def get_credentials(account: GCPAccount):
    """Load credentials from the stored JSON file."""
    try:
        return service_account.Credentials.from_service_account_file(account.key_file_path)
    except Exception as e:
        print(f"Error loading credentials for account {account.name}: {e}")
        return None

def list_subnetworks(account: GCPAccount, region: str):
    """Lists subnetworks in a specific region."""
    credentials = get_credentials(account)
    if not credentials:
        return []

    try:
        compute = build('compute', 'v1', credentials=credentials)
        request = compute.subnetworks().list(project=account.project_id, region=region)
        response = request.execute()

        subnets = []
        if 'items' in response:
            for item in response['items']:
                subnets.append({
                    'name': item['name'],
                    'network': item['network'].split('/')[-1]
                })
        return subnets
    except Exception as e:
        print(f"Error listing subnetworks: {e}")
        return []

def extract_region_from_zone(zone: str):
    # Example zone: us-central1-a -> region: us-central1
    parts = zone.split('-')
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return zone

def list_tpus(account: GCPAccount, zone: str):
    """Lists TPUs in a specific zone using the newer tpu v2/v2alpha1 API."""
    credentials = get_credentials(account)
    if not credentials:
        return []

    try:
        tpu = build('tpu', 'v2', credentials=credentials)
        parent = f"projects/{account.project_id}/locations/{zone}"

        request = tpu.projects().locations().nodes().list(parent=parent)
        response = request.execute()

        nodes = []
        if 'nodes' in response:
            nodes = response['nodes']

        return nodes
    except Exception as e:
        print(f"Error listing TPUs: {e}")
        return []

def get_tpu_state(account: GCPAccount, zone: str, name: str):
    """Gets the current state of a specific TPU."""
    credentials = get_credentials(account)
    if not credentials:
        return "ERROR"

    try:
        tpu = build('tpu', 'v2', credentials=credentials)
        name_path = f"projects/{account.project_id}/locations/{zone}/nodes/{name}"

        request = tpu.projects().locations().nodes().get(name=name_path)
        response = request.execute()

        return response.get('state', 'UNKNOWN')
    except Exception as e:
        if "HttpError 404" in str(e):
            return "DELETED"
        print(f"Error getting TPU state: {e}")
        return "ERROR"

def delete_tpu(account: GCPAccount, zone: str, name: str):
    """Deletes a TPU."""
    credentials = get_credentials(account)
    if not credentials:
        return False

    try:
        tpu = build('tpu', 'v2', credentials=credentials)
        name_path = f"projects/{account.project_id}/locations/{zone}/nodes/{name}"

        request = tpu.projects().locations().nodes().delete(name=name_path)
        request.execute()
        return True
    except Exception as e:
        print(f"Error deleting TPU: {e}")
        return False

def create_standard_tpu(account: GCPAccount, managed_tpu):
    """Creates a standard TPU Node directly."""
    credentials = get_credentials(account)
    if not credentials:
        return False, "Failed to load credentials"

    try:
        tpu = build('tpu', 'v2', credentials=credentials)
        parent = f"projects/{account.project_id}/locations/{managed_tpu.zone}"

        # Prepare network config
        network_config = {
            'enableExternalIps': managed_tpu.use_public_ip,
            'network': f"projects/{account.project_id}/global/networks/{managed_tpu.network}",
        }

        if managed_tpu.subnetwork:
            region = extract_region_from_zone(managed_tpu.zone)
            network_config['subnetwork'] = f"projects/{account.project_id}/regions/{region}/subnetworks/{managed_tpu.subnetwork}"

        # Prepare metadata and labels
        metadata = {}
        if managed_tpu.metadata_json:
            try:
                metadata = json.loads(managed_tpu.metadata_json)
            except:
                pass

        labels = {}
        if managed_tpu.labels_json:
            try:
                labels = json.loads(managed_tpu.labels_json)
            except:
                pass

        labels['managed-by'] = 'tpu-manager'

        node_spec = {
            'acceleratorType': managed_tpu.tpu_type,
            'runtimeVersion': managed_tpu.software_version,
            'networkConfig': network_config,
            'metadata': metadata,
            'labels': labels,
        }

        if managed_tpu.is_spot:
             if 'schedulingConfig' not in node_spec:
                 node_spec['schedulingConfig'] = {}
             node_spec['schedulingConfig']['spot'] = True

        request = tpu.projects().locations().nodes().create(
            parent=parent,
            nodeId=managed_tpu.current_name,
            body=node_spec
        )

        response = request.execute()
        return True, response
    except Exception as e:
        print(f"Error creating standard TPU: {e}")
        return False, str(e)


def create_queued_tpu(account: GCPAccount, managed_tpu):
    """Creates a Queued Resource TPU."""
    credentials = get_credentials(account)
    if not credentials:
        return False, "Failed to load credentials"

    try:
        # We need the v2alpha1 API for full Queued Resource support including Spot VMs
        tpu = build('tpu', 'v2alpha1', credentials=credentials)
        parent = f"projects/{account.project_id}/locations/{managed_tpu.zone}"

        # Prepare network config
        network_config = {
            'enableExternalIps': managed_tpu.use_public_ip,
            'network': f"projects/{account.project_id}/global/networks/{managed_tpu.network}",
        }

        if managed_tpu.subnetwork:
            region = extract_region_from_zone(managed_tpu.zone)
            network_config['subnetwork'] = f"projects/{account.project_id}/regions/{region}/subnetworks/{managed_tpu.subnetwork}"

        # Prepare metadata and labels
        metadata = {}
        if managed_tpu.metadata_json:
            try:
                metadata = json.loads(managed_tpu.metadata_json)
            except:
                pass

        labels = {}
        if managed_tpu.labels_json:
            try:
                labels = json.loads(managed_tpu.labels_json)
            except:
                pass

        # Add our management label
        labels['managed-by'] = 'tpu-manager'

        # Build node spec
        node_spec = {
            'parent': parent,
            'node': {
                'acceleratorType': managed_tpu.tpu_type,
                'runtimeVersion': managed_tpu.software_version,
                'networkConfig': network_config,
                'metadata': metadata,
                'labels': labels,
            }
        }

        if managed_tpu.is_spot:
            # For Spot VMs, data path is currently defined via schedulingConfig in node
            # But in v2alpha1 QueuedResource, we might need spot inside the node spec or in the queue spec.
            pass # Standard TPUs via queue might implicitly handle spot differently, but lets add scheduling config

        queued_resource_id = managed_tpu.current_name

        body = {
            'tpu': {
                'nodeSpec': [node_spec]
            }
        }

        # Spot/Preemptible logic in Queued Resources is handled by setting the root "spot" object
        if managed_tpu.is_spot:
             body['spot'] = {}

        # Ensure start immediately and no cancel logic
        # For queued resources, queueingPolicy can be provided if needed.
        # By default start request is immediate.

        request = tpu.projects().locations().queuedResources().create(
            parent=parent,
            queuedResourceId=queued_resource_id,
            body=body
        )

        response = request.execute()
        return True, response
    except Exception as e:
        print(f"Error creating Queued TPU: {e}")
        return False, str(e)

def delete_queued_resource(account: GCPAccount, zone: str, name: str):
    """Deletes a Queued Resource (which cascades to deleting the underlying TPU)."""
    credentials = get_credentials(account)
    if not credentials:
        return False

    try:
        tpu = build('tpu', 'v2alpha1', credentials=credentials)
        name_path = f"projects/{account.project_id}/locations/{zone}/queuedResources/{name}"

        request = tpu.projects().locations().queuedResources().delete(name=name_path, force=True)
        request.execute()
        return True
    except Exception as e:
        if "HttpError 404" in str(e):
             return True # Already deleted
        print(f"Error deleting Queued Resource: {e}")
        return False

def get_queued_resource_state(account: GCPAccount, zone: str, name: str):
    """Gets state of queued resource to determine if node is preempted."""
    credentials = get_credentials(account)
    if not credentials:
        return "ERROR"

    try:
        tpu = build('tpu', 'v2alpha1', credentials=credentials)
        name_path = f"projects/{account.project_id}/locations/{zone}/queuedResources/{name}"

        request = tpu.projects().locations().queuedResources().get(name=name_path)
        response = request.execute()

        return response.get('state', {}).get('state', 'UNKNOWN')
    except Exception as e:
         if "HttpError 404" in str(e):
             return "DELETED"
         print(f"Error getting Queued Resource state: {e}")
         return "ERROR"
