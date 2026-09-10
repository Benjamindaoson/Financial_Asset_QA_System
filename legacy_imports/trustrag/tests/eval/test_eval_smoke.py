"""
Smoke test for evaluation framework.

Ensures evaluation can run and generate reports without external dependencies.
"""
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from trust_rag.eval.run import run_evaluation
from trust_rag.eval.schema import EvalReport


def test_eval_smoke():
    """Test that evaluation can run and generate reports."""
    # Create temporary output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Run minimal evaluation
            report = run_evaluation(
                suite="core",
                dataset="golden_v1",
                output_dir=tmpdir
            )
            
            # Verify report structure
            assert isinstance(report, EvalReport)
            assert report.run_meta is not None
            assert report.online_query_metrics is not None
            assert report.scorecard is not None
            
            # Verify reports were generated
            assert "json_report" in report.artifacts_links
            assert "html_report" in report.artifacts_links
            
            json_path = report.artifacts_links["json_report"]
            html_path = report.artifacts_links["html_report"]
            
            # Verify files exist
            assert os.path.exists(json_path), f"JSON report not found: {json_path}"
            assert os.path.exists(html_path), f"HTML report not found: {html_path}"
            
            # Verify JSON is valid
            with open(json_path, "r", encoding="utf-8") as f:
                report_data = json.load(f)
                assert "run_meta" in report_data
                assert "online_query_metrics" in report_data
                assert "scorecard" in report_data
            
            # Verify HTML is not empty
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
                assert len(html_content) > 100, "HTML report is too short"
                assert "TrustRAG Evaluation Report" in html_content
            
            print("✓ Evaluation smoke test passed")
            print(f"  JSON report: {json_path}")
            print(f"  HTML report: {html_path}")
            
        except Exception as e:
            pytest.fail(f"Evaluation smoke test failed: {e}")


if __name__ == "__main__":
    test_eval_smoke()

