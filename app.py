import os, uuid, base64
from flask import Flask, request, jsonify, send_from_directory, abort
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import seaborn as sns
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

app = Flask(__name__)
DATA = "/data/charts"
BASE = os.getenv("PUBLIC_BASE_URL", "http://localhost:5055")
env = Environment(loader=FileSystemLoader("/app"), autoescape=select_autoescape(["j2"]))

SEV = {"critical": "#C0392B", "high": "#E67E22", "medium": "#F4D03F", "low": "#58B368"}
BRAND, ACCENT, GREY, EXT = "#1F3A5F", "#2E86DE", "#8A97A5", "#C0392B"
sns.set_theme(style="whitegrid", rc={
    "axes.edgecolor": "#D5DCE4", "grid.color": "#E6EBF1", "font.size": 9,
    "axes.titleweight": "bold", "axes.titlesize": 11, "axes.labelcolor": "#4A5A6A",
})

# ---------- helpers ----------
def finish(fig, folder, name):
    fig.savefig(os.path.join(folder, name), dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return name

def short(s, n=40):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"

def empty(ax, msg="No data"):
    ax.text(.5, .5, msg, ha="center", va="center", transform=ax.transAxes, color=GREY)
    ax.set_xticks([]); ax.set_yticks([])

def ip_colors(df):
    return [EXT if t == "external" else ACCENT for t in df["type"]]

def hbar_ax(ax, items, title, colors=None, shorten=36):
    ax.set_title(title, loc="left", fontsize=10, color=BRAND, fontweight="bold")
    if not items:
        empty(ax); return
    df = pd.DataFrame(items).iloc[::-1]
    labels = [short(n, shorten) for n in df["name"]]
    cols = colors(df) if callable(colors) else (colors or ACCENT)
    ax.barh(labels, df["count"], color=cols)
    for i, v in enumerate(df["count"]):
        ax.text(v, i, f" {int(v):,}", va="center", fontsize=8)
    ax.margins(x=.18)
    ax.grid(axis="y", visible=False)
    sns.despine(ax=ax)

# ---------- charts ----------
def c_timeline(m):
    tl = pd.DataFrame(m["timeline"])
    if tl.empty or tl["count"].sum() == 0:
        return None
    fig, ax = plt.subplots(figsize=(7.4, 3.3))
    x = np.arange(len(tl))
    shaded = False
    for i, h in enumerate(tl["h"]):
        if h < m["biz"]["start"] or h >= m["biz"]["end"]:
            ax.axvspan(i - .5, i + .5, color="#E9EDF2", zorder=0,
                       label=None if shaded else "Outside business hours")
            shaded = True
    bottom = np.zeros(len(tl))
    for k in ("low", "medium", "high", "critical"):
        ax.bar(x, tl[k], bottom=bottom, color=SEV[k], width=.8, label=k.title(), zorder=2)
        bottom += tl[k].values
    mean = float(tl["count"].mean())
    ax.axhline(mean, color=BRAND, ls="--", lw=1, zorder=3)
    ax.text(len(tl) - .4, mean, " avg", va="bottom", ha="right", color=BRAND, fontsize=8)
    si = m.get("spike_index")
    if si is not None:
        ax.annotate("Spike", (si, int(tl["count"].iloc[si])), xytext=(0, 16), textcoords="offset points",
                    ha="center", color=SEV["critical"], fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=SEV["critical"]))
    ax.set_xticks(x[::2]); ax.set_xticklabels(tl["hour"].iloc[::2], fontsize=8)
    ax.set_ylabel("Alerts")
    ax.set_title("Alerts per hour, by severity (Pakistan time)", loc="left", color=BRAND)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, ncol=5, frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(.5, -.12))
    sns.despine(ax=ax)
    return fig

def c_severity(m):
    keys = ("critical", "high", "medium", "low")
    cur = [m["sev"][k] for k in keys]
    if sum(cur) == 0:
        return None
    prev = m.get("prev_sev")
    fig, axes = plt.subplots(1, 2 if prev else 1, figsize=(7.4, 3.2),
                             gridspec_kw={"width_ratios": [1, 1.25]} if prev else None)
    axes = np.atleast_1d(axes)
    ax = axes[0]
    ax.pie(cur, colors=[SEV[k] for k in keys], startangle=90, counterclock=False,
           wedgeprops=dict(width=.38, edgecolor="white"))
    ax.text(0, 0, f"{sum(cur):,}\nalerts", ha="center", va="center", fontsize=12, fontweight="bold", color=BRAND)
    ax.legend([f"{k.title()}  {v:,}" for k, v in zip(keys, cur)], loc="upper center",
              bbox_to_anchor=(.5, 0), ncol=2, frameon=False, fontsize=8)
    ax.set_title("Today's severity mix", loc="left", color=BRAND)
    if prev:
        df = pd.DataFrame({"Severity": [k.title() for k in keys] * 2,
                           "Alerts": [prev[k] for k in keys] + cur,
                           "Day": ["Yesterday"] * 4 + ["Today"] * 4})
        ax2 = axes[1]
        sns.barplot(data=df, x="Severity", y="Alerts", hue="Day",
                    palette={"Yesterday": "#C9D3DF", "Today": BRAND}, ax=ax2)
        for c in ax2.containers:
            ax2.bar_label(c, fmt="%d", fontsize=7, padding=2)
        ax2.set_title("Today vs yesterday", loc="left", color=BRAND)
        ax2.set_xlabel(""); ax2.legend(frameon=False, fontsize=8)
        sns.despine(ax=ax2)
    return fig

def c_heatmap(m):
    h = m.get("heat") or {}
    if not h.get("agents"):
        return None
    df = pd.DataFrame(h["matrix"], index=[short(a, 26) for a in h["agents"]],
                      columns=[f"{i:02d}" for i in range(24)])
    if df.values.sum() == 0:
        return None
    fig, ax = plt.subplots(figsize=(7.6, 0.45 * len(df) + 1.7))
    sns.heatmap(df, cmap="YlOrRd", linewidths=.6, linecolor="white",
                cbar_kws={"label": "Alerts", "shrink": .8}, ax=ax)
    ax.set_xlabel("Hour of day (Pakistan time)"); ax.set_ylabel("")
    ax.set_title("When is each endpoint noisy?", loc="left", color=BRAND)
    plt.setp(ax.get_yticklabels(), rotation=0)
    return fig

def c_agents(m):
    rows = m.get("agent_sev") or []
    if not rows:
        return None
    df = pd.DataFrame(rows).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.4, 0.42 * len(df) + 1.5))
    left = np.zeros(len(df))
    labels = [short(n, 30) for n in df["name"]]
    for k in ("critical", "high", "medium", "low"):
        ax.barh(labels, df[k], left=left, color=SEV[k], label=k.title())
        left += df[k].values
    for i, t in enumerate(left):
        ax.text(t, i, f" {int(t):,}", va="center", fontsize=8)
    ax.margins(x=.12)
    ax.set_title("Endpoints ranked by risk (alerts, coloured by severity)", loc="left", color=BRAND)
    ax.legend(ncol=4, frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(.5, -.12))
    ax.grid(axis="y", visible=False); sns.despine(ax=ax)
    return fig

def c_pareto(m):
    r = m.get("top_rules") or []
    if not r:
        return None
    df = pd.DataFrame(r[:10])
    analyzed = max(m.get("analyzed", 1), 1)
    df["cum"] = df["count"].cumsum() / analyzed * 100
    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    x = np.arange(len(df))
    ax.bar(x, df["count"], color=[SEV[b] for b in df["band"]])
    ax.set_xticks(x); ax.set_xticklabels([f"#{i + 1}" for i in x])
    ax.set_ylabel("Alerts")
    ax2 = ax.twinx()
    ax2.plot(x, df["cum"], color=ACCENT, marker="o", lw=2)
    ax2.set_ylim(0, 112); ax2.set_ylabel("Cumulative % of alerts"); ax2.grid(False)
    for i, v in enumerate(df["cum"]):
        ax2.text(i, v + 4, f"{v:.0f}%", ha="center", fontsize=8, color=ACCENT)
    ax.set_title("Which rules create the most alerts? (Pareto)", loc="left", color=BRAND)
    ax.legend(handles=[Patch(color=SEV[k], label=k.title()) for k in ("critical", "high", "medium", "low")],
              ncol=4, frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(.5, -.12))
    sns.despine(ax=ax, right=False)
    return fig

def c_auth(m):
    a = m.get("auth") or {}
    if not (a.get("ips") or a.get("users")):
        return None
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.3))
    hbar_ax(axes[0], a.get("ips"), "Failed logins by source IP", ip_colors, 18)
    hbar_ax(axes[1], a.get("users"), "Most targeted usernames", SEV["high"], 18)
    fig.legend(handles=[Patch(color=EXT, label="External IP"), Patch(color=ACCENT, label="Internal IP")],
               loc="lower center", ncol=2, frameon=False, fontsize=8, bbox_to_anchor=(.5, -.04))
    fig.tight_layout()
    return fig

def c_mitre(m):
    t = m.get("mitre_chain") or []
    if not any(x["count"] for x in t):
        return None
    df = pd.DataFrame(t)
    fig, ax = plt.subplots(figsize=(7.4, 0.32 * len(df) + 1.3))
    pal = sns.color_palette("YlOrRd", len(df))
    ax.barh(df["name"], df["count"], color=[pal[i] if c else "#E6EBF1" for i, c in enumerate(df["count"])])
    ax.invert_yaxis()
    for i, c in enumerate(df["count"]):
        if c:
            ax.text(c, i, f" {int(c):,}", va="center", fontsize=8)
    ax.margins(x=.12)
    ax.set_title("Attack stages observed (early at top, late at bottom)", loc="left", color=BRAND)
    ax.grid(axis="y", visible=False); sns.despine(ax=ax)
    return fig

def c_fim(m):
    f = m.get("fim") or {}
    if not (f.get("events") or f.get("paths")):
        return None
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.2), gridspec_kw={"width_ratios": [1, 1.7]})
    pal = {"added": "#58B368", "modified": "#F4D03F", "deleted": "#C0392B"}
    hbar_ax(axes[0], f.get("events"), "Type of change", lambda df: [pal.get(str(n).lower(), ACCENT) for n in df["name"]])
    paths = [{"name": ("…" + p["name"][-34:]) if len(p["name"]) > 35 else p["name"], "count": p["count"]}
             for p in f.get("paths", [])]
    hbar_ax(axes[1], paths, "Most-changed paths", ACCENT, 38)
    fig.tight_layout()
    return fig

def c_network(m):
    n = m.get("network") or {}
    if not n.get("ips"):
        return None
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.3))
    hbar_ax(axes[0], n["ips"], "Most active source IPs", ip_colors, 18)
    ax = axes[1]
    if n.get("countries"):
        hbar_ax(ax, n["countries"], "Countries of external IPs", SEV["high"], 20)
    else:
        vals = [n.get("internal", 0), n.get("external", 0)]
        if sum(vals):
            ax.pie(vals, labels=["Internal", "External"], colors=[ACCENT, EXT], startangle=90,
                   wedgeprops=dict(width=.4, edgecolor="white"),
                   autopct=lambda p: f"{p:.0f}%", textprops={"fontsize": 9})
        ax.set_title("Internal vs external addresses", loc="left", fontsize=10, color=BRAND, fontweight="bold")
    fig.tight_layout()
    return fig

CHARTS = [("timeline", c_timeline), ("severity", c_severity), ("heatmap", c_heatmap),
          ("agents", c_agents), ("pareto", c_pareto), ("auth", c_auth),
          ("mitre", c_mitre), ("fim", c_fim), ("network", c_network)]

# ---------- routes ----------
@app.post("/render")
def render():
    m = request.get_json(force=True)
    rid = uuid.uuid4().hex[:10]
    folder = os.path.join(DATA, rid)
    os.makedirs(folder, exist_ok=True)

    files = {}
    for key, fn in CHARTS:
        try:
            fig = fn(m)
            if fig is not None:
                files[key] = finish(fig, folder, f"{key}.png")
        except Exception:
            app.logger.exception("chart %s failed", key)   # one bad chart never kills the report

    tpl = env.get_template("report.html.j2")
    html_email = tpl.render(m=m, mode="email",
                            charts={k: f"{BASE}/charts/{rid}/{v}" for k, v in files.items()})

    def b64(f):
        with open(os.path.join(folder, f), "rb") as fh:
            return "data:image/png;base64," + base64.b64encode(fh.read()).decode()

    html_pdf = tpl.render(m=m, mode="pdf", charts={k: b64(v) for k, v in files.items()})
    pdf = HTML(string=html_pdf).write_pdf()
    return jsonify(html_email=html_email,
                   pdf_base64=base64.b64encode(pdf).decode(),
                   filename=f"Ombre_Apparel_Security_Report_{m['report_date']}.pdf")

@app.get("/charts/<rid>/<fn>")
def chart(rid, fn):
    if not rid.isalnum() or "/" in fn or ".." in fn:
        abort(404)
    return send_from_directory(os.path.join(DATA, rid), fn)

@app.get("/health")
def health():
    return "ok"
