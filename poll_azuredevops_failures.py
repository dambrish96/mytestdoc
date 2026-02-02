
import os
import requests
import base64
import time
import json
from datetime import datetime, timezone


# Configuration

ORG = "welldynerx"
PROJECT = None
PAT = os.getenv("ADO_PAT")  
FLASK_ITSM_URL = "http://127.0.0.1:5000/create-ticket"

POLL_INTERVAL_MIN = 5
CHECKPOINT_FILE = "ado_checkpoint.json"
BASE_URL = f"https://dev.azure.com/{ORG}"


# Authenticationn

def build_auth_headers():
    # Azure DevOps Basic Auth requires base64(":PAT")
    auth_string = f":{PAT}".encode("ascii")
    auth_header = base64.b64encode(auth_string).decode("ascii")
    return {
        "Authorization": f"Basic {auth_header}",
        "Accept": "application/json",
        "User-Agent": "ado-failure-poller/1.0"
    }

SESSION = requests.Session()
SESSION.headers.update(build_auth_headers())

#Checkpoint
def load_checkpoint():
    if not os.path.exists(CHECKPOINT_FILE):
        # default to checking last 24h
        return {"last_check": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()}
    with open(CHECKPOINT_FILE, "r") as f:
        return json.load(f)

def save_checkpoint(data):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f)

#Get Project Details 
def get_projects():
    if PROJECT:
        return [{"name": PROJECT}]
    url = f"{BASE_URL}/_apis/projects?api-version=7.1"
    resp = SESSION.get(url)
    resp.raise_for_status()
    return resp.json()["value"]

#fetch Build Run
def get_failed_runs(project, since_iso):
    """Fetch failed build runs from Azure DevOps (classic build pipelines)."""
    url = f"{BASE_URL}/{project}/_apis/build/builds?api-version=7.1"
    params = {
        "resultFilter": "failed",
        "statusFilter": "completed",
        "queryOrder": "finishTimeDescending",
        "$top": 100
    }

    print(f"🔍 Querying ADO Build API for project: {project}")
    resp = SESSION.get(url, params=params)

    # Helpful diagnostics if the server returns HTML instead of JSON
    ct = resp.headers.get("Content-Type", "")
    if "html" in ct.lower():
        print("❌ Received HTML (likely sign-in). Check PAT scopes/validity.")
        print(resp.text[:500])

    resp.raise_for_status()
    data = resp.json()

    # Compare datetimes robustly
    try:
        since_dt = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    except Exception:
        since_dt = datetime.utcnow().replace(tzinfo=timezone.utc)

    failed = []
    for run in data.get("value", []):
        ft = run.get("finishTime")
        if not ft:
            continue
        try:
            ft_dt = datetime.fromisoformat(ft.replace("Z", "+00:00"))
        except Exception:
            continue
        if ft_dt > since_dt:
            failed.append(run)

    print(f"📌 Found {len(failed)} newly failed runs")
    return failed

#fetch logs
def get_build_logs(project_name, build_id):
    """Fetch and join logs for a failed build (classic)."""
    list_url = f"{BASE_URL}/{project_name}/_apis/build/builds/{build_id}/logs?api-version=7.1"
    r = SESSION.get(list_url)
    r.raise_for_status()
    logs = r.json().get("value", [])

    combined = []
    for log in logs:
        log_id = log.get("id")
        if log_id is None:
            continue
        # Grab raw lines for each log
        log_url = f"{BASE_URL}/{project_name}/_apis/build/builds/{build_id}/logs/{log_id}?api-version=7.1"
        lr = SESSION.get(log_url, headers={"Accept": "text/plain"})
        if lr.ok and lr.headers.get("Content-Type", "").startswith("text/plain"):
            combined.append(lr.text)
        else:
            # Fallback: include metadata URL if raw text isn't available
            combined.append(f"[log {log_id}] {log.get('url')}")

    return ("\n\n--- LOG FILE ---\n".join(combined))[:15000]  # practical cap

#send to ITSM
def send_ticket(project, pipeline, log_text, severity="High"):
    payload = {
        "project": project,
        "pipeline": pipeline,
        "log": log_text,
        "severity": severity,
    }
    resp = requests.post(FLASK_ITSM_URL, json=payload, timeout=30)
    print(f"[ITSM] Sent ticket → {resp.status_code}")
    print(resp.text[:300])

#main funcction
def main():
    print("🚀 Starting Azure DevOps Failure Poller")
    checkpoint = load_checkpoint()
    last_check = checkpoint["last_check"]

    while True:
        print("\n⏳ Checking for failures since", last_check)
        now_iso = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

        for project in get_projects():
            name = project["name"]
            print(f"🔍 Project: {name}")

            failed_runs = get_failed_runs(name, last_check)
            print(f"  → Found {len(failed_runs)} failed runs")

            for run in failed_runs:
                build_id = run["id"]
                # Build result 
                pipeline_name = (run.get("definition") or {}).get("name", "Unknown Build")
                print(f"    ❌ Failed Build: {pipeline_name} (ID={build_id})")

                try:
                    logs = get_build_logs(name, build_id)
                except Exception as e:
                    logs = f"Failed to download logs: {e}"

                send_ticket(name, pipeline_name, logs)

        # update checkpoint
        last_check = now_iso
        save_checkpoint({"last_check": now_iso})

        print(f"⏲ Sleeping {POLL_INTERVAL_MIN} minutes...\n")
        time.sleep(POLL_INTERVAL_MIN * 60)


if __name__ == "__main__":
    main()

