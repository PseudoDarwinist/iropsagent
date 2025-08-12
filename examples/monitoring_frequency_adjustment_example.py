#!/usr/bin/env python3
"""
Monitoring Frequency Adjustment Example
Task 2.3: Implement monitoring frequency adjustment

This example demonstrates:
- Dynamic polling frequency (15min default, 5min high-risk)
- High-risk route flagging based on historical data (>40% delay rate)
- Monitoring interruption notifications (30min threshold)
- Integration with existing monitoring infrastructure

Usage:
    python examples/monitoring_frequency_adjustment_example.py
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flight_agent.models import (
    create_user, create_booking, create_trip_monitor, create_disruption_event,
    SessionLocal, TripMonitor, Booking, DisruptionEvent
)
from flight_agent.services.adaptive_flight_monitoring_service import AdaptiveFlightMonitoringService
from flight_agent.services.monitoring_frequency_manager import (
    MonitoringFrequencyManager, run_monitoring_frequency_adjustment
)


async def create_example_data():
    """Create example flight bookings and monitors for demonstration"""
    print("🛠️  Setting up example data...")
    
    # Create test user
    user = create_user("demo@example.com", "+1234567890")
    print(f"Created user: {user.email}")
    
    # Create various flight scenarios
    scenarios = []
    
    # Scenario 1: High-risk route with poor historical performance
    print("\n📍 Creating Scenario 1: High-risk route (ORD-DFW)")
    
    # Create historical flights for ORD-DFW route with high delay rate
    historical_flights = []
    for i in range(20):  # 20 historical flights
        historical_date = datetime.now(timezone.utc) - timedelta(days=30-i)
        booking_data = {
            "pnr": f"HIST{i:03d}",
            "airline": "AA",
            "flight_number": f"AA{1000+i}",
            "departure_date": historical_date,
            "origin": "ORD",
            "destination": "DFW"
        }
        hist_booking = create_booking(user.user_id, booking_data)
        historical_flights.append(hist_booking)
        
        # Create delays for 60% of flights (exceeds 40% threshold)
        if i < 12:  # 12 out of 20 = 60% delay rate
            disruption_data = {
                "type": "DELAYED",
                "original_departure": hist_booking.departure_date,
                "delay_minutes": 45 + (i * 5),  # Variable delays
                "reason": f"Weather/ATC delays - historical pattern"
            }
            create_disruption_event(hist_booking.booking_id, disruption_data)
    
    print(f"Created 20 historical flights for ORD-DFW with 60% delay rate")
    
    # Create current booking on this high-risk route
    high_risk_booking_data = {
        "pnr": "HIGHRISK001",
        "airline": "AA",
        "flight_number": "AA2000",
        "departure_date": datetime.now(timezone.utc) + timedelta(hours=6),
        "origin": "ORD",
        "destination": "DFW"
    }
    high_risk_booking = create_booking(user.user_id, high_risk_booking_data)
    
    # Create monitor with default frequency (will be adjusted to high-risk)
    high_risk_monitor_data = {
        "check_frequency_minutes": 15,  # Default - should become 5min
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1)
    }
    high_risk_monitor = create_trip_monitor(
        user.user_id, 
        high_risk_booking.booking_id, 
        "high_risk_flight",
        high_risk_monitor_data
    )
    
    scenarios.append({
        "name": "High-Risk Route",
        "booking": high_risk_booking,
        "monitor": high_risk_monitor,
        "expected_frequency": 5,  # Should be adjusted to high-risk frequency
        "reason": "Route has >40% historical delay rate"
    })
    
    # Scenario 2: Low-risk route with good performance
    print("\n📍 Creating Scenario 2: Low-risk route (ATL-DEN)")
    
    # Create historical flights with low delay rate
    for i in range(15):
        historical_date = datetime.now(timezone.utc) - timedelta(days=25-i)
        booking_data = {
            "pnr": f"LOWH{i:03d}",
            "airline": "DL",
            "flight_number": f"DL{2000+i}",
            "departure_date": historical_date,
            "origin": "ATL",
            "destination": "DEN"
        }
        hist_booking = create_booking(user.user_id, booking_data)
        
        # Only 2 out of 15 flights delayed (13% delay rate - low risk)
        if i < 2:
            disruption_data = {
                "type": "DELAYED",
                "original_departure": hist_booking.departure_date,
                "delay_minutes": 25,
                "reason": "Minor weather delay"
            }
            create_disruption_event(hist_booking.booking_id, disruption_data)
    
    print(f"Created 15 historical flights for ATL-DEN with 13% delay rate")
    
    # Create current booking on low-risk route
    low_risk_booking_data = {
        "pnr": "LOWRISK002",
        "airline": "DL", 
        "flight_number": "DL3000",
        "departure_date": datetime.now(timezone.utc) + timedelta(days=3),  # Far future
        "origin": "ATL",
        "destination": "DEN"
    }
    low_risk_booking = create_booking(user.user_id, low_risk_booking_data)
    
    low_risk_monitor_data = {
        "check_frequency_minutes": 15,  # Should become 30min (low-risk)
        "expires_at": datetime.now(timezone.utc) + timedelta(days=4)
    }
    low_risk_monitor = create_trip_monitor(
        user.user_id,
        low_risk_booking.booking_id,
        "low_risk_flight", 
        low_risk_monitor_data
    )
    
    scenarios.append({
        "name": "Low-Risk Route",
        "booking": low_risk_booking,
        "monitor": low_risk_monitor,
        "expected_frequency": 30,  # Should be adjusted to low-risk frequency
        "reason": "Route has <20% historical delay rate, departure >24h away"
    })
    
    # Scenario 3: Monitoring interruption
    print("\n📍 Creating Scenario 3: Monitoring interruption")
    
    interruption_booking_data = {
        "pnr": "INTERRUPT003",
        "airline": "UA",
        "flight_number": "UA4000",
        "departure_date": datetime.now(timezone.utc) + timedelta(days=1),
        "origin": "LAX",
        "destination": "SFO"
    }
    interruption_booking = create_booking(user.user_id, interruption_booking_data)
    
    # Create monitor with last check >30 minutes ago (interruption)
    interruption_time = datetime.now(timezone.utc) - timedelta(minutes=45)
    interruption_monitor_data = {
        "check_frequency_minutes": 10,
        "last_check": interruption_time,  # 45 minutes ago
        "expires_at": datetime.now(timezone.utc) + timedelta(days=2)
    }
    interruption_monitor = create_trip_monitor(
        user.user_id,
        interruption_booking.booking_id,
        "interrupted_flight",
        interruption_monitor_data
    )
    
    # Update last_check in database
    db = SessionLocal()
    try:
        monitor_record = db.query(TripMonitor).filter(TripMonitor.monitor_id == interruption_monitor.monitor_id).first()
        monitor_record.last_check = interruption_time
        db.commit()
    finally:
        db.close()
    
    scenarios.append({
        "name": "Monitoring Interruption",
        "booking": interruption_booking,
        "monitor": interruption_monitor,
        "expected_frequency": 10,  # May stay the same, but should generate alert
        "reason": "Monitor has 45min gap - should trigger interruption alert"
    })
    
    print(f"\n✅ Created {len(scenarios)} test scenarios")
    return user, scenarios


async def demonstrate_frequency_adjustment():
    """Demonstrate monitoring frequency adjustment functionality"""
    
    print("=" * 80)
    print("🚀 MONITORING FREQUENCY ADJUSTMENT DEMONSTRATION")
    print("   Task 2.3: Implement monitoring frequency adjustment")
    print("=" * 80)
    
    # Create example data
    user, scenarios = await create_example_data()
    
    # Initialize monitoring frequency manager
    print("\n🔧 Initializing Monitoring Frequency Manager...")
    frequency_manager = MonitoringFrequencyManager()
    
    print(f"   • High-risk delay threshold: {frequency_manager.high_risk_delay_threshold * 100}%")
    print(f"   • Interruption notification threshold: {frequency_manager.interruption_notification_threshold} minutes")
    print(f"   • Frequency mapping:")
    print(f"     - Critical/High risk: {frequency_manager.frequency_mapping['high']} minutes")
    print(f"     - Medium risk: {frequency_manager.frequency_mapping['medium']} minutes") 
    print(f"     - Low risk: {frequency_manager.frequency_mapping['low']} minutes")
    
    # Demonstrate route delay statistics calculation
    print("\n📊 Route Delay Statistics Analysis")
    print("-" * 50)
    
    routes_to_analyze = [
        ("ORD", "DFW", "Expected high-risk (60% delay rate)"),
        ("ATL", "DEN", "Expected low-risk (13% delay rate)"),
        ("LAX", "SFO", "Expected low-risk (no historical data)")
    ]
    
    route_stats = {}
    for origin, dest, description in routes_to_analyze:
        stats = await frequency_manager.get_route_delay_statistics(origin, dest)
        route_stats[f"{origin}-{dest}"] = stats
        risk_level = frequency_manager.classify_route_risk_level(stats)
        
        print(f"\n📍 Route {origin} → {dest} ({description})")
        print(f"   • Total flights: {stats.total_flights}")
        print(f"   • Delayed flights: {stats.delayed_flights}")
        print(f"   • Delay rate: {stats.delay_rate:.1%}")
        print(f"   • Average delay: {stats.average_delay_minutes:.1f} minutes")
        print(f"   • Risk classification: {risk_level.value.upper()}")
        
        if risk_level.value == "high":
            print(f"   ⚠️  HIGH-RISK ROUTE: Exceeds {frequency_manager.high_risk_delay_threshold:.0%} threshold")
    
    # Demonstrate frequency optimization
    print(f"\n⚙️  Frequency Optimization Analysis")
    print("-" * 50)
    
    for scenario in scenarios:
        print(f"\n🔍 Analyzing: {scenario['name']}")
        print(f"   Flight: {scenario['booking'].flight_number} ({scenario['booking'].origin} → {scenario['booking'].destination})")
        print(f"   Current frequency: {scenario['monitor'].check_frequency_minutes} minutes")
        print(f"   Expected outcome: {scenario['reason']}")
        
        # Calculate optimal frequency
        try:
            adjustment = await frequency_manager.calculate_optimal_frequency(scenario['monitor'])
            
            if adjustment:
                print(f"   📋 Recommendation:")
                print(f"      • Recommended frequency: {adjustment.recommended_frequency} minutes")
                print(f"      • Risk level: {adjustment.risk_level.value}")
                print(f"      • Route risk: {adjustment.route_risk_level.value}")
                print(f"      • Priority: {adjustment.priority}")
                print(f"      • Reason: {adjustment.reason}")
                
                # Apply the adjustment
                if adjustment.recommended_frequency != adjustment.current_frequency:
                    success = await frequency_manager.apply_frequency_adjustment(adjustment)
                    if success:
                        print(f"   ✅ Frequency adjusted: {adjustment.current_frequency}min → {adjustment.recommended_frequency}min")
                    else:
                        print(f"   ❌ Failed to apply frequency adjustment")
                else:
                    print(f"   ℹ️  No frequency change needed")
            else:
                print(f"   ❌ Could not calculate optimal frequency")
                
        except Exception as e:
            print(f"   ❌ Error calculating frequency: {e}")
    
    # Demonstrate interruption detection
    print(f"\n🚨 Monitoring Interruption Detection")
    print("-" * 50)
    
    interruption_alerts = await frequency_manager.check_monitoring_interruptions()
    
    if interruption_alerts:
        print(f"Found {len(interruption_alerts)} monitoring interruptions:")
        for alert_id in interruption_alerts:
            print(f"   • Alert created: {alert_id}")
    else:
        print("No monitoring interruptions detected")
    
    # Run complete adjustment cycle
    print(f"\n🔄 Complete Monitoring Adjustment Cycle")
    print("-" * 50)
    
    cycle_summary = await frequency_manager.run_monitoring_adjustment_cycle()
    
    print(f"Cycle Summary:")
    print(f"   • Cycle completed at: {cycle_summary.get('cycle_completed_at', 'N/A')}")
    print(f"   • Duration: {cycle_summary.get('cycle_duration_seconds', 0):.1f} seconds")
    print(f"   • Monitors optimized: {cycle_summary.get('monitors_optimized', 0)}")
    print(f"   • Frequency increases: {cycle_summary.get('frequency_adjustments', {}).get('increases', 0)}")
    print(f"   • Frequency decreases: {cycle_summary.get('frequency_adjustments', {}).get('decreases', 0)}")
    print(f"   • Performance gained: {cycle_summary.get('performance_gained_minutes', 0)} minutes")
    print(f"   • Interruption alerts: {cycle_summary.get('interruption_alerts_created', 0)}")
    
    # Show final statistics
    print(f"\n📈 Final Statistics")
    print("-" * 50)
    
    final_stats = frequency_manager.get_adjustment_statistics()
    
    print(f"Adjustment Statistics:")
    for key, value in final_stats["adjustment_stats"].items():
        print(f"   • {key.replace('_', ' ').title()}: {value}")
    
    print(f"\nCache Statistics:")
    for key, value in final_stats["cache_stats"].items():
        print(f"   • {key.replace('_', ' ').title()}: {value}")
    
    # Demonstrate adaptive monitoring service
    print(f"\n🎯 Adaptive Monitoring Service Integration")
    print("-" * 50)
    
    try:
        adaptive_service = AdaptiveFlightMonitoringService(
            check_interval_seconds=60,
            enable_mock_provider=True,
            frequency_adjustment_interval=300
        )
        
        print(f"Adaptive service initialized successfully")
        print(f"   • Base check interval: {adaptive_service.check_interval} seconds")
        print(f"   • Frequency adjustment interval: {adaptive_service.frequency_adjustment_interval} seconds")
        
        # Get high-risk routes
        high_risk_routes = await adaptive_service.get_high_risk_routes()
        print(f"   • High-risk routes detected: {len(high_risk_routes)}")
        
        for route in high_risk_routes:
            print(f"     - {route['route']}: {route['delay_rate']:.1%} delay rate")
        
        # Get monitoring interruptions
        interruptions = await adaptive_service.get_monitoring_interruptions()
        print(f"   • Active interruptions: {len(interruptions)}")
        
        for interruption in interruptions:
            print(f"     - {interruption['flight_number']}: {interruption['interruption_minutes']:.0f}min gap ({interruption['severity']})")
        
        # Get adaptive service statistics
        adaptive_stats = adaptive_service.get_adaptive_service_stats()
        print(f"   • Service status: {adaptive_stats.get('service_status', 'unknown')}")
        print(f"   • Average frequency: {adaptive_stats['adaptive_statistics']['average_monitoring_frequency']:.1f} minutes")
        
    except Exception as e:
        print(f"   ❌ Error with adaptive service: {e}")
    
    print(f"\n🎉 Demonstration completed successfully!")
    print("\nKey Requirements Implemented:")
    print("   ✅ REQ-1.3: Dynamic monitoring frequency (15min default, 5min high-risk)")
    print("   ✅ REQ-1.4: High-risk route flagging (>40% delay rate threshold)")
    print("   ✅ REQ-1.6: Monitoring interruption notifications (30min threshold)")
    print("   ✅ Performance optimization through intelligent polling intervals")


async def demonstrate_standalone_function():
    """Demonstrate standalone monitoring frequency adjustment function"""
    print(f"\n🔧 Standalone Function Demonstration")
    print("-" * 50)
    
    try:
        summary = await run_monitoring_frequency_adjustment()
        print("Standalone function executed successfully")
        print(f"Summary: {summary}")
    except Exception as e:
        print(f"Error running standalone function: {e}")


def cleanup_example_data():
    """Clean up example data (optional - for development)"""
    print(f"\n🧹 Cleaning up example data...")
    
    try:
        db = SessionLocal()
        
        # Clean up in reverse dependency order
        # DisruptionEvents first, then TripMonitors, then Bookings
        
        demo_pnr_patterns = ['HIST', 'HIGHRISK', 'LOWRISK', 'LOWH', 'INTERRUPT']
        
        for pattern in demo_pnr_patterns:
            bookings = db.query(Booking).filter(Booking.pnr.like(f"{pattern}%")).all()
            
            for booking in bookings:
                # Delete disruption events
                disruptions = db.query(DisruptionEvent).filter(DisruptionEvent.booking_id == booking.booking_id).all()
                for disruption in disruptions:
                    db.delete(disruption)
                
                # Delete trip monitors
                monitors = db.query(TripMonitor).filter(TripMonitor.booking_id == booking.booking_id).all()
                for monitor in monitors:
                    db.delete(monitor)
                
                # Delete booking
                db.delete(booking)
        
        db.commit()
        db.close()
        
        print("Example data cleaned up successfully")
        
    except Exception as e:
        print(f"Error cleaning up: {e}")


async def main():
    """Main demonstration function"""
    try:
        # Run the main demonstration
        await demonstrate_frequency_adjustment()
        
        # Demonstrate standalone function
        await demonstrate_standalone_function()
        
        # Ask if user wants to clean up
        print(f"\n" + "=" * 80)
        response = input("Clean up example data? (y/N): ").lower().strip()
        if response in ['y', 'yes']:
            cleanup_example_data()
        else:
            print("Example data preserved for further analysis")
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Demonstration interrupted by user")
    except Exception as e:
        print(f"\n❌ Error in demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Starting Monitoring Frequency Adjustment Demonstration...")
    asyncio.run(main())