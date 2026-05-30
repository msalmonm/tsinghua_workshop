#!/usr/bin/env python3
"""
Test the complete RAG Health & Fitness system
"""

import os
import sys
import subprocess

def run_command(cmd, description):
    """Run a command and display results"""
    print("\n" + "=" * 70)
    print(f"TEST: {description}")
    print("=" * 70)
    print(f"Command: {cmd}\n")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"\n✓ {description} - SUCCESS")
            return True
        else:
            print(f"\n✗ {description} - FAILED (exit code: {result.returncode})")
            return False
    
    except subprocess.TimeoutExpired:
        print(f"\n✗ {description} - TIMEOUT (exceeded 120 seconds)")
        return False
    except Exception as e:
        print(f"\n✗ {description} - ERROR: {e}")
        return False

def main():
    """Run complete system test"""
    
    print("=" * 70)
    print("RAG HEALTH & FITNESS ENGINE - COMPLETE SYSTEM TEST")
    print("=" * 70)
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("\n✗ ERROR: .env file not found")
        print("Please create .env file with required credentials")
        sys.exit(1)
    
    print("\n✓ .env file found")
    
    # Test 1: Run crawler
    test1 = run_command(
        "python crawler.py",
        "Data Crawler - Index exercises and recipes"
    )
    
    if not test1:
        print("\n✗ Crawler failed - cannot continue with query tests")
        sys.exit(1)
    
    # Test 2: Run query for muscle building
    test2 = run_command(
        'python query.py "I want to build muscle and lose fat"',
        "Query Test 1 - Muscle building and fat loss"
    )
    
    # Test 3: Run query for cardio
    test3 = run_command(
        'python query.py "What exercises and meals are good for cardio fitness?"',
        "Query Test 2 - Cardio fitness"
    )
    
    # Test 4: Run query for beginners
    test4 = run_command(
        'python query.py "I am a beginner, what should I start with?"',
        "Query Test 3 - Beginner recommendations"
    )
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    tests = [
        ("Crawler", test1),
        ("Query Test 1 (Muscle building)", test2),
        ("Query Test 2 (Cardio)", test3),
        ("Query Test 3 (Beginner)", test4)
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for name, result in tests:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status} - {name}")
    
    print("\n" + "=" * 70)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is working correctly.")
        sys.exit(0)
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Please review the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
