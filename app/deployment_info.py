"""本番のデプロイ識別子（Render 等の環境変数から取得）。"""

from __future__ import annotations

import os


def deployment_revision() -> dict[str, str]:
    """
    Render: https://render.com/docs/environment-variables
    RENDER_GIT_COMMIT がランタイムに入る。
    """
    commit = (
        os.environ.get("RENDER_GIT_COMMIT")
        or os.environ.get("GIT_COMMIT")
        or os.environ.get("SOURCE_VERSION")
        or ""
    ).strip()
    short = commit[:7] if len(commit) >= 7 else (commit or "unknown")
    return {
        "git_commit": commit or "unknown",
        "git_commit_short": short,
    }
