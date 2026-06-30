# Pushing this project to GitHub

Everything is ready to commit — a `.gitignore` (excluding real student data) and sample PDFs are in place. Git couldn't be finalized from the build environment, so run these steps on your own machine, where git works natively.

## Easiest way (Windows)

1. Install Git for Windows if you don't have it: <https://git-scm.com/download/win>
2. Double-click **`git_setup.bat`**. It removes any half-made repo, then runs `git init`, `git add`, and the first commit for you.
3. Create a new **empty** repository on <https://github.com/new> (do **not** add a README or .gitignore there).
4. In a terminal opened in this folder, run (replace the URL with yours):

   ```bash
   git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
   git push -u origin main
   ```

## Manual way (any OS)

```bash
# from inside the "2023 CSE" folder
rm -rf .git                 # remove any half-created repo (Windows: rmdir /s /q .git)
git init -b main
git add -A
git commit -m "Initial commit: KTU Grade Card Extractor"

# then, after creating an empty repo on GitHub:
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

## What gets committed

Tracked: `scraper.py`, `requirements.txt`, `runs.bat`, `run.sh`, `README.md`, `.gitignore`, and `sample_pdfs/` (one example PDF per section).

**Ignored** (kept private by `.gitignore`): `pdfs/`, `semester_detailed_pdfs/`, `student_grades.csv`, `semester_pass_fail.csv`, `config.csv`, `first_chance_map.csv`, and the `env/` virtual environment.

> Want your real config/CSVs in the repo too? Remove the matching lines from `.gitignore` before committing. Only do this for repos that should contain student data.
