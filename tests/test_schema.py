import json
from pathlib import Path

from sales_ivr.models import export_json_schema


def test_export_json_schema(tmp_path: Path):
    paths = export_json_schema(tmp_path)
    assert "CallSession" in paths
    data = json.loads(paths["CallSession"].read_text(encoding="utf-8"))
    assert data["title"] == "CallSession"
