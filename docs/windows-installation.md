# Windows setup and launch

VEUS 3.0.0rc1 uses Python **3.12**, runs directly on Windows and serves a browser UI.
These commands reflect the actual `veus.studio.main:app` package and dependency files.
**They have not been tested on a clean Windows machine.** Linux verification is recorded
in [release evidence](veus3/evidence/README.md). No WSL or Docker is required.

## Fresh PowerShell setup

Install Git and Python 3.12 using an approved method on your PC. University-managed PCs
may already provide Python through Anaconda; use that environment as described below.

```powershell
git clone --branch main https://github.com/AsherFerdinand/VEUS-ev-testbench.git
Set-Location VEUS-ev-testbench
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-report.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m uvicorn veus.studio.main:app --port 8770
```

Open http://localhost:8770 manually, or in a **second** PowerShell window:

```powershell
Start-Process 'http://localhost:8770'
```

The server command stays running; stop it with Ctrl+C. It binds to localhost by default.
No `Activate.ps1` is needed, so there is no need to change PowerShell execution policy.
The folder must contain `veus`, `requirements-report.txt` and `pyproject.toml`.

## Start again / update an existing Git checkout

Replace the example path with your actual folder. A ZIP download may have an extra nested
folder; use `Get-ChildItem` to find the one containing `veus`.

```powershell
Set-Location 'C:\path\to\VEUS-ev-testbench'
git status --short
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements-report.txt
.\.venv\Scripts\python.exe -m uvicorn veus.studio.main:app --port 8770
```

Keep local changes before switching/pulling; these commands do not discard them.
A ZIP download is not a Git checkout, so it cannot use `git pull`.

## If Anaconda provides Python

In **Anaconda Prompt**, first select an environment with Python 3.12. Confirm its version.
If your existing `(base)` environment is Python 3.11, use an approved Python 3.12 environment
rather than changing base in place. From the actual project directory:

```bat
python --version
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-report.txt
.venv\Scripts\python.exe -m uvicorn veus.studio.main:app --port 8770
```

Use `cd /d "Z:\Eigene Dateien\Masters\Coding\VEUS-ev-testbench-main"` if that is your
extracted folder. This is cmd/Anaconda syntax; PowerShell uses `Set-Location` instead.
Anaconda supplies Python; VS Code remains an optional editor.

A virtual environment is machine-specific. Recreate it when moving between university
PC and laptop; do not copy it or assume an old `%LOCALAPPDATA%\veus-venv` still exists.
On a restricted network drive, create it in an approved local directory and invoke that
Python executable while keeping the current directory at the project root.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m veus.testing physics --output reports/windows-review
```

Use a new output directory. `requirements.txt` is the server dependency set;
`requirements-report.txt` adds plotting; `requirements-dev.txt` adds test tools.
`requirements-lock.txt` records an existing resolved environment and is **not** a
verified Windows wheel lock. No dependency or Python-version upgrade is required by 3.0.

Optional Node checks:

```powershell
node --test tests/browser/replay-controller.test.cjs tests/browser/driving-scene-state.test.mjs
```

## Common startup problems

| Symptom                                | Check                                                                                           |
| -------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `py` / `python` not found              | Open the Anaconda Prompt where Python is available, or use the approved Python executable path. |
| Cannot find `.venv\Scripts\python.exe` | Create `.venv` on this PC; verify its directory with `Get-ChildItem .venv\Scripts`.             |
| `No module named veus`                 | Change to the project root containing `veus`, not the outer ZIP directory or `.venv` directory. |
| Missing FastAPI / plotting package     | Install using the same `.venv` Python used to launch the server.                                |
| Port 8770 already in use               | Stop the old VEUS process or use `--port 8771`, then browse that port.                          |
| Saved designs appear missing           | Use the same browser/origin/port, or import your exported design JSON.                          |

The server runs on the PC where you execute these commands. Cloud Codex editing and
GitHub pushes do not update an already downloaded local copy or automatically host it.
