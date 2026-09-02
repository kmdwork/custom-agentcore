"""Prepare Playwright for the AgentCore CodeZip environment."""
# AgentCore CodeZip環境でPlaywrightを動かすため、Playwright付属のNode.jsを実行可能な/tmpへコピーし、実行権限を付け、その場所を環境変数でPlaywrightへ知らせる起動前処理です。

import os
from pathlib import Path
import shutil
import playwright


def prepare_playwright(log) -> None:
    """Copy Playwright's Node executable to an executable temporary path."""
    # /var/task/playwright/driver/node を作る
    packaged_node = Path(playwright.__file__).resolve().parent / "driver" / "node"
    executable_node = Path("/tmp/playwright-driver-node")

    shutil.copyfile(packaged_node, executable_node)
    # 権限付与
    executable_node.chmod(0o755)
    # PLAYWRIGHT_NODEJS_PATHにパスを入れる
    os.environ["PLAYWRIGHT_NODEJS_PATH"] = str(executable_node)

    log.info("Using Playwright Node executable at %s", executable_node)
