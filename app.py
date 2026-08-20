"""
Web UI Application for Evidence-Grounded Resume Parser Agent.
Provides a clean, responsive single-page interface with 1-click sample loaders,
evidence inspect drawers, match status badges, and browser launch support.
Zero external server dependencies (uses standard library http.server).
"""

import http.server
import socketserver
import json
import os
import sys
import tempfile
import urllib.parse
import webbrowser
from extractor import extract_text_from_file, ExtractionError
from segmenter import segment_sections
from field_parser import parse_all_fields
from scorer import score_candidate
from report_generator import generate_markdown_report, generate_json_profile
from models import CandidateProfile

PORT = 8501
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resume Parser Agent — Evidence-Grounded AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #0f172a;
            --bg-surface: #1e293b;
            --bg-elevated: #334155;
            --border: #475569;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-base);
            color: var(--text-main);
            line-height: 1.5;
            padding: 24px;
        }

        .container { max-width: 1200px; margin: 0 auto; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
        }
        .header-title h1 { font-size: 1.5rem; font-weight: 700; color: #fff; }
        .header-title p { color: var(--text-muted); font-size: 0.875rem; }
        .badge-grounded {
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid var(--success);
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }

        .card {
            background-color: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 600;
            font-size: 1.1rem;
        }

        .form-group { display: flex; flex-direction: column; gap: 8px; }
        label { font-size: 0.875rem; font-weight: 500; color: var(--text-muted); }
        input[type="file"], textarea, select {
            background-color: var(--bg-base);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px;
            color: var(--text-main);
            font-family: inherit;
            font-size: 0.875rem;
        }
        textarea { resize: vertical; min-height: 140px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }
        textarea:focus, select:focus { outline: none; border-color: var(--primary); }

        .btn {
            background-color: var(--primary);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 20px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: background-color 0.2s;
        }
        .btn:hover { background-color: var(--primary-hover); }
        .btn-secondary {
            background-color: var(--bg-elevated);
            color: var(--text-main);
            padding: 6px 12px;
            font-size: 0.8rem;
        }
        .btn-secondary:hover { background-color: var(--border); }

        /* Score Summary Box */
        .score-hero {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        }
        .score-circle {
            width: 84px;
            height: 84px;
            border-radius: 50%;
            border: 4px solid var(--primary);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            font-weight: 700;
            color: #fff;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            flex-grow: 1;
            margin-left: 24px;
        }
        .metric-card {
            background-color: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }
        .metric-value { font-size: 1.25rem; font-weight: 700; }
        .metric-label { font-size: 0.75rem; color: var(--text-muted); }

        /* Match Statuses */
        .status-badge {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status-FOUND, .status-MATCHED { background: rgba(16, 185, 129, 0.2); color: #34d399; }
        .status-PARTIAL, .status-AMBIGUOUS { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
        .status-MISSING, .status-NOT_FOUND { background: rgba(239, 68, 68, 0.2); color: #f87171; }

        .item-row {
            background-color: var(--bg-base);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .item-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
        }
        .item-title { font-weight: 600; font-size: 0.9rem; }
        .item-explanation { font-size: 0.825rem; color: var(--text-muted); }
        .item-evidence {
            background-color: #0b0f19;
            border-left: 3px solid var(--primary);
            padding: 8px 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: #cbd5e1;
            white-space: pre-wrap;
            border-radius: 0 4px 4px 0;
        }

        .tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
        .tab {
            padding: 8px 16px;
            cursor: pointer;
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-muted);
            border-bottom: 2px solid transparent;
        }
        .tab.active { color: var(--primary); border-bottom-color: var(--primary); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .hidden { display: none !important; }
        .loader {
            border: 3px solid var(--bg-elevated);
            border-top: 3px solid var(--primary);
            border-radius: 50%;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            display: inline-block;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-title">
                <h1>Evidence-Grounded Resume Parser Agent</h1>
                <p>Zero Hallucination • 100% Deterministic Evidence Citation • JD Fit Scoring</p>
            </div>
            <span class="badge-grounded">🔒 Zero-Drift Grounded</span>
        </header>

        <div class="grid">
            <!-- INPUT PANEL -->
            <div class="card">
                <div class="card-header">
                    <span>Input Documents</span>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn btn-secondary" onclick="loadSample('fullstack')">Sample 1: Full-Stack</button>
                        <button class="btn btn-secondary" onclick="loadSample('data_engineer')">Sample 2: Data Eng</button>
                    </div>
                </div>

                <div class="form-group">
                    <label>Resume File (PDF / DOCX / TXT)</label>
                    <input type="file" id="resumeFileInput" accept=".pdf,.docx,.txt">
                    <small style="color: var(--text-muted);">Or paste raw resume text below:</small>
                    <textarea id="resumeTextInput" placeholder="Paste resume text or upload a file..."></textarea>
                </div>

                <div class="form-group">
                    <label>Job Description (JD)</label>
                    <textarea id="jdTextInput" placeholder="Paste Job Description requirements..."></textarea>
                </div>

                <button class="btn" id="analyzeBtn" onclick="runAnalysis()">
                    <span id="btnText">🔍 Analyze Resume & Match JD</span>
                    <span id="btnLoader" class="loader hidden"></span>
                </button>
            </div>

            <!-- RESULTS PANEL -->
            <div class="card" id="resultsCard">
                <div class="card-header">
                    <span>Analysis & Evidence Report</span>
                    <span id="extractionStatusBadge" class="status-badge status-FOUND hidden">READY</span>
                </div>

                <div id="emptyState" style="text-align: center; padding: 60px 20px; color: var(--text-muted);">
                    <p style="font-size: 1.1rem; margin-bottom: 8px;">No analysis executed yet</p>
                    <p style="font-size: 0.85rem;">Select a sample or upload a resume to view grounded fields and fit score.</p>
                </div>

                <div id="resultsContent" class="hidden">
                    <!-- Score Banner -->
                    <div class="score-hero">
                        <div class="score-circle" id="overallScoreDisplay">0%</div>
                        <div class="metrics-grid">
                            <div class="metric-card">
                                <div class="metric-value" style="color: var(--success);" id="matchedCount">0</div>
                                <div class="metric-label">Matched</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-value" style="color: var(--warning);" id="partialCount">0</div>
                                <div class="metric-label">Partial</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-value" style="color: var(--danger);" id="missingCount">0</div>
                                <div class="metric-label">Missing</div>
                            </div>
                        </div>
                    </div>

                    <!-- Tabs -->
                    <div class="tabs">
                        <div class="tab active" onclick="switchTab('requirementsTab', this)">JD Requirements Match</div>
                        <div class="tab" onclick="switchTab('fieldsTab', this)">10 Grounded Fields</div>
                    </div>

                    <!-- Tab 1: JD Requirements -->
                    <div id="requirementsTab" class="tab-content active">
                        <div id="requirementsList"></div>
                    </div>

                    <!-- Tab 2: 10 Grounded Fields -->
                    <div id="fieldsTab" class="tab-content">
                        <div id="fieldsList"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function switchTab(tabId, el) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            el.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }

        async function loadSample(sampleType) {
            try {
                const res = await fetch(`/api/sample?type=${sampleType}`);
                const data = await res.json();
                document.getElementById('resumeTextInput').value = data.resume_text;
                document.getElementById('jdTextInput').value = data.jd_text;
                document.getElementById('resumeFileInput').value = '';
                runAnalysis();
            } catch (err) {
                alert('Error loading sample: ' + err);
            }
        }

        async function runAnalysis() {
            const btn = document.getElementById('analyzeBtn');
            const btnText = document.getElementById('btnText');
            const btnLoader = document.getElementById('btnLoader');
            const fileInput = document.getElementById('resumeFileInput');
            const textInput = document.getElementById('resumeTextInput').value;
            const jdInput = document.getElementById('jdTextInput').value;

            btn.disabled = true;
            btnText.innerText = 'Analyzing...';
            btnLoader.classList.remove('hidden');

            try {
                let payload;
                if (fileInput.files.length > 0) {
                    const formData = new FormData();
                    formData.append('file', fileInput.files[0]);
                    formData.append('jd_text', jdInput);
                    const res = await fetch('/api/upload_analyze', { method: 'POST', body: formData });
                    payload = await res.json();
                } else {
                    const res = await fetch('/api/analyze', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ resume_text: textInput, jd_text: jdInput })
                    });
                    payload = await res.json();
                }

                renderResults(payload);
            } catch (err) {
                alert('Analysis failed: ' + err);
            } finally {
                btn.disabled = false;
                btnText.innerText = '🔍 Analyze Resume & Match JD';
                btnLoader.classList.add('hidden');
            }
        }

        function renderResults(data) {
            if (data.error) {
                alert('Error: ' + data.error);
                return;
            }

            document.getElementById('emptyState').classList.add('hidden');
            document.getElementById('resultsContent').classList.remove('hidden');

            // Extraction badge
            const badge = document.getElementById('extractionStatusBadge');
            badge.innerText = data.extraction_status || 'PARSED';
            badge.className = 'status-badge status-FOUND';
            badge.classList.remove('hidden');

            // Fit Score
            if (data.fit_report) {
                document.getElementById('overallScoreDisplay').innerText = data.fit_report.overall_score + '%';
                document.getElementById('matchedCount').innerText = data.fit_report.matched_count;
                document.getElementById('partialCount').innerText = data.fit_report.partial_count;
                document.getElementById('missingCount').innerText = data.fit_report.missing_count;

                // Render JD Requirements List
                const reqList = document.getElementById('requirementsList');
                reqList.innerHTML = '';
                data.fit_report.matches.forEach(m => {
                    const div = document.createElement('div');
                    div.className = 'item-row';
                    div.innerHTML = `
                        <div class="item-top">
                            <span class="item-title">${escapeHtml(m.requirement)}</span>
                            <span class="status-badge status-${m.match_status}">${m.match_status}</span>
                        </div>
                        <div class="item-explanation">${escapeHtml(m.explanation)}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">
                            Evidence Ref: <strong style="color: var(--text-main);">${m.evidence_ref}</strong> • Confidence: <em>${m.confidence}</em>
                        </div>
                    `;
                    reqList.appendChild(div);
                });
            }

            // Render 10 Grounded Fields List
            const fieldsList = document.getElementById('fieldsList');
            fieldsList.innerHTML = '';
            Object.keys(data.fields).sort().forEach(fid => {
                const f = data.fields[fid];
                const div = document.createElement('div');
                div.className = 'item-row';
                let valFormatted = f.value ? JSON.stringify(f.value) : 'NOT_FOUND';
                if (typeof f.value === 'object' && f.value !== null) {
                    valFormatted = Object.entries(f.value).map(([k, v]) => `${k}: ${v}`).join(' | ');
                }
                div.innerHTML = `
                    <div class="item-top">
                        <span class="item-title">${f.field_id} <span style="font-weight: 400; color: var(--text-muted);">(${f.category})</span></span>
                        <span class="status-badge status-${f.status}">${f.status}</span>
                    </div>
                    <div style="font-size: 0.85rem; font-weight: 500; color: #38bdf8;">
                        Value: ${escapeHtml(String(valFormatted))}
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-muted);">Source Section: <strong>${f.source_section}</strong></div>
                    ${f.evidence ? `<div class="item-evidence"><strong>Evidence:</strong>\n${escapeHtml(f.evidence)}</div>` : ''}
                `;
                fieldsList.appendChild(div);
            });
        }

        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }
    </script>
</body>
</html>
"""


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        
        if parsed_url.path == "/" or parsed_url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return
            
        elif parsed_url.path == "/api/sample":
            query = urllib.parse.parse_qs(parsed_url.query)
            sample_type = query.get("type", ["fullstack"])[0]
            
            resume_filename = "resume_fullstack.txt" if sample_type == "fullstack" else "resume_data_engineer.txt"
            jd_filename = "jd_fullstack.txt" if sample_type == "fullstack" else "jd_data_engineer.txt"
            
            with open(os.path.join(SAMPLES_DIR, resume_filename), "r", encoding="utf-8") as f:
                resume_text = f.read()
            with open(os.path.join(SAMPLES_DIR, jd_filename), "r", encoding="utf-8") as f:
                jd_text = f.read()
                
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"resume_text": resume_text, "jd_text": jd_text}).encode("utf-8"))
            return
            
        super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        
        if parsed_url.path == "/api/analyze":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            data = json.loads(body)
            
            resume_text = data.get("resume_text", "")
            jd_text = data.get("jd_text", "")
            
            if not resume_text.strip():
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Resume text cannot be empty"}).encode("utf-8"))
                return
                
            sections, found, missing = segment_sections(resume_text)
            fields = parse_all_fields(sections, resume_text)
            fit_report = score_candidate(fields, resume_text, jd_text) if jd_text.strip() else None
            
            profile = CandidateProfile(
                source_file="direct_input",
                extraction_status="SUCCESS",
                raw_character_count=len(resume_text),
                sections_found=found,
                sections_missing=missing,
                fields=fields,
                fit_report=fit_report
            )
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(profile.to_dict()).encode("utf-8"))
            return

        elif parsed_url.path == "/api/upload_analyze":
            # Handle multipart file upload safely
            content_type = self.headers.get('Content-Type', '')
            content_len = int(self.headers.get('Content-Length', 0))
            raw_body = self.rfile.read(content_len)
            
            # Simple multipart boundary parsing
            boundary = content_type.split("boundary=")[-1].encode("utf-8")
            parts = raw_body.split(b"--" + boundary)
            
            file_bytes = None
            filename = "uploaded_resume.pdf"
            jd_text = ""
            
            for part in parts:
                if b'name="file"' in part and b'filename="' in part:
                    header_end = part.find(b"\r\n\r\n")
                    if header_end != -1:
                        headers = part[:header_end].decode("utf-8", "replace")
                        for h in headers.split("\r\n"):
                            if "filename=" in h:
                                fn = h.split('filename="')[-1].split('"')[0]
                                if fn:
                                    filename = fn
                        file_bytes = part[header_end + 4:].rstrip(b"\r\n")
                elif b'name="jd_text"' in part:
                    header_end = part.find(b"\r\n\r\n")
                    if header_end != -1:
                        jd_text = part[header_end + 4:].rstrip(b"\r\n").decode("utf-8", "replace")

            if not file_bytes:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No file uploaded"}).encode("utf-8"))
                return

            # Save temporary file for extractor
            suffix = os.path.splitext(filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                raw_text, status = extract_text_from_file(tmp_path)
            except Exception as e:
                raw_text = ""
                status = f"ERROR: {str(e)}"
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

            if not raw_text:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"extraction_status": status, "fields": {}, "fit_report": None}).encode("utf-8"))
                return

            sections, found, missing = segment_sections(raw_text)
            fields = parse_all_fields(sections, raw_text)
            fit_report = score_candidate(fields, raw_text, jd_text) if jd_text.strip() else None

            profile = CandidateProfile(
                source_file=filename,
                extraction_status=status,
                raw_character_count=len(raw_text),
                sections_found=found,
                sections_missing=missing,
                fields=fields,
                fit_report=fit_report
            )

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(profile.to_dict()).encode("utf-8"))
            return


# Ensure Windows terminal compatibility for UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_server(open_browser: bool = True):
    url = f"http://127.0.0.1:{PORT}"
    print("=" * 65)
    print(" [RESUME PARSER AGENT] Web Demo Server")
    print("=" * 65)
    print(f" * Listening on: {url}")
    print(" * Press Ctrl+C to stop the server.")
    print("=" * 65)
    
    if open_browser:
        try:
            webbrowser.open(url)
            print(f"[+] Successfully opened {url} in your default browser.")
        except Exception as e:
            print(f"[!] Could not auto-launch browser: {e}")

    with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[+] Server stopped.")


if __name__ == "__main__":
    should_open = "--no-browser" not in sys.argv
    run_server(open_browser=should_open)
