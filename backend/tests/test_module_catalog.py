"""Tests for production and experimental module classification."""

from app.experimental.catalog import get_experimental_modules, get_production_modules


def test_module_catalog_has_no_duplicate_paths():
    modules = get_production_modules() + get_experimental_modules()
    paths = [module.path for module in modules]

    assert len(paths) == len(set(paths))


def test_catalog_marks_hybrid_pipeline_as_production():
    production = {module.module for module in get_production_modules()}

    assert "rag.hybrid_pipeline" in production
    assert "routing.router" in production


def test_catalog_marks_experimental_branches_explicitly():
    experimental = {module.module for module in get_experimental_modules()}

    assert "rag.ultimate_pipeline" in experimental
    assert "routing.hybrid_router" in experimental
