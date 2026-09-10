#!/usr/bin/env python3
"""
Production Readiness Verification: External Tools Safety Check.

Verifies that external tool integrations (APIs, databases, etc.) are:
- Not using hardcoded credentials
- Not bypassing security controls
- Properly configured for production
- Have appropriate rate limiting and monitoring
"""

import os
import sys
import json
import re
import ast
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field
import argparse


@dataclass
class SecurityViolation:
    """Security violation found in external tool usage."""
    violation_type: str
    severity: str  # "high", "medium", "low"
    file_path: str
    line_number: int
    description: str
    code_snippet: str
    recommendation: str


@dataclass
class ToolVerificationReport:
    """Complete external tools verification report."""
    scanned_files: int = 0
    violations: List[SecurityViolation] = field(default_factory=list)
    tools_verified: Set[str] = field(default_factory=set)
    risk_score: float = 0.0
    status: str = "unknown"  # "pass", "fail"


class ExternalToolsVerifier:
    """Verifies external tool integrations for production safety."""

    def __init__(self):
        self.violations: List[SecurityViolation] = []
        self.tools_verified: Set[str] = set()

        # Define security patterns to check
        self.security_patterns = self._define_security_patterns()

        # Define known external tools
        self.known_tools = {
            "openai": ["openai", "OpenAI"],
            "anthropic": ["anthropic", "claude"],
            "google": ["google", "vertex", "palm"],
            "azure": ["azure", "openai.azure"],
            "aws": ["boto3", "aws", "sagemaker"],
            "slack": ["slack", "slack-sdk"],
            "discord": ["discord"],
            "twitter": ["tweepy", "twitter"],
            "database": ["psycopg2", "pymongo", "sqlalchemy"],
            "redis": ["redis", "redis-py"],
            "elasticsearch": ["elasticsearch"],
            "pinecone": ["pinecone"],
            "weaviate": ["weaviate"],
            "qdrant": ["qdrant"],
            "chromadb": ["chromadb"]
        }

    def _define_security_patterns(self) -> List[Tuple[str, str, str, str]]:
        """Define security patterns to detect violations."""
        return [
            # Hardcoded API keys
            ("hardcoded_api_key", r'(?i)(api_key|apikey|token|secret|password)\s*=\s*["\'][^"\']{10,}["\']',
             "Hardcoded API key or secret detected",
             "Move credentials to environment variables or secure key management"),

            # Hardcoded endpoints with sensitive data
            ("hardcoded_credentials", r'https?://[^/]+:[^@]+@',
             "Hardcoded credentials in URL",
             "Use environment variables for authentication"),

            # Database connection strings with embedded credentials
            ("db_connection_creds", r'(mongodb|postgresql|mysql)://[^/]+:[^@]+@',
             "Database connection string with embedded credentials",
             "Use connection parameters from environment variables"),

            # Direct file system database access (security risk)
            ("direct_fs_db", r'(sqlite:///|file:///).*\.db',
             "Direct file system database access",
             "Consider using in-memory or managed database services"),

            # Missing rate limiting
            ("missing_rate_limit", r'import\s+(?:requests|httpx|aiohttp)',
             "HTTP client imported without rate limiting context",
             "Implement rate limiting and retry logic"),

            # Synchronous external calls (blocking)
            ("sync_external_call", r'requests\.(get|post|put|delete)\(',
             "Synchronous external API call",
             "Consider async calls or proper timeout handling"),

            # No timeout on external calls
            ("no_timeout", r'(requests|httpx)\.(get|post|put|delete)\([^)]*\)\s*$',
             "External API call without timeout",
             "Always set reasonable timeouts"),

            # Missing error handling for external calls
            ("no_error_handling", r'(?:requests|httpx)\.(?:get|post|put|delete)\([^)]*\)(?:\s*(?:\.json\(\)|\.text)?)?\s*$',
             "External API call without error handling",
             "Wrap calls in try-except blocks"),

            # Insecure SSL settings
            ("insecure_ssl", r'verify=False|ssl=False|check_hostname=False',
             "Insecure SSL/TLS settings",
             "Always verify SSL certificates in production"),

            # Missing authentication context
            ("missing_auth", r'(?:openai|anthropic|google)\.Client\(',
             "API client initialized without authentication context",
             "Ensure proper authentication is configured"),
        ]

    def verify_codebase(self, root_path: str) -> ToolVerificationReport:
        """Verify external tools usage across codebase."""
        report = ToolVerificationReport()

        # Scan Python files for external tool usage and security issues
        for file_path in self._find_python_files(root_path):
            self._analyze_file(file_path)
            report.scanned_files += 1

        report.violations = self.violations
        report.tools_verified = self.tools_verified
        report.risk_score = self._calculate_risk_score()
        report.status = "pass" if report.risk_score < 3.0 else "fail"

        return report

    def _find_python_files(self, root_path: str) -> List[str]:
        """Find all Python files to analyze."""
        python_files = []

        exclude_dirs = {
            '__pycache__', '.git', 'node_modules', '.pytest_cache',
            'artifacts', 'logs', 'tests/fixtures', 'venv', 'env'
        }

        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file.endswith('.py'):
                    # Exclude this verification script itself as it contains regex patterns
                    if file != 'verify_external_tools.py':
                        python_files.append(os.path.join(root, file))

        return sorted(python_files)

    def _analyze_file(self, file_path: str):
        """Analyze a single Python file for external tool usage and security."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')

            # Check for known external tools
            self._detect_tools(file_path, content)

            # Check for security violations
            self._check_security_violations(file_path, lines)

        except Exception as e:
            self.violations.append(SecurityViolation(
                violation_type="file_read_error",
                severity="low",
                file_path=file_path,
                line_number=0,
                description=f"Could not analyze file: {e}",
                code_snippet="",
                recommendation="Ensure file is readable and properly encoded"
            ))

    def _detect_tools(self, file_path: str, content: str):
        """Detect usage of known external tools."""
        for tool_name, patterns in self.known_tools.items():
            for pattern in patterns:
                if re.search(r'\b' + re.escape(pattern) + r'\b', content, re.IGNORECASE):
                    self.tools_verified.add(tool_name)
                    break

    def _check_security_violations(self, file_path: str, lines: List[str]):
        """Check for security violations in file."""
        for line_num, line in enumerate(lines, 1):
            for violation_type, pattern, description, recommendation in self.security_patterns:
                if re.search(pattern, line):
                    # Extract code context
                    start = max(0, line_num - 2)
                    end = min(len(lines), line_num + 2)
                    context = [f"{i+1:4d}: {lines[i]}" for i in range(start, end)]

                    # Determine severity based on violation type
                    severity = self._get_violation_severity(violation_type)

                    violation = SecurityViolation(
                        violation_type=violation_type,
                        severity=severity,
                        file_path=file_path,
                        line_number=line_num,
                        description=description,
                        code_snippet=line.strip(),
                        recommendation=recommendation
                    )

                    self.violations.append(violation)

    def _get_violation_severity(self, violation_type: str) -> str:
        """Determine severity level for violation type."""
        high_severity = {
            "hardcoded_api_key", "hardcoded_credentials", "db_connection_creds",
            "insecure_ssl", "missing_auth"
        }
        medium_severity = {
            "sync_external_call", "no_timeout", "no_error_handling",
            "missing_rate_limit", "direct_fs_db"
        }

        if violation_type in high_severity:
            return "high"
        elif violation_type in medium_severity:
            return "medium"
        else:
            return "low"

    def _calculate_risk_score(self) -> float:
        """Calculate overall risk score from violations."""
        if not self.violations:
            return 0.0

        score = 0.0
        severity_weights = {"high": 3.0, "medium": 1.5, "low": 0.5}

        for violation in self.violations:
            score += severity_weights.get(violation.severity, 1.0)

        # Normalize by number of files scanned (rough heuristic)
        return min(score, 10.0)  # Cap at 10.0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Verify external tools security")
    parser.add_argument('--path', default='.', help='Root path to scan')
    parser.add_argument('--output', default='artifacts/tools_verification.json',
                       help='Output JSON file')
    parser.add_argument('--fail-on-any', action='store_true',
                       help='Fail on any violation found')

    args = parser.parse_args()

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    os.makedirs(output_dir, exist_ok=True)

    # Run verification
    verifier = ExternalToolsVerifier()
    report = verifier.verify_codebase(args.path)

    # Determine if this is a failure
    should_fail = (
        report.risk_score >= 5.0 or  # High risk score
        any(v.severity == "high" for v in report.violations) or  # Any high-severity violation
        (args.fail_on_any and report.violations)  # Any violation if strict mode
    )

    # Prepare output data
    output_data = {
        "timestamp": str(Path(args.output).stat().st_mtime) if os.path.exists(args.output) else None,
        "scanned_files": report.scanned_files,
        "tools_verified": list(report.tools_verified),
        "total_violations": len(report.violations),
        "risk_score": report.risk_score,
        "status": "PASS" if not should_fail else "FAIL",
        "violations_by_severity": {
            "high": len([v for v in report.violations if v.severity == "high"]),
            "medium": len([v for v in report.violations if v.severity == "medium"]),
            "low": len([v for v in report.violations if v.severity == "low"])
        },
        "violations": [
            {
                "type": v.violation_type,
                "severity": v.severity,
                "file": v.file_path,
                "line": v.line_number,
                "description": v.description,
                "recommendation": v.recommendation
            }
            for v in report.violations
        ]
    }

    # Write JSON output
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"🔍 Scanned {report.scanned_files} files")
    print(f"🔧 Tools verified: {', '.join(report.tools_verified) if report.tools_verified else 'None'}")
    print(f"⚠️  Total violations: {len(report.violations)}")
    print(f"📊 Risk score: {report.risk_score:.1f}/10.0")

    if report.violations:
        print("\n🚨 SECURITY VIOLATIONS FOUND:")

        # Group by severity
        for severity in ["high", "medium", "low"]:
            severity_violations = [v for v in report.violations if v.severity == severity]
            if severity_violations:
                print(f"\n{severity.upper()} SEVERITY ({len(severity_violations)}):")
                for v in severity_violations[:5]:  # Show first 5
                    print(f"  • {v.file_path}:{v.line_number} - {v.description}")

        print(f"\n📋 Full report: {args.output}")

    if should_fail:
        print("\n❌ EXTERNAL TOOLS VERIFICATION FAILED")
        print("🔧 Fix security violations before production deployment!")
        sys.exit(1)
    else:
        print("\n✅ EXTERNAL TOOLS VERIFICATION PASSED")
        print("🔒 External integrations are validation-ready!")
        sys.exit(0)


if __name__ == "__main__":
    main()
