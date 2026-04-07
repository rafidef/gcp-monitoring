# Obtaining a Google Cloud Service Account JSON Key

To allow the TPU Manager application to create, monitor, and delete TPUs on your behalf, you need to provide it with a Service Account JSON Key. This key acts as the application's secure login to your Google Cloud Project.

Follow these steps to create a Service Account with the necessary permissions and generate the key file.

---

### Step 1: Navigate to the Google Cloud Console
1. Open your web browser and go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Ensure you have selected the correct Project from the top dropdown menu where you want your TPUs to be managed.

### Step 2: Open the Service Accounts Page
1. Use the main navigation menu (hamburger icon in the top left).
2. Go to **IAM & Admin** > **Service Accounts**.

### Step 3: Create a New Service Account
1. Click the **+ CREATE SERVICE ACCOUNT** button at the top of the page.
2. **Service account details:**
   - **Service account name:** Enter a descriptive name (e.g., `tpu-manager-app`).
   - **Service account ID:** This will auto-populate based on the name.
   - **Service account description:** (Optional) "Service account used by the TPU Manager web app."
3. Click **CREATE AND CONTINUE**.

### Step 4: Grant Permissions (Crucial Step)
The application needs specific permissions to manage Compute Engine networks and TPU nodes.

1. In the **Select a role** dropdown, add the following roles:
   - **TPU Admin** (`roles/tpu.admin`): Required to create, list, delete, and get the status of TPU nodes and Queued Resources.
   - **Compute Network Viewer** (`roles/compute.networkViewer`): Required to list available subnetworks for the creation form dropdown.
2. Click **CONTINUE**.

### Step 5: Generate the JSON Key
1. The third step (Grant users access) is optional. Click **DONE** to finish creating the account.
2. You will be returned to the list of Service Accounts. Find the account you just created and click on its email address.
3. Go to the **KEYS** tab at the top.
4. Click **ADD KEY** > **Create new key**.
5. Select **JSON** as the Key type.
6. Click **CREATE**.

The JSON file will automatically download to your computer. **Keep this file secure!** It provides programmatic access to your Google Cloud project.

---

### Step 6: Upload to the TPU Manager App
Once your TPU Manager application is running and you have logged in:
1. Navigate to the **GCP Accounts** page in the application.
2. Provide a friendly name for this account.
3. Upload the `.json` file you just downloaded.
4. Click **Add Account**.

You are now ready to start creating and managing TPUs!
