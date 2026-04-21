"""Shared fixtures for the Ashby MCP test suite.

The server module initializes an `AshbyClient` at import time that reads
`ASHBY_API_KEY` from the environment. For unit tests we set a dummy key
here so the client constructs cleanly; `responses` intercepts the HTTP
calls before they leave the process.

Live tests (marked `live`) will pick up the real key from whatever is
already in the environment.
"""

import json
import os

import pytest

# Must be set before importing server, which reads ASHBY_API_KEY at module load.
os.environ.setdefault("ASHBY_API_KEY", "test-key-not-real")

from ashby import server as ashby_server  # noqa: E402


@pytest.fixture
def call_tool():
    """Async helper that invokes the MCP tool dispatcher and returns
    the parsed JSON body of its text response.

    The dispatcher wraps every response as `[TextContent(text="<prefix>: <json>")]`.
    We strip the prefix and return the decoded JSON so tests can assert on shape.
    """

    async def _call(name: str, arguments: dict | None = None) -> dict | str:
        result = await ashby_server.handle_call_tool(name, arguments or {})
        assert len(result) == 1
        text = result[0].text
        # Every handler uses the pattern "<prefix>: <json>"; split once.
        _, _, body = text.partition(": ")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            # Error branch returns plain text; surface it directly.
            return text

    return _call


@pytest.fixture
def ashby_client():
    """The module-level AshbyClient — re-used so tests can inspect it."""
    return ashby_server.ashby_client
