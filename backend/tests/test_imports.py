import importlib


def test_services_package_imports():
    module = importlib.import_module("app.services")
    assert hasattr(module, "EmbeddingService")


def test_schemas_package_imports():
    module = importlib.import_module("app.schemas")
    assert hasattr(module, "LabResultIngest")
