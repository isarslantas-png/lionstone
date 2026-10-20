import pytest

pytest.importorskip("mcp")


def test_mcp_server_builds():
    from lionstone.mcp_server import build
    app = build()
    assert app is not None
