"""Report generator — export scan results as HTML, JSON, or Markdown."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from dbug.orchestrator.state import PipelineState

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate beautiful reports from scan results."""

    def generate_json(self, state: PipelineState, output: str = "dbug_report.json") -> str:
        data = {
            "generated_at": datetime.now().isoformat(),
            "version": "0.1.0",
            "scan": {
                "target": state.target_path,
                "files": state.total_files,
                "chunks": state.total_chunks,
                "languages": state.languages,
            },
            "results": {
                "bugs_found": state.bugs_found,
                "bugs_fixed": state.bugs_fixed,
                "status": state.stage.value,
            },
            "bugs": [b.model_dump() for b in state.bugs],
            "errors": state.errors,
        }
        Path(output).write_text(json.dumps(data, indent=2, default=str))
        logger.info(f"📄 JSON report: {output}")
        return output

    def generate_markdown(self, state: PipelineState, output: str = "dbug_report.md") -> str:
        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        lines = [
            f"# 🐛 D-BUG Scan Report",
            f"",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Target:** `{state.target_path}`",
            f"",
            f"## Summary",
            f"",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Files Scanned | {state.total_files} |",
            f"| Code Chunks | {state.total_chunks} |",
            f"| Languages | {', '.join(state.languages)} |",
            f"| Bugs Found | {state.bugs_found} |",
            f"| Auto-Fixed | {state.bugs_fixed} |",
            f"",
            f"## Bugs",
            f"",
        ]

        for i, bug in enumerate(state.bugs, 1):
            emoji = severity_emoji.get(bug.severity, "⚪")
            lines.extend([
                f"### {i}. {emoji} [{bug.severity.upper()}] {bug.title}",
                f"",
                f"- **File:** `{bug.file_path}`",
                f"- **Lines:** {bug.start_line}-{bug.end_line}",
                f"- **Category:** {bug.category}",
                f"- **Confidence:** {bug.confidence:.0%}",
                f"- **Auto-fixed:** {'✅ Yes' if bug.fix_validated else '❌ No'}",
                f"",
            ])
            if bug.root_cause:
                lines.extend([f"**Root Cause:** {bug.root_cause}", f""])
            if bug.fix_diff:
                lines.extend([f"**Fix:**", f"```diff", bug.fix_diff, f"```", f""])

        Path(output).write_text("\n".join(lines))
        logger.info(f"📄 Markdown report: {output}")
        return output

    def generate_html(self, state: PipelineState, output: str = "dbug_report.html") -> str:
        severity_colors = {"critical": "#ff4444", "high": "#ff8800", "medium": "#ffcc00", "low": "#44bb44"}

        bugs_html = ""
        for bug in state.bugs:
            color = severity_colors.get(bug.severity, "#888")
            fixed = "✅" if bug.fix_validated else "❌"
            bugs_html += f"""
            <div class="bug" style="border-left: 4px solid {color}">
                <div class="bug-header">
                    <span class="severity" style="background:{color}">{bug.severity.upper()}</span>
                    <span class="title">{bug.title[:80]}</span>
                    <span class="fixed">{fixed}</span>
                </div>
                <div class="bug-meta">
                    📁 {Path(bug.file_path).name} &nbsp;|&nbsp; Lines {bug.start_line}-{bug.end_line} &nbsp;|&nbsp; {bug.category}
                </div>
                {"<div class='root-cause'>" + bug.root_cause + "</div>" if bug.root_cause else ""}
                {"<pre class='diff'>" + bug.fix_diff + "</pre>" if bug.fix_diff else ""}
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>D-BUG Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', -apple-system, sans-serif; background: #0a0a0f; color: #e0e0e0; padding: 40px; }}
.container {{ max-width: 900px; margin: 0 auto; }}
h1 {{ font-size: 2rem; margin-bottom: 8px; background: linear-gradient(135deg, #00d4ff, #7b2ff7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
.subtitle {{ color: #888; margin-bottom: 30px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; margin-bottom: 40px; }}
.stat {{ background: #1a1a2e; border-radius: 12px; padding: 20px; text-align: center; }}
.stat-value {{ font-size: 2rem; font-weight: 700; color: #00d4ff; }}
.stat-label {{ color: #888; font-size: 0.85rem; margin-top: 4px; }}
.bug {{ background: #1a1a2e; border-radius: 12px; padding: 20px; margin-bottom: 16px; }}
.bug-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
.severity {{ color: white; padding: 2px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; }}
.title {{ font-weight: 600; flex: 1; }}
.fixed {{ font-size: 1.2rem; }}
.bug-meta {{ color: #888; font-size: 0.85rem; margin-bottom: 8px; }}
.root-cause {{ color: #ccc; font-size: 0.9rem; margin-top: 8px; padding: 12px; background: #12121e; border-radius: 8px; }}
.diff {{ background: #12121e; padding: 12px; border-radius: 8px; font-size: 0.8rem; overflow-x: auto; margin-top: 8px; color: #aaa; }}
</style></head><body><div class="container">
<h1>🐛 D-BUG Scan Report</h1>
<p class="subtitle">{datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; {state.target_path}</p>
<div class="stats">
    <div class="stat"><div class="stat-value">{state.total_files}</div><div class="stat-label">Files</div></div>
    <div class="stat"><div class="stat-value">{state.total_chunks}</div><div class="stat-label">Functions</div></div>
    <div class="stat"><div class="stat-value">{state.bugs_found}</div><div class="stat-label">Bugs Found</div></div>
    <div class="stat"><div class="stat-value">{state.bugs_fixed}</div><div class="stat-label">Auto-Fixed</div></div>
</div>
<h2 style="margin-bottom:16px;">Bugs</h2>
{bugs_html}
</div></body></html>"""

        Path(output).write_text(html)
        logger.info(f"📄 HTML report: {output}")
        return output
