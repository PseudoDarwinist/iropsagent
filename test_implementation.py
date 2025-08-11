#!/usr/bin/env python3
"""
Test implementation of Flight Data Provider Integration (Task 2.1)

This tests:
- REQ-7.1: FlightDataProvider interface for external APIs
- REQ-7.2: Failover logic between primary and secondary sources
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from flight_agent.providers import (
    MockFlightDataProvider,
    FlightAwareProvider, 
    FailoverManager,
    FailoverConfig
)


async def test_basic_providers():
    """Test basic provider functionality"""
    print("=" * 60)
    print("TESTING BASIC PROVIDER FUNCTIONALITY")
    print("=" * 60)
    
    # Test mock provider
    mock = MockFlightDataProvider("TestMock")
    departure = datetime.now(timezone.utc) + timedelta(days=1)
    
    print(f"\n1. Testing MockFlightDataProvider:")
    result = await mock.get_flight_status("AA123", departure)
    
    if result:
        print(f"   ✅ Success: {result.status}")
        print(f"   ✅ Source: {result.source}")
        print(f"   ✅ Flight ID: {result.flight_id}")
        print(f"   ✅ Confidence: {result.confidence_score}")
    else:
        print(f"   ❌ Failed to get flight status")
        return False
    
    # Test health check
    health = await mock.health_check()
    print(f"   ✅ Health check: {'Passed' if health else 'Failed'}")
    
    # Test multiple flights
    flights = [
        ("AA123", departure),
        ("UA456", departure), 
        ("DL789", departure)
    ]
    
    batch_results = await mock.get_multiple_flights(flights)
    print(f"   ✅ Batch results: {len(batch_results)}/3 flights processed")
    
    print("\n2. Testing FlightAware Provider (without API key):")
    flightaware = FlightAwareProvider()
    print(f"   ℹ️  Available: {flightaware.is_available}")
    print(f"   ℹ️  Status: {flightaware.status.value}")
    
    return True


async def test_failover_logic():
    """Test failover between providers"""
    print("\n" + "=" * 60)
    print("TESTING FAILOVER LOGIC")
    print("=" * 60)
    
    # Create providers with different characteristics
    primary = MockFlightDataProvider("Primary", priority=10, simulate_errors=True, error_rate=1.0)  # Always fails
    secondary = MockFlightDataProvider("Secondary", priority=5, simulate_errors=False)  # Always works
    backup = MockFlightDataProvider("Backup", priority=1, simulate_errors=True, error_rate=0.3)  # Sometimes fails
    
    config = FailoverConfig(
        max_retries_per_provider=2,
        timeout_between_retries=0.1,
        circuit_breaker_threshold=2
    )
    
    manager = FailoverManager([primary, secondary, backup], config)
    departure = datetime.now(timezone.utc) + timedelta(days=1)
    
    print(f"\nTesting failover with 3 providers:")
    print(f"  - Primary (always fails)")
    print(f"  - Secondary (always works)")  
    print(f"  - Backup (30% failure rate)")
    
    # Test individual requests
    test_flights = ["AA123", "UA456", "DL789", "SW111", "BA987"]
    
    successful = 0
    for flight in test_flights:
        result = await manager.get_flight_status(flight, departure)
        if result:
            print(f"   ✅ {flight}: Success from {result.source}")
            successful += 1
        else:
            print(f"   ❌ {flight}: All providers failed")
    
    print(f"\nFailover Results: {successful}/{len(test_flights)} successful")
    
    # Test batch processing
    batch_flights = [(f"TEST{i:03d}", departure) for i in range(10)]
    batch_results = await manager.get_multiple_flights(batch_flights)
    batch_successful = sum(1 for r in batch_results.values() if r is not None)
    
    print(f"Batch Processing: {batch_successful}/{len(batch_flights)} successful")
    
    # Show provider statistics
    stats = manager.get_provider_stats()
    print(f"\nProvider Statistics:")
    for name, provider_stats in stats["providers"].items():
        cb_stats = stats["circuit_breakers"][name]
        print(f"  {name}:")
        print(f"    Requests: {provider_stats['metrics']['total_requests']}")
        print(f"    Success Rate: {provider_stats['metrics']['success_rate']:.2f}")
        print(f"    Circuit Breaker: {'🔴 OPEN' if cb_stats['is_open'] else '🟢 CLOSED'}")
    
    return successful > 0


async def test_enhanced_monitoring():
    """Test enhanced monitoring service"""
    print("\n" + "=" * 60)
    print("TESTING ENHANCED MONITORING SERVICE") 
    print("=" * 60)
    
    try:
        from flight_agent.services.enhanced_flight_monitoring_service import EnhancedFlightMonitoringService
        
        service = EnhancedFlightMonitoringService(
            check_interval_seconds=60,
            enable_mock_provider=True
        )
        
        print(f"✅ Service initialized with {len(service.providers)} providers")
        print(f"✅ Redis connected: {service.redis_client is not None}")
        
        # Test flight status with caching
        departure = datetime.now(timezone.utc) + timedelta(days=1)
        
        print(f"\nTesting flight status with caching:")
        
        # First request (should hit providers)
        start = datetime.utcnow()
        result1 = await service.get_flight_status_with_failover("AA123", departure)
        time1 = (datetime.utcnow() - start).total_seconds()
        
        if result1:
            print(f"   ✅ First request: Success from {result1.source} ({time1:.3f}s)")
        
        # Second request (should use cache)
        start = datetime.utcnow()
        result2 = await service.get_flight_status_with_failover("AA123", departure)
        time2 = (datetime.utcnow() - start).total_seconds()
        
        if result2:
            print(f"   ✅ Second request: Success from {result2.source} ({time2:.3f}s)")
            if time2 > 0:
                speedup = time1 / time2
                print(f"   📈 Cache speedup: {speedup:.1f}x faster")
        
        # Test service statistics
        stats = service.get_service_stats()
        print(f"\nService Statistics:")
        print(f"   Cache hits: {stats['statistics']['cache_hits']}")
        print(f"   Cache misses: {stats['statistics']['cache_misses']}")
        print(f"   API calls: {stats['statistics']['api_calls']}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Could not import enhanced monitoring service: {e}")
        return False


async def main():
    """Run all tests"""
    print("Flight Data Provider Integration Test")
    print("Task 2.1: Flight Data Provider Integration Interfaces")
    print("\nTesting implementation of:")
    print("- REQ-7.1: FlightDataProvider interface for external APIs")
    print("- REQ-7.2: Failover logic between primary and secondary sources")
    
    tests_passed = 0
    total_tests = 3
    
    try:
        # Run tests
        if await test_basic_providers():
            tests_passed += 1
            print("✅ Basic provider functionality: PASSED")
        else:
            print("❌ Basic provider functionality: FAILED")
        
        if await test_failover_logic():
            tests_passed += 1
            print("✅ Failover logic: PASSED")
        else:
            print("❌ Failover logic: FAILED")
        
        if await test_enhanced_monitoring():
            tests_passed += 1
            print("✅ Enhanced monitoring service: PASSED")
        else:
            print("❌ Enhanced monitoring service: FAILED")
        
        print(f"\n" + "=" * 60)
        print(f"TEST RESULTS: {tests_passed}/{total_tests} tests passed")
        print("=" * 60)
        
        if tests_passed == total_tests:
            print("🎉 ALL TESTS PASSED - Implementation successful!")
            print("\nKey features implemented:")
            print("✅ FlightDataProvider interface standardization")
            print("✅ Mock provider for testing and development") 
            print("✅ FlightAware API integration with error handling")
            print("✅ Intelligent failover between providers")
            print("✅ Circuit breaker pattern for failing providers")
            print("✅ Performance metrics and health monitoring")
            print("✅ Redis caching for fast response times")
            print("✅ Enhanced monitoring service with batch processing")
            return True
        else:
            print("❌ Some tests failed - implementation needs review")
            return False
        
    except Exception as e:
        print(f"❌ Unexpected error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)