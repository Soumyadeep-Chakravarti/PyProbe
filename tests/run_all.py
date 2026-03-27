import unittest
import sys
import os

def run_suite():
    """Discover and run all Python tests in the tests/ directory."""
    print("="*60)
    print("PyProbe Memory Interpreter: Unified Test Runner".center(60))
    print("="*60)
    
    # Discovery
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')
    
    # Run
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    if result.wasSuccessful():
        print("ALL TESTS PASSED! Memory engine is stable.".center(60))
    else:
        print(f"FAILED: {len(result.failures)} failures, {len(result.errors)} errors.".center(60))
    print("="*60)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_suite()
    sys.exit(0 if success else 1)
