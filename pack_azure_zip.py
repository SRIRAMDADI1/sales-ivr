"""Build a Linux-safe zip for Azure App Service zip-deploy.

Do NOT use PowerShell Compress-Archive for this. It stores entries with
backslashes (sales_ivr\\__init__.py). Linux unzip/Oryx then fails to create a
real sales_ivr/ package directory → ModuleNotFoundError: No module named 'sales_ivr'.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "harborline-deploy.zip"

# Paths relative to sales-ivr/ that Azure needs at the zip root.
INCLUDE_FILES = [
    "app.py",
    "startup.sh",
    "requirements.txt",
    "pyproject.toml",
    "config.yaml",
    "README.md",
]
INCLUDE_DIRS = [
    "sales_ivr",
]

SKIP_DIR_NAMES = {
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    "tests",
}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def should_skip(path: Path) -> bool:
    if path.name in SKIP_DIR_NAMES:
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    return False


def add_file(zf: zipfile.ZipFile, path: Path) -> None:
    arcname = path.relative_to(ROOT).as_posix()  # forward slashes for Linux
    zf.write(path, arcname)


def main() -> None:
    missing = [name for name in INCLUDE_FILES if not (ROOT / name).is_file()]
    missing += [name for name in INCLUDE_DIRS if not (ROOT / name).is_dir()]
    if missing:
        raise SystemExit(f"Missing required paths: {missing}")

    if OUT.exists():
        OUT.unlink()

    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in INCLUDE_FILES:
            add_file(zf, ROOT / name)
        for dirname in INCLUDE_DIRS:
            base = ROOT / dirname
            for path in base.rglob("*"):
                if path.is_dir():
                    if path.name in SKIP_DIR_NAMES:
                        # rglob still descends; skip files under these via should_skip on parts
                        continue
                    continue
                if any(part in SKIP_DIR_NAMES for part in path.parts):
                    continue
                if should_skip(path):
                    continue
                add_file(zf, path)

    # Sanity: require posix-style package entry
    with zipfile.ZipFile(OUT, "r") as zf:
        names = zf.namelist()
    if "sales_ivr/__init__.py" not in names:
        raise SystemExit(
            "Zip is invalid: missing sales_ivr/__init__.py (forward-slash entry). "
            f"Sample entries: {names[:10]}"
        )
    if "app.py" not in names or "startup.sh" not in names:
        raise SystemExit("Zip is invalid: missing app.py or startup.sh")

    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {len(names)} entries)")
    print("OK: sales_ivr/__init__.py present with forward slashes")


if __name__ == "__main__":
    main()
