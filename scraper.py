import os
import re
import csv
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from collections import defaultdict

import pdfplumber

# ===========================================================================
# Configuration
# ===========================================================================
TARGET_DIRECTORY = "./pdfs"
OUTPUT_CSV = "student_grades.csv"

DETAIL_DIRECTORY = "./semester_detailed_pdfs"
DETAIL_CSV = "semester_pass_fail.csv"
CONFIG_CSV = "config.csv"          # registerno,class_name
UNASSIGNED = "(unassigned)"
FIRST_CHANCE_CSV = "first_chance_map.csv"   # semester,month,year

# Default "first chance" exam schedule: the expected month+year a student
# would sit each semester's exam on their FIRST attempt. Section A uses this
# to mark whether a grade was earned in the first chance.
DEFAULT_FIRST_CHANCE_MAP = {
    "S1": ("december", "2023"),
    "S2": ("may", "2024"),
    "S3": ("november", "2024"),
    "S4": ("april", "2025"),
    "S5": ("november", "2025"),
    "S6": ("april", "2026"),
    "S7": ("", ""),
    "S8": ("", ""),
}

SEM_LIST_8 = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]


def load_first_chance_map(path=FIRST_CHANCE_CSV):
    """Load first-chance schedule from CSV, falling back to defaults."""
    fcmap = dict(DEFAULT_FIRST_CHANCE_MAP)
    if os.path.exists(path):
        try:
            with open(path, newline='', encoding='utf-8') as f:
                for r in csv.DictReader(f):
                    sem = (r.get("semester") or "").strip().upper()
                    if sem:
                        fcmap[sem] = ((r.get("month") or "").strip().lower(),
                                      (r.get("year") or "").strip())
        except Exception:
            pass
    return fcmap


def save_first_chance_map(fcmap, path=FIRST_CHANCE_CSV):
    with open(path, "w", newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["semester", "month", "year"])
        for sem in SEM_LIST_8:
            month, year = fcmap.get(sem, ("", ""))
            w.writerow([sem, month, year])


FIRST_CHANCE_MAP = load_first_chance_map()

GRADE_RE = re.compile(r'^(O|A\+|A|B\+|B|C|D|P|F|FE|S|I|W|AB|U)$', re.IGNORECASE)
CODE_RE = re.compile(r'^[A-Z]{2,4}\d{3}[A-Z]?$')
DATE_RE = re.compile(
    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
    re.IGNORECASE,
)

HEADERS = [
    "Register Number", "Student Name", "Semester",
    "Subject Code", "Grade", "Month of Examination",
    "Year of Examination", "First Chance",
]

DETAIL_HEADERS = [
    "Register Number", "Student Name", "Semester",
    "Number of Fails", "Number of Pass", "Failed Subject Codes",
]

# Fail: F, FE, AB, W, R  |  Pass: O,A+,A,B+,B,C+,C,D,P,S,LP
FAIL_GRADES = {"F", "FE", "AB", "W", "R"}
PASS_GRADES_DETAIL = {"O", "A+", "A", "B+", "B", "C+", "C", "D", "P", "S", "LP"}


def clean(cell):
    return str(cell).replace('\n', ' ').strip() if cell else ""


# ===========================================================================
# SECTION A -- Semester Grade Card extraction
# ===========================================================================
def determine_first_chance(semester, month, year):
    sem_key = semester.upper().strip()
    if sem_key in FIRST_CHANCE_MAP:
        exp_month, exp_year = FIRST_CHANCE_MAP[sem_key]
        if not exp_month or not exp_year:
            return "No"
        if month.lower().strip() == exp_month and str(year).strip() == exp_year:
            return "Yes"
    return "No"


def parse_metadata(table):
    meta = {"name": "Unknown", "reg": "Unknown", "sem": "Unknown"}
    for row in table:
        for i, cell in enumerate(row):
            label = clean(cell).lower()
            nxt = clean(row[i + 1]) if i + 1 < len(row) else ""
            if not nxt:
                continue
            if "name of candidate" in label:
                meta["name"] = nxt
            elif "register no" in label:
                meta["reg"] = nxt
            elif label == "semester":
                meta["sem"] = nxt
    return meta


def parse_grades(table, meta):
    records = []
    header = [clean(c).lower() for c in table[0]]
    col = {"code": None, "grade": None, "date": None}
    for idx, h in enumerate(header):
        if "code" in h:
            col["code"] = idx
        elif "grade" in h:
            col["grade"] = idx
        elif "month" in h or "examination" in h or "year" in h:
            col["date"] = idx

    for row in table[1:]:
        cells = [clean(c) for c in row]
        joined = " ".join(cells).lower()
        if not joined or "total credits" in joined or "sgpa" in joined:
            continue

        subject_code = grade = ""
        exam_month = exam_year = "Unknown"

        if col["code"] is not None and col["code"] < len(cells):
            if CODE_RE.match(cells[col["code"]]):
                subject_code = cells[col["code"]]
        if col["grade"] is not None and col["grade"] < len(cells):
            if GRADE_RE.match(cells[col["grade"]]):
                grade = cells[col["grade"]].upper()
        if col["date"] is not None and col["date"] < len(cells):
            m = DATE_RE.search(cells[col["date"]])
            if m:
                exam_month, exam_year = m.group(1).capitalize(), m.group(2)

        for c in cells:
            if not subject_code and CODE_RE.match(c):
                subject_code = c
            if not grade and GRADE_RE.match(c):
                grade = c.upper()
            if exam_month == "Unknown":
                m = DATE_RE.search(c)
                if m:
                    exam_month, exam_year = m.group(1).capitalize(), m.group(2)

        if subject_code and grade:
            records.append({
                "Register Number": meta["reg"],
                "Student Name": meta["name"],
                "Semester": meta["sem"],
                "Subject Code": subject_code,
                "Grade": grade,
                "Month of Examination": exam_month,
                "Year of Examination": exam_year,
                "First Chance": determine_first_chance(meta["sem"], exam_month, exam_year),
            })
    return records


def process_pdf_file(pdf_path):
    records = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue
                meta = {"name": "Unknown", "reg": "Unknown", "sem": "Unknown"}
                grade_tables = []
                for table in tables:
                    if not table or not table[0]:
                        continue
                    first_row = " ".join(clean(c) for c in table[0]).lower()
                    if "name of candidate" in first_row:
                        meta = parse_metadata(table)
                    elif "code" in first_row and "grade" in first_row:
                        grade_tables.append(table)
                for gt in grade_tables:
                    records.extend(parse_grades(gt, meta))
    except Exception as e:
        return [], f"Error parsing {pdf_path}: {e}"
    return records, None


def process_pdfs(root_folder, output_csv, log=print):
    total_files = total_records = no_record_files = 0
    with open(output_csv, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        for root, _, files in os.walk(root_folder):
            for file in files:
                if file.lower().endswith('.pdf'):
                    path = os.path.join(root, file)
                    total_files += 1
                    rows, err = process_pdf_file(path)
                    if err:
                        log(err)
                    if not rows:
                        no_record_files += 1
                        log(f"  [no records] {os.path.basename(path)}")
                    for row in rows:
                        writer.writerow(row)
                        total_records += 1
    summary = (f"Done. Processed {total_files} PDFs, found {total_records} records "
               f"({no_record_files} files with no records). Saved to '{output_csv}'.")
    log(summary)
    return total_files, total_records


# ===========================================================================
# SECTION B -- Course-wise extraction
# ===========================================================================
# Register numbers: MEA23CS049, AAE23CS022, lateral-entry LMEA23CS097
STUDENT_ID_RE = re.compile(r'([A-Z]{2,4}\d{2}[A-Z]{2}\d{3})[-\s]+(.*)', re.DOTALL)


def _codes_from_header(header_row):
    cols, codes = [], []
    for idx, cell in enumerate(header_row):
        if idx == 0:
            continue
        raw = (str(cell) if cell else "").replace('\n', '').replace(' ', '')
        if CODE_RE.match(raw):
            cols.append(idx)
            codes.append(raw)
    return cols, codes


def process_detail_pdf(pdf_path):
    records = []
    unknown_tokens = set()
    try:
        with pdfplumber.open(pdf_path) as pdf:
            semester = "Unknown"
            col_idx = codes = None
            for page in pdf.pages:
                txt = page.extract_text() or ""
                for line in txt.splitlines():
                    if line.strip().lower().startswith("semester :"):
                        semester = line.split(":", 1)[1].strip()
                        break
                for table in page.extract_tables():
                    if not table or len(table[0]) < 6:
                        continue
                    start = 0
                    if clean(table[0][0]).lower() == "student":
                        col_idx, codes = _codes_from_header(table[0])
                        start = 1
                    if not col_idx:
                        continue
                    for row in table[start:]:
                        sid = clean(row[0])
                        m = STUDENT_ID_RE.match(sid)
                        if not m:
                            continue
                        reg = m.group(1)
                        name = m.group(2).strip()
                        fails = passes = 0
                        failed_codes = []
                        for ci, code in zip(col_idx, codes):
                            if ci >= len(row):
                                continue
                            g = clean(row[ci]).upper()
                            if not g:
                                continue
                            if g in FAIL_GRADES:
                                fails += 1
                                failed_codes.append(code)
                            elif g in PASS_GRADES_DETAIL:
                                passes += 1
                            else:
                                unknown_tokens.add(g)
                        records.append({
                            "Register Number": reg,
                            "Student Name": name,
                            "Semester": semester,
                            "Number of Fails": fails,
                            "Number of Pass": passes,
                            "Failed Subject Codes": ";".join(failed_codes),
                        })
    except Exception as e:
        return [], f"Error parsing {pdf_path}: {e}", set()
    return records, None, unknown_tokens


def process_detail_pdfs(root_folder, output_csv, log=print):
    total_files = total_records = no_record_files = 0
    all_unknown = set()
    with open(output_csv, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=DETAIL_HEADERS)
        writer.writeheader()
        for root, _, files in os.walk(root_folder):
            for file in files:
                if file.lower().endswith('.pdf'):
                    path = os.path.join(root, file)
                    total_files += 1
                    rows, err, unknown = process_detail_pdf(path)
                    if err:
                        log(err)
                    if unknown:
                        all_unknown |= unknown
                    if not rows:
                        no_record_files += 1
                        log(f"  [no records] {os.path.basename(path)}")
                    for row in rows:
                        writer.writerow(row)
                        total_records += 1
    summary = (f"Done. Processed {total_files} PDFs, found {total_records} student rows "
               f"({no_record_files} files with no records). Saved to '{output_csv}'.")
    log(summary)
    if all_unknown:
        log(f"  WARNING: unrecognized grade codes (counted as neither pass nor fail): "
            f"{', '.join(sorted(all_unknown))}. Tell me how to classify them.")
    return total_files, total_records


def load_class_map(config_path=CONFIG_CSV):
    mapping = {}
    if not os.path.exists(config_path):
        return mapping
    with open(config_path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            reg = (r.get("registerno") or r.get("Register Number") or "").strip()
            cls = (r.get("class_name") or "").strip()
            if reg:
                mapping[reg] = cls or UNASSIGNED
    return mapping


def list_classes(config_path=CONFIG_CSV):
    return sorted({c for c in load_class_map(config_path).values() if c and c != UNASSIGNED})


def build_detail_report(csv_path, class_filter=None, config_path=CONFIG_CSV):
    if not os.path.exists(csv_path):
        return None
    class_map = load_class_map(config_path)
    sem = defaultdict(lambda: {"fails": 0, "passes": 0, "students": 0, "students_with_fail": 0})
    with open(csv_path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            s = r["Semester"].strip()
            if not s or s.lower() == "semester":
                continue
            reg = r["Register Number"].strip()
            cls = class_map.get(reg, UNASSIGNED)
            if class_filter and class_filter != "(All)" and cls != class_filter:
                continue
            d = sem[s]
            fails = int(r["Number of Fails"] or 0)
            d["fails"] += fails
            d["passes"] += int(r["Number of Pass"] or 0)
            d["students"] += 1
            if fails > 0:
                d["students_with_fail"] += 1
    return {s: sem[s] for s in sorted(sem)}


def build_fail_distribution(csv_path, class_filter=None, config_path=CONFIG_CSV):
    """Bucket students by total fails across ALL semesters combined."""
    if not os.path.exists(csv_path):
        return None
    class_map = load_class_map(config_path)
    totals = defaultdict(int)
    names = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            s = r["Semester"].strip()
            if not s or s.lower() == "semester":
                continue
            reg = r["Register Number"].strip()
            if not reg:
                continue
            cls = class_map.get(reg, UNASSIGNED)
            if class_filter and class_filter != "(All)" and cls != class_filter:
                continue
            names.setdefault(reg, r.get("Student Name", "").strip())
            totals[reg] += int(r["Number of Fails"] or 0)

    buckets = [
        ("All subjects passed (0 fails)", lambda n: n == 0),
        ("Failed exactly 1 subject", lambda n: n == 1),
        ("Failed exactly 2 subjects", lambda n: n == 2),
        ("Failed exactly 3 subjects", lambda n: n == 3),
        ("Failed exactly 4 subjects", lambda n: n == 4),
        ("Failed exactly 5 subjects", lambda n: n == 5),
        ("Failed 6-10 subjects", lambda n: 6 <= n <= 10),
        ("Failed more than 10 subjects", lambda n: n > 10),
    ]
    result = {"total_students": len(totals), "rows": []}
    for label, test in buckets:
        members = sorted((reg, names.get(reg, ""), totals[reg])
                         for reg in totals if test(totals[reg]))
        result["rows"].append({"label": label, "count": len(members), "students": members})
    return result


# ===========================================================================
# Section A reports
# ===========================================================================
def build_report(csv_path):
    if not os.path.exists(csv_path):
        return None
    sem_student = defaultdict(lambda: defaultdict(set))
    names = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            sem = r["Semester"].strip()
            reg = r["Register Number"].strip()
            if not sem or sem.lower() == "semester" or not reg:
                continue
            names.setdefault(reg, r.get("Student Name", "").strip())
            sem_student[sem][reg].add(r["First Chance"].strip())

    report = []
    for sem in sorted(sem_student):
        students = sem_student[sem]
        yes_list, no_list = [], []
        for reg in sorted(students):
            entry = (reg, names.get(reg, ""))
            if students[reg] == {"Yes"}:
                yes_list.append(entry)
            else:
                no_list.append(entry)
        report.append({
            "semester": sem, "total": len(students),
            "yes": len(yes_list), "no": len(no_list),
            "yes_students": yes_list, "no_students": no_list,
        })
    return report


PASS_GRADES = {"O", "A+", "A", "B+", "B", "C", "D", "P", "S"}
SEM_ORDER = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]


def build_cumulative_report(csv_path):
    if not os.path.exists(csv_path):
        return None
    sem_data = defaultdict(lambda: defaultdict(lambda: {"passed": True, "fc": True}))
    names = {}
    available = set()
    with open(csv_path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            sem = r["Semester"].strip().upper()
            reg = r["Register Number"].strip()
            grade = r["Grade"].strip().upper()
            fc = r["First Chance"].strip()
            if not sem or sem.lower() == "semester" or not reg:
                continue
            available.add(sem)
            names.setdefault(reg, r.get("Student Name", "").strip())
            rec = sem_data[sem][reg]
            if grade not in PASS_GRADES:
                rec["passed"] = False
            if fc != "Yes":
                rec["fc"] = False

    report = []
    for n in range(1, len(SEM_ORDER) + 1):
        span = SEM_ORDER[:n]
        label = "+".join(span)
        if any(s not in available for s in span):
            report.append({"label": label, "available": False})
            continue
        common = None
        for s in span:
            regs = set(sem_data[s].keys())
            common = regs if common is None else (common & regs)
        common = common or set()
        fc_students, not_fc_students = [], []
        for reg in sorted(common):
            if not all(sem_data[s][reg]["passed"] for s in span):
                continue
            entry = (reg, names.get(reg, ""))
            if all(sem_data[s][reg]["fc"] for s in span):
                fc_students.append(entry)
            else:
                not_fc_students.append(entry)
        report.append({
            "label": label, "available": True,
            "first_chance": len(fc_students),
            "not_first_chance": len(not_fc_students),
            "total_passed": len(fc_students) + len(not_fc_students),
            "fc_students": fc_students, "not_fc_students": not_fc_students,
        })
    return report


# ===========================================================================
# GUI
# ===========================================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KTU Grade Card Extractor")
        self.geometry("960x650")
        self.resizable(True, True)

        secA = ttk.LabelFrame(self, text="Section A  -  Semester Grade Cards (individual student PDFs)", padding=8)
        secA.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(secA, text="Folder:").pack(side="left")
        self.folder_var = tk.StringVar(value=TARGET_DIRECTORY)
        ttk.Entry(secA, textvariable=self.folder_var, width=14).pack(side="left", padx=5)
        self.extract_btn = ttk.Button(secA, text="1. Extract", command=self.run_extract)
        self.extract_btn.pack(side="left", padx=3)
        self.report_btn = ttk.Button(secA, text="2. Report", command=self.show_report)
        self.report_btn.pack(side="left", padx=3)
        self.cum_btn = ttk.Button(secA, text="3. Cumulative", command=self.show_cumulative_report)
        self.cum_btn.pack(side="left", padx=3)
        self.fcmap_btn = ttk.Button(secA, text="Edit First-Chance Schedule", command=self.edit_first_chance_map)
        self.fcmap_btn.pack(side="left", padx=3)
        self.help_btn = ttk.Button(secA, text="? Help", command=self.show_help)
        self.help_btn.pack(side="left", padx=3)

        secB = ttk.LabelFrame(self, text="Section B  -  Course-wise / Semester-detailed Reports", padding=8)
        secB.pack(fill="x", padx=10, pady=(4, 8))
        ttk.Label(secB, text="Folder:").pack(side="left")
        self.detail_folder_var = tk.StringVar(value=DETAIL_DIRECTORY)
        ttk.Entry(secB, textvariable=self.detail_folder_var, width=14).pack(side="left", padx=5)
        self.detail_extract_btn = ttk.Button(secB, text="A. Extract", command=self.run_detail_extract)
        self.detail_extract_btn.pack(side="left", padx=3)
        ttk.Label(secB, text="Class:").pack(side="left", padx=(8, 2))
        self.class_var = tk.StringVar(value="(All)")
        self.class_combo = ttk.Combobox(secB, textvariable=self.class_var, width=11,
                                        state="readonly", values=self._class_options())
        self.class_combo.pack(side="left", padx=2)
        self.detail_report_btn = ttk.Button(secB, text="B. Pass/Fail", command=self.show_detail_report)
        self.detail_report_btn.pack(side="left", padx=3)
        self.faildist_btn = ttk.Button(secB, text="C. Fail Distribution", command=self.show_fail_distribution)
        self.faildist_btn.pack(side="left", padx=3)

        self.status = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self.status, anchor="w", relief="sunken").pack(fill="x", side="bottom")

        self.output = scrolledtext.ScrolledText(self, wrap="word", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        # Report 2
        self.sem_frame = ttk.Frame(self)
        ttk.Label(self.sem_frame,
                  text="Tip: double-click the 'First Chance Yes' or 'First Chance No' count to see register numbers & names.").pack(anchor="w", padx=10, pady=(4, 2))
        self.sem_tree = ttk.Treeview(self.sem_frame, columns=("sem", "total", "yes", "no"), show="headings", height=12)
        for c, t, w in [("sem", "Semester", 150), ("total", "Total Students", 160),
                        ("yes", "First Chance Yes", 170), ("no", "First Chance No", 170)]:
            self.sem_tree.heading(c, text=t)
            self.sem_tree.column(c, width=w, anchor=("w" if c == "sem" else "center"))
        self.sem_tree.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        self.sem_tree.bind("<Double-1>", self.on_sem_click)
        self._sem_rows = {}

        # Report 3
        self.tree_frame = ttk.Frame(self)
        ttk.Label(self.tree_frame,
                  text="Tip: double-click the 'All FC' or 'Not FC' count in a row to see register numbers & names.").pack(anchor="w", padx=10, pady=(4, 2))
        self.tree = ttk.Treeview(self.tree_frame, columns=("span", "all_fc", "not_fc", "total"), show="headings", height=12)
        for c, t, w in [("span", "Span", 240), ("all_fc", "Passed (All FC)", 140),
                        ("not_fc", "Passed (Not FC)", 140), ("total", "Total Passed", 120)]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=("w" if c == "span" else "center"))
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        self.tree.bind("<Double-1>", self.on_tree_click)
        self._cum_rows = {}

        # Report B
        self.detail_frame = ttk.Frame(self)
        self.detail_title = ttk.Label(self.detail_frame, text="Pass/Fail totals per semester.")
        self.detail_title.pack(anchor="w", padx=10, pady=(4, 2))
        self.detail_tree = ttk.Treeview(self.detail_frame,
                                        columns=("sem", "students", "passes", "fails", "withfail"),
                                        show="headings", height=12)
        for c, t, w in [("sem", "Semester", 120), ("students", "Students", 110),
                        ("passes", "Total Pass", 130), ("fails", "Total Fails", 130),
                        ("withfail", "Students w/ Fail", 150)]:
            self.detail_tree.heading(c, text=t)
            self.detail_tree.column(c, width=w, anchor=("w" if c == "sem" else "center"))
        self.detail_tree.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        # Report C
        self.faildist_frame = ttk.Frame(self)
        self.faildist_title = ttk.Label(self.faildist_frame, text="Fail distribution.")
        self.faildist_title.pack(anchor="w", padx=10, pady=(4, 2))
        ttk.Label(self.faildist_frame,
                  text="Tip: double-click a category to see the students in it.").pack(anchor="w", padx=10, pady=(0, 2))
        self.faildist_tree = ttk.Treeview(self.faildist_frame, columns=("cat", "count"),
                                          show="headings", height=12)
        self.faildist_tree.heading("cat", text="Category (fails across all semesters)")
        self.faildist_tree.heading("count", text="No. of Students")
        self.faildist_tree.column("cat", width=340, anchor="w")
        self.faildist_tree.column("count", width=140, anchor="center")
        self.faildist_tree.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        self.faildist_tree.bind("<Double-1>", self.on_faildist_click)
        self._faildist_rows = {}

    # ----- view switching -----
    def log(self, msg):
        self.output.insert("end", msg + "\n")
        self.output.see("end")
        self.update_idletasks()

    def _hide_all(self):
        for w in (self.output, self.sem_frame, self.tree_frame,
                  self.detail_frame, self.faildist_frame):
            w.pack_forget()

    def _show_text(self):
        self._hide_all()
        self.output.pack(fill="both", expand=True, padx=10, pady=(0, 5))

    def _show(self, frame):
        self._hide_all()
        frame.pack(fill="both", expand=True)

    # ----- Section A actions -----
    def run_extract(self):
        folder = self.folder_var.get().strip() or TARGET_DIRECTORY
        if not os.path.isdir(folder):
            messagebox.showerror("Folder not found", f"'{folder}' does not exist.")
            return
        self._show_text()
        for b in (self.extract_btn, self.report_btn, self.cum_btn):
            b.config(state="disabled")
        self.output.delete("1.0", "end")
        self.status.set("Extracting (Section A)...")

        def worker():
            try:
                files, records = process_pdfs(folder, OUTPUT_CSV, log=self.log)
                self.status.set(f"Done: {records} records from {files} PDFs.")
                messagebox.showinfo("Extraction complete", f"{records} records from {files} PDFs.\nSaved to {OUTPUT_CSV}")
            except Exception as e:
                self.log(f"FAILED: {e}")
                self.status.set("Failed.")
                messagebox.showerror("Error", str(e))
            finally:
                for b in (self.extract_btn, self.report_btn, self.cum_btn):
                    b.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()

    def show_report(self):
        report = build_report(OUTPUT_CSV)
        if not report:
            self._show_text()
            self.output.delete("1.0", "end")
            self.log("No CSV found. Run Section A extraction first.")
            self.status.set("No CSV. Run extraction first.")
            return
        self._show(self.sem_frame)
        self.sem_tree.delete(*self.sem_tree.get_children())
        self._sem_rows.clear()
        t_total = t_yes = t_no = 0
        for d in report:
            iid = self.sem_tree.insert("", "end", values=(d["semester"], d["total"], d["yes"], d["no"]))
            self._sem_rows[iid] = d
            t_total += d["total"]; t_yes += d["yes"]; t_no += d["no"]
        tid = self.sem_tree.insert("", "end", values=("TOTAL", t_total, t_yes, t_no))
        self._sem_rows[tid] = None
        self.status.set("Double-click a Yes/No count to list students.")

    def on_sem_click(self, event):
        iid = self.sem_tree.identify_row(event.y)
        d = self._sem_rows.get(iid) if iid else None
        if not d:
            return
        col = self.sem_tree.identify_column(event.x)
        if col == "#3":
            self._popup_students(d["semester"], "First Chance Yes", d["yes_students"])
        elif col == "#4":
            self._popup_students(d["semester"], "First Chance No", d["no_students"])
        else:
            self._popup_students(d["semester"], "All students", d["yes_students"] + d["no_students"])

    def show_cumulative_report(self):
        report = build_cumulative_report(OUTPUT_CSV)
        if not report:
            self._show_text()
            self.output.delete("1.0", "end")
            self.log("No CSV found. Run Section A extraction first.")
            self.status.set("No CSV. Run extraction first.")
            return
        self._show(self.tree_frame)
        self.tree.delete(*self.tree.get_children())
        self._cum_rows.clear()
        for d in report:
            if not d["available"]:
                iid = self.tree.insert("", "end", values=(d["label"], "not available", "not available", "-"))
            else:
                iid = self.tree.insert("", "end", values=(d["label"], d["first_chance"], d["not_first_chance"], d["total_passed"]))
            self._cum_rows[iid] = d
        self.status.set("Double-click a count (All FC / Not FC) to list students.")

    def on_tree_click(self, event):
        iid = self.tree.identify_row(event.y)
        d = self._cum_rows.get(iid) if iid else None
        if not d or not d.get("available"):
            return
        col = self.tree.identify_column(event.x)
        if col == "#2":
            self._popup_students(d["label"], "Passed (All First Chance)", d["fc_students"])
        elif col == "#3":
            self._popup_students(d["label"], "Passed (Not First Chance)", d["not_fc_students"])
        else:
            self._popup_students(d["label"], "All who passed", d["fc_students"] + d["not_fc_students"])

    # ----- Section B actions -----
    def _class_options(self):
        return ["(All)"] + list_classes() + [UNASSIGNED]

    def run_detail_extract(self):
        folder = self.detail_folder_var.get().strip() or DETAIL_DIRECTORY
        if not os.path.isdir(folder):
            messagebox.showerror("Folder not found",
                                 f"'{folder}' does not exist.\nCreate it and add your course-wise PDFs.")
            return
        self._show_text()
        for b in (self.detail_extract_btn, self.detail_report_btn, self.faildist_btn):
            b.config(state="disabled")
        self.output.delete("1.0", "end")
        self.status.set("Extracting (Section B)...")

        def worker():
            try:
                files, records = process_detail_pdfs(folder, DETAIL_CSV, log=self.log)
                self.status.set(f"Done: {records} student rows from {files} PDFs.")
                messagebox.showinfo("Extraction complete", f"{records} student rows from {files} PDFs.\nSaved to {DETAIL_CSV}")
            except Exception as e:
                self.log(f"FAILED: {e}")
                self.status.set("Failed.")
                messagebox.showerror("Error", str(e))
            finally:
                for b in (self.detail_extract_btn, self.detail_report_btn, self.faildist_btn):
                    b.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()

    def show_detail_report(self):
        self.class_combo["values"] = self._class_options()
        cls = self.class_var.get()
        report = build_detail_report(DETAIL_CSV, class_filter=cls)
        if not report:
            self._show_text()
            self.output.delete("1.0", "end")
            self.log("No CSV found. Run Section B extraction first.")
            self.status.set("No CSV. Run Section B extraction first.")
            return
        self._show(self.detail_frame)
        label = "all classes" if cls == "(All)" else f"class '{cls}'"
        self.detail_title.config(text=f"Pass/Fail totals per semester  ({label}).")
        self.detail_tree.delete(*self.detail_tree.get_children())
        t_stu = t_pass = t_fail = t_wf = 0
        for sem, d in report.items():
            self.detail_tree.insert("", "end", values=(sem, d["students"], d["passes"], d["fails"], d["students_with_fail"]))
            t_stu += d["students"]; t_pass += d["passes"]; t_fail += d["fails"]; t_wf += d["students_with_fail"]
        self.detail_tree.insert("", "end", values=("TOTAL", t_stu, t_pass, t_fail, t_wf))
        self.status.set(f"Pass/Fail report shown ({label}).")

    def show_fail_distribution(self):
        self.class_combo["values"] = self._class_options()
        cls = self.class_var.get()
        report = build_fail_distribution(DETAIL_CSV, class_filter=cls)
        if not report:
            self._show_text()
            self.output.delete("1.0", "end")
            self.log("No CSV found. Run Section B extraction first.")
            self.status.set("No CSV. Run Section B extraction first.")
            return
        self._show(self.faildist_frame)
        label = "all classes" if cls == "(All)" else f"class '{cls}'"
        self.faildist_title.config(
            text=f"Fail distribution ({label})  -  Total students: {report['total_students']}")
        self.faildist_tree.delete(*self.faildist_tree.get_children())
        self._faildist_rows.clear()
        for row in report["rows"]:
            iid = self.faildist_tree.insert("", "end", values=(row["label"], row["count"]))
            self._faildist_rows[iid] = row
        tid = self.faildist_tree.insert("", "end", values=("TOTAL STUDENTS", report["total_students"]))
        self._faildist_rows[tid] = None
        self.status.set(f"Fail distribution shown ({label}). Double-click a category for names.")

    def on_faildist_click(self, event):
        iid = self.faildist_tree.identify_row(event.y)
        row = self._faildist_rows.get(iid) if iid else None
        if not row:
            return
        students = [(reg, f"{name}   [{tf} fail(s)]") for reg, name, tf in row["students"]]
        self._popup_students(row["label"], "students", students)

    # ----- Help -----
    def show_help(self):
        win = tk.Toplevel(self)
        win.title("How to use - KTU Grade Card Extractor")
        win.geometry("680x620")
        txt = scrolledtext.ScrolledText(win, wrap="word", font=("Segoe UI", 10))
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        guide = (
            "KTU GRADE CARD EXTRACTOR - QUICK GUIDE\n"
            "=======================================\n\n"
            "This tool reads KTU result PDFs and turns them into CSV files and reports.\n"
            "There are two independent sections.\n\n"
            "------------------------------------------------------------\n"
            "SECTION A - Semester Grade Cards (per-student PDFs)\n"
            "------------------------------------------------------------\n"
            "Use this for the individual 'Semester Grade Card' PDFs (one per student\n"
            "per semester). Put them inside the folder shown (default: ./pdfs), in any\n"
            "sub-folders you like.\n\n"
            "  1. Extract      - reads all PDFs and writes student_grades.csv\n"
            "                    (register no, name, semester, subject, grade, exam\n"
            "                     month/year, and First Chance Yes/No).\n"
            "  2. Report       - per-semester table: total students, First Chance Yes,\n"
            "                    First Chance No. Double-click a Yes/No count to see\n"
            "                    the register numbers + names behind it.\n"
            "  3. Cumulative   - students who passed S1, then S1+S2, then S1+S2+S3 ...\n"
            "                    split by all-first-chance vs not. Double-click a count\n"
            "                    for the name list. Missing semesters show 'not available'.\n\n"
            "  Edit First-Chance Schedule - set the exam Month+Year that counts as each\n"
            "                    semester's FIRST attempt (S1-S8). A grade is 'First\n"
            "                    Chance = Yes' only if earned in that exact sitting.\n\n"
            "------------------------------------------------------------\n"
            "SECTION B - Course-wise / Semester-detailed Reports\n"
            "------------------------------------------------------------\n"
            "Use this for the 'coursewiseReport' PDFs (one per semester, listing every\n"
            "student in a grid). Put them in the folder shown\n"
            "(default: ./semester_detailed_pdfs).\n\n"
            "  A. Extract      - reads all PDFs and writes semester_pass_fail.csv\n"
            "                    (register no, name, semester, no. of fails, no. of pass,\n"
            "                     failed subject codes).\n"
            "  Class (dropdown)- filter reports by class. Classes come from config.csv\n"
            "                    (format: registerno,class_name). '(All)' = everyone,\n"
            "                    '(unassigned)' = students with no class entry.\n"
            "  B. Pass/Fail    - per-semester totals: students, total pass, total fails,\n"
            "                    and number of students with at least one fail.\n"
            "  C. Fail Distribution - buckets students by total fails across ALL\n"
            "                    semesters: 0 (all passed), exactly 1-5, 6-10, >10.\n"
            "                    Double-click a bucket to list those students.\n\n"
            "GRADE RULES (Section B):\n"
            "  Pass  = O, A+, A, B+, B, C+, C, D, P, S, LP\n"
            "  Fail  = F, FE, AB, W, R     (blanks are ignored)\n\n"
            "TIP: every name-list popup has a 'Copy to clipboard' button (tab-separated,\n"
            "ready to paste into Excel).\n\n"
            "FILES CREATED:\n"
            "  student_grades.csv       (Section A)\n"
            "  semester_pass_fail.csv   (Section B)\n"
            "  config.csv               (your class assignments - editable)\n"
            "  first_chance_map.csv     (the first-chance schedule - editable in UI)\n"
        )
        txt.insert("1.0", guide)
        txt.config(state="disabled")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))

    # ----- First-Chance schedule editor -----
    def edit_first_chance_map(self):
        win = tk.Toplevel(self)
        win.title("Edit First-Chance Exam Schedule")
        win.geometry("560x560")

        explain = (
            "What is the First-Chance Schedule?\n\n"
            "For each semester, this is the exam sitting (Month + Year) that counts\n"
            "as a student's FIRST attempt. In Section A, a subject grade is marked\n"
            "'First Chance = Yes' only if it was earned in this exact month & year;\n"
            "any later sitting (a re-exam / supplementary) counts as 'No'.\n\n"
            "Leave S7 / S8 blank until those exams happen, then fill them in here.\n"
            "Changes are saved to 'first_chance_map.csv' and used on the next report."
        )
        ttk.Label(win, text=explain, justify="left", font=("Segoe UI", 9)).pack(
            anchor="w", padx=12, pady=(12, 8))

        grid = ttk.Frame(win)
        grid.pack(fill="x", padx=12)
        ttk.Label(grid, text="Semester", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Label(grid, text="Month", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, padx=6, pady=4)
        ttk.Label(grid, text="Year", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, padx=6, pady=4)

        months = ["", "January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        entries = {}
        for i, sem in enumerate(SEM_LIST_8, start=1):
            month, year = FIRST_CHANCE_MAP.get(sem, ("", ""))
            ttk.Label(grid, text=sem).grid(row=i, column=0, padx=6, pady=3, sticky="w")
            mvar = tk.StringVar(value=month.capitalize() if month else "")
            ttk.Combobox(grid, textvariable=mvar, values=months, width=16,
                         state="readonly").grid(row=i, column=1, padx=6, pady=3)
            yvar = tk.StringVar(value=year)
            ttk.Entry(grid, textvariable=yvar, width=10).grid(row=i, column=2, padx=6, pady=3)
            entries[sem] = (mvar, yvar)

        def save():
            newmap = {}
            for sem, (mvar, yvar) in entries.items():
                newmap[sem] = (mvar.get().strip().lower(), yvar.get().strip())
            FIRST_CHANCE_MAP.clear()
            FIRST_CHANCE_MAP.update(newmap)
            save_first_chance_map(FIRST_CHANCE_MAP)
            self.status.set("First-chance schedule saved. Re-run Section A Extract to apply.")
            win.destroy()

        def reset():
            for sem, (mvar, yvar) in entries.items():
                m, y = DEFAULT_FIRST_CHANCE_MAP.get(sem, ("", ""))
                mvar.set(m.capitalize() if m else "")
                yvar.set(y)

        btns = ttk.Frame(win)
        btns.pack(pady=14)
        ttk.Button(btns, text="Save", command=save).pack(side="left", padx=6)
        ttk.Button(btns, text="Reset to defaults", command=reset).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=6)

    # ----- shared popup -----
    def _popup_students(self, title_left, group, students):
        win = tk.Toplevel(self)
        win.title(f"{title_left} - {group}")
        win.geometry("500x470")
        ttk.Label(win, text=f"{title_left}  |  {group}  ({len(students)} students)",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=8)
        tv = ttk.Treeview(win, columns=("reg", "name"), show="headings")
        tv.heading("reg", text="Register Number")
        tv.heading("name", text="Student Name")
        tv.column("reg", width=150, anchor="w")
        tv.column("name", width=310, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        for reg, name in students:
            tv.insert("", "end", values=(reg, name))

        def copy_all():
            text = "\n".join(f"{r}\t{n}" for r, n in students)
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status.set("Copied list to clipboard.")

        ttk.Button(win, text="Copy to clipboard", command=copy_all).pack(pady=(0, 10))


if __name__ == "__main__":
    App().mainloop()
