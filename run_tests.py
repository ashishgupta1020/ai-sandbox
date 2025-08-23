#!/usr/bin/env python3
"""
Simple test runner for task_manager.py
"""

import sys
import subprocess
import os

def run_tests():
    """Run all tests for task_manager.py"""
    print("🧪 Running tests for JIRA-like Task Manager...")
    print("=" * 60)
    
    # Check if test file exists
    if not os.path.exists("test_task_manager.py"):
        print("❌ Error: test_task_manager.py not found!")
        return False
    
    # Run the tests
    try:
        result = subprocess.run(
            [sys.executable, "test_task_manager.py"],
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # Check result
        if result.returncode == 0:
            print("✅ All tests passed!")
            return True
        else:
            print(f"❌ Tests failed with exit code: {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Tests timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def run_specific_test(test_name):
    """Run a specific test"""
    print(f"🧪 Running specific test: {test_name}")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", f"test_task_manager.{test_name}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✅ Test passed!")
            return True
        else:
            print(f"❌ Test failed with exit code: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
    else:
        # Run all tests
        success = run_tests()
    
    sys.exit(0 if success else 1)
