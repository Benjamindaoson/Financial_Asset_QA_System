"""
HTML Report Generator.

Generates HTML evaluation reports from EvalReport.
"""
import os
from typing import Dict, Any
from trust_rag.eval.schema import EvalReport


def _get_p50_latency(report: EvalReport) -> float:
    """Get P50 latency from report."""
    for stage in report.online_query_metrics.stage_latencies:
        if stage.stage_name == "overall" or stage.stage_name == "retrieve":
            return stage.p50_ms
    return 0.0


def _get_p95_latency(report: EvalReport) -> float:
    """Get P95 latency from report."""
    for stage in report.online_query_metrics.stage_latencies:
        if stage.stage_name == "overall" or stage.stage_name == "retrieve":
            return stage.p95_ms
    return 0.0


def _get_p99_latency(report: EvalReport) -> float:
    """Get P99 latency from report."""
    for stage in report.online_query_metrics.stage_latencies:
        if stage.stage_name == "overall" or stage.stage_name == "retrieve":
            return stage.p99_ms
    return 0.0


def generate_html_report(report: EvalReport, output_path: str) -> str:
    """
    Generate HTML report from EvalReport.
    
    Args:
        report: EvalReport instance
        output_path: Output file path
        
    Returns:
        Path to generated HTML file
    """
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrustRAG Evaluation Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .meta {{
            color: #7f8c8d;
            font-size: 14px;
            margin-bottom: 30px;
        }}
        .scorecard {{
            background: {'#fee' if report.scorecard.status == 'FAIL' else '#efe' if report.scorecard.status == 'PASS' else '#ffeaa7'};
            border: 2px solid {'#c00' if report.scorecard.status == 'FAIL' else '#0c0' if report.scorecard.status == 'PASS' else '#f39c12'};
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }}
        .scorecard h2 {{
            margin-bottom: 15px;
            color: {'#c00' if report.scorecard.status == 'FAIL' else '#0c0' if report.scorecard.status == 'PASS' else '#f39c12'};
        }}
        .score {{
            font-size: 48px;
            font-weight: bold;
            color: #2c3e50;
        }}
        .status {{
            font-size: 24px;
            font-weight: bold;
            margin-top: 10px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            color: #34495e;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #3498db;
        }}
        .metric-label {{
            font-size: 12px;
            color: #7f8c8d;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #2c3e50;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .failures {{
            background: #fff5f5;
            border-left: 4px solid #e74c3c;
            padding: 15px;
            margin-top: 15px;
        }}
        .failure-item {{
            margin-bottom: 15px;
            padding: 10px;
            background: white;
            border-radius: 4px;
        }}
        .failure-query {{
            font-weight: 600;
            color: #c0392b;
            margin-bottom: 5px;
        }}
        .failure-reason {{
            color: #7f8c8d;
            font-size: 14px;
        }}
        .trace-id {{
            font-family: monospace;
            font-size: 12px;
            color: #95a5a6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>TrustRAG Evaluation Report</h1>
        <div class="meta">
            <strong>Run ID:</strong> {report.run_meta.run_id}<br>
            <strong>Timestamp:</strong> {report.run_meta.timestamp}<br>
            <strong>Commit:</strong> {report.run_meta.commit_hash}<br>
            <strong>Branch:</strong> {report.run_meta.branch}<br>
            <strong>Suite:</strong> {report.run_meta.suite}<br>
            <strong>Dataset:</strong> {report.run_meta.dataset}
        </div>
        
        <div class="scorecard">
            <h2>Scorecard</h2>
            <div class="score">{report.scorecard.overall_score:.1f}</div>
            <div class="status">Status: {report.scorecard.status}</div>
            {f'<p style="margin-top: 15px; color: #c00;"><strong>Failures:</strong><br>' + '<br>'.join(report.scorecard.failures) + '</p>' if report.scorecard.failures else ''}
            {f'<p style="margin-top: 15px; color: #f39c12;"><strong>Warnings:</strong><br>' + '<br>'.join(report.scorecard.warnings) + '</p>' if report.scorecard.warnings else ''}
        </div>
        
        <div class="section">
            <h2>Latency Metrics</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">P50 Latency</div>
                    <div class="metric-value">{_get_p50_latency(report):.0f}ms</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">P95 Latency</div>
                    <div class="metric-value">{_get_p95_latency(report):.0f}ms</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">P99 Latency</div>
                    <div class="metric-value">{_get_p99_latency(report):.0f}ms</div>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Stage</th>
                        <th>Count</th>
                        <th>Avg (ms)</th>
                        <th>P50 (ms)</th>
                        <th>P95 (ms)</th>
                        <th>P99 (ms)</th>
                    </tr>
                </thead>
                <tbody>
                    {_format_stage_latencies(report)}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>Accuracy Metrics</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Overall Accuracy</div>
                    <div class="metric-value">{report.online_query_metrics.accuracy.accuracy * 100:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Exact Match Rate</div>
                    <div class="metric-value">{report.online_query_metrics.accuracy.exact_match_rate * 100:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Numeric Error Rate</div>
                    <div class="metric-value">{report.online_query_metrics.accuracy.numeric_error_rate * 100:.1f}%</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Retrieval Metrics</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Recall@5</div>
                    <div class="metric-value">{report.online_query_metrics.retrieval.recall_at_5 * 100:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Recall@10</div>
                    <div class="metric-value">{report.online_query_metrics.retrieval.recall_at_10 * 100:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">MRR@10</div>
                    <div class="metric-value">{report.online_query_metrics.retrieval.mrr_at_10 * 100:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">NDCG@10</div>
                    <div class="metric-value">{report.online_query_metrics.retrieval.ndcg_at_10 * 100:.1f}%</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Trust & Safety Metrics</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Refusal Precision</div>
                    <div class="metric-value">{report.trust_metrics.refusal_precision * 100:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Refusal Recall</div>
                    <div class="metric-value">{report.trust_metrics.refusal_recall * 100:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Evidence Support Rate</div>
                    <div class="metric-value">{report.trust_metrics.evidence_support_rate * 100:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Verification Pass Rate</div>
                    <div class="metric-value">{report.trust_metrics.verification_pass_rate * 100:.1f}%</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Cost Metrics</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Total Tokens</div>
                    <div class="metric-value">{report.cost_metrics.total_tokens:,}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Token Cost (USD)</div>
                    <div class="metric-value">${report.cost_metrics.token_cost_usd:.4f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Cost per Query</div>
                    <div class="metric-value">${report.cost_metrics.cost_per_query_usd:.4f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Peak Memory</div>
                    <div class="metric-value">{report.cost_metrics.peak_mem_mb:.1f} MB</div>
                </div>
            </div>
        </div>
        
        {_format_robustness_section(report)}
        
        {_format_top_failures(report)}
    </div>
</body>
</html>
"""
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    return output_path


def _get_p50_latency(report: EvalReport) -> float:
    """Get P50 latency from report."""
    for stage in report.online_query_metrics.stage_latencies:
        if stage.stage_name == "overall" or stage.stage_name == "retrieve":
            return stage.p50_ms
    return 0.0


def _get_p95_latency(report: EvalReport) -> float:
    """Get P95 latency from report."""
    for stage in report.online_query_metrics.stage_latencies:
        if stage.stage_name == "overall" or stage.stage_name == "retrieve":
            return stage.p95_ms
    return 0.0


def _get_p99_latency(report: EvalReport) -> float:
    """Get P99 latency from report."""
    for stage in report.online_query_metrics.stage_latencies:
        if stage.stage_name == "overall" or stage.stage_name == "retrieve":
            return stage.p99_ms
    return 0.0


def _format_stage_latencies(report: EvalReport) -> str:
    """Format stage latencies as HTML table rows."""
    rows = []
    for stage in report.online_query_metrics.stage_latencies:
        rows.append(f"""
            <tr>
                <td><strong>{stage.stage_name}</strong></td>
                <td>{stage.count}</td>
                <td>{stage.avg_ms:.1f}</td>
                <td>{stage.p50_ms:.1f}</td>
                <td>{stage.p95_ms:.1f}</td>
                <td>{stage.p99_ms:.1f}</td>
            </tr>
        """)
    return "".join(rows) if rows else "<tr><td colspan='6'>No latency data</td></tr>"


def _format_robustness_section(report: EvalReport) -> str:
    """Format robustness metrics section."""
    if not report.robustness_metrics.total_extreme_tests:
        return ""
    
    return f"""
        <div class="section">
            <h2>Robustness Metrics</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Robustness Score</div>
                    <div class="metric-value">{report.robustness_metrics.robustness_score * 100:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Tests Passed</div>
                    <div class="metric-value">{report.robustness_metrics.passed_extreme_tests}/{report.robustness_metrics.total_extreme_tests}</div>
                </div>
            </div>
        </div>
    """


def _format_top_failures(report: EvalReport) -> str:
    """Format top failures section."""
    if not report.top_failures:
        return ""
    
    failure_items = []
    for failure in report.top_failures[:20]:
        failure_items.append(f"""
            <div class="failure-item">
                <div class="failure-query">{failure.get('query', 'Unknown')}</div>
                <div class="failure-reason">{failure.get('reason', 'No reason provided')}</div>
                <div class="trace-id">Trace ID: {failure.get('trace_id', 'N/A')}</div>
            </div>
        """)
    
    return f"""
        <div class="section">
            <h2>Top Failures (Top 20)</h2>
            <div class="failures">
                {''.join(failure_items)}
            </div>
        </div>
    """

