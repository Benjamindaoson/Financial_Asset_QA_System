"""
Extreme Cases Performance Tests / 极端用例压力测试

Tests system behavior under extreme conditions:
- Ultra-long documents (1000+ pages, million+ words)
- Large file batch uploads (10GB+, 100+ files)
- Special formats (image PDFs, complex tables, mixed encoding)
- Concurrent operations
- Resource consumption monitoring

所有测试统计执行时间、CPU/内存/磁盘占用、成功率、失败原因，自动生成报告（HTML/PDF）。
"""
import os
import sys
import time
import json
import psutil
import pytest
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trust_rag.system import TrustRAG
from trust_rag.core.monitoring import get_monitor
from trust_rag.engine.ingest.pipeline import IngestPipeline
from trust_rag.config import get_paths


@dataclass
class TestMetrics:
    """Test execution metrics."""
    test_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    
    # Resource usage
    cpu_percent_avg: float = 0.0
    cpu_percent_max: float = 0.0
    memory_mb_avg: float = 0.0
    memory_mb_max: float = 0.0
    disk_read_mb: float = 0.0
    disk_write_mb: float = 0.0
    
    # Test-specific metrics
    files_processed: int = 0
    files_succeeded: int = 0
    files_failed: int = 0
    total_chunks: int = 0
    total_size_mb: float = 0.0
    
    def finish(self, success: bool = True, error: Optional[str] = None):
        """Mark test as finished."""
        self.end_time = time.time()
        self.duration_seconds = self.end_time - self.start_time
        self.success = success
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ResourceMonitor:
    """Monitor system resources during test execution."""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.samples: List[Dict[str, float]] = []
        self.start_io = None
        self.running = False
    
    def start(self):
        """Start monitoring."""
        self.running = True
        self.start_io = self.process.io_counters()
        self.samples = []
    
    def sample(self):
        """Take a resource sample."""
        if not self.running:
            return
        
        try:
            cpu_percent = self.process.cpu_percent(interval=0.1)
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            self.samples.append({
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb,
                "timestamp": time.time()
            })
        except Exception as e:
            print(f"Warning: Failed to sample resources: {e}")
    
    def stop(self) -> Dict[str, float]:
        """Stop monitoring and return summary."""
        self.running = False
        
        if not self.samples:
            return {
                "cpu_percent_avg": 0.0,
                "cpu_percent_max": 0.0,
                "memory_mb_avg": 0.0,
                "memory_mb_max": 0.0,
                "disk_read_mb": 0.0,
                "disk_write_mb": 0.0
            }
        
        cpu_values = [s["cpu_percent"] for s in self.samples]
        memory_values = [s["memory_mb"] for s in self.samples]
        
        end_io = self.process.io_counters()
        disk_read_mb = (end_io.read_bytes - self.start_io.read_bytes) / 1024 / 1024
        disk_write_mb = (end_io.write_bytes - self.start_io.write_bytes) / 1024 / 1024
        
        return {
            "cpu_percent_avg": sum(cpu_values) / len(cpu_values),
            "cpu_percent_max": max(cpu_values),
            "memory_mb_avg": sum(memory_values) / len(memory_values),
            "memory_mb_max": max(memory_values),
            "disk_read_mb": disk_read_mb,
            "disk_write_mb": disk_write_mb
        }


class PerformanceTestRunner:
    """Runner for performance tests with reporting."""
    
    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or os.path.join(get_paths().artifacts_dir, "perf_reports")
        os.makedirs(self.output_dir, exist_ok=True)
        self.results: List[TestMetrics] = []
    
    def run_test(self, test_func, test_name: str, *args, **kwargs) -> TestMetrics:
        """Run a test with resource monitoring."""
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print(f"{'='*60}")
        
        metrics = TestMetrics(test_name=test_name, start_time=time.time())
        monitor = ResourceMonitor()
        monitor.start()
        
        try:
            # Run test in background thread to allow monitoring
            def run_with_monitoring():
                while monitor.running:
                    monitor.sample()
                    time.sleep(0.5)
            
            import threading
            monitor_thread = threading.Thread(target=run_with_monitoring, daemon=True)
            monitor_thread.start()
            
            # Execute test
            result = test_func(*args, **kwargs)
            
            # Stop monitoring
            resource_summary = monitor.stop()
            metrics.__dict__.update(resource_summary)
            
            if isinstance(result, dict):
                metrics.__dict__.update(result)
            
            metrics.finish(success=True)
            print(f"✓ Test completed: {metrics.duration_seconds:.2f}s")
            
        except Exception as e:
            monitor.stop()
            metrics.finish(success=False, error=str(e))
            print(f"✗ Test failed: {e}")
        
        self.results.append(metrics)
        return metrics
    
    def generate_report(self, format: str = "html") -> str:
        """Generate test report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "html":
            return self._generate_html_report(timestamp)
        elif format == "json":
            return self._generate_json_report(timestamp)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_standardized_output(self) -> Dict[str, Any]:
        """
        Get standardized output for evaluation framework.
        
        Returns:
            Dictionary compatible with RobustnessMetrics
        """
        return {
            "ultra_long_doc_test": self._get_test_result("Ultra-Long Document Test"),
            "batch_large_files_test": self._get_test_result("Batch Large Files Test"),
            "special_formats_test": self._get_test_result("Special Formats Test"),
            "concurrent_queries_test": self._get_test_result("Concurrent Queries Test"),
            "total_extreme_tests": len(self.results),
            "passed_extreme_tests": sum(1 for r in self.results if r.success),
            "robustness_score": sum(1 for r in self.results if r.success) / len(self.results) if self.results else 0.0,
            "failure_reasons": self._get_failure_reasons(),
            "failure_cases": [r.to_dict() for r in self.results if not r.success]
        }
    
    def _get_test_result(self, test_name: str) -> Dict[str, Any]:
        """Get result for a specific test."""
        for result in self.results:
            if result.test_name == test_name:
                return result.to_dict()
        return {}
    
    def _get_failure_reasons(self) -> Dict[str, int]:
        """Aggregate failure reasons."""
        reasons = {}
        for result in self.results:
            if not result.success and result.error:
                error_type = result.error.split(":")[0] if ":" in result.error else result.error
                reasons[error_type] = reasons.get(error_type, 0) + 1
        return reasons
    
    def _generate_html_report(self, timestamp: str) -> str:
        """Generate HTML report."""
        file_path = os.path.join(self.output_dir, f"perf_report_{timestamp}.html")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        
        total_duration = sum(r.duration_seconds or 0 for r in self.results)
        avg_cpu = sum(r.cpu_percent_avg for r in self.results) / total_tests if total_tests > 0 else 0
        avg_memory = sum(r.memory_mb_avg for r in self.results) / total_tests if total_tests > 0 else 0
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>TrustRAG Performance Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
        .metric {{ background: #f8f9fa; padding: 15px; border-radius: 4px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
        .metric-label {{ color: #666; font-size: 12px; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; font-weight: bold; }}
        .success {{ color: #28a745; }}
        .failure {{ color: #dc3545; }}
        .error {{ background: #fff3cd; padding: 10px; border-radius: 4px; margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>TrustRAG Performance Test Report</h1>
        <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <div class="summary">
            <div class="metric">
                <div class="metric-value">{total_tests}</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric">
                <div class="metric-value success">{passed_tests}</div>
                <div class="metric-label">Passed</div>
            </div>
            <div class="metric">
                <div class="metric-value failure">{failed_tests}</div>
                <div class="metric-label">Failed</div>
            </div>
            <div class="metric">
                <div class="metric-value">{total_duration:.2f}s</div>
                <div class="metric-label">Total Duration</div>
            </div>
        </div>
        
        <h2>Test Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Test Name</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>CPU Avg</th>
                    <th>Memory Avg</th>
                    <th>Files</th>
                    <th>Chunks</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for result in self.results:
            status_class = "success" if result.success else "failure"
            status_text = "✓ Pass" if result.success else "✗ Fail"
            
            html += f"""
                <tr>
                    <td><strong>{result.test_name}</strong></td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{result.duration_seconds:.2f}s</td>
                    <td>{result.cpu_percent_avg:.1f}%</td>
                    <td>{result.memory_mb_avg:.1f} MB</td>
                    <td>{result.files_processed}</td>
                    <td>{result.total_chunks}</td>
                </tr>
"""
            
            if result.error:
                html += f"""
                <tr>
                    <td colspan="7" class="error">
                        <strong>Error:</strong> {result.error}
                    </td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
        
        <h2>Resource Usage Summary</h2>
        <table>
            <thead>
                <tr>
                    <th>Test Name</th>
                    <th>CPU Avg</th>
                    <th>CPU Max</th>
                    <th>Memory Avg</th>
                    <th>Memory Max</th>
                    <th>Disk Read</th>
                    <th>Disk Write</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for result in self.results:
            html += f"""
                <tr>
                    <td>{result.test_name}</td>
                    <td>{result.cpu_percent_avg:.1f}%</td>
                    <td>{result.cpu_percent_max:.1f}%</td>
                    <td>{result.memory_mb_avg:.1f} MB</td>
                    <td>{result.memory_mb_max:.1f} MB</td>
                    <td>{result.disk_read_mb:.2f} MB</td>
                    <td>{result.disk_write_mb:.2f} MB</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"\n✓ HTML report generated: {file_path}")
        return file_path
    
    def _generate_json_report(self, timestamp: str) -> str:
        """Generate JSON report."""
        file_path = os.path.join(self.output_dir, f"perf_report_{timestamp}.json")
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_tests": len(self.results),
                "passed": sum(1 for r in self.results if r.success),
                "failed": sum(1 for r in self.results if not r.success),
                "total_duration_seconds": sum(r.duration_seconds or 0 for r in self.results)
            },
            "results": [r.to_dict() for r in self.results]
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ JSON report generated: {file_path}")
        return file_path


# ============================================================================
# Test Cases / 测试用例
# ============================================================================

def test_ultra_long_document():
    """Test ingestion of ultra-long document (1000+ pages, million+ words)."""
    # Create a large test document (simulated)
    # In real test, use actual large PDF
    test_file = os.path.join(get_paths().raw_docs_dir, "ultra_long_test.pdf")
    
    if not os.path.exists(test_file):
        print("⚠ Warning: Ultra-long test file not found, skipping test")
        return {"files_processed": 0, "total_chunks": 0}
    
    pipeline = IngestPipeline(output_dir=get_paths().ingestion_dir)
    
    start_time = time.time()
    result = pipeline.ingest(test_file, ingest_profile="generic")
    duration = time.time() - start_time
    
    file_size_mb = os.path.getsize(test_file) / 1024 / 1024
    
    return {
        "files_processed": 1,
        "files_succeeded": 1 if result.ingest_status == "OK" else 0,
        "files_failed": 0 if result.ingest_status == "OK" else 1,
        "total_chunks": len(result.chunks),
        "total_size_mb": file_size_mb,
        "ingest_status": result.ingest_status
    }


def test_batch_large_files():
    """Test concurrent batch upload of large files (10GB+, 100+ files)."""
    test_dir = os.path.join(get_paths().raw_docs_dir, "batch_test")
    
    if not os.path.exists(test_dir):
        print("⚠ Warning: Batch test directory not found, skipping test")
        return {"files_processed": 0, "total_chunks": 0}
    
    pipeline = IngestPipeline(output_dir=get_paths().ingestion_dir)
    
    # Find all PDF files
    pdf_files = list(Path(test_dir).glob("*.pdf"))
    if len(pdf_files) > 100:
        pdf_files = pdf_files[:100]  # Limit to 100 files
    
    total_size_mb = sum(f.stat().st_size for f in pdf_files) / 1024 / 1024
    
    def ingest_file(file_path):
        try:
            result = pipeline.ingest(str(file_path), ingest_profile="generic")
            return {"success": result.ingest_status == "OK", "chunks": len(result.chunks)}
        except Exception as e:
            return {"success": False, "error": str(e), "chunks": 0}
    
    # Process files concurrently
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(ingest_file, f) for f in pdf_files]
        results = [f.result() for f in as_completed(futures)]
    
    duration = time.time() - start_time
    
    succeeded = sum(1 for r in results if r.get("success", False))
    total_chunks = sum(r.get("chunks", 0) for r in results)
    
    return {
        "files_processed": len(pdf_files),
        "files_succeeded": succeeded,
        "files_failed": len(pdf_files) - succeeded,
        "total_chunks": total_chunks,
        "total_size_mb": total_size_mb
    }


def test_special_formats():
    """Test ingestion of special formats (image PDFs, complex tables, mixed encoding)."""
    test_cases = [
        ("image_pdf", "Image-based PDF"),
        ("complex_table", "Complex table structure"),
        ("mixed_encoding", "Mixed character encoding"),
        ("scanned_document", "Scanned document with OCR")
    ]
    
    pipeline = IngestPipeline(output_dir=get_paths().ingestion_dir)
    test_dir = get_paths().raw_docs_dir
    
    results = []
    total_chunks = 0
    
    for test_type, description in test_cases:
        test_file = os.path.join(test_dir, f"{test_type}_test.pdf")
        
        if not os.path.exists(test_file):
            print(f"⚠ Warning: {description} test file not found, skipping")
            continue
        
        try:
            result = pipeline.ingest(test_file, ingest_profile="generic")
            results.append({
                "type": test_type,
                "status": result.ingest_status,
                "chunks": len(result.chunks),
                "success": result.ingest_status in ["OK", "DEGRADED"]
            })
            total_chunks += len(result.chunks)
        except Exception as e:
            results.append({
                "type": test_type,
                "status": "FAILED",
                "error": str(e),
                "success": False
            })
    
    succeeded = sum(1 for r in results if r.get("success", False))
    
    return {
        "files_processed": len(results),
        "files_succeeded": succeeded,
        "files_failed": len(results) - succeeded,
        "total_chunks": total_chunks,
        "test_results": results
    }


def test_concurrent_queries():
    """Test concurrent query processing."""
    rag = TrustRAG(artifact_dir=get_paths().artifacts_dir)
    
    queries = [
        "What was Nvidia's revenue for FY2023?",
        "Calculate Nvidia's net profit margin",
        "What was Apple's revenue growth?",
        "Compare Microsoft and Google revenue"
    ] * 10  # 40 queries total
    
    def process_query(query):
        try:
            result = rag.process_query(query, risk_level="medium")
            return {
                "success": result.verdict != "REFUSED" or result.verdict == "VERIFIED",
                "verdict": result.verdict,
                "trace_id": result.trace_id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_query, q) for q in queries]
        results = [f.result() for f in as_completed(futures)]
    
    duration = time.time() - start_time
    succeeded = sum(1 for r in results if r.get("success", False))
    
    return {
        "queries_processed": len(queries),
        "queries_succeeded": succeeded,
        "queries_failed": len(queries) - succeeded,
        "throughput_qps": len(queries) / duration if duration > 0 else 0
    }


# ============================================================================
# Main Test Runner / 主测试运行器
# ============================================================================

def main():
    """Run all performance tests."""
    print("="*60)
    print("TrustRAG Extreme Cases Performance Tests")
    print("="*60)
    
    runner = PerformanceTestRunner()
    
    # Run tests
    runner.run_test(test_ultra_long_document, "Ultra-Long Document Test")
    runner.run_test(test_batch_large_files, "Batch Large Files Test")
    runner.run_test(test_special_formats, "Special Formats Test")
    runner.run_test(test_concurrent_queries, "Concurrent Queries Test")
    
    # Generate reports
    html_report = runner.generate_report("html")
    json_report = runner.generate_report("json")
    
    print("\n" + "="*60)
    print("Performance Tests Complete")
    print("="*60)
    print(f"HTML Report: {html_report}")
    print(f"JSON Report: {json_report}")
    
    # Summary
    total = len(runner.results)
    passed = sum(1 for r in runner.results if r.success)
    print(f"\nSummary: {passed}/{total} tests passed")


if __name__ == "__main__":
    main()

