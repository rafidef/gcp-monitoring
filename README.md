<div align="center">
  <h1>☁️ GCP TPU Manager</h1>
  <p>A secure, automated web dashboard for managing Google Cloud Spot TPUs across multiple accounts.</p>
</div>

---

## 📖 Overview

Google Cloud Spot TPUs are highly cost-effective but suffer from frequent preemptions, requiring tedious manual intervention to recreate them via the GCP Console.

**TPU Manager** is a self-hosted Python (Flask) web application designed to run on a lightweight VPS. It acts as an automated management layer over your Google Cloud accounts, allowing you to configure TPUs exactly as you would in the GCP Console, while automatically handling active background monitoring, Discord/Telegram notifications, and instantaneous auto-recreation when a preemption occurs.

---

## ✨ Features

- **🌐 Complete Dashboard UI:** Mirrors the GCP Cloud Console creation form, supporting dynamic subnetwork fetching, metadata keys, Spot toggles, and Queued Resources.
- **🔄 Auto-Recreation Engine:** Monitors your TPUs every 5 minutes. If a Spot TPU is preempted, it bypasses GCP's strict deletion-wait-times by smartly toggling the resource name (e.g., `tpu-a` -> `tpu-a-1`) and automatically requesting a replacement with the exact same configuration.
- **🔑 Multi-Account Support:** Upload and manage multiple Google Cloud Projects using isolated Service Account JSON keys.
- **🔔 Real-time Notifications:** Get alerts sent directly to a Discord Webhook or a Telegram Bot whenever a TPU changes state (e.g., ACTIVE, PREEMPTED, CREATING).
- **🛡️ Built for Security:** Features secure password-hashed admin authentication, strictly scoped file handling, CSRF token validation on all forms, and automated cryptographic session key generation.

---

## 🚀 Getting Started

### Prerequisites
- A Linux environment (VPS, Raspberry Pi, or local WSL). A lightweight 2-core / 2GB RAM VPS is perfectly sufficient.
- Python 3.8+ installed.
- A Google Cloud Account.

### 1. Installation

Clone the repository and install the required dependencies:

```bash
git clone https://github.com/your-username/tpu-manager.git
cd tpu-manager
pip install -r requirements.txt
```

### 2. Execution (Development / Local Testing)

To test the application locally, you can run the Flask server directly.

```bash
python app.py
```
*Note: The app will run on `http://0.0.0.0:5000`.*

---

## 🔒 Running Safely in Production

Because this application manages expensive cloud resources, it **must** be deployed securely if exposed to the internet.

**Do not use the built-in Flask development server (`python app.py`) for production exposure.**

### Deploying with Gunicorn

We highly recommend using a production WSGI server like `gunicorn`.

1. Install Gunicorn:
```bash
pip install gunicorn
```

2. Run the application in the background:
```bash
# Runs gunicorn on port 5000 with 2 worker threads in the background
# The --daemon flag runs the process silently in the background.
# We use log files to capture the output.
gunicorn --workers 2 --bind 0.0.0.0:5000 app:app --daemon --access-logfile access.log --error-logfile error.log
```

You can view the logs at any time using:
```bash
tail -f access.log
tail -f error.log
```

*For a robust setup, consider placing Gunicorn behind a reverse proxy like **Nginx** and securing it with a free SSL certificate from **Let's Encrypt**.*

---

## ⚙️ Initial Configuration

1. **Login:** On your first visit, the app creates a default admin account.
   - Username: `admin`
   - Password: `admin`
   > **⚠️ CRITICAL:** Immediately navigate to the **Settings** page and change your admin password.

2. **Add a GCP Account:** To manage TPUs, you need to provide the application with a Google Cloud Service Account JSON Key.
   - 📚 Please follow the [Service Account Setup Guide](SERVICE_ACCOUNT_GUIDE.md) for step-by-step instructions on generating this file with the correct permissions.
   - Upload the generated `.json` file in the **GCP Accounts** tab.

3. **Notifications (Optional):** In the **Settings** tab, configure your Discord Webhook URL or Telegram Bot Token/Chat ID to receive active status alerts.

---

## 🛠️ Architecture

- **Backend:** Flask, Flask-SQLAlchemy (SQLite), Flask-Login, Flask-WTF.
- **Background Tasks:** APScheduler (BackgroundScheduler).
- **GCP Integration:** `google-cloud-tpu`, `google-cloud-compute`, `google-api-python-client`.
- **Frontend:** Bootstrap 5, Jinja2 templating.
