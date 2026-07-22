import io
import json

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
import pandas as pd

from analysis import guess_column, run_analysis, to_excel_bytes

app = FastAPI(title="Settlement Coverage Analysis")

FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="6" fill="#ff4b4b"/>'
    '<path d="M16 6l8 18h-4l-1.5-4h-5L12 24H8L16 6zm0 8.5L14.2 18h3.6L16 14.5z" fill="#fff"/>'
    "</svg>"
)


async def read_csv_upload(file: UploadFile) -> pd.DataFrame:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        return pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Could not read CSV: {exc}"
        ) from exc


def records_json_safe(df: pd.DataFrame, limit: int | None = None) -> list[dict]:
    subset = df.head(limit) if limit is not None else df
    return json.loads(subset.to_json(orient="records"))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(content=FAVICON_SVG, media_type="image/svg+xml")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return INDEX_HTML


@app.post("/api/preview")
async def preview(file: UploadFile = File(...)) -> dict:
    raw_df = await read_csv_upload(file)
    columns = raw_df.columns.tolist()
    return {
        "row_count": int(len(raw_df)),
        "column_count": int(len(raw_df.columns)),
        "columns": columns,
        "defaults": {
            "lga_col": guess_column(columns, ["lga_name", "grid_lga", "LGA"]),
            "ward_col": guess_column(columns, ["ward_name", "grid_ward", "Ward"]),
            "settlement_col": guess_column(
                columns, ["settlement_name", "grid_settlement", "Settlement"]
            ),
            "visitation_col": guess_column(columns, ["visitation", "visit_status"]),
            "points_col": guess_column(columns, ["NUMPOINTS", "building_count"]),
        },
        "preview": records_json_safe(raw_df, limit=50),
    }


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    lga_col: str = Form(...),
    ward_col: str = Form(...),
    settlement_col: str = Form(...),
    visitation_col: str = Form(...),
    points_col: str = Form(...),
    visited_label: str = Form("Visited"),
    not_visited_label: str = Form("Not Visited"),
) -> dict:
    raw_df = await read_csv_upload(file)
    try:
        return run_analysis(
            raw_df,
            lga_col=lga_col,
            ward_col=ward_col,
            settlement_col=settlement_col,
            visitation_col=visitation_col,
            points_col=points_col,
            visited_label=visited_label,
            not_visited_label=not_visited_label,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=400, detail=f"Column not found in CSV: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Analysis failed: {exc}"
        ) from exc


@app.post("/api/download")
async def download(
    records: str = Form(...),
    sheet_name: str = Form("Sheet1"),
    file_name: str = Form("export.xlsx"),
) -> Response:
    try:
        df = pd.DataFrame(json.loads(records))
        content = to_excel_bytes(df, sheet_name=sheet_name)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Download failed: {exc}"
        ) from exc

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Settlement Coverage Analysis</title>
  <link rel="icon" href="/favicon.ico" type="image/svg+xml" />
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #0f1419;
      --panel: #1a2332;
      --border: #2d3a4f;
      --text: #e7ecf3;
      --muted: #9aa8bc;
      --accent: #ff4b4b;
      --success: #21c354;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    .layout {
      display: grid;
      grid-template-columns: 280px 1fr;
      min-height: 100vh;
    }
    aside {
      background: var(--panel);
      border-right: 1px solid var(--border);
      padding: 1.25rem;
    }
    main { padding: 1.5rem 2rem; max-width: 1400px; }
    h1 { margin: 0 0 0.25rem; font-size: 1.75rem; }
    .caption { color: var(--muted); margin-bottom: 1.5rem; }
    label { display: block; font-size: 0.85rem; color: var(--muted); margin: 0.75rem 0 0.35rem; }
    select, input[type="text"], input[type="file"] {
      width: 100%;
      padding: 0.5rem 0.65rem;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: #111822;
      color: var(--text);
    }
    button {
      cursor: pointer;
      border: none;
      border-radius: 8px;
      padding: 0.6rem 1rem;
      background: var(--accent);
      color: white;
      font-weight: 600;
    }
    button.secondary { background: #334155; }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      margin-bottom: 1rem;
    }
    .kpis {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1rem;
      margin: 1rem 0 1.5rem;
    }
    .kpi .value { font-size: 1.5rem; font-weight: 700; }
    .kpi .label { color: var(--muted); font-size: 0.85rem; }
    .tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap; }
    .tab {
      background: #243044;
      color: var(--text);
      border: 1px solid var(--border);
    }
    .tab.active { background: var(--accent); border-color: var(--accent); }
    .hidden { display: none; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
    }
    th, td {
      border-bottom: 1px solid var(--border);
      padding: 0.45rem 0.6rem;
      text-align: left;
    }
    th { color: var(--muted); position: sticky; top: 0; background: var(--panel); }
    .table-wrap { max-height: 420px; overflow: auto; }
    .alert {
      background: #3d2a00;
      border: 1px solid #a16207;
      color: #fde68a;
      padding: 0.75rem 1rem;
      border-radius: 8px;
      margin-bottom: 1rem;
    }
    .success {
      background: #052e16;
      border: 1px solid #166534;
      color: #86efac;
    }
    .toolbar { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; margin-bottom: 1rem; }
    canvas { max-height: 360px; }
    @media (max-width: 900px) {
      .layout { grid-template-columns: 1fr; }
      .kpis { grid-template-columns: repeat(2, 1fr); }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <h2 style="margin-top:0;font-size:1.1rem;">Column mapping</h2>
      <p style="color:var(--muted);font-size:0.85rem;">Match your CSV columns to the analysis fields.</p>
      <label for="lga_col">LGA column</label>
      <select id="lga_col" disabled></select>
      <label for="ward_col">Ward column</label>
      <select id="ward_col" disabled></select>
      <label for="settlement_col">Settlement column</label>
      <select id="settlement_col" disabled></select>
      <label for="visitation_col">Visitation status column</label>
      <select id="visitation_col" disabled></select>
      <label for="points_col">Points / building count column</label>
      <select id="points_col" disabled></select>
      <label for="visited_label">Value meaning &quot;Visited&quot;</label>
      <input id="visited_label" type="text" value="Visited" />
      <label for="not_visited_label">Value meaning &quot;Not Visited&quot;</label>
      <input id="not_visited_label" type="text" value="Not Visited" />
      <div style="margin-top:1rem;">
        <button id="analyzeBtn" disabled>Run analysis</button>
      </div>
    </aside>

    <main>
      <h1>Settlement Coverage Analysis</h1>
      <p class="caption">Python rebuild of the KNIME workflow <strong>Coverage_Analysis_v2.1</strong> — deployed on Vercel</p>

      <div class="card">
        <label for="csvFile">Upload the settlement visitation CSV (QGIS export)</label>
        <input id="csvFile" type="file" accept=".csv" />
        <p id="uploadHint" style="color:var(--muted);margin:0.75rem 0 0;">Upload a CSV to get started.</p>
      </div>

      <div id="messages"></div>

      <details class="card">
        <summary>Preview raw data</summary>
        <div class="table-wrap" id="previewTable"></div>
      </details>

      <section id="results" class="hidden">
        <h2>Results</h2>
        <div class="kpis">
          <div class="card kpi"><div class="value" id="kpiSettlements">0</div><div class="label">Settlements analyzed</div></div>
          <div class="card kpi"><div class="value" id="kpiFully">0</div><div class="label">Fully Covered</div></div>
          <div class="card kpi"><div class="value" id="kpiNotVisited">0</div><div class="label">Not Visited</div></div>
          <div class="card kpi"><div class="value" id="kpiOverall">0%</div><div class="label">Overall % Visitation</div></div>
        </div>

        <div class="tabs">
          <button class="tab active" data-tab="tab1">Settlement-level</button>
          <button class="tab" data-tab="tab2">Coverage by LGA</button>
          <button class="tab" data-tab="tab3">Follow-up list</button>
        </div>

        <div id="tab1" class="panel card">
          <div class="toolbar">
            <h3 style="margin:0;">Settlement-level Coverage</h3>
            <button class="secondary" data-download="settlement">Download Excel</button>
          </div>
          <div class="table-wrap" id="tableSettlement"></div>
        </div>

        <div id="tab2" class="panel card hidden">
          <div class="toolbar">
            <h3 style="margin:0;">Coverage by LGA</h3>
            <button class="secondary" data-download="pivot">Download Excel</button>
          </div>
          <div class="table-wrap" id="tablePivot"></div>
          <canvas id="lgaChart"></canvas>
        </div>

        <div id="tab3" class="panel card hidden">
          <div class="toolbar">
            <h3 style="margin:0;">Settlements needing follow-up</h3>
            <button class="secondary" data-download="followup">Download Excel</button>
          </div>
          <div class="table-wrap" id="tableFollowup"></div>
        </div>
      </section>
    </main>
  </div>

  <script>
    let analysisData = null;
    let chartInstance = null;

    const fileInput = document.getElementById("csvFile");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const messages = document.getElementById("messages");
    const selectIds = ["lga_col", "ward_col", "settlement_col", "visitation_col", "points_col"];

    const API = "";

    async function readError(res) {
      const text = await res.text();
      try {
        const payload = JSON.parse(text);
        if (typeof payload.detail === "string") return payload.detail;
        if (Array.isArray(payload.detail)) {
          return payload.detail.map(d => d.msg || String(d)).join("; ");
        }
      } catch (_) {}
      return text.slice(0, 500) || `Request failed (${res.status})`;
    }

    function showMessage(text, type = "alert") {
      messages.innerHTML = `<div class="${type}">${text}</div>`;
    }

    function fillSelect(id, columns, selected) {
      const el = document.getElementById(id);
      el.innerHTML = columns.map(c => `<option value="${c}" ${c === selected ? "selected" : ""}>${c}</option>`).join("");
      el.disabled = false;
    }

    function renderTable(containerId, records) {
      const container = document.getElementById(containerId);
      if (!records.length) {
        container.innerHTML = "<p>No rows.</p>";
        return;
      }
      const cols = Object.keys(records[0]);
      const head = cols.map(c => `<th>${c}</th>`).join("");
      const body = records.map(row =>
        `<tr>${cols.map(c => `<td>${row[c] ?? ""}</td>`).join("")}</tr>`
      ).join("");
      container.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    }

    fileInput.addEventListener("change", async () => {
      analysisData = null;
      document.getElementById("results").classList.add("hidden");
      messages.innerHTML = "";
      const file = fileInput.files[0];
      if (!file) return;

      const form = new FormData();
      form.append("file", file);

      analyzeBtn.disabled = true;
      analyzeBtn.textContent = "Loading preview...";

      try {
        const res = await fetch(`${API}/api/preview`, { method: "POST", body: form });
        if (!res.ok) throw new Error(await readError(res));
        const data = await res.json();

        selectIds.forEach(id => fillSelect(id, data.columns, data.defaults[id]));
        renderTable("previewTable", data.preview);
        showMessage(`Loaded ${data.row_count.toLocaleString()} rows and ${data.column_count} columns.`, "success");
        document.getElementById("uploadHint").textContent = file.name;
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "Run analysis";
      } catch (err) {
        showMessage(`Preview failed: ${err.message}`);
      } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "Run analysis";
      }
    });

    analyzeBtn.addEventListener("click", async () => {
      const file = fileInput.files[0];
      if (!file) return;

      const form = new FormData();
      form.append("file", file);
      selectIds.forEach(id => form.append(id, document.getElementById(id).value));
      form.append("visited_label", document.getElementById("visited_label").value);
      form.append("not_visited_label", document.getElementById("not_visited_label").value);

      analyzeBtn.disabled = true;
      analyzeBtn.textContent = "Analyzing...";

      try {
        const res = await fetch(`${API}/api/analyze`, { method: "POST", body: form });
        if (!res.ok) throw new Error(await readError(res));
        analysisData = await res.json();

        messages.innerHTML = analysisData.warnings.map(w => `<div class="alert">${w}</div>`).join("");

        document.getElementById("kpiSettlements").textContent = analysisData.kpis.settlements.toLocaleString();
        document.getElementById("kpiFully").textContent = analysisData.kpis.fully_covered.toLocaleString();
        document.getElementById("kpiNotVisited").textContent = analysisData.kpis.not_visited.toLocaleString();
        document.getElementById("kpiOverall").textContent = `${analysisData.kpis.overall_pct}%`;

        renderTable("tableSettlement", analysisData.settlement_level);
        renderTable("tablePivot", analysisData.pivot);
        renderTable("tableFollowup", analysisData.followup);

        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(document.getElementById("lgaChart"), {
          type: "bar",
          data: {
            labels: analysisData.chart.labels,
            datasets: analysisData.chart.datasets
          },
          options: {
            responsive: true,
            plugins: { legend: { labels: { color: "#e7ecf3" } } },
            scales: {
              x: { stacked: true, ticks: { color: "#9aa8bc" }, grid: { color: "#2d3a4f" } },
              y: { stacked: true, ticks: { color: "#9aa8bc" }, grid: { color: "#2d3a4f" } }
            }
          }
        });

        document.getElementById("results").classList.remove("hidden");
      } catch (err) {
        showMessage(`Analysis failed: ${err.message}`);
      } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "Run analysis";
      }
    });

    document.querySelectorAll(".tab").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".panel").forEach(p => p.classList.add("hidden"));
        btn.classList.add("active");
        document.getElementById(btn.dataset.tab).classList.remove("hidden");
      });
    });

    document.querySelectorAll("[data-download]").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!analysisData) return;
        const key = btn.dataset.download;
        const map = {
          settlement: { records: analysisData.settlement_level, sheet: "Settlement_Level", file: "Settlement_level_RAW.xlsx" },
          pivot: { records: analysisData.pivot, sheet: "LGA_Level_Coverage", file: "LGA_Level_Coverage.xlsx" },
          followup: { records: analysisData.followup, sheet: "Missed_LowCovered", file: "Missed_Low_covered_Settlements.xlsx" }
        };
        const cfg = map[key];
        const form = new FormData();
        form.append("records", JSON.stringify(cfg.records));
        form.append("sheet_name", cfg.sheet);
        form.append("file_name", cfg.file);

        const res = await fetch(`${API}/api/download`, { method: "POST", body: form });
        if (!res.ok) throw new Error(await readError(res));
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = cfg.file;
        a.click();
        URL.revokeObjectURL(url);
      });
    });
  </script>
</body>
</html>
"""
