#!/usr/bin/env python3
"""
Flight Monitoring Service Example

This example demonstrates how to use the FlightMonitoringService for:
- REQ-1.1: Real-time flight status monitoring using FlightAware API
- REQ-1.6: Flight status checks within 5 seconds (via Redis caching)

Usage:
    python examples/flight_monitoring_example.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flight_agent.services.flight_monitoring_service import FlightMonitoringService
from flight_agent.models import create_user, create_booking, create_trip_monitor


async def demonstrate_flight_monitoring():
    """Demonstrate the Flight Monitoring Service functionality"""
    print("🚀 Flight Monitoring Service Demonstration")
    print("=" * 50)
    
    # Create service instance
    service = FlightMonitoringService(
        check_interval_seconds=30,  # Check every 30 seconds for demo
        cache_ttl_seconds=300       # Cache for 5 minutes
    )
    
    # Display service info
    stats = service.get_service_stats()
    print(f"\n📊 Service Configuration:")
    print(f"   Check Interval: {stats['check_interval_seconds']} seconds")
    print(f"   Cache TTL: {stats['cache_ttl_seconds']} seconds") 
    print(f"   Redis Connected: {stats['redis_connected']}")
    print(f"   Data Sources: {len(stats['data_sources'])}")
    
    for source in stats['data_sources']:
        print(f"     - {source['name']} (Priority: {source['priority']}, Available: {source['available']})")
    
    # Demonstrate flight status lookup with multi-source aggregation
    print(f"\n🔍 Testing Multi-Source Flight Status Lookup:")
    
    departure_date = datetime.now(timezone.utc) + timedelta(days=1)
    test_flights = ["AA123", "DL456", "UA789"]
    
    for flight_number in test_flights:
        print(f"\n  ✈️  Looking up {flight_number}...")
        
        # Time the lookup for performance testing (REQ-1.6)
        start_time = datetime.now()
        
        try:
            status_data = await service.get_flight_status_multi_source(flight_number, departure_date)
            
            end_time = datetime.now()
            lookup_time = (end_time - start_time).total_seconds()
            
            if status_data:
                print(f"     ✅ Status: {status_data.status}")
                print(f"     📍 Source: {status_data.source}")
                print(f"     🚨 Disrupted: {status_data.is_disrupted}")
                if status_data.is_disrupted:
                    print(f"     ⚠️  Type: {status_data.disruption_type}")
                print(f"     ⏱️  Lookup Time: {lookup_time:.3f}s")
                
                # Verify REQ-1.6 compliance
                if lookup_time <= 5.0:
                    print(f"     ✅ REQ-1.6 PASSED: Within 5 seconds")
                else:
                    print(f"     ❌ REQ-1.6 FAILED: Exceeded 5 seconds")
            else:
                print(f"     ❌ No status data available")
                print(f"     ⏱️  Lookup Time: {lookup_time:.3f}s")
                
        except Exception as e:
            print(f"     ❌ Error: {e}")
    
    # Demonstrate caching performance improvement
    print(f"\n💾 Testing Cache Performance:")
    
    flight_number = "AA123"
    print(f"  First lookup (cache miss)...")
    start_time = datetime.now()
    status_data_1 = await service.get_flight_status_multi_source(flight_number, departure_date)
    time_1 = (datetime.now() - start_time).total_seconds()
    
    print(f"     ⏱️  Time: {time_1:.3f}s")
    
    print(f"  Second lookup (cache hit)...")
    start_time = datetime.now()
    status_data_2 = await service.get_flight_status_multi_source(flight_number, departure_date)
    time_2 = (datetime.now() - start_time).total_seconds()
    
    print(f"     ⏱️  Time: {time_2:.3f}s")
    
    if time_2 < time_1:
        print(f"  ✅ Cache speedup: {time_1/time_2:.1f}x faster")
    
    # Show final statistics
    final_stats = service.get_service_stats()
    print(f"\n📈 Final Statistics:")
    print(f"   API Calls: {final_stats['statistics']['api_calls']}")
    print(f"   Cache Hits: {final_stats['statistics']['cache_hits']}")
    print(f"   Cache Misses: {final_stats['statistics']['cache_misses']}")
    print(f"   Errors: {final_stats['statistics']['errors']}")
    
    # Calculate cache hit rate
    total_cache_requests = final_stats['statistics']['cache_hits'] + final_stats['statistics']['cache_misses']
    if total_cache_requests > 0:
        hit_rate = (final_stats['statistics']['cache_hits'] / total_cache_requests) * 100
        print(f"   Cache Hit Rate: {hit_rate:.1f}%")


async def demonstrate_monitoring_integration():
    """Demonstrate integration with existing booking system"""
    print(f"\n🔗 Integration with Booking System:")
    print("=" * 40)
    
    try:
        # Create test user and booking
        print("  📝 Creating test user and booking...")
        user = create_user("demo@example.com", "+1234567890")
        
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        booking_data = {
            "pnr": "DEMO123",
            "airline": "AA",
            "flight_number": "AA123",
            "departure_date": departure_date,
            "origin": "JFK",
            "destination": "LAX"
        }
        booking = create_booking(user.user_id, booking_data)
        
        # Create trip monitor
        monitor = create_trip_monitor(
            user.user_id,
            booking.booking_id,
            "flight_AA123_demo",
            {
                "check_frequency_minutes": 30,
                "expires_at": datetime.now(timezone.utc) + timedelta(days=2)
            }
        )
        
        print(f"     ✅ User: {user.email}")
        print(f"     ✅ Booking: {booking.flight_number} ({booking.pnr})")
        print(f"     ✅ Monitor: {monitor.monitor_id}")
        
        # Demonstrate monitoring
        service = FlightMonitoringService(check_interval_seconds=60)
        
        print("  🔍 Testing single flight monitoring...")
        from flight_agent.models import SessionLocal
        db = SessionLocal()
        try:
            await service._monitor_single_flight(monitor, db)
            print("     ✅ Monitoring completed successfully")
        finally:
            db.close()
        
    except Exception as e:
        print(f"     ❌ Integration error: {e}")


async def run_demo_monitoring_service():
    """Run a short demonstration of the monitoring service loop"""
    print(f"\n🔄 Short Monitoring Service Demo:")
    print("=" * 35)
    
    service = FlightMonitoringService(
        check_interval_seconds=5  # Very frequent for demo
    )
    
    print("  Starting monitoring service for 15 seconds...")
    
    # Start monitoring in background
    monitor_task = asyncio.create_task(service.start_monitoring())
    
    try:
        # Let it run for 15 seconds
        await asyncio.sleep(15)
        
        # Show stats
        stats = service.get_service_stats()
        print(f"  📊 Service ran {stats['statistics']['checks_performed']} check cycles")
        
    finally:
        # Stop service
        service.stop_monitoring()
        print("  🛑 Service stopped")
        
        # Cancel the background task
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


async def main():
    """Run all demonstration examples"""
    print("Flight Monitoring Service - Complete Demonstration")
    print("==================================================")
    
    try:
        await demonstrate_flight_monitoring()
        await demonstrate_monitoring_integration()
        await run_demo_monitoring_service()
        
        print("\n✅ All demonstrations completed successfully!")
        
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(main())