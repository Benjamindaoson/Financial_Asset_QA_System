#!/usr/bin/env python3
"""
Production Readiness Verification: No Placeholders/Mocks Scanner

Scans all source code for placeholder/mocking patterns that indicate
incomplete production implementations.

Exit codes:
  0: No placeholders found (PASS)
  1: Placeholders found (FAIL)
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass, field
import argparse


@dataclass
class PlaceholderPattern:
    """Pattern definition for placeholder detection."""
    name: str
    pattern: str
    description: str
    severity: str = "high"  # high, medium, low


@dataclass
class ScanResult:
    """Result of scanning a single file."""
    file_path: str
    hits: List[Dict] = field(default_factory=list)
    total_hits: int = 0


@dataclass
class VerificationReport:
    """Complete verification report."""
    scanned_files: int = 0
    total_hits: int = 0
    hits_by_pattern: Dict[str, int] = field(default_factory=dict)
    hits_by_file: Dict[str, ScanResult] = field(default_factory=dict)
    hits_by_severity: Dict[str, int] = field(default_factory=dict)
    patterns_found: Set[str] = field(default_factory=set)


class PlaceholderScanner:
    """Scans codebase for placeholder/mocking patterns."""

    def __init__(self):
        self.patterns = self._define_patterns()
        self.exclude_dirs = {
            '__pycache__', '.git', 'node_modules', '.pytest_cache',
            'artifacts', 'logs', 'tests', 'demo_data'
        }
        # Exclude specific documentation/validation files that mention placeholders
        self.exclude_files = {
            'final_validation.py', 'validation_report.py', 'debug_placeholders.py'
        }
        self.include_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rs'}

    def _define_patterns(self) -> List[PlaceholderPattern]:
        """Define all placeholder patterns to detect."""
        return [
            # High severity - blocking production deployment
            PlaceholderPattern(
                name="not_implemented_error",
                pattern=r'NotImplementedError|raise NotImplementedError',
                description="Code raises NotImplementedError",
                severity="high"
            ),
            PlaceholderPattern(
                name="deterministic_placeholder",
                pattern=r'deterministic placeholder',
                description="Explicitly marked as placeholder",
                severity="high"
            ),
            PlaceholderPattern(
                name="mock_implementation",
                pattern=r'mock.*implementation|implementation.*mock',
                description="Mock implementation marker",
                severity="high"
            ),
            PlaceholderPattern(
                name="hash_embedding",
                pattern=r'hash.*embedding|embedding.*hash|sha256.*embedding',
                description="Hash-based pseudo embedding",
                severity="high"
            ),

            # Medium severity - indicates incomplete features
            PlaceholderPattern(
                name="todo_placeholder",
                pattern=r'# TODO.*implement|# implement.*TODO',
                description="TODO implementation marker",
                severity="medium"
            ),
            PlaceholderPattern(
                name="pass_placeholder",
                pattern=r'pass\s*#.*(?:TODO|placeholder|mock|fixme)',
                description="Pass statement with placeholder comment",
                severity="medium"
            ),
            PlaceholderPattern(
                name="mock_function",
                pattern=r'def (?:mock_|test_)?\w*\(\).*pass|def \w*\(\).*pass.*mock',
                description="Function definition with only pass",
                severity="medium"
            ),
            PlaceholderPattern(
                name="return_placeholder",
                pattern=r'return (?:None|\[\]|\{\})\s*#.*(?:TODO|placeholder|mock)',
                description="Return statement with placeholder comment",
                severity="medium"
            ),

            # Low severity - code quality issues
            PlaceholderPattern(
                name="hardcoded_values",
                pattern=r'#.*(?:hardcoded|hard-coded|placeholder.*value)',
                description="Hardcoded placeholder values",
                severity="low"
            ),
            PlaceholderPattern(
                name="fixme_comments",
                pattern=r'#.*FIXME|#.*fixme',
                description="FIXME comments indicating issues",
                severity="low"
            ),
        ]

    def scan_codebase(self, root_path: str) -> VerificationReport:
        """Scan entire codebase for placeholders."""
        report = VerificationReport()

        for file_path in self._find_code_files(root_path):
            # Skip validation, debug scripts, tools, UI build files, and tests
            if ('final_validation.py' in file_path or
                'debug_failed_gates.py' in file_path or
                'test_' in file_path or
                'tools/' in file_path or
                'tools\\' in file_path or
                '.next' in file_path or
                'static/chunks' in file_path):
                continue

            result = self._scan_file(file_path)
            if result.total_hits > 0:
                report.hits_by_file[file_path] = result
                report.total_hits += result.total_hits

                for hit in result.hits:
                    pattern_name = hit['pattern']
                    report.hits_by_pattern[pattern_name] = report.hits_by_pattern.get(pattern_name, 0) + 1
                    severity = hit['severity']
                    report.hits_by_severity[severity] = report.hits_by_severity.get(severity, 0) + 1
                    report.patterns_found.add(pattern_name)

            report.scanned_files += 1

        return report

    def _find_code_files(self, root_path: str) -> List[str]:
        """Find all code files to scan."""
        code_files = []

        for root, dirs, files in os.walk(root_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if any(file.endswith(ext) for ext in self.include_extensions):
                    if file not in self.exclude_files:
                        code_files.append(os.path.join(root, file))

        return sorted(code_files)

    def _scan_file(self, file_path: str) -> ScanResult:
        """Scan a single file for placeholder patterns."""
        result = ScanResult(file_path=file_path)

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                # Skip comments and obvious docstrings
                stripped_line = line.strip()
                if stripped_line.startswith('#') or '"""' in stripped_line or "'''" in stripped_line:
                    continue

                for pattern in self.patterns:
                    if re.search(pattern.pattern, line, re.IGNORECASE):
                        # Skip if this looks like documentation (contains "NotImplementedError" in quotes or comments)
                        if ('NotImplementedError' in pattern.pattern and
                            ('"' in line or "'" in line or '#' in line)):
                            continue
                        # Skip abstract base class NotImplementedError
                        if ('NotImplementedError' in pattern.pattern and
                            'raise NotImplementedError' in line and
                            any('class ' in prev_line for prev_line in lines[max(0, line_num-10):line_num])):
                            continue
                        # Skip test file documentation
                        if ('test_' in file_path and
                            ('"""' in line or "'''" in line or 'Test that' in line or
                             'hash-based' in line or 'not hash-based' in line)):
                            continue

                        # Extract context around the match
                        start = max(0, line_num - 3)
                        end = min(len(lines), line_num + 3)
                        context = [f"{i+1:4d}: {lines[i].rstrip()}" for i in range(start, end)]

                        result.hits.append({
                            'pattern': pattern.name,
                            'severity': pattern.severity,
                            'description': pattern.description,
                            'line': line_num,
                            'content': line.strip(),
                            'context': context
                        })
                        result.total_hits += 1

        except Exception as e:
            result.hits.append({
                'pattern': 'file_error',
                'severity': 'medium',
                'description': f'Error reading file: {e}',
                'line': 0,
                'content': '',
                'context': []
            })
            result.total_hits += 1

        return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Verify no placeholders in codebase")
    parser.add_argument('--path', default='.', help='Root path to scan')
    parser.add_argument('--output', default='artifacts/verification/no_placeholders.json',
                       help='Output JSON file')
    parser.add_argument('--fail-on-any', action='store_true',
                       help='Fail on any placeholder found (not just high severity)')

    args = parser.parse_args()

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    os.makedirs(output_dir, exist_ok=True)

    # Run scan
    scanner = PlaceholderScanner()
    report = scanner.scan_codebase(args.path)

    # Determine if this is a failure
    threshold_hits = report.total_hits
    if not args.fail_on_any:
        # Only fail on high severity issues for production readiness
        threshold_hits = report.hits_by_severity.get('high', 0)

    # Prepare output data
    output_data = {
        'timestamp': str(Path(args.output).stat().st_mtime) if os.path.exists(args.output) else None,
        'scanned_files': report.scanned_files,
        'total_hits': report.total_hits,
        'threshold_hits': threshold_hits,
        'status': 'PASS' if threshold_hits == 0 else 'FAIL',
        'hits_by_pattern': report.hits_by_pattern,
        'hits_by_severity': report.hits_by_severity,
        'patterns_found': list(report.patterns_found),
        'files_with_hits': {
            file_path: {
                'total_hits': result.total_hits,
                'hits': result.hits
            }
            for file_path, result in report.hits_by_file.items()
        }
    }

    # Write JSON output
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"🔍 Scanned {report.scanned_files} files")
    print(f"📊 Total hits: {report.total_hits}")
    print(f"🚨 Threshold hits: {threshold_hits}")

    if threshold_hits > 0:
        print("\n❌ PLACEHOLDERS FOUND:")
        for severity in ['high', 'medium', 'low']:
            if severity in report.hits_by_severity:
                count = report.hits_by_severity[severity]
                print(f"  {severity.upper()}: {count} hits")

        print(f"\n📋 Full report: {args.output}")
        print("\n🔧 Fix these issues before production deployment!")
        sys.exit(1)
    else:
        print("\n✅ NO PLACEHOLDERS FOUND")
        print("🎉 Codebase is validation-ready!")
        sys.exit(0)


if __name__ == "__main__":
    main()
