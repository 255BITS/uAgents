"""Exercise the existing stream handler without funding wallets or calling APIs."""

import ast
import importlib.util
import io
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
import datetime


ROOT = Path(__file__).resolve().parents[1]


def load_handler(response):
    # Importing the complete demo funds a testnet wallet. Extract only the actual
    # handler AST so these tests cannot register agents, fund wallets or run them.
    source = ROOT / "src/agents/stable_diffusion_agent.py"
    tree = ast.parse(source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                    and node.name == "get_image")
    spec = importlib.util.spec_from_file_location("image_messages", ROOT / "src/messages/basic.py")
    messages = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(messages)
    post = Mock(return_value=response)
    namespace = dict(Context=object, os=os, datetime=datetime, shutil=shutil,
                     requests=SimpleNamespace(post=post), SDResponse=messages.SDResponse,
                     Error=messages.Error, HEADERS={}, STABLE_DIFFUSION_URL="https://example.com/image")
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["get_image"], post


class ImageStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_success_streams_identical_bytes_without_a_decoder(self):
        payload = b"opaque image bytes; no image decoder is invoked"
        handler, post = load_handler(SimpleNamespace(status_code=200, raw=io.BytesIO(payload)))
        context = SimpleNamespace(send=AsyncMock())
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                Path("generated-image").mkdir()
                await handler(context, "test-recipient", "offline test image")
                files = list(Path("generated-image").iterdir())
                self.assertEqual(len(files), 1)
                self.assertEqual(files[0].read_bytes(), payload)
            finally:
                os.chdir(previous)
        self.assertEqual(post.call_args.kwargs["json"], {"inputs": "offline test image"})
        context.send.assert_awaited_once()
        self.assertIn("file saved", context.send.call_args.args[1].image_data)

    async def test_provider_error_returns_error_without_writing(self):
        handler, _ = load_handler(SimpleNamespace(status_code=404, content=b"not found"))
        context = SimpleNamespace(send=AsyncMock())
        await handler(context, "test-recipient", "offline test image")
        context.send.assert_awaited_once()
        self.assertIn("not found", context.send.call_args.args[1].error)


if __name__ == "__main__":
    unittest.main()
