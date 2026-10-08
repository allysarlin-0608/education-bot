"""GNOSIS backend: the API, authentication, data access and AI orchestration
the product runs on (docs/ARCHITECTURE_ASSESSMENT.md, docs/adr/).

Layers (imports only go down; tests/test_layers.py holds it):

    api        HTTP routes and request/response schemas
    services   application services (one per use case area)
    domain     the learning rules: the shared package `coach` (pure modules)
    data       PostgreSQL schema and repositories
    migrate    one-off importers from the systems we are leaving
    infra      configuration, logging, health
"""
__version__ = "0.1.0"
