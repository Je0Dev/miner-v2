"""Statistics dashboard web viewer."""
import json
from pathlib import Path
from flask import Flask, render_template_string
from config import MINING_DIR
from stats import load_stats, format_stats_report

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head><title>Mining Dashboard</title><meta charset="utf-8">
<style>
body {{ font-family: sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
.card {{ background: #16213e; border-radius: 8px; padding: 20px; margin: 10px 0; }}
h1 {{ color: #00d4ff; }} h2 {{ color: #ffdd57; }}
.stat {{ font-size: 24px; color: #00d4ff; margin: 10px 0; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #333; }}
th {{ color: #00d4ff; }}
</style></head>
<body>
<h1>Mining Dashboard</h1>
<div class="card">
<h2>Overview</h2>
<div class="stat">Total Mined: {total}</div>
<div class="stat">OCR Failures: {ocr_fail}</div>
<div class="stat">Avg Confidence: {avg_conf}%</div>
</div>
<div class="card">
<h2>By Language</h2>
<table><tr><th>Language</th><th>Mined</th><th>Failures</th><th>Fail Rate</th></tr>
{lang_rows}
</table></div>
</body></html>
"""

@app.route("/")
def dashboard():
    stats = load_stats()
    lang_rows = ""
    for lang, data in stats.get("by_lang", {}).items():
        fail_rate = data["failures"] / data["count"] * 100 if data["count"] > 0 else 0
        lang_rows += f"<tr><td>{lang}</td><td>{data['count']}</td><td>{data['failures']}</td><td>{fail_rate:.1f}%</td></tr>"
    html = DASHBOARD_HTML.format(
        total=stats.get("total_mined", 0),
        ocr_fail=stats.get("ocr_failures", 0),
        avg_conf=f"{stats.get('avg_confidence', 0):.1f}",
        lang_rows=lang_rows
    )
    return html

def run_dashboard(port: int = 5001):
    print(f"Dashboard: http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
