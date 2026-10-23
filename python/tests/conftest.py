"""Keep unit tests independent of live contract deployments and HTTP internals."""

from unittest.mock import Mock, patch

import aiohttp
import aioresponses.core
import pytest

from uagents.config import ALMANAC_CONTRACT_VERSION
from uagents.network import AlmanacContract


def _contract_state(_contract, query):
    assert query == {"query_contract_state": {}}, query
    return {"contract_version": ALMANAC_CONTRACT_VERSION}


def pytest_configure(config):
    # Agent instances are created during collection, before function fixtures.
    # A live testnet contract upgrade must not change the offline unit contract.
    config._contract_patch = patch.object(
        AlmanacContract, "query_contract", _contract_state
    )
    config._contract_patch.start()


def pytest_unconfigure(config):
    config._contract_patch.stop()


@pytest.fixture(autouse=True)
def aiohttp_response_compat(monkeypatch):
    # aioresponses 0.7.9 predates aiohttp 3.14's required stream_writer argument.
    # Preserve its real response implementation while supplying the absent writer.
    class MockClientResponse(aiohttp.ClientResponse):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault(
                "stream_writer",
                Mock(spec=aiohttp.abc.AbstractStreamWriter, output_size=0),
            )
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(aioresponses.core, "ClientResponse", MockClientResponse)
