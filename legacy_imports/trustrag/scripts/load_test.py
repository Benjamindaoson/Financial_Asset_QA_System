import os
import sys
import time
import requests
import concurrent.futures
import json
from datetime import datetime

# Configure staging API endpoint
API_URL = os.getenv("TRUSTRAG_API_URL", "http://localhost:8000/api/v1")
CONCURRENT_USERS = int(os.getenv("LOAD_TEST_USERS", "5"))
REQUESTS_PER_USER = int(os.getenv("LOAD_TEST_REQUESTS", "5"))

# Wait for the API to be ready
def wait_for_api(timeout=60):
    print(f"Waiting for API to be ready at {API_URL}/health...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"http://localhost:8000/api/health", timeout=2)
            if r.status_code == 200:
                print("✅ API is healthy and ready to accept traffic.")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
        print(".", end="", flush=True)
    
    print("\n❌ API failed to become ready in time.")
    return False

# Simulate a user performing queries
def simulate_user(user_id):
    queries = [
        "What is the net profit of Apple in 2023?",
        "Can you compare the revenue of Google and Microsoft?",
        "What are the risk factors mentioned in the recent annual report?",
        "Tell me about the CEO's statement regarding AI.",
        "What is the total asset valuation based on the audit?"
    ]
    
    results = {
        "user_id": user_id,
        "success": 0,
        "failed": 0,
        "latencies": []
    }
    
    for i in range(REQUESTS_PER_USER):
        query = queries[i % len(queries)]
        payload = {"query": query, "stream": False}
        
        start_time = time.time()
        try:
            # We assume a standard POST /query endpoint exists.
            # Modify to match the exact Swagger spec of TrustRAG if different.
            response = requests.post(f"{API_URL}/query", json=payload, timeout=30)
            latency = time.time() - start_time
            results["latencies"].append(latency)
            
            if response.status_code == 200:
                results["success"] += 1
                # print(f"[User {user_id}] Query {i+1} succeeded in {latency:.2f}s")
            else:
                results["failed"] += 1
                print(f"[User {user_id}] Query {i+1} failed with status {response.status_code}: {response.text}")
        except Exception as e:
            latency = time.time() - start_time
            results["latencies"].append(latency)
            results["failed"] += 1
            print(f"[User {user_id}] Query {i+1} encountered exception: {e}")
            
        # Think time
        time.sleep(1)
        
    return results

def main():
    print("==========================================================")
    print("🔥 TrustRAG Staging End-to-End Load Test")
    print(f"URL: {API_URL}")
    print(f"Concurrent Users: {CONCURRENT_USERS}")
    print(f"Requests per User: {REQUESTS_PER_USER}")
    print("==========================================================")
    
    # Optional wait if spinning up Docker containers currently
    if not wait_for_api():
        sys.exit(1)
        
    print(f"\n🚀 Starting load test at {datetime.now()}...")
    overall_start = time.time()
    
    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
        futures = [executor.submit(simulate_user, i) for i in range(CONCURRENT_USERS)]
        
        for future in concurrent.futures.as_completed(futures):
            all_results.append(future.result())
            
    overall_duration = time.time() - overall_start
    
    # Calculate aggregate metrics
    total_success = sum(r["success"] for r in all_results)
    total_failed = sum(r["failed"] for r in all_results)
    all_latencies = [l for r in all_results for l in r["latencies"]]
    
    avg_latency = sum(all_latencies) / len(all_latencies) if all_latencies else 0
    max_latency = max(all_latencies) if all_latencies else 0
    min_latency = min(all_latencies) if all_latencies else 0
    
    requests_per_second = (total_success + total_failed) / overall_duration if overall_duration > 0 else 0
    
    print("\n==========================================================")
    print("📊 Load Test Results")
    print("==========================================================")
    print(f"Total Time:         {overall_duration:.2f}s")
    print(f"Total Requests:     {total_success + total_failed}")
    print(f"Successful:         {total_success}")
    print(f"Failed:             {total_failed}")
    print(f"Troughput:          {requests_per_second:.2f} req/s")
    print(f"Average Latency:    {avg_latency:.2f}s")
    print(f"Min Latency:        {min_latency:.2f}s")
    print(f"Max Latency:        {max_latency:.2f}s")
    print("==========================================================")
    
    if total_failed > 0:
        print("⚠️ Test finished with some failures. Check API logs for details.")
        sys.exit(1)
    else:
        print("✅ All requests succeeded! System is stable under load.")
        sys.exit(0)

if __name__ == "__main__":
    main()
