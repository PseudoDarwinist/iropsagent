#!/usr/bin/env python3
"""
Flight Data Provider Integration Example

This example demonstrates how to use the new flight data provider interfaces
and failover logic implemented in task 2.1.

Shows:
- REQ-7.1: FlightDataProvider interface for external APIs
- REQ-7.2: Failover logic between primary and secondary sources
- Mock provider for testing and development
- Integration with enhanced monitoring service
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from flight_agent.providers import (
    FlightDataProvider,
    FlightAwareProvider,
    MockFlightDataProvider,
    FailoverManager,
    FailoverConfig
)
from flight_agent.services.enhanced_flight_monitoring_service import EnhancedFlightMonitoringService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demonstrate_individual_providers():
    """Demonstrate using individual providers"""
    print("\n" + "="*60)
    print("DEMONSTRATING INDIVIDUAL PROVIDERS")
    print("="*60)
    
    # Create providers
    flightaware = FlightAwareProvider(priority=10)
    mock_primary = MockFlightDataProvider("MockPrimary", priority=8)
    mock_backup = MockFlightDataProvider("MockBackup", priority=5, simulate_errors=True, error_rate=0.3)
    
    providers = [flightaware, mock_primary, mock_backup]
    departure_date = datetime.now(timezone.utc) + timedelta(days=1)
    
    print(f"\nTesting flight AA123 scheduled for {departure_date.strftime('%Y-%m-%d %H:%M')}")
    
    for provider in providers:
        print(f"\n--- Testing {provider.name} (Priority: {provider.priority}) ---")
        print(f"Available: {provider.is_available}")
        
        if not provider.is_available:
            print("Provider unavailable, skipping...")
            continue
        
        try:
            # Test health check
            health = await provider.health_check()
            print(f"Health Check: {'✅ Healthy' if health else '❌ Unhealthy'}")
            
            # Test flight status
            start_time = datetime.utcnow()
            result = await provider.get_flight_status("AA123", departure_date)
            end_time = datetime.utcnow()
            
            response_time = (end_time - start_time).total_seconds()
            
            if result:
                print(f"✅ Success ({response_time:.2f}s)")
                print(f"   Status: {result.status}")
                print(f"   Disrupted: {result.is_disrupted}")
                print(f"   Source: {result.source}")
                print(f"   Confidence: {result.confidence_score:.2f}")
                if result.delay_minutes > 0:
                    print(f"   Delay: {result.delay_minutes} minutes")
            else:
                print(f"❌ No data returned ({response_time:.2f}s)")
            
            # Show metrics
            metrics = provider.metrics
            print(f"   Metrics: {metrics.total_requests} requests, {metrics.success_rate:.2f} success rate")
            
        except Exception as e:
            print(f"❌ Error: {e}")


async def demonstrate_failover_manager():
    """Demonstrate failover manager with circuit breaker"""
    print("\n" + "="*60)
    print("DEMONSTRATING FAILOVER MANAGER")
    print("="*60)
    
    # Create providers with different characteristics
    providers = [
        FlightAwareProvider(priority=10),  # May not have API key
        MockFlightDataProvider("ReliableMock", priority=8, simulate_errors=False),
        MockFlightDataProvider("UnreliableMock", priority=5, simulate_errors=True, error_rate=0.7),
        MockFlightDataProvider("BackupMock", priority=1, simulate_errors=False)
    ]
    
    # Configure failover with aggressive settings for demonstration
    config = FailoverConfig(
        max_retries_per_provider=2,
        timeout_between_retries=0.5,
        circuit_breaker_threshold=2,  # Open after 2 failures
        circuit_breaker_timeout=10     # Reset after 10 seconds
    )
    
    failover_manager = FailoverManager(providers, config)
    departure_date = datetime.now(timezone.utc) + timedelta(days=1)
    
    print(f"\nTesting failover with {len(providers)} providers")
    print("Configuration:")
    print(f"  - Max retries per provider: {config.max_retries_per_provider}")
    print(f"  - Circuit breaker threshold: {config.circuit_breaker_threshold}")
    
    # Test individual requests
    print(f"\n--- Individual Flight Status Requests ---")
    test_flights = ["AA123", "UA456", "DL789", "SW111", "AA999"]  # AA999 triggers mock error
    
    for flight_number in test_flights:
        print(f"\nTesting {flight_number}:")
        try:
            start_time = datetime.utcnow()
            result = await failover_manager.get_flight_status(flight_number, departure_date)
            end_time = datetime.utcnow()
            
            response_time = (end_time - start_time).total_seconds()
            
            if result:
                print(f"  ✅ Success from {result.source} ({response_time:.2f}s)")
                print(f"     Status: {result.status}")
                if result.is_disrupted:
                    print(f"     🚨 Disrupted: {result.disruption_type}")
            else:
                print(f"  ❌ All providers failed ({response_time:.2f}s)")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Test batch requests
    print(f"\n--- Batch Flight Status Requests ---")
    batch_requests = [(f"AA{i:03d}", departure_date) for i in range(100, 105)]
    
    print(f"Requesting status for {len(batch_requests)} flights in batch...")
    start_time = datetime.utcnow()
    batch_results = await failover_manager.get_multiple_flights(batch_requests)
    end_time = datetime.utcnow()
    
    batch_time = (end_time - start_time).total_seconds()
    successful = sum(1 for result in batch_results.values() if result is not None)
    
    print(f"Batch results: {successful}/{len(batch_requests)} successful ({batch_time:.2f}s total)")
    print(f"Average per flight: {batch_time/len(batch_requests):.2f}s")
    
    # Show provider statistics
    print(f"\n--- Provider Statistics ---")
    stats = failover_manager.get_provider_stats()
    
    for provider_name, provider_stats in stats["providers"].items():
        circuit_breaker = stats["circuit_breakers"][provider_name]
        performance = stats["performance_summary"][provider_name]
        
        print(f"\n{provider_name}:")
        print(f"  Status: {provider_stats['status']}")
        print(f"  Requests: {provider_stats['metrics']['total_requests']}")
        print(f"  Success Rate: {provider_stats['metrics']['success_rate']:.2f}")
        print(f"  Avg Response Time: {provider_stats['metrics']['average_response_time']:.2f}s")
        print(f"  Circuit Breaker: {'🔴 OPEN' if circuit_breaker['is_open'] else '🟢 CLOSED'}")
        if circuit_breaker['failure_count'] > 0:
            print(f"  Failures: {circuit_breaker['failure_count']}")


async def demonstrate_enhanced_monitoring_service():
    """Demonstrate the enhanced monitoring service"""
    print("\n" + "="*60)
    print("DEMONSTRATING ENHANCED MONITORING SERVICE")
    print("="*60)
    
    # Create enhanced service with mock providers for testing
    service = EnhancedFlightMonitoringService(
        check_interval_seconds=60,
        cache_ttl_seconds=300,
        enable_mock_provider=True  # Enable mock providers for demo
    )
    
    print(f"Service initialized with {len(service.providers)} providers")
    
    # Test individual flight status with caching
    departure_date = datetime.now(timezone.utc) + timedelta(days=1)
    
    print(f"\n--- Testing Flight Status with Caching ---")
    test_flights = ["AA123", "UA456", "DL789"]
    
    for flight_number in test_flights:
        print(f"\nFirst request for {flight_number}:")
        start_time = datetime.utcnow()
        result1 = await service.get_flight_status_with_failover(flight_number, departure_date)
        end_time = datetime.utcnow()
        time1 = (end_time - start_time).total_seconds()
        
        if result1:
            print(f"  ✅ Success from {result1.source} ({time1:.3f}s)")
        
        print(f"Second request (should use cache):")
        start_time = datetime.utcnow()
        result2 = await service.get_flight_status_with_failover(flight_number, departure_date)
        end_time = datetime.utcnow()
        time2 = (end_time - start_time).total_seconds()
        
        if result2:
            print(f"  ✅ Success from {result2.source} ({time2:.3f}s)")
            print(f"  Cache speedup: {time1/time2:.1f}x faster" if time2 > 0 else "")
    
    # Test batch processing
    print(f"\n--- Testing Batch Processing ---")
    batch_flights = [(f"AA{i:03d}", departure_date) for i in range(200, 210)]
    
    print(f"Processing {len(batch_flights)} flights in batch...")
    start_time = datetime.utcnow()
    batch_results = await service.get_multiple_flights_status(batch_flights)
    end_time = datetime.utcnow()
    
    batch_time = (end_time - start_time).total_seconds()
    successful = sum(1 for result in batch_results.values() if result is not None)
    
    print(f"Results: {successful}/{len(batch_flights)} successful ({batch_time:.2f}s total)")
    
    # Show service statistics
    print(f"\n--- Service Statistics ---")
    stats = service.get_service_stats()
    
    print(f"Service Status: {stats['service_status']}")
    print(f"Redis Connected: {stats['redis_connected']}")
    print(f"Provider Count: {stats['provider_count']}")
    print(f"Statistics:")
    for key, value in stats['statistics'].items():
        print(f"  {key}: {value}")
    
    # Force health check
    print(f"\n--- Provider Health Check ---")
    health_report = await service.force_health_check()
    
    for provider_name, is_healthy in health_report['health_check_results'].items():
        status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
        print(f"  {provider_name}: {status}")


async def demonstrate_error_scenarios():
    """Demonstrate various error scenarios and recovery"""
    print("\n" + "="*60)
    print("DEMONSTRATING ERROR SCENARIOS")
    print("="*60)
    
    # Create a provider that fails predictably
    failing_provider = MockFlightDataProvider(
        "FailingProvider", 
        priority=10, 
        simulate_errors=True, 
        error_rate=1.0  # Always fail
    )
    
    reliable_provider = MockFlightDataProvider(
        "ReliableProvider", 
        priority=5, 
        simulate_errors=False
    )
    
    providers = [failing_provider, reliable_provider]
    
    config = FailoverConfig(
        max_retries_per_provider=1,
        circuit_breaker_threshold=2,
        circuit_breaker_timeout=5  # Quick reset for demo
    )
    
    failover_manager = FailoverManager(providers, config)
    departure_date = datetime.now(timezone.utc) + timedelta(days=1)
    
    print("Testing circuit breaker behavior...")
    print(f"Primary provider will always fail, secondary should take over")
    
    # Make several requests to trigger circuit breaker
    for i in range(5):
        print(f"\nRequest {i+1}:")
        try:
            result = await failover_manager.get_flight_status("TEST123", departure_date)
            if result:
                print(f"  ✅ Success from {result.source}")
            else:
                print(f"  ❌ All providers failed")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Check circuit breaker status
        cb_status = failover_manager.circuit_breakers["FailingProvider"]
        if cb_status.is_open:
            print(f"  🔴 Circuit breaker OPEN for FailingProvider (failures: {cb_status.failure_count})")
        else:
            print(f"  🟢 Circuit breaker CLOSED for FailingProvider")
    
    # Wait for circuit breaker to reset
    print(f"\nWaiting {config.circuit_breaker_timeout} seconds for circuit breaker reset...")
    await asyncio.sleep(config.circuit_breaker_timeout + 1)
    
    # Test again after reset
    print(f"\nTesting after circuit breaker timeout:")
    
    # Temporarily fix the failing provider
    failing_provider.set_error_rate(0.0)  # No more errors
    
    result = await failover_manager.get_flight_status("TEST123", departure_date)
    if result:
        print(f"  ✅ Success from {result.source} (provider recovered)")
    
    cb_status = failover_manager.circuit_breakers["FailingProvider"]
    if cb_status.is_open:
        print(f"  Circuit breaker still OPEN")
    else:
        print(f"  🟢 Circuit breaker CLOSED - provider recovered")


async def main():
    """Run all demonstrations"""
    print("Flight Data Provider Integration Example")
    print("Task 2.1: Flight Data Provider Integration Interfaces")
    print("REQ-7.1: FlightDataProvider interface for external APIs")
    print("REQ-7.2: Failover logic between primary and secondary sources")
    
    try:
        # Run demonstrations
        await demonstrate_individual_providers()
        await demonstrate_failover_manager()
        await demonstrate_enhanced_monitoring_service()
        await demonstrate_error_scenarios()
        
        print("\n" + "="*60)
        print("ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY")
        print("="*60)
        print("\nKey Features Demonstrated:")
        print("✅ FlightDataProvider interface standardization")
        print("✅ Mock provider for testing and development")
        print("✅ FlightAware API integration with error handling")
        print("✅ Intelligent failover between providers")
        print("✅ Circuit breaker pattern for failing providers")
        print("✅ Performance metrics and health monitoring")
        print("✅ Redis caching for sub-5-second response times")
        print("✅ Batch processing optimization")
        print("✅ Comprehensive error handling and recovery")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error in demonstration: {e}")
        logger.exception("Demo error")


if __name__ == "__main__":
    asyncio.run(main())