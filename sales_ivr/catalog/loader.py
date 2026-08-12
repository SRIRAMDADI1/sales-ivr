from __future__ import annotations

from pathlib import Path

import yaml

from sales_ivr.config import InsuranceProduct, resolve_path
from sales_ivr.models.enums import ProductLine


def load_catalog(catalog_dir: Path) -> list[InsuranceProduct]:
    products: list[InsuranceProduct] = []
    for path in sorted(catalog_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        products.append(InsuranceProduct.model_validate(data))
    if not products:
        raise FileNotFoundError(f"No product YAML files found in {catalog_dir}")
    return products


def get_product(products: list[InsuranceProduct], product_id: str) -> InsuranceProduct | None:
    return next((p for p in products if p.product_id == product_id), None)


def filter_by_state(products: list[InsuranceProduct], state: str) -> list[InsuranceProduct]:
    upper = state.upper()
    return [p for p in products if upper in p.eligible_states]


def filter_by_line(
    products: list[InsuranceProduct], product_line: ProductLine
) -> list[InsuranceProduct]:
    return [p for p in products if p.product_line == product_line]


def load_catalog_from_config(config_path: Path, project_root: Path | None = None) -> list[InsuranceProduct]:
    from sales_ivr.config import load_config

    config = load_config(config_path)
    catalog_dir = resolve_path(config, config.paths.catalog_dir, base=project_root)
    return load_catalog(catalog_dir)
