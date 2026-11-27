# Installing T3

T3 needs Python 3.8 or newer and nothing else. It uses only the standard library.

## 1. Get the code

```
git clone https://github.com/MajaSwiderska/Team7Comp312.git
cd Team7Comp312
```

## 2. Install it

Using a virtual environment keeps T3 separate from other Python projects.

**Windows (PowerShell)**
```
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

**Windows (Git Bash) / macOS / Linux**
```
python -m venv .venv
source .venv/Scripts/activate    # Git Bash on Windows
source .venv/bin/activate        # macOS / Linux
python -m pip install -e .
```

`-e` means "editable": changes you make to `t3.py` take effect immediately, with no need to reinstall.

## 3. Use it

```
t3 --help
t3 --add Website Design Build
t3 --start Website Design
t3 --stop Website Design
t3 --report all
```

While the virtual environment is active, the `t3` command works from any folder.

If you prefer not to install, `python t3.py --help` still works from inside the project folder.

## Where your data is stored

All projects and tasks are kept in one SQLite file:

| System  | Location                         |
|---------|----------------------------------|
| Windows | `C:\Users\<you>\.t3\t3.db`       |
| macOS   | `/Users/<you>/.t3/t3.db`         |
| Linux   | `/home/<you>/.t3/t3.db`          |

The folder and tables are created automatically the first time you run T3. You no longer need to run `init_db.py` first, although it still works.

To use a different file (for example, a separate test database), set the `T3_DB` environment variable:

```
# PowerShell
$env:T3_DB = "C:\temp\test.db"
# Git Bash / macOS / Linux
export T3_DB=/tmp/test.db
```

`t3 --help` shows which data file is currently in use, at the bottom of its output.

## Uninstall

```
python -m pip uninstall t3-tracker
```

Your data in `~/.t3/` is not deleted by uninstalling.
