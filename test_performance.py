"""
Performance test script for /v1/quotes endpoint.

Tests the p50, p95, and p99 latencies to ensure < 250ms for p50.
"""

import httpx
import time
import statistics
from typing import List

API_URL = "http://localhost:8000"
API_KEY = "KLARITY_TEST_KEY"  # Using ptnr_klarity from seed.json

def test_single_request(client, payload, headers):
    """Test a single request and return timing + response."""
    start = time.time()
    try:
        response = client.post(
            f"{API_URL}/v1/quotes",
            json=payload,
            headers=headers,
            timeout=10.0
        )
        elapsed_ms = (time.time() - start) * 1000
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
            "server_time": response.headers.get("X-Response-Time-Ms"),
            "response_data": response.json() if response.status_code == 200 else None,
            "error": response.text if response.status_code != 200 else None
        }
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        return {
            "success": False,
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "server_time": None,
            "response_data": None,
            "error": str(e)
        }

def validate_payloads():
    """First validate that both payloads work."""
    print("Validating payloads...")
    print("=" * 60)
    
    # Flat structure per API requirements
    shipping_payload = {
        "product_code": "shipping",
        "partner_id": "ptnr_klarity",
        "declared_value": 5000.0,
        "item_category": "standard",
        "destination_state": "CA",
        "destination_risk": "low",
        "service_level": "ground"
    }
    
    ppi_payload = {
        "product_code": "ppi",
        "partner_id": "ptnr_klarity",
        "order_value": 10000.0,
        "term_months": 6,
        "age": 30,
        "tenure_months": 12,
        "job_category": "professional",
        "state": "NY"
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": "validation-test-1"
    }
    
    with httpx.Client() as client:
        # Test shipping
        result = test_single_request(client, shipping_payload, headers)
        if result["success"]:
            print(f"✓ Shipping payload valid ({result['elapsed_ms']:.2f}ms)")
            print(f"  Response: {result['response_data']}")
        else:
            print(f"✗ Shipping payload FAILED: {result['status_code']}")
            print(f"  Error: {result['error'][:200] if result['error'] else 'Unknown'}")
            return False
        
        print()
        
        # Test PPI
        headers["X-Idempotency-Key"] = "validation-test-2"
        result = test_single_request(client, ppi_payload, headers)
        if result["success"]:
            print(f"✓ PPI payload valid ({result['elapsed_ms']:.2f}ms)")
            print(f"  Response: {result['response_data']}")
        else:
            print(f"✗ PPI payload FAILED: {result['status_code']}")
            print(f"  Error: {result['error'][:200] if result['error'] else 'Unknown'}")
            return False
    
    print()
    return True

def test_quote_performance(num_requests: int = 100) -> List[float]:
    """
    Test quote endpoint performance.
    
    Args:
        num_requests: Number of requests to make
        
    Returns:
        List of response times in milliseconds
    """
    times = []
    failures = []
    
    # Test shipping quote - flat structure per API requirements
    shipping_payload = {
        "product_code": "shipping",
        "partner_id": "ptnr_klarity",
        "declared_value": 5000.0,
        "item_category": "standard",
        "destination_state": "CA",
        "destination_risk": "low",
        "service_level": "ground"
    }
    
    # Test PPI quote - flat structure per API requirements
    ppi_payload = {
        "product_code": "ppi",
        "partner_id": "ptnr_klarity",
        "order_value": 10000.0,
        "term_months": 6,
        "age": 30,
        "tenure_months": 12,
        "job_category": "professional",
        "state": "NY"
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"Running {num_requests} requests to /v1/quotes...")
    print("=" * 60)
    
    with httpx.Client() as client:
        for i in range(num_requests):
            # Alternate between shipping and PPI
            payload = shipping_payload if i % 2 == 0 else ppi_payload
            product_type = "shipping" if i % 2 == 0 else "ppi"
            
            # Add unique idempotency key to avoid caching
            headers["X-Idempotency-Key"] = f"perf-test-{i}"
            
            result = test_single_request(client, payload, headers)
            
            if result["success"]:
                times.append(result["elapsed_ms"])
                
                if i % 10 == 0 or i < 5:
                    print(f"Request {i+1} ({product_type}): {result['elapsed_ms']:.2f}ms "
                          f"(server: {result['server_time']}ms)")
                    if i % 10 == 0:  # Print full response for first 5 requests
                        print(f"  Response: {result['response_data']}")
            else:
                failures.append({
                    "request_num": i + 1,
                    "product": product_type,
                    "status": result["status_code"],
                    "error": result["error"]
                })
                if i < 5:  # Print first few failures for debugging
                    print(f"Request {i+1} ({product_type}) FAILED: {result['status_code']}")
    
    # Print failure summary if any
    if failures:
        print()
        print("=" * 60)
        print(f"WARNING: {len(failures)} requests failed!")
        print("=" * 60)
        print("First failure details:")
        first_failure = failures[0]
        print(f"Request {first_failure['request_num']} ({first_failure['product']}): "
              f"Status {first_failure['status']}")
        print(f"Error: {first_failure['error'][:300] if first_failure['error'] else 'Unknown'}")
        print()
    
    return times

def calculate_percentiles(times: List[float]) -> dict:
    """Calculate performance percentiles."""
    if not times:
        return {}
    
    sorted_times = sorted(times)
    
    return {
        "count": len(times),
        "min": min(times),
        "max": max(times),
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "p50": sorted_times[int(len(sorted_times) * 0.50)],
        "p75": sorted_times[int(len(sorted_times) * 0.75)],
        "p90": sorted_times[int(len(sorted_times) * 0.90)],
        "p95": sorted_times[int(len(sorted_times) * 0.95)],
        "p99": sorted_times[int(len(sorted_times) * 0.99)],
    }

def main():
    """Run performance tests."""
    print("Embedded Insurance API - Performance Test")
    print("=" * 60)
    print()
    
    # Wait for server to be ready
    print("Waiting for server to be ready...")
    max_retries = 10
    for i in range(max_retries):
        try:
            response = httpx.get(f"{API_URL}/health", timeout=2.0)
            if response.status_code == 200:
                print("✓ Server is ready")
                break
        except Exception:
            if i < max_retries - 1:
                time.sleep(1)
            else:
                print("✗ Server not responding after 10 seconds")
                return
    
    print()
    
    # First validate payloads work
    if not validate_payloads():
        print("✗ Payload validation failed - aborting performance test")
        return
    
    # Run performance test
    times = test_quote_performance(num_requests=100)
    
    if not times:
        print("✗ No successful requests")
        return
    
    # Calculate and display results
    print()
    print("=" * 60)
    print("PERFORMANCE RESULTS")
    print("=" * 60)
    
    stats = calculate_percentiles(times)
    
    print(f"Requests completed: {stats['count']}/100 ({stats['count']}%)")
    print(f"Min:    {stats['min']:.2f} ms")
    print(f"Mean:   {stats['mean']:.2f} ms")
    print(f"Median: {stats['median']:.2f} ms")
    print(f"p50:    {stats['p50']:.2f} ms")
    print(f"p75:    {stats['p75']:.2f} ms")
    print(f"p90:    {stats['p90']:.2f} ms")
    print(f"p95:    {stats['p95']:.2f} ms")
    print(f"p99:    {stats['p99']:.2f} ms")
    print(f"Max:    {stats['max']:.2f} ms")
    print()
    
    # Check against target
    target_p50 = 250.0
    if stats['count'] < 95:
        print(f"⚠ WARNING: Only {stats['count']}/100 requests succeeded")
        print(f"  Performance metrics may not be representative")
        print()
    
    if stats['p50'] < target_p50:
        print(f"✓ PASS: p50 ({stats['p50']:.2f}ms) < {target_p50}ms target")
    else:
        print(f"✗ FAIL: p50 ({stats['p50']:.2f}ms) >= {target_p50}ms target")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
