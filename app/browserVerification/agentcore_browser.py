"""Playwright setup required by AgentCore Runtime CodeZip."""

import logging
import os
from pathlib import Path
import shutil
import stat

import playwright


_PLAYWRIGHT_NODE_PATH = Path("/tmp/playwright-driver-node")


def prepare_playwright(log: logging.Logger) -> None:
    """Copy Playwright's Node driver to writable storage for CodeZip."""
    packaged_node = Path(playwright.__file__).resolve().parent / "driver" / "node"
    if not packaged_node.is_file():
        raise RuntimeError("Playwright's packaged Node executable was not found")

    if not _PLAYWRIGHT_NODE_PATH.is_file() or (
        _PLAYWRIGHT_NODE_PATH.stat().st_size != packaged_node.stat().st_size
    ):
        shutil.copyfile(packaged_node, _PLAYWRIGHT_NODE_PATH)

    mode = _PLAYWRIGHT_NODE_PATH.stat().st_mode
    _PLAYWRIGHT_NODE_PATH.chmod(mode | stat.S_IXUSR)
    os.environ["PLAYWRIGHT_NODEJS_PATH"] = str(_PLAYWRIGHT_NODE_PATH)
    log.info("Playwright driver is ready")
