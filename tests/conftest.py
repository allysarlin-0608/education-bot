"""The end-to-end suite (tests/e2e) is slow and starts servers: it only runs
when asked for by path (`pytest tests/e2e`), not with the unit tests."""


def pytest_ignore_collect(collection_path, config):
    if "e2e" in collection_path.parts and not any("e2e" in str(a) for a in config.args):
        return True
    return None
