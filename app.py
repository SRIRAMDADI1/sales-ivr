"""Azure App Service ASGI entry (zip root).

Oryx may run gunicorn with cwd under /tmp/<extract> or wwwroot.
Putting `app.py` next to `sales_ivr/` keeps the import path stable.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sales_ivr.web.app import app  # noqa: E402

__all__ = ["app"]
