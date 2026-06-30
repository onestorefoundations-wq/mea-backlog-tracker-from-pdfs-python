# KTU Grade Card Extractor

A small desktop app (Python + Tkinter) that reads **APJ Abdul Kalam Technological University (KTU)** result PDFs and turns them into clean CSV files and reports.

It handles two kinds of PDFs, each in its own section of the UI:

- **Section A — Semester Grade Cards**: the individual per-student "Semester Grade Card" PDFs.
- **Section B — Course-wise Reports**: the per-semester "coursewiseReport" PDFs that list every student in a grid.

---

## Features

**Section A (per-student grade cards)**

- Extract all PDFs (including sub-folders) into `student_grades.csv`.
- Per-semester report: total students, First Chance Yes / First Chance No — click a count to see the register numbers and names.
- Cumulative pass report: students who passed S1, then S1+S2, then S1+S2+S3 … split by all-first-chance vs not.
- Editable **First-Chance Schedule** (S1–S8): the exam month/year that counts as each semester's first attempt.

**Section B (course-wise reports)**

- Extract all PDFs into `semester_pass_fail.csv` (register no, name, semester, no. of fails, no. of pass, failed subject codes).
- **Class filter** driven by `config.csv`.
- Pass/Fail report: per-semester totals (students, pass, fails, students with at least one fail).
- Fail distribution: students bucketed by total fails across all semesters (0, exactly 1–5, 6–10, more than 10) — click a bucket to list the students.

Every name-list popup has a **Copy to clipboard** button (tab-separated, ready for Excel).

---

## Folder layout

```
2023 CSE/
├─ scraper.py                  # the application
├─ requirements.txt
├─ runs.bat                    # Windows launcher (auto-installs Python if missing)
├─ run.sh                      # Linux/macOS launcher
├─ config.csv                  # registerno,class_name  (your class assignments)
├─ first_chance_map.csv        # semester,month,year    (editable in the UI)
├─ pdfs/                       # Section A PDFs go here (any sub-folders)
├─ semester_detailed_pdfs/     # Section B PDFs go here
└─ sample_pdfs/                # example PDFs for a quick try
   ├─ section_a_grade_cards/
   └─ section_b_coursewise/
```

> **Privacy note:** `pdfs/`, `semester_detailed_pdfs/`, and the generated CSVs are git-ignored so real student data is never committed. Only the files in `sample_pdfs/` are tracked.

---

## Quick start

### Windows

1. Double-click **`runs.bat`**.
   - If Python isn't installed, it tries to install it via `winget` (Windows 10/11). After it installs, close the window and run `runs.bat` again.
   - If `winget` isn't available, install Python 3 from <https://www.python.org/downloads/> and tick **"Add Python to PATH"**, then run `runs.bat` again.
2. The launcher creates a virtual environment, installs requirements, and opens the app.

### Linux

```bash
chmod +x run.sh      # first time only
./run.sh
```

The script installs Python 3 and Tkinter via your package manager (`apt`, `dnf`, or `pacman`) if they're missing, sets up the virtual environment, and launches the app.

> Tkinter is required for the GUI. On Debian/Ubuntu it's `python3-tk`; on Fedora `python3-tkinter`; on Arch it's bundled with `tk`. `run.sh` handles this for you.

### macOS

```bash
chmod +x run.sh
./run.sh
```

Uses Homebrew (`brew install python python-tk`) if Python/Tkinter are missing.

### Manual run (any OS)

```bash
python -m venv env
# Windows:
env\Scripts\activate
# Linux/macOS:
source env/bin/activate

pip install -r requirements.txt
python scraper.py
```

---

## How to use

1. **Put your PDFs in place**
   - Section A grade cards → `pdfs/` (sub-folders are fine).
   - Section B course-wise reports → `semester_detailed_pdfs/`.
   - To try it out first, point the folder boxes at the `sample_pdfs/...` folders.

2. **Section A**
   - Click **1. Extract** → writes `student_grades.csv`.
   - Click **2. Report** or **3. Cumulative** to view results. Double-click any count to see student names.
   - Use **Edit First-Chance Schedule** to set/adjust the first-attempt exam month & year per semester.

3. **Section B**
   - Click **A. Extract** → writes `semester_pass_fail.csv`.
   - Pick a **Class** (or `(All)`), then **B. Pass/Fail** or **C. Fail Distribution**.

4. Click **? Help** in the app any time for an in-app version of these instructions.

---

## Configuration files

### `config.csv` — class assignments

```csv
registerno,class_name
MEA23CS049,cse2
MEA23CS050,cse2
...
```

Add a row per student. Any register number not listed shows up under `(unassigned)` in the class filter. Edit this file freely; the dropdown refreshes each time you open a report.

### `first_chance_map.csv` — first-chance schedule

```csv
semester,month,year
S1,december,2023
S2,may,2024
...
S7,,
S8,,
```

Best edited from the app (**Edit First-Chance Schedule**), but you can edit the CSV directly too. Leave S7/S8 blank until those exams happen.

---

## Grade rules (Section B)

| Category | Grades |
|----------|--------|
| **Pass** | O, A+, A, B+, B, C+, C, D, P, S, LP |
| **Fail** | F, FE, AB, W, R |

Blank cells are ignored. (`LP` = pass in a pass/fail course; `R` = result withheld/reappearance, counted as a fail.)

---

## Requirements

- Python 3.8+
- [`pdfplumber`](https://github.com/jsvine/pdfplumber) (installed from `requirements.txt`)
- Tkinter (ships with Python on Windows/macOS; install `python3-tk` on Linux)

---

## Troubleshooting

- **"No CSV found. Run extraction first."** — Click the section's Extract button before viewing a report.
- **A PDF shows `[no records]` in the log** — its layout wasn't recognized; the others still process. Send the file if you need it supported.
- **Unrecognized grade code warning** — a grade not in the pass/fail lists was found and skipped. Decide how to classify it and update the lists in `scraper.py`.
- **GUI won't start on Linux** — install Tkinter: `sudo apt install python3-tk`.
