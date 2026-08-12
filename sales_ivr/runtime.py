"""Shared runtime resources (config, catalog, CRM) for IVR agents."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from sales_ivr.catalog.loader import load_catalog
from sales_ivr.config import AppConfig, InsuranceProduct, load_config, resolve_path
from sales_ivr.pricing.engine import load_objection_corpus


def package_root() -> Path:
    return Path(__file__).resolve().parent


def project_root() -> Path:
    return package_root().parent


def _load_dotenv() -> None:
    """Load sales-ivr/.env once so keys don't need PowerShell each session."""
    env_path = project_root() / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_dotenv()


def _discover_config_path() -> Path:
    env = os.environ.get("SALES_IVR_CONFIG_PATH")
    if env:
        return Path(env)
    candidates = [
        Path.cwd() / "config.yaml",
        project_root() / "config.yaml",
        project_root() / "config.example.yaml",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "No config.yaml found. Set SALES_IVR_CONFIG_PATH or run from sales-ivr/."
    )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config(_discover_config_path())


@lru_cache(maxsize=1)
def get_catalog() -> tuple[InsuranceProduct, ...]:
    config = get_config()
    catalog_dir = resolve_path(config, config.paths.catalog_dir, base=project_root())
    return tuple(load_catalog(catalog_dir))


@lru_cache(maxsize=1)
def get_crm() -> dict:
    config = get_config()
    crm_path = resolve_path(config, config.paths.crm_path, base=project_root())
    return json.loads(crm_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_objection_corpus() -> dict[str, str]:
    config = get_config()
    objections_dir = resolve_path(config, config.paths.objections_dir, base=project_root())
    return load_objection_corpus(objections_dir)


def get_compliance_dir() -> Path:
    config = get_config()
    return resolve_path(config, config.paths.compliance_dir, base=project_root())


def clear_resource_cache() -> None:
    get_config.cache_clear()
    get_catalog.cache_clear()
    get_crm.cache_clear()
    get_objection_corpus.cache_clear()
