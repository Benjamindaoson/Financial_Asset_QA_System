#!/usr/bin/env python3
"""
Production Release Gate - TrustRAG Production Readiness Verification.

Runs all 7 acceptance verifications in sequence:
1. No Placeholders Scanner
2. E2E Acceptance Test
3. GA Iron Laws Enforcement
4. Continuous Evaluation Metrics
5. Deterministic Replay Verification
6. Task Queue Fault Tolerance
7. External Tools Security Verification

Exit codes:
  0: All gates PASS - Ready for production deployment
  1: One or more gates FAIL - Not ready for production
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
import argparse


@dataclass
class GateResult:
    """Result of a single gate verification."""
    name: str
    status: str  # "PASS", "FAIL", "ERROR"
    exit_code: int
    execution_time: float
    output_file: str = ""
    error_message: str = ""
    summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReleaseGateReport:
    """Complete release gate verification report."""
    timestamp: str = ""
    total_gates: int = 7
    passed_gates: int = 0
    failed_gates: int = 0
    error_gates: int = 0
    total_execution_time: float = 0.0
    overall_status: str = "UNKNOWN"
    gate_results: List[GateResult] = field(default_factory=list)
    blocking_issues: List[str] = field(default_factory=list)


class ReleaseGate:
    """Production release gate orchestrator."""

    def __init__(self):
        self.gates = self._define_gates()
        self.artifacts_dir = Path("artifacts/release_gate")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _define_gates(self) -> List[Dict[str, Any]]:
        """Define all release gates to execute."""
        return [
            {
                "id": "placeholders",
                "name": "No Placeholders/Mocks Scanner",
                "command": ["python", "tools/verify_no_placeholders.py"],
                "description": "Ensures no placeholder/mocking code remains",
                "critical": True
            },
            {
                "id": "e2e",
                "name": "E2E Acceptance Test",
                "command": ["python", "demo_comprehensive.py", "--audit", "--out", "artifacts/e2e_run"],
                "description": "Verifies end-to-end RAG pipeline functionality",
                "critical": True
            },
            {
                "id": "ga_laws",
                "name": "GA Iron Laws Enforcement",
                "command": ["pytest", "-q", "tests/ga_acceptance_test.py", "-v", "--tb=short"],
                "description": "Ensures GA constraints are enforced",
                "critical": True
            },
            {
                "id": "continuous_eval",
                "name": "Continuous Evaluation Metrics",
                "command": ["python", "trust_rag/runtime/extensions/continuous_eval.py",
                           "--suite", "artifacts/eval/task_suite.json",
                           "--out", "artifacts/continuous_eval"],
                "description": "Verifies performance metrics and regression detection",
                "critical": False
            },
            {
                "id": "replay",
                "name": "Deterministic Replay Verification",
                "command": ["python", "trust_rag/runtime/extensions/replay.py",
                           "--run-id", "demo_run_latest",
                           "--out", "artifacts/replay"],
                "description": "Ensures deterministic behavior",
                "critical": True
            },
            {
                "id": "task_queue",
                "name": "Task Queue Fault Tolerance",
                "command": ["pytest", "-q", "trust_rag/tests/test_task_queue.py", "-v", "--tb=short"],
                "description": "Verifies distributed task queue reliability",
                "critical": True
            },
            {
                "id": "external_tools",
                "name": "External Tools Security Verification",
                "command": ["python", "tools/verify_external_tools.py"],
                "description": "Ensures external API integrations are secure",
                "critical": True
            }
        ]

    def run_all_gates(self) -> ReleaseGateReport:
        """Run all release gates in sequence."""
        report = ReleaseGateReport()
        report.timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

        print("🚀 TrustRAG Production Release Gate Verification")
        print("=" * 60)
        print(f"Started at: {report.timestamp}")
        print()

        start_time = time.time()

        for i, gate_config in enumerate(self.gates, 1):
            print(f"[{i}/{len(self.gates)}] Running: {gate_config['name']}")
            print(f"   Description: {gate_config['description']}")

            gate_start = time.time()
            result = self._run_single_gate(gate_config)
            gate_time = time.time() - gate_start

            result.execution_time = gate_time
            report.gate_results.append(result)

            # Update counters
            if result.status == "PASS":
                report.passed_gates += 1
                status_icon = "✅"
            elif result.status == "FAIL":
                report.failed_gates += 1
                status_icon = "❌"
                if gate_config["critical"]:
                    report.blocking_issues.append(f"CRITICAL: {gate_config['name']} failed")
            else:  # ERROR
                report.error_gates += 1
                status_icon = "🔥"
                if gate_config["critical"]:
                    report.blocking_issues.append(f"CRITICAL: {gate_config['name']} error")

            print(f"   {status_icon} {result.status} ({gate_time:.1f}s)")
            if result.error_message:
                print(f"      Error: {result.error_message}")
            print()

        report.total_execution_time = time.time() - start_time

        # Determine overall status
        if report.failed_gates > 0 or report.error_gates > 0:
            report.overall_status = "FAIL"
        else:
            report.overall_status = "PASS"

        return report

    def _run_single_gate(self, gate_config: Dict[str, Any]) -> GateResult:
        """Run a single gate verification."""
        result = GateResult(
            name=gate_config["name"],
            status="UNKNOWN",
            exit_code=-1,
            execution_time=0.0
        )

        try:
            # Run the command
            process = subprocess.run(
                gate_config["command"],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout per gate
                cwd=os.getcwd()
            )

            result.exit_code = process.returncode

            # Determine status based on exit code
            if process.returncode == 0:
                result.status = "PASS"
            else:
                result.status = "FAIL"
                result.error_message = process.stderr.strip() or "Non-zero exit code"

        except subprocess.TimeoutExpired:
            result.status = "ERROR"
            result.error_message = "Gate timed out after 5 minutes"

        except FileNotFoundError:
            result.status = "ERROR"
            result.error_message = f"Command not found: {gate_config['command'][0]}"

        except Exception as e:
            result.status = "ERROR"
            result.error_message = f"Unexpected error: {e}"

        return result

    def generate_report(self, report: ReleaseGateReport) -> Dict[str, Any]:
        """Generate comprehensive release gate report."""
        report_data = {
            "timestamp": report.timestamp,
            "summary": {
                "total_gates": report.total_gates,
                "passed_gates": report.passed_gates,
                "failed_gates": report.failed_gates,
                "error_gates": report.error_gates,
                "overall_status": report.overall_status,
                "total_execution_time": round(report.total_execution_time, 2),
                "pass_rate": round(report.passed_gates / report.total_gates * 100, 1)
            },
            "blocking_issues": report.blocking_issues,
            "gate_results": [
                {
                    "name": r.name,
                    "status": r.status,
                    "execution_time": round(r.execution_time, 2),
                    "error_message": r.error_message
                }
                for r in report.gate_results
            ],
            "recommendations": self._generate_recommendations(report)
        }

        return report_data

    def _generate_recommendations(self, report: ReleaseGateReport) -> List[str]:
        """Generate recommendations based on gate results."""
        recommendations = []

        failed_gates = [r for r in report.gate_results if r.status != "PASS"]

        if failed_gates:
            recommendations.append("Fix failed gates before production deployment:")

            for gate in failed_gates:
                if "placeholders" in gate.name.lower():
                    recommendations.append("  • Remove all mock/placeholder code from production codebase")
                elif "e2e" in gate.name.lower():
                    recommendations.append("  • Fix RAG pipeline issues and ensure citation verification works")
                elif "ga_laws" in gate.name.lower():
                    recommendations.append("  • Implement GA iron laws: evidence sufficiency, citation verification")
                elif "continuous_eval" in gate.name.lower():
                    recommendations.append("  • Set up proper evaluation metrics and baseline comparisons")
                elif "replay" in gate.name.lower():
                    recommendations.append("  • Ensure deterministic behavior across executions")
                elif "task_queue" in gate.name.lower():
                    recommendations.append("  • Fix distributed task queue fault tolerance")
                elif "external_tools" in gate.name.lower():
                    recommendations.append("  • Secure external API integrations and remove hardcoded credentials")

        if report.overall_status == "PASS":
            recommendations.append("🎉 All gates passed! TrustRAG is validation-ready.")
            recommendations.append("   Proceed with confidence to production deployment.")

        return recommendations


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="TrustRAG Production Release Gate")
    parser.add_argument("--output", default="artifacts/release_gate/report.json",
                       help="Output report file")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose output")

    args = parser.parse_args()

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    os.makedirs(output_dir, exist_ok=True)

    # Run all gates
    gate = ReleaseGate()
    report = gate.run_all_gates()

    # Generate and save report
    report_data = gate.generate_report(report)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    # Print final summary
    print("=" * 60)
    print("RELEASE GATE VERIFICATION COMPLETE")
    print("=" * 60)
    print(f"Overall Status: {'✅ PASS' if report.overall_status == 'PASS' else '❌ FAIL'}")
    print(f"Gates Passed: {report.passed_gates}/{report.total_gates}")
    print(f"Total Time: {report.total_execution_time:.1f}s")
    print()

    if report.blocking_issues:
        print("🚫 BLOCKING ISSUES:")
        for issue in report.blocking_issues:
            print(f"  • {issue}")
        print()

    print("📋 Full report saved to:", args.output)
    print()

    if report.overall_status == "PASS":
        print("🎯 RESULT: Validation Gate = PASS")
        print("   TrustRAG meets all advanced production standards!")
        print("   Safe to proceed with production deployment.")
        sys.exit(0)
    else:
        print("🚫 RESULT: Validation Gate = FAIL")
        print("   TrustRAG requires fixes before production deployment.")
        print("   See blocking issues above and fix before retrying.")
        sys.exit(1)


if __name__ == "__main__":
    main()
