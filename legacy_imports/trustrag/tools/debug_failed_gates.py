#!/usr/bin/env python3
"""
Debug Failed Gates - Extract and analyze failed release gate checks.

This script reads the release gate report and provides structured analysis
of failed gates for targeted fixes.
"""
import json
from pathlib import Path
from typing import Dict, List, Any


def analyze_failed_gates(report_path: str) -> Dict[str, Any]:
    """Analyze the release gate report for failed gates."""
    if not Path(report_path).exists():
        print(f"❌ Report file not found: {report_path}")
        return {"error": "report_not_found"}

    try:
        with open(report_path, 'r') as f:
            report = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in report: {e}")
        return {"error": "invalid_json"}

    # Extract failed gates
    failed_gates = []
    gate_results = report.get("gate_results", [])

    for gate in gate_results:
        if gate.get("status") != "PASS":
            failed_gates.append({
                "name": gate.get("name", "unknown"),
                "status": gate.get("status", "unknown"),
                "error_message": gate.get("error_message", "").strip(),
                "execution_time": gate.get("execution_time", 0.0)
            })

    # Categorize failures
    analysis = {
        "total_gates": report.get("summary", {}).get("total_gates", 0),
        "passed_gates": report.get("summary", {}).get("passed_gates", 0),
        "failed_gates": report.get("summary", {}).get("failed_gates", 0),
        "failed_gate_details": failed_gates,
        "blocking_issues": report.get("blocking_issues", [])
    }

    return analysis


def print_structured_analysis(analysis: Dict[str, Any]):
    """Print structured analysis of failed gates."""
    if "error" in analysis:
        print(f"❌ Analysis failed: {analysis['error']}")
        return

    print("🔍 RELEASE GATE FAILURE ANALYSIS")
    print("=" * 50)
    print(f"📊 Overall: {analysis['passed_gates']}/{analysis['total_gates']} gates passed")
    print(f"❌ Failed: {analysis['failed_gates']} gates")
    print()

    if analysis['blocking_issues']:
        print("🚫 BLOCKING ISSUES:")
        for issue in analysis['blocking_issues']:
            print(f"  • {issue}")
        print()

    if analysis['failed_gate_details']:
        print("🔴 FAILED GATES DETAILS:")
        for i, gate in enumerate(analysis['failed_gate_details'], 1):
            print(f"{i}. {gate['name']}")
            print(f"   Status: {gate['status']}")
            print(f"   Time: {gate['execution_time']:.1f}s")
            if gate['error_message']:
                # Truncate long error messages
                error = gate['error_message']
                if len(error) > 200:
                    error = error[:197] + "..."
                print(f"   Error: {error}")
            print()

        print("🧩 ENGINEERING CLASSIFICATION:")
        classifications = [
            ("A", "No Placeholders/Mocks Scanner", "Implementation bug - placeholder detection logic"),
            ("A", "E2E Acceptance Test", "Syntax error in demo_comprehensive.py"),
            ("A", "GA Iron Laws Enforcement", "GA test implementation incomplete"),
            ("A", "Task Queue Fault Tolerance", "Task queue test implementation incomplete"),
            ("A", "External Tools Security Verification", "External tools verification implementation incomplete")
        ]

        for cls, name, reason in classifications:
            print(f"  {cls}类: {name}")
            print(f"      原因: {reason}")
        print()


def main():
    """Main entry point."""
    report_path = "artifacts/release_gate/final_verification.json"

    print(f"Reading release gate report: {report_path}")
    print()

    analysis = analyze_failed_gates(report_path)
    print_structured_analysis(analysis)

    if analysis.get('failed_gates', 0) > 0:
        print("🎯 NEXT STEPS:")
        print("1. Classify each failed gate (A/B/C)")
        print("2. Apply targeted fixes")
        print("3. Re-run release gate")
        print("4. Repeat until all gates pass")


if __name__ == "__main__":
    main()