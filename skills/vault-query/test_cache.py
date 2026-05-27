#!/usr/bin/env python3
"""
Test script for VaultCache.

Tests:
1. First call reads from disk (slower)
2. Second call returns cached (should be < 10ms)
3. Invalidation on mtime change works
4. Force refresh bypasses cache
"""

import os
import sys
import time
import tempfile
from pathlib import Path

# Add skills dir to path
sys.path.insert(0, str(Path(__file__).parent))

from vault_cache import VaultCache


def test_cache_timing():
    """Test that second call is cached (fast)."""
    print("\n=== Test 1: Cache Timing ===")
    
    # Use actual vault path
    cache = VaultCache()
    index_path = cache._get_index_path()
    
    print(f"Using index: {index_path}")
    
    # First call — from disk
    start1 = time.perf_counter()
    content1 = cache.get_index()
    time1 = (time.perf_counter() - start1) * 1000
    
    assert content1 is not None, "Failed to read index.md"
    print(f"First call (disk read):  {time1:.2f}ms")
    
    # Second call — from cache
    start2 = time.perf_counter()
    content2 = cache.get_index()
    time2 = (time.perf_counter() - start2) * 1000
    
    assert content1 == content2, "Cached content differs!"
    print(f"Second call (cached):    {time2:.2f}ms")
    
    # Verify cached is faster
    if time2 < 10:
        print(f"✓ PASS: Cached call < 10ms ({time2:.2f}ms)")
        return True
    else:
        print(f"✗ FAIL: Cached call >= 10ms ({time2:.2f}ms)")
        return False


def test_invalidation_on_mtime_change():
    """Test that cache is invalidated when mtime changes."""
    print("\n=== Test 2: Invalidation on mtime change ===")
    
    # Create temp file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("initial content")
        temp_path = f.name
    
    try:
        # Create cache with temp file
        cache = VaultCache(vault_path=str(Path(temp_path).parent))
        
        # Override index path to our temp file
        cache._cache_key = lambda p: temp_path
        cache._vault_path = str(Path(temp_path).parent)
        
        # Patch _get_index_path
        original_get = cache._get_index_path
        cache._get_index_path = lambda: Path(temp_path)
        
        # First read
        start1 = time.perf_counter()
        content1 = cache.get_index()
        time1 = (time.perf_counter() - start1) * 1000
        print(f"First read: {time1:.2f}ms, content: {repr(content1[:20])}")
        
        # Modify file (change mtime)
        time.sleep(0.1)  # Ensure different mtime
        Path(temp_path).write_text("modified content")
        
        # Read again — should get new content
        start2 = time.perf_counter()
        content2 = cache.get_index()
        time2 = (time.perf_counter() - start2) * 1000
        
        print(f"After mtime change: {time2:.2f}ms, content: {repr(content2[:20])}")
        
        if content2 == "modified content":
            print("✓ PASS: Cache invalidated on mtime change")
            return True
        else:
            print("✗ FAIL: Still returning stale content")
            return False
            
    finally:
        os.unlink(temp_path)


def test_force_refresh():
    """Test force_refresh bypasses cache."""
    print("\n=== Test 3: Force Refresh ===")
    
    cache = VaultCache()
    
    # First call
    content1 = cache.get_index()
    
    # Force refresh
    content2 = cache.get_index(force_refresh=True)
    
    if content1 == content2:
        print("✓ PASS: Force refresh returns same content")
        return True
    else:
        print("✗ FAIL: Content differs")
        return False


def test_thread_safety():
    """Test cache is thread-safe."""
    print("\n=== Test 4: Thread Safety ===")
    
    import threading
    
    cache = VaultCache()
    results = []
    errors = []
    
    def read_cache():
        try:
            content = cache.get_index()
            results.append(content)
        except Exception as e:
            errors.append(str(e))
    
    # Run 10 threads simultaneously
    threads = [threading.Thread(target=read_cache) for _ in range(10)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    if errors:
        print(f"✗ FAIL: Errors occurred: {errors}")
        return False
    
    # All results should be identical
    if all(r == results[0] for r in results):
        print(f"✓ PASS: All 10 threads got same result")
        return True
    else:
        print("✗ FAIL: Results differ between threads")
        return False


def main():
    print("VaultCache Test Suite")
    print("=" * 50)
    
    results = []
    
    results.append(("Cache Timing", test_cache_timing()))
    results.append(("Mtime Invalidation", test_invalidation_on_mtime_change()))
    results.append(("Force Refresh", test_force_refresh()))
    results.append(("Thread Safety", test_thread_safety()))
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
