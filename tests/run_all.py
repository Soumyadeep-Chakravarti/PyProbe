import unittest
import sys

def run_suite():
    """Discover and run all Python tests in the tests/ directory."""
    print("PyProbe — Test Runner")
    print("=" * 40)
    
    # Discovery
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')
    
    # Run
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 40)
    if result.wasSuccessful():
        print("ALL PASSED")
    else:
        print(f"FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 40)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_suite()
    sys.exit(0 if success else 1)
