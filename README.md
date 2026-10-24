# 📊 wazuh-report-engine

[![Docker](https://img.shields.io/badge/Docker-Supported-blue?logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A lightweight web service that transforms analyzed **Wazuh** alert data into a complete, publication-ready security report. It generates **dynamic charts**, an **HTML email body**, and a **PDF attachment**—all from a single shared Jinja2 template.

---

## 💡 Overview

Designed primarily to be invoked by automation platforms (such as **n8n**), this engine accepts pre-analyzed alert JSON payloads and handles all heavy presentation rendering.

```
┌────────────────────────┐     POST /render      ┌──────────────────────────────────────────────┐
│  Analyzed Alert Data   │ ────────────────────► │             wazuh-report-engine              │
│       (JSON)           │                       │                                              │
└────────────────────────┘                       │  1. Draws charts (Matplotlib & Seaborn)       │
                                                 │  2. Fills HTML template (Email & PDF)        │
                                                 │  3. Converts HTML to PDF via WeasyPrint      │
                                                 └──────────────────────┬───────────────────────┘
                                                                        │
                                                                        ▼
                                                       JSON Reply: Email HTML + PDF (Base64)
```

> ℹ️ **Note:** The service handles presentation work (graphs, layout, PDF). Log analysis (counting alerts, calculating risk scores, generating recommendations) is performed beforehand (e.g., in an n8n Code node) and passed via the request payload.

---

## ✨ Features & Capabilities

### 📈 Generated Charts

| Chart Name | Description |
| :--- | :--- |
| **Alerts per hour** | Volume over the last 24 hours, colored by severity, with business hours shaded and spikes highlighted. |
| **Severity mix** | Share of critical, high, medium, and low alerts, comparing today versus yesterday. |
| **Endpoint heatmap** | Visual grid showing machine activity levels broken down by hour. |
| **Endpoint risk ranking** | Endpoints ranked by overall risk score, broken down by severity. |
| **Rule Pareto chart** | Highlights the top rules responsible for driving the majority of alerts. |
| **Login attacks** | Failed login attempts mapped by source IP address and targeted usernames. |
| **MITRE ATT&CK stages** | Visibility into how far along the attack chain suspicious activity reached. |
| **File changes** | Details on file-integrity monitoring (FIM) modifications and locations. |
| **Source IPs & Countries** | Categorization of external vs. internal network activity sources. |

> **Note:** Charts are dynamically rendered. If a payload contains no data for a specific chart, it is skipped automatically without failing the report generation.

---

## 🚀 Quick Start with Docker Compose

### Prerequisites
* **Docker**
* **Docker Compose v2**

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/report-engine.git
   cd report-engine
   ```

2. **Configure environment:**
   Open `docker-compose.yml` and set `PUBLIC_BASE_URL` to your accessible server URL (e.g., `http://192.168.1.10:5055`). Email clients use this URL to load inline chart images.

3. **Build and start the container:**
   ```bash
   docker compose up -d --build
   ```

4. **Verify service status:**
   ```bash
   docker compose ps
   curl http://localhost:5055/health
   # Returns: ok
   ```

---

## 🛠️ Management Commands

| Action | Command |
| :--- | :--- |
| **View logs** | `docker compose logs -f report-engine` |
| **Restart service** | `docker compose restart` |
| **Stop service** | `docker compose down` |
| **Rebuild application** | `docker compose up -d --build` |

---

## 🔌 API Reference

### `POST /render`

Send analyzed JSON payload to generate the report files.

#### Response Format (`200 OK`)
```json
{
  "html_email": "<!DOCTYPE html>...",
  "pdf_base64": "JVBERi0xLjc...",
  "filename": "Wazuh-Security-Report.pdf"
}
```

#### Test via Curl
```bash
curl -s -X POST http://localhost:5055/render \
  -H "Content-Type: application/json" -d @sample.json \
  | python3 -c "import sys,json,base64; d=json.load(sys.stdin); open(d['filename'],'wb').write(base64.b64decode(d['pdf_base64']))"
```

### Additional Endpoints

* `GET /health` – Returns status `ok` for health monitoring.
* `GET /charts/<id>/<file>` – Serves dynamic chart images for HTML emails.

---

## 📂 Project Structure

```text
report-engine/
├── app.py               # Flask application handling charting & rendering
├── report.html.j2       # Unified Jinja2 template (Email & PDF)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container build spec
└── docker-compose.yml   # Docker service configuration
```

---

## 🔐 Security & Maintenance

* **Network Security:** The endpoint does not feature built-in authentication. Keep port `5055` restricted to your trusted local network or secure it behind an authenticating reverse proxy (e.g., NGINX / Traefik).
* **Disk Cleanup:** Rendered charts accumulate in `./data/charts/<id>/`. You can schedule periodic cleanup using cron:
  ```bash
  find data/charts -mtime +30 -type d -exec rm -rf {} +
  ```
