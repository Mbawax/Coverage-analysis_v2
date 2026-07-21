# Settlement Coverage Analysis — Streamlit App

A Python/Streamlit rebuild of your KNIME workflow `Coverage_Analysis_v2.1`.

## What's in this folder
- `app.py` — the Streamlit app
- `requirements.txt` — the Python libraries it needs

## 1. Folder to save these files in
Create one project folder on your Desktop and keep both files together, e.g.:

```
Windows:  C:\Users\<you>\Desktop\Coverage-Analysis-App\
Mac:      /Users/<you>/Desktop/Coverage-Analysis-App/
```

Put `app.py` and `requirements.txt` directly inside that folder.

## 2. Install Python (one-time)
1. Go to https://www.python.org/downloads/ and install **Python 3.11 or later**.
2. On Windows, tick **"Add python.exe to PATH"** during install.
3. Confirm it worked — open a terminal (Command Prompt / PowerShell / Terminal) and run:
   ```
   python --version
   ```

## 3. Set up the workbench (virtual environment)
A virtual environment keeps this app's libraries separate from everything else on your machine.

Open a terminal, navigate into the project folder, then run:

```bash
cd Desktop/Coverage-Analysis-App

# create the virtual environment (one-time)
python -m venv venv

# activate it (every time you work on the app)
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

You'll know it's active because your terminal prompt will show `(venv)` at the start.

## 4. Install the libraries
With the virtual environment active:

```bash
pip install -r requirements.txt
```

This installs:
- **streamlit** — turns the Python script into a web app
- **pandas** — data processing (replaces KNIME's GroupBy/Pivot/Rule Engine nodes)
- **numpy** — numeric operations
- **openpyxl** — reads/writes `.xlsx` files (replaces KNIME's Excel Writer nodes)

## 5. Run the app
Still inside the activated virtual environment:

```bash
streamlit run app.py
```

Your browser will open automatically to something like `http://localhost:8501`.
Leave the terminal window open while you use the app — closing it stops the app.

## 6. Using the app
1. Upload your visitation CSV (the same kind of export KNIME's CSV Reader used).
2. Check the column mapping in the left sidebar — it auto-guesses `lga_name`,
   `ward_name`, `settlement_name`, `visitation`, `NUMPOINTS`, but you can change
   them if your column names differ.
3. Review the three tabs:
   - **Settlement-level (raw output)** — one row per settlement with % visitation and Coverage
   - **Coverage by LGA (pivot)** — count of settlements per Coverage bucket, by LGA, plus a chart
   - **Follow-up list** — settlements that are Not Visited or Low Coverage
4. Use the **Download** buttons to get `.xlsx` files, same as the KNIME Excel Writer nodes produced.

## Next time you want to run it
You only need steps 3 (activate) and 5 (run) again — no need to reinstall anything:
```bash
cd Desktop/Coverage-Analysis-App
venv\Scripts\activate      # or source venv/bin/activate on Mac
streamlit run app.py
```

## A note on the original KNIME file
While converting, I found the KNIME pivot branch (`GroupBy` → `Pivot` → `Missing
Value`) referenced columns (`lga`, `settlement`, `LGA`) that don't match the
CSV Reader's actual output (`lga_name`, `settlement_name`) — those nodes were
never fully configured/executed in the saved workflow. This app uses the
correct column names throughout, so the LGA-level pivot here actually works.
The `TimeSpent`/`number of mins` nodes were unrelated leftovers (mislabeled —
"number of mins" was really a sum of `NUMPOINTS`) and don't affect coverage,
so they're left out.
