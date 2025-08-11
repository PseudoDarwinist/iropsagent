"""
Mock Flight Data Provider for testing and development.

Implements REQ-7.1: Mock provider for testing and development
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .interfaces import FlightDataProvider, FlightStatusData, ProviderStatus


class MockFlightDataProvider(FlightDataProvider):
    """
    Mock flight data provider for testing and development.
    
    Provides realistic flight data simulation with configurable:
    - Response delays
    - Error rates  
    - Disruption scenarios
    - Rate limiting simulation
    """
    
    def __init__(
        self, 
        name: str = "MockProvider",
        priority: int = 1,
        simulate_errors: bool = False,
        error_rate: float = 0.1,
        simulate_delays: bool = True,
        base_delay_ms: int = 100
    ):
        """
        Initialize mock provider.
        
        Args:
            name: Provider name
            priority: Provider priority
            simulate_errors: Whether to randomly simulate errors
            error_rate: Probability of simulated errors (0.0-1.0)
            simulate_delays: Whether to simulate network delays
            base_delay_ms: Base response delay in milliseconds
        """
        super().__init__(name, priority, timeout_seconds=5.0)
        self.simulate_errors = simulate_errors
        self.error_rate = error_rate
        self.simulate_delays = simulate_delays
        self.base_delay_ms = base_delay_ms
        
        # Predefined flight scenarios for consistent testing
        self.flight_scenarios = {
            "AA123": {"status": "ON TIME", "disrupted": False},
            "UA456": {"status": "DELAYED", "disrupted": True, "delay": 45, "type": "DELAYED"},
            "DL789": {"status": "CANCELLED", "disrupted": True, "type": "CANCELLED"},
            "SW111": {"status": "DIVERTED", "disrupted": True, "type": "DIVERTED"},
            "AA999": {"status": "ERROR", "disrupted": False},  # Simulate API error
        }
    
    async def get_flight_status(
        self, 
        flight_number: str, 
        departure_date: datetime
    ) -> Optional[FlightStatusData]:
        """Get mock flight status data"""
        start_time = datetime.utcnow()
        
        try:
            # Simulate network delay
            if self.simulate_delays:
                delay_seconds = self.base_delay_ms / 1000.0
                delay_seconds += random.uniform(0, 0.5)  # Add some jitter
                await asyncio.sleep(delay_seconds)
            
            # Simulate random errors
            if self.simulate_errors and random.random() < self.error_rate:
                response_time = (datetime.utcnow() - start_time).total_seconds()
                self.update_metrics(False, response_time, "Simulated random error")
                return None
            
            # Check for specific error scenarios
            if flight_number in self.flight_scenarios:
                scenario = self.flight_scenarios[flight_number]
                if scenario["status"] == "ERROR":
                    response_time = (datetime.utcnow() - start_time).total_seconds()
                    self.update_metrics(False, response_time, f"Mock error for {flight_number}")
                    return None
            
            # Generate mock flight data
            flight_data = self._generate_mock_flight_data(flight_number, departure_date)
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self.update_metrics(True, response_time)
            
            return flight_data
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self.update_metrics(False, response_time, str(e))
            return None
    
    async def health_check(self) -> bool:
        """Perform mock health check"""
        if self.simulate_delays:
            await asyncio.sleep(0.1)  # Simulate health check delay
        
        # Randomly fail health checks to test failover
        if self.simulate_errors and random.random() < 0.05:  # 5% failure rate
            self.set_status(ProviderStatus.UNAVAILABLE, "Mock health check failed")
            return False
        
        self.set_status(ProviderStatus.AVAILABLE)
        return True
    
    async def get_multiple_flights(
        self, 
        flight_requests: List[tuple[str, datetime]]
    ) -> Dict[str, Optional[FlightStatusData]]:
        """Get status for multiple flights"""
        results = {}
        
        # Simulate batch processing efficiency
        if self.simulate_delays:
            # Batch requests are more efficient than individual ones
            batch_delay = min(len(flight_requests) * 0.05, 1.0)  # Max 1 second
            await asyncio.sleep(batch_delay)
        
        for flight_number, departure_date in flight_requests:
            try:
                # Don't add individual delays for batch processing
                original_simulate_delays = self.simulate_delays
                self.simulate_delays = False
                
                result = await self.get_flight_status(flight_number, departure_date)
                results[flight_number] = result
                
                self.simulate_delays = original_simulate_delays
                
            except Exception as e:
                results[flight_number] = None
        
        return results
    
    def _generate_mock_flight_data(
        self, 
        flight_number: str, 
        departure_date: datetime
    ) -> FlightStatusData:
        """Generate realistic mock flight data"""
        
        # Use predefined scenario if available
        if flight_number in self.flight_scenarios:
            scenario = self.flight_scenarios[flight_number]
        else:
            # Generate random scenario
            scenario = self._generate_random_scenario()
        
        flight_id = f"{flight_number}_{departure_date.strftime('%Y%m%d')}"
        now = datetime.now(timezone.utc)
        
        # Calculate arrival time (assume 2-4 hour flight)
        flight_duration = timedelta(hours=random.uniform(1.5, 4.0))
        scheduled_arrival = departure_date + flight_duration
        
        # Handle different disruption types
        delay_minutes = scenario.get("delay", 0)
        actual_departure = None
        actual_arrival = None
        
        if scenario["disrupted"]:
            if scenario.get("type") == "DELAYED":
                actual_departure = departure_date + timedelta(minutes=delay_minutes)
                actual_arrival = scheduled_arrival + timedelta(minutes=delay_minutes)
            elif scenario.get("type") == "DIVERTED":
                # Diverted flights might have different arrival times
                actual_departure = departure_date
                actual_arrival = scheduled_arrival + timedelta(minutes=random.randint(30, 120))
        else:
            # On-time flights
            if random.random() < 0.3:  # 30% chance to be slightly early/late
                variance = random.randint(-10, 15)  # -10 to +15 minutes
                actual_departure = departure_date + timedelta(minutes=variance)
                actual_arrival = scheduled_arrival + timedelta(minutes=variance)
        
        # Generate realistic gate and terminal info
        gates = ["A1", "A12", "B5", "B23", "C7", "C14", "D3", "D18"]
        terminals = ["1", "2", "3", "North", "South", "International"]
        
        return FlightStatusData(
            flight_id=flight_id,
            status=scenario["status"],
            delay_minutes=delay_minutes,
            scheduled_departure=departure_date,
            actual_departure=actual_departure,
            scheduled_arrival=scheduled_arrival,
            actual_arrival=actual_arrival,
            gate=random.choice(gates) if random.random() < 0.8 else None,
            terminal=random.choice(terminals) if random.random() < 0.9 else None,
            is_disrupted=scenario["disrupted"],
            disruption_type=scenario.get("type"),
            last_updated=now,
            source=self.name,
            confidence_score=random.uniform(0.85, 1.0),  # Mock providers have high confidence
            raw_data={
                "mock": True,
                "scenario": scenario,
                "generated_at": now.isoformat()
            }
        )
    
    def _generate_random_scenario(self) -> dict:
        """Generate a random flight scenario"""
        rand = random.random()
        
        if rand < 0.7:  # 70% on time
            return {"status": "ON TIME", "disrupted": False}
        elif rand < 0.85:  # 15% delayed
            delay = random.randint(15, 180)  # 15 minutes to 3 hours
            return {
                "status": "DELAYED", 
                "disrupted": True, 
                "delay": delay, 
                "type": "DELAYED"
            }
        elif rand < 0.95:  # 10% cancelled
            return {"status": "CANCELLED", "disrupted": True, "type": "CANCELLED"}
        else:  # 5% diverted
            return {"status": "DIVERTED", "disrupted": True, "type": "DIVERTED"}
    
    def add_custom_scenario(self, flight_number: str, scenario: dict):
        """Add a custom scenario for testing specific cases"""
        self.flight_scenarios[flight_number] = scenario
    
    def set_error_rate(self, error_rate: float):
        """Update error simulation rate"""
        self.error_rate = max(0.0, min(1.0, error_rate))
    
    def reset_metrics(self):
        """Reset provider metrics for testing"""
        self._metrics = type(self._metrics)(
            success_rate=0.0,
            average_response_time=0.0,
            last_successful_call=None,
            last_error=None,
            total_requests=0,
            failed_requests=0,
            rate_limit_hits=0
        )