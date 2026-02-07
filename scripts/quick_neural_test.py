#!/usr/bin/env python3
"""
QUICK NEURAL TEST - Verify Neural Core Installation
Run this after setup to verify all components work correctly.

Usage: python scripts/quick_neural_test.py

Author: ReviewSignal Team
Version: 5.1.0
Date: February 2026
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from datetime import datetime


def print_header(text: str):
    print("\n" + "━"*60)
    print(f"  {text}")
    print("━"*60)


def print_result(test: str, passed: bool, details: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {test}")
    if details:
        print(f"         {details}")


def test_neural_core():
    """Test Neural Core basic functionality"""
    print_header("TEST 1: Neural Core Import & Initialize")

    try:
        from modules.neural_core import NeuralCore, get_neural_core
        core = get_neural_core()
        print_result("Import neural_core", True)
        print_result("Initialize NeuralCore", True, f"Config loaded")
        return core
    except Exception as e:
        print_result("Neural Core", False, str(e))
        return None


def test_embeddings(core):
    """Test MiniLM embeddings"""
    print_header("TEST 2: MiniLM Embeddings")

    if core is None:
        print_result("Skipped", False, "Neural Core not available")
        return False

    try:
        start = time.time()
        text = "This restaurant has amazing food and great service"
        embedding = core.embed(text)

        elapsed = (time.time() - start) * 1000
        print_result("Generate embedding", True, f"Shape: {embedding.shape}, Time: {elapsed:.0f}ms")

        # Test similarity
        text2 = "Delicious meals with excellent customer service"
        sim = core.similarity(text, text2)
        print_result("Similarity calculation", True, f"Score: {sim:.4f}")

        # Test batch
        texts = ["Good food", "Bad service", "Average experience"]
        embeddings = core.embed_batch(texts)
        print_result("Batch embedding", True, f"{len(texts)} texts → {embeddings.shape}")

        return True
    except Exception as e:
        print_result("Embeddings", False, str(e))
        return False


def test_incremental_stats(core):
    """Test incremental statistics"""
    print_header("TEST 3: Incremental Statistics")

    if core is None:
        print_result("Skipped", False, "Neural Core not available")
        return False

    try:
        # Add some test values
        import numpy as np
        np.random.seed(42)

        entity_id = f"test_loc_{datetime.now().strftime('%H%M%S')}"

        for i in range(30):
            value = np.random.normal(4.0, 0.3)
            stats = core.update_stats(entity_id, value)

        print_result("Update statistics", True, f"Count: {stats.count}, Mean: {stats.mean:.4f}")
        print_result("Calculate std", True, f"Std: {stats.std:.4f}")
        print_result("Detect trend", True, f"Trend: {stats.trend_direction}")

        # Test anomaly detection
        anomaly = core.check_anomaly(entity_id, 2.0)  # Unusual low value
        print_result("Anomaly detection", True, f"Is anomaly: {anomaly.is_anomaly}, Score: {anomaly.anomaly_score:.4f}")

        return True
    except Exception as e:
        print_result("Statistics", False, str(e))
        return False


def test_cache(core):
    """Test Redis cache"""
    print_header("TEST 4: Redis Cache")

    if core is None:
        print_result("Skipped", False, "Neural Core not available")
        return False

    try:
        # First embedding (should compute)
        text = f"Cache test text {datetime.now().isoformat()}"

        start1 = time.time()
        result1 = core.embeddings.embed(text, use_cache=True)
        time1 = (time.time() - start1) * 1000

        # Second embedding (should use cache)
        start2 = time.time()
        result2 = core.embeddings.embed(text, use_cache=True)
        time2 = (time.time() - start2) * 1000

        print_result("First call (compute)", True, f"Time: {time1:.0f}ms, From cache: {result1.from_cache}")
        print_result("Second call (cache)", True, f"Time: {time2:.0f}ms, From cache: {result2.from_cache}")

        # Cache stats
        cache_stats = core.cache.get_cache_stats()
        print_result("Cache stats", True, f"Hit rate: {cache_stats['hit_rate']:.2%}")

        return True
    except Exception as e:
        print_result("Cache", False, str(e))
        return False


def test_isolation_forest(core):
    """Test Adaptive Isolation Forest"""
    print_header("TEST 5: Isolation Forest")

    if core is None:
        print_result("Skipped", False, "Neural Core not available")
        return False

    try:
        import numpy as np

        # Add training samples
        for _ in range(150):
            sample = np.random.normal(0, 1, 5)  # 5 features
            core.add_training_sample(sample)

        print_result("Add training samples", True, "150 samples added")

        # Refit
        refit_result = core.weekly_refit()
        print_result("Refit model", True, f"Status: {refit_result.get('status')}")

        # Predict
        normal_sample = np.random.normal(0, 1, 5)
        anomaly_sample = np.array([10, 10, 10, 10, 10])  # Clearly anomalous

        is_anomaly_normal, score_normal = core.predict_anomaly(normal_sample)
        is_anomaly_anom, score_anom = core.predict_anomaly(anomaly_sample)

        print_result("Normal sample", True, f"Anomaly: {is_anomaly_normal}, Score: {score_normal:.4f}")
        print_result("Anomaly sample", True, f"Anomaly: {is_anomaly_anom}, Score: {score_anom:.4f}")

        return True
    except Exception as e:
        print_result("Isolation Forest", False, str(e))
        return False


def test_api_endpoint():
    """Test Neural API endpoint"""
    print_header("TEST 6: Neural API (Port 8005)")

    try:
        import urllib.request
        import json

        # Health check
        try:
            with urllib.request.urlopen("http://localhost:8005/health", timeout=5) as response:
                data = json.loads(response.read().decode())
                print_result("Health endpoint", True, f"Status: {data.get('status')}")
        except Exception as e:
            print_result("Health endpoint", False, str(e))
            return False

        # Embed endpoint
        try:
            req_data = json.dumps({"text": "test embedding"}).encode()
            req = urllib.request.Request(
                "http://localhost:8005/api/neural/embed",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                print_result("Embed endpoint", True, f"Dimension: {data.get('dimension')}")
        except Exception as e:
            print_result("Embed endpoint", False, str(e))

        return True
    except Exception as e:
        print_result("API", False, str(e))
        return False


def test_integration():
    """Test Echo-Neural Bridge integration"""
    print_header("TEST 7: Echo-Neural Bridge")

    try:
        from modules.echo_neural_bridge import EchoNeuralBridge

        bridge = EchoNeuralBridge()
        health = bridge.health_check()

        print_result("Bridge initialization", True, f"Status: {health.get('status')}")
        print_result("Neural Core connected", health['neural_core']['status'] == 'healthy', "")

        # Test review analysis
        test_reviews = [
            {"text": "Great food!", "rating": 5.0, "location_id": "loc_1"},
            {"text": "Terrible!", "rating": 1.0, "location_id": "loc_2"},
        ]

        analysis = bridge.analyze_brand_reviews("TestBrand", test_reviews)
        print_result("Brand analysis", True, f"Coherence: {analysis.get('semantic_coherence', 0):.4f}")

        return True
    except Exception as e:
        print_result("Integration", False, str(e))
        return False


def main():
    """Run all tests"""
    print("\n" + "═"*60)
    print("  NEURAL CORE - INSTALLATION VERIFICATION")
    print("  ReviewSignal 5.1.0")
    print("═"*60)

    start_time = time.time()
    results = []

    # Run tests
    core = test_neural_core()
    results.append(("Neural Core", core is not None))

    results.append(("Embeddings", test_embeddings(core)))
    results.append(("Statistics", test_incremental_stats(core)))
    results.append(("Cache", test_cache(core)))
    results.append(("Isolation Forest", test_isolation_forest(core)))
    results.append(("API", test_api_endpoint()))
    results.append(("Integration", test_integration()))

    # Summary
    elapsed = time.time() - start_time
    passed = sum(1 for _, p in results if p)
    total = len(results)

    print("\n" + "═"*60)
    print("  SUMMARY")
    print("═"*60)
    print(f"\n  Tests: {passed}/{total} passed")
    print(f"  Time: {elapsed:.2f}s")
    print()

    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")

    print()

    if passed == total:
        print("  🎉 ALL TESTS PASSED - Neural Core is ready!")
    else:
        print("  ⚠️  Some tests failed. Check the output above.")

    print("\n" + "═"*60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
