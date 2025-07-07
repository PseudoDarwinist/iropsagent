# flight_agent/monitor.py
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import json
from .models import SessionLocal, Booking, DisruptionEvent, User
from .tools import get_flight_status, find_alternative_flights
from google.adk.agents import LlmAgent
import uuid


class DisruptionMonitor:
    """Monitors flights for disruptions and triggers rebooking"""
    
    def __init__(self, check_interval_seconds: int = 300):  # 5 minutes default
        self.check_interval = check_interval_seconds
        self.running = False
        self.last_check = {}
        
        # Create monitoring agent
        self.monitor_agent = LlmAgent(
            name="DisruptionMonitorAgent",
            model="gemini-2.5-flash",
            instruction="""
            You are a flight disruption detection specialist.
            
            When given a flight status, determine if it indicates a disruption:
            - CANCELLED/CANCELED = Major disruption
            - DELAYED more than 2 hours = Major disruption  
            - DELAYED less than 2 hours = Minor disruption
            - DIVERTED = Major disruption
            - ON TIME = No disruption
            
            Respond with JSON: {"disrupted": true/false, "type": "CANCELLED/DELAYED/DIVERTED/NONE", "severity": "major/minor/none"}
            """
        )
    
    async def start_monitoring(self):
        """Start the monitoring loop"""
        self.running = True
        print(f"🚀 Disruption monitor started (checking every {self.check_interval}s)")
        
        while self.running:
            try:
                await self._check_all_flights()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"❌ Monitor error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False
        print("🛑 Disruption monitor stopped")
    
    async def _check_all_flights(self):
        """Check all upcoming flights for disruptions"""
        db = SessionLocal()
        try:
            # Get flights departing in next 7 days
            cutoff_time = datetime.now(timezone.utc) + timedelta(days=7)
            
            upcoming_flights = db.query(Booking).filter(
                Booking.departure_date > datetime.now(timezone.utc),
                Booking.departure_date < cutoff_time,
                Booking.status == "CONFIRMED"
            ).all()
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking {len(upcoming_flights)} flights...")
            
            for booking in upcoming_flights:
                await self._check_single_flight(booking, db)
                
        finally:
            db.close()
    
    async def _check_single_flight(self, booking: Booking, db):
        """Check a single flight for disruptions"""
        try:
            # Skip if checked recently (within 30 minutes)
            if booking.booking_id in self.last_check:
                if datetime.now(timezone.utc) - self.last_check[booking.booking_id] < timedelta(minutes=30):
                    return
            
            # Get current flight status
            print(f"  ✈️  Checking {booking.flight_number}...")
            status_result = get_flight_status(booking.flight_number)
            
            # Use agent to analyze disruption
            analysis = await self._analyze_disruption(status_result)
            
            if analysis['disrupted']:
                print(f"  🚨 DISRUPTION DETECTED: {booking.flight_number} - {analysis['type']}")
                await self._handle_disruption(booking, analysis, db)
            else:
                print(f"  ✅ {booking.flight_number} is on time")
            
            # Update last check time
            booking.last_checked = datetime.now(timezone.utc)
            self.last_check[booking.booking_id] = datetime.now(timezone.utc)
            db.commit()
            
        except Exception as e:
            print(f"  ❌ Error checking {booking.flight_number}: {e}")
    
    async def _analyze_disruption(self, status: str) -> Dict:
        """Use LLM to analyze if flight is disrupted"""
        try:
            # In a real implementation, would use the agent
            # For now, simple keyword detection
            status_upper = status.upper()
            
            if 'CANCELLED' in status_upper or 'CANCELED' in status_upper:
                return {"disrupted": True, "type": "CANCELLED", "severity": "major"}
            elif 'DELAYED' in status_upper:
                return {"disrupted": True, "type": "DELAYED", "severity": "major"}
            elif 'DIVERTED' in status_upper:
                return {"disrupted": True, "type": "DIVERTED", "severity": "major"}
            else:
                return {"disrupted": False, "type": "NONE", "severity": "none"}
                
        except Exception as e:
            print(f"Analysis error: {e}")
            return {"disrupted": False, "type": "NONE", "severity": "none"}
    
    async def _handle_disruption(self, booking: Booking, analysis: Dict, db):
        """Handle a detected disruption"""
        try:
            # Check if we already have an active disruption event
            existing_event = db.query(DisruptionEvent).filter(
                DisruptionEvent.booking_id == booking.booking_id,
                DisruptionEvent.rebooking_status.in_(["PENDING", "IN_PROGRESS"])
            ).first()
            
            if existing_event:
                print(f"    ℹ️  Disruption already being handled")
                return
            
            # Create disruption event
            event = DisruptionEvent(
                event_id=str(uuid.uuid4()),
                booking_id=booking.booking_id,
                disruption_type=analysis['type'],
                original_departure=booking.departure_date,
                rebooking_status="PENDING"
            )
            db.add(event)
            
            # Find alternatives
            print(f"    🔍 Finding alternatives for {booking.origin} → {booking.destination}")
            alternatives = find_alternative_flights(
                booking.origin,
                booking.destination,
                booking.departure_date.strftime("%Y-%m-%d")
            )
            
            # Store alternatives
            if alternatives and "error" not in alternatives.lower():
                event.rebooking_options = {"alternatives": alternatives}
                event.rebooking_status = "IN_PROGRESS"
                
                # Notify user (in real system, would send email/SMS)
                await self._notify_user(booking, event, alternatives)
            
            db.commit()
            print(f"    ✅ Disruption handled, user notified")
            
        except Exception as e:
            print(f"    ❌ Error handling disruption: {e}")
            db.rollback()
    
    async def _notify_user(self, booking: Booking, event: DisruptionEvent, alternatives: str):
        """Notify user of disruption and alternatives"""
        # In real implementation, would send email/SMS
        # For now, just log
        print(f"\n    📧 NOTIFICATION TO USER {booking.user_id}:")
        print(f"    Your flight {booking.flight_number} has been {event.disruption_type}")
        print(f"    We found these alternatives:")
        print(f"    {alternatives}\n")
        
        event.user_notified = True


# Standalone monitoring service
async def run_monitor_service():
    """Run the monitoring service standalone"""
    monitor = DisruptionMonitor(check_interval_seconds=60)  # Check every minute for testing
    
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        monitor.stop_monitoring()
        print("\nMonitoring service stopped")


if __name__ == "__main__":
    # Run: python -m flight_agent.monitor
    asyncio.run(run_monitor_service())