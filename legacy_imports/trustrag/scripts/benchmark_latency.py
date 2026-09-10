#!/usr/bin/env python3
"""
benchmark_latency.py
Automated script for benchmarking TrustRAG API latency (Target: P95 300-450ms).
Simulates concurrent load on the retrieval and generation endpoints.
"""
import asyncio
import time
import statistics
import aiohttp
import argparse
import sys
import json
from typing import List

# Default test queries focusing on financial terminology
TEST_QUERIES = [
    "What is the total revenue of Tesla in Q3 2023?",
    "Summarize the risk factors mentioned in the latest 10-K report.",
    "Compare the operational expenses between FY2021 and FY2022.",
    "What are the forward-looking statements regarding supply chain disruptions?",
    "List the major acquisitions made by the company this year."
]

async def fire_query(session: aiohttp.ClientSession, url: str, query: str) -> float:
    """Send a single query to the API and measure latency."""
    payload = {
        "query": query,
        "chat_id": "benchmark_test",
        "stream": False
    }
    start = time.perf_counter()
    try:
        async with session.post(url, json=payload, timeout=60) as response:
            await response.text()  # Wait for full response
            if response.status != 200:
                print(f"Error {response.status} for query: {query}")
    except Exception as e:
        print(f"Request failed: {e}")
        
    end = time.perf_counter()
    return (end - start) * 1000 # returns milliseconds

async def run_benchmark(api_url: str, concurrency: int, runs_per_query: int) -> List[float]:
    latencies = []
    
    # Repeat the test queries to generate enough requests
    queries = TEST_QUERIES * runs_per_query
    q_iter = iter(queries)
    
    async with aiohttp.ClientSession() as session:
        async def worker():
            nonlocal latencies
            for query in q_iter:
                latency = await fire_query(session, api_url, query)
                latencies.append(latency)
                
        # Launch concurrent workers
        tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await asyncio.gather(*tasks)
        
    return latencies

def main():
    parser = argparse.ArgumentParser(description="TrustRAG Latency Benchmark")
    parser.add_argument("--url", default="http://localhost:8000/api/v1/chat/completions", help="API Endpoint URL")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--runs", type=int, default=10, help="Runs per test query")
    args = parser.parse_args()
    
    print(f"Starting Benchmark against {args.url}")
    print(f"Concurrency: {args.concurrency}, Total Requests: {len(TEST_QUERIES) * args.runs}")
    print("-" * 50)
    
    start_time = time.time()
    latencies = asyncio.run(run_benchmark(args.url, args.concurrency, args.runs))
    total_time = time.time() - start_time
    
    if not latencies:
        print("No successful requests. Benchmark failed.")
        sys.exit(1)
        
    latencies.sort()
    
    p50 = statistics.median(latencies)
    p90 = latencies[int(len(latencies) * 0.9)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    
    print("\n=== Benchmark Results ===")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Requests Processed: {len(latencies)}")
    print(f"Throughput: {len(latencies) / total_time:.2f} req/s")
    print("\n=== Latency Profile ===")
    print(f"P50: {p50:.2f} ms")
    print(f"P90: {p90:.2f} ms")
    print(f"P95: {p95:.2f} ms")
    print(f"P99: {p99:.2f} ms")
    print(f"Max: {max(latencies):.2f} ms")
    print(f"Min: {min(latencies):.2f} ms")
    
    # Output target requirement 
    if p95 <= 450:
        print("\n✅ PASSED: P95 Latency is within the 300-450ms target range!")
    else:
        print(f"\n❌ FAILED: P95 Latency ({p95:.2f}ms) exceeds the target maximum of 450ms.")
        
    # Write report
    report = {
        "timestamp": time.time(),
        "concurrency": args.concurrency,
        "total_requests": len(latencies),
        "metrics": {
            "p50_ms": p50,
            "p90_ms": p90,
            "p95_ms": p95,
            "p99_ms": p99,
            "throughput_rps": len(latencies) / total_time
        }
    }
    
    with open("benchmark_report.json", "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    main()
