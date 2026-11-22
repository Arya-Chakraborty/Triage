from triage.agent.tools.base import Tool, ToolContext, ToolResult
from triage.agent.tools.escalate import EscalateTool
from triage.agent.tools.git_commit import GitCommitTool
from triage.agent.tools.git_diff import GitDiffTool
from triage.agent.tools.git_status import GitStatusTool
from triage.agent.tools.grep import GrepTool
from triage.agent.tools.http_get import HttpGetTool
from triage.agent.tools.list_dir import ListDirTool
from triage.agent.tools.query_store import QueryStoreTool
from triage.agent.tools.read_file import ReadFileTool
from triage.agent.tools.restart_asset import RestartAssetTool
from triage.agent.tools.run_shell import RunShellTool
from triage.agent.tools.write_file import WriteFileTool


def default_tools() -> list[Tool]:
    return [
        ReadFileTool(),
        ListDirTool(),
        GrepTool(),
        WriteFileTool(),
        RunShellTool(),
        GitStatusTool(),
        GitDiffTool(),
        GitCommitTool(),
        RestartAssetTool(),
        HttpGetTool(),
        QueryStoreTool(),
        EscalateTool(),
    ]


__all__ = ["Tool", "ToolContext", "ToolResult", "default_tools"]
