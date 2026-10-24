# wazuh-report-engine
A small web service that turns analyzed Wazuh alert data into a finished security report: charts, an HTML email body, and a PDF, all generated from one shared template.

It is built to be called by an automation tool (for example n8n) that collects and analyzes the alerts, but it works with anything that can send it JSON.

What it does
analyzed alert data (JSON)  --->  POST /render
                                     |
                                     |-- 1. draws charts (matplotlib + seaborn, saved as PNG)
                                     |-- 2. fills one HTML template twice
                                     |       - email version (charts loaded from this server)
                                     |       - PDF version  (charts embedded in the file)
                                     |-- 3. converts the PDF version to a PDF (WeasyPrint)
                                     v
                       JSON reply: email HTML + PDF (base64) + file name

The service does the presentation work: graphs, layout and PDF. The log analysis itself (counting alerts, risk score, insights, recommendations) happens before the request is sent, for example in an n8n Code node, and arrives as the JSON payload.

Charts it creates
Chart	What it shows
Alerts per hour	Volume over the last 24 hours, colored by severity, with business hours shaded and spikes marked
Severity mix	Share of critical, high, medium and low alerts, plus today versus yesterday
Endpoint heatmap	Which machines were noisy at which hour
Endpoint risk ranking	Endpoints ranked by risk, split by severity
Rule Pareto chart	The few rules that create most of the alerts
Login attacks	Failed logins by source IP and by targeted username
MITRE ATT&CK stages	How far along the attack chain activity was seen
File changes	Type and location of file-integrity changes
Source IPs and countries	Internal versus external sources

A chart is skipped automatically if the payload has no data for it, and one failing chart never stops the report.

Run it with Docker Compose

Requirements: Docker and Docker Compose v2.

bash
git clone https://github.com/YOUR_USERNAME/report-engine.git
cd report-engine
Open docker-compose.yml and set PUBLIC_BASE_URL to the address people will use to reach this service, for example http://192.168.1.10:5055. Charts in the email body are loaded from this address.
Build and start:
bash
   docker compose up -d --build
Check that it is running:
bash
   docker compose ps
   curl http://localhost:5055/health        # prints: ok

Everyday commands:

bash
docker compose logs -f report-engine     # follow the logs
docker compose restart                   # restart
docker compose down                      # stop
docker compose up -d --build             # rebuild after changing app.py or the template

The first build downloads about 100 MB of Python packages. On a slow connection it can time out; run the same build command again and it continues using cached downloads.

API
POST /render

Send the analyzed data as JSON (Content-Type: application/json). Reply:

json
{
  "html_email": "<!DOCTYPE html>...",
  "pdf_base64": "JVBERi0xLjc...",
  "filename": "YOUR-FILE-NAME"
}
Reply field	Use
html_email	Put this in the body of the email
pdf_base64	Decode it to get the PDF file to attach
filename	Suggested name for the attachment

Try it with a payload saved in a file:

bash
curl -s -X POST http://localhost:5055/render \
  -H "Content-Type: application/json" -d @sample.json \
  | python3 -c "import sys,json,base64; d=json.load(sys.stdin); open(d['filename'],'wb').write(base64.b64decode(d['pdf_base64']))"
Main fields of the request
Field	Content
org, report_date, period, generated_at	Header text
risk_score, risk_label, risk_color	Overall status banner
exec_summary	Plain-English summary paragraph
kpis	List of {label, value, sub, sub_color, color} cards
total, analyzed, sev, prev_sev	Alert counts and severity split (critical, high, medium, low)
timeline, spike_index, biz	Hourly counts (hour, h, severity counts, count) and business hours
top_rules, heat, agent_sev, auth, mitre_chain, fim, network	Data for the individual charts
captions	Per-chart how and finding text shown under each graph
notable, recommendations, data_notes	Tables and lists in the report

The full payload is produced by the analysis step of your workflow; report.html.j2 and app.py show exactly which fields are read.

Other endpoints
Endpoint	Purpose
GET /health	Returns ok; used for health checks
GET /charts/<id>/<file>	Serves the chart images referenced by the email HTML
Project layout
report-engine/
├── app.py               Flask app: charts, rendering, PDF
├── report.html.j2       Single template used for both the email and the PDF
├── requirements.txt     Python packages
├── Dockerfile           Image definition
└── docker-compose.yml   Service, port 5055, data volume

Built with Flask, Gunicorn, matplotlib, seaborn, pandas, Jinja2 and WeasyPrint.

Notes
Changing the look: edit report.html.j2 (layout, colors, text) or the chart functions in app.py, then rebuild with docker compose up -d --build.
Disk space: every request saves its chart images in ./data/charts/<id>/. Remove old ones from time to time, for example with find data/charts -mtime +30 -type d -exec rm -rf {} +.
Email charts: mail clients block embedded images, so the email version loads charts from PUBLIC_BASE_URL. Readers must be able to reach that address. The PDF always contains its charts.
Security: the service has no login. Keep port 5055 on a trusted network, or put a reverse proxy with authentication in front of it.
