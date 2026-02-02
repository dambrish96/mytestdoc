from flask import Flask, request, jsonify, render_template_string, send_from_directory
import os
import json
import uuid
from datetime import datetime
import openai
from dotenv import load_dotenv
import threading

load_dotenv()

OPENAI_API_KEY = os.getenv('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')
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

DB_FILE = "tickets.json"
if not os.path.exists(DB_FILE):
    with open(DB_FILE, 'w') as f:
        json.dump([], f)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

#categorize
ERROR_CATEGORIES = {
    "Authentication": ["unauthorized", "access denied", "401", "403", "auth"],
    "Deployment": ["deployment failed", "rollback", "deployment error", "deploy"],
    "Script": ["script error", "exit code", "command not found", "syntax error", "exception"],
    "Configuration": ["missing variable", "invalid config", "configuration error", "config"],
    "Network": ["timeout", "connection refused", "dns", "proxy error", "connection timed out"],
    "Agent": ["agent lost", "agent error", "agent disconnected", "agent"],
}



def load_tickets():
    with open(DB_FILE, 'r') as f:
        return json.load(f)


def save_tickets(tickets):
    with open(DB_FILE, 'w') as f:
        json.dump(tickets, f, indent=2, default=str)


def generate_ticket_id():
    return "TICK-" + str(uuid.uuid4())[:8]


#categorization logic

def fallback_categorize(text):
    text_l = text.lower()
    matched = []
    for cat, keywords in ERROR_CATEGORIES.items():
        if any(k in text_l for k in keywords):
            matched.append(cat)
    return matched if matched else ["Uncategorized"]


def ai_categorize(text):
    """Call OpenAI to classify/categorize the log text. Returns list of categories.
    If OpenAI key is missing or call fails, returns fallback categorization."""
    if not OPENAI_API_KEY:
        return fallback_categorize(text)
    try:
        prompt = (
            "You are a helpful assistant that classifies Azure DevOps pipeline failure logs into one or more categories. "
            "Return a JSON array of categories from the following allowed list: [Authentication, Deployment, Script, Configuration, Network, Agent, Other]. "
            "If none match, return [\"Other\"].\n\nLog:\n" + text[:4000]
        )
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0
        )
        raw = resp.choices[0].message.content.strip()
        # Try to parse JSON-like output
        import re
        import ast
        # Extract first JSON array-like content
        m = re.search(r"\[.*\]", raw, re.S)
        if m:
            arr_text = m.group(0)
            try:
                categories = ast.literal_eval(arr_text)
                return [c for c in categories]
            except Exception:
                pass
        # Fallback: split by commas
        parts = [p.strip() for p in raw.replace('\n', ',').split(',') if p.strip()]
        return parts if parts else fallback_categorize(text)
    except Exception as e:
        print("AI categorization failed:", e)
        return fallback_categorize(text)


# API to create ticket 
@app.route('/create-ticket', methods=['POST'])
def create_ticket():
    """Receives JSON payload with at least: pipeline, project, log (or message). Optional: severity."""
    data = request.get_json() or {}
    # Accept variations
    pipeline = data.get('pipeline') or data.get('buildNumber') or data.get('release') or 'unknown'
    project = data.get('project') or data.get('projectName') or 'unknown'
    log_text = data.get('log') or data.get('message') or data.get('log_text') or ''
    severity = data.get('severity') or 'Medium'

    # Categorize (prefer AI if configured)
    categories = ai_categorize(log_text)

    ticket = {
        'ticket_id': generate_ticket_id(),
        'created_on': datetime.utcnow().isoformat() + 'Z',
        'pipeline': pipeline,
        'project': project,
        'categories': categories,
        'severity': severity,
        'status': 'Open',
        'raw_log_excerpt': log_text[:2000]
    }

    tickets = load_tickets()
    tickets.insert(0, ticket)
    save_tickets(tickets)
    return jsonify({'message': 'Ticket created', 'ticket': ticket}), 201


# === API to list tickets (JSON) ===
@app.route('/api/tickets', methods=['GET'])
def api_tickets():
    tickets = load_tickets()
    return jsonify(tickets)


# Dashboard

DASHBOARD_HTML = '''
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Pipeline Failure Auto-Ticketing - Demo Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  </head>
  <body class="bg-light">
    <nav class="navbar navbar-dark bg-dark mb-3">
      <div class="container-fluid">
        <span class="navbar-brand mb-0 h1">Auto-Ticketing</span>
        <span class="text-white">Local demo</span>
      </div>
    </nav>
    <div class="container">
      <div class="row mb-4">
        <div class="col-md-8">
          <div class="card p-3">
            <h5>Tickets Overview</h5>
            <canvas id="categoryChart" height="120"></canvas>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card p-3">
            <h5>Actions</h5>
            <button class="btn btn-primary mb-2" onclick="refresh()">Refresh</button>
            <button class="btn btn-secondary mb-2" onclick="clearTickets()">Clear Tickets</button>
            <p class="text-muted small">Tip: POST to <code>/create-ticket</code> to create demo tickets.</p>
          </div>
        </div>
      </div>

      <div class="card p-3">
        <h5>Ticket Queue</h5>
        <div id="tickets"></div>
      </div>
    </div>

    <script>
      async function fetchTickets(){
        const r = await fetch('/api/tickets');
        return await r.json();
      }

      function renderTickets(tickets){
        const el = document.getElementById('tickets');
        if(!tickets.length) { el.innerHTML = '<p class="text-muted">No tickets yet</p>'; return }
        el.innerHTML = '';
        tickets.forEach(t=>{
          const card = document.createElement('div');
          card.className = 'card mb-2 p-2';
          card.innerHTML = `<div class="d-flex justify-content-between"><div><strong>${t.ticket_id}</strong> <small class="text-muted">${t.project} / ${t.pipeline}</small></div><div><span class="badge bg-warning text-dark">${t.severity}</span></div></div><div class="mt-2"><strong>Categories:</strong> ${t.categories.join(', ')}</div><div class="mt-2"><pre style="white-space:pre-wrap; max-height:120px; overflow:auto">${t.raw_log_excerpt}</pre></div>`;
          el.appendChild(card);
        })
      }

      var chart=null;
      async function refresh(){
        const tickets = await fetchTickets();
        renderTickets(tickets);
        // build category counts
        const counts = {};
        tickets.forEach(t=>{
          t.categories.forEach(c=>{ counts[c]=(counts[c]||0)+1 });
        });
        const labels = Object.keys(counts);
        const data = labels.map(l=>counts[l]);

        const ctx = document.getElementById('categoryChart');
        if(chart) chart.destroy();
        chart = new Chart(ctx, { type:'bar', data:{ labels:labels, datasets:[{ label:'Tickets', data:data }] }, options:{ responsive:true } });
      }

      async function clearTickets(){
        if(!confirm('Clear all tickets?')) return;
        await fetch('/clear-tickets',{method:'POST'});
        refresh();
      }

      refresh();
    </script>
  </body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route('/clear-tickets', methods=['POST'])
def clear_tickets():
    save_tickets([])
    return jsonify({'message': 'cleared'})


# === Static file serving (for convenience) ===
@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory('.', filename, as_attachment=True)


# === Sample helper the user can copy into their retrieval script ===
SAMPLE_CLIENT = '''
# Sample snippet to POST to your local mock ITSM
import requests

local_itsm = 'http://127.0.0.1:5000/create-ticket'

def post_ticket_to_local_itsm(pipeline, project, log_excerpt, severity='Medium'):
    payload = {
        'pipeline': pipeline,
        'project': project,
        'log': log_excerpt,
        'severity': severity
    }
    r = requests.post(local_itsm, json=payload)
    print('Posted to local ITSM', r.status_code, r.text)

# Usage: post_ticket_to_local_itsm('build-123','MyProject','Error: deployment failed...')
'''

@app.route('/sample-client')
def sample_client():
    return f"<pre>{SAMPLE_CLIENT}</pre>"


#main app run
if __name__ == '__main__':
    print('\nPipeline Failure Auto-Ticketing Demo')
    print('Dashboard: http://127.0.0.1:5000')
    if OPENAI_API_KEY:
        print('OpenAI API key detected: AI categorization ENABLED')
    else:
        print('No OpenAI API key found: using keyword fallback categorizer')
    app.run(host='0.0.0.0', port=5000, debug=True)
