"""
FlightAware API Provider implementation.

Implements REQ-7.1: FlightAware provider with proper error handling and metrics
"""

import asyncio
import aiohttp
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import logging

from .interfaces import (
    FlightDataProvider, 
    FlightStatusData, 
    ProviderStatus,
    ProviderError,
    RateLimitError,
    TimeoutError,
    AuthenticationError
)

logger = logging.getLogger(__name__)


class FlightAwareProvider(FlightDataProvider):
    """
    FlightAware AeroAPI provider implementation.
    
    Provides real-time flight data using FlightAware's AeroAPI with:
    - Proper error handling and retry logic
    - Rate limiting awareness
    - Performance metrics tracking
    - Authentication management
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: str = "https://aeroapi.flightaware.com/aeroapi",
        priority: int = 10,
        timeout_seconds: float = 10.0
    ):
        """
        Initialize FlightAware provider.
        
        Args:
            api_key: FlightAware API key (defaults to FLIGHTAWARE_API_KEY env var)
            base_url: API base URL
            priority: Provider priority (higher = preferred)
            timeout_seconds: Request timeout
        """
        super().__init__("FlightAware", priority, timeout_seconds)
        
        self.api_key = api_key or os.getenv("FLIGHTAWARE_API_KEY")
        self.base_url = base_url.rstrip("/")
        
        if not self.api_key:
            self.set_status(ProviderStatus.UNAVAILABLE, "API key not configured")
            logger.warning("FlightAware API key not found")
        
        # Rate limiting tracking
        self.rate_limit_remaining = None
        self.rate_limit_reset = None
        
    async def get_flight_status(
        self, 
        flight_number: str, 
        departure_date: datetime
    ) -> Optional[FlightStatusData]:
        """Get flight status from FlightAware API"""
        
        if not self.is_available:
            return None
            
        start_time = datetime.utcnow()
        
        try:
            # Construct API endpoint
            url = f"{self.base_url}/flights/{flight_number}"
            headers = {
                "x-apikey": self.api_key,
                "Accept": "application/json"
            }
            
            # Add date filter if needed
            params = {}
            if departure_date:
                # FlightAware expects dates in YYYY-MM-DD format
                params["start"] = departure_date.strftime("%Y-%m-%d")
                params["end"] = (departure_date + timedelta(days=1)).strftime("%Y-%m-%d")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    headers=headers, 
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
                ) as response:
                    
                    # Update rate limiting info
                    self._update_rate_limit_info(response.headers)
                    
                    response_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    if response.status == 200:
                        data = await response.json()
                        flight_data = self._parse_flight_data(flight_number, data, departure_date)
                        
                        if flight_data:
                            self.update_metrics(True, response_time)
                            return flight_data
                        else:
                            self.update_metrics(False, response_time, "No flight data in response")
                            return None
                            
                    elif response.status == 429:
                        # Rate limited
                        self.set_status(ProviderStatus.RATE_LIMITED, "Rate limit exceeded")
                        self._metrics.rate_limit_hits += 1
                        
                        retry_after = response.headers.get("Retry-After")
                        raise RateLimitError(
                            "FlightAware rate limit exceeded", 
                            self.name,
                            int(retry_after) if retry_after else 300
                        )
                        
                    elif response.status == 401:
                        self.set_status(ProviderStatus.UNAVAILABLE, "Authentication failed")
                        raise AuthenticationError("Invalid FlightAware API key", self.name)
                        
                    else:
                        error_text = await response.text()
                        error_msg = f"HTTP {response.status}: {error_text}"
                        self.update_metrics(False, response_time, error_msg)
                        
                        if response.status >= 500:
                            self.set_status(ProviderStatus.DEGRADED, "Server error")
                        
                        raise ProviderError(error_msg, self.name)
                        
        except asyncio.TimeoutError:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Request timeout after {self.timeout_seconds}s"
            self.update_metrics(False, response_time, error_msg)
            raise TimeoutError(error_msg, self.name)
            
        except (aiohttp.ClientError, ConnectionError) as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Network error: {str(e)}"
            self.update_metrics(False, response_time, error_msg)
            self.set_status(ProviderStatus.DEGRADED, error_msg)
            raise ProviderError(error_msg, self.name)
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Unexpected error: {str(e)}"
            self.update_metrics(False, response_time, error_msg)
            logger.exception("Unexpected error in FlightAware provider")
            return None
    
    async def health_check(self) -> bool:
        """Perform health check by making a simple API call"""
        if not self.api_key:
            return False
            
        try:
            # Use a simple endpoint to check API health
            url = f"{self.base_url}/airports/LAX"  # Get LAX airport info
            headers = {
                "x-apikey": self.api_key,
                "Accept": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5.0)
                ) as response:
                    
                    self._update_rate_limit_info(response.headers)
                    
                    if response.status == 200:
                        self.set_status(ProviderStatus.AVAILABLE)
                        return True
                    elif response.status == 401:
                        self.set_status(ProviderStatus.UNAVAILABLE, "Authentication failed")
                        return False
                    elif response.status == 429:
                        self.set_status(ProviderStatus.RATE_LIMITED, "Rate limited")
                        return False
                    else:
                        self.set_status(ProviderStatus.DEGRADED, f"HTTP {response.status}")
                        return False
                        
        except Exception as e:
            error_msg = f"Health check failed: {str(e)}"
            self.set_status(ProviderStatus.UNAVAILABLE, error_msg)
            return False
    
    async def get_multiple_flights(
        self, 
        flight_requests: List[tuple[str, datetime]]
    ) -> Dict[str, Optional[FlightStatusData]]:
        """
        Get status for multiple flights.
        
        FlightAware doesn't have a native batch endpoint, so we make
        concurrent individual requests with rate limiting awareness.
        """
        results = {}
        
        # Limit concurrent requests to avoid overwhelming the API
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def fetch_single(flight_number: str, departure_date: datetime):
            async with semaphore:
                try:
                    result = await self.get_flight_status(flight_number, departure_date)
                    return flight_number, result
                except RateLimitError:
                    # If rate limited, wait and retry once
                    await asyncio.sleep(1)
                    try:
                        result = await self.get_flight_status(flight_number, departure_date)
                        return flight_number, result
                    except Exception:
                        return flight_number, None
                except Exception:
                    return flight_number, None
        
        # Execute all requests concurrently
        tasks = [
            fetch_single(flight_number, departure_date) 
            for flight_number, departure_date in flight_requests
        ]
        
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in completed_results:
            if isinstance(result, tuple):
                flight_number, flight_data = result
                results[flight_number] = flight_data
            else:
                # Handle exceptions
                logger.warning(f"Error in batch flight request: {result}")
        
        return results
    
    def _parse_flight_data(
        self, 
        flight_number: str, 
        api_data: dict, 
        departure_date: datetime
    ) -> Optional[FlightStatusData]:
        """Parse FlightAware API response into standardized format"""
        
        try:
            flights = api_data.get("flights", [])
            if not flights:
                return None
            
            # Find the flight closest to the requested departure date
            target_flight = None
            min_time_diff = None
            
            for flight in flights:
                scheduled_out = flight.get("scheduled_out")
                if not scheduled_out:
                    continue
                    
                flight_departure = datetime.fromisoformat(scheduled_out.replace("Z", "+00:00"))
                time_diff = abs((flight_departure - departure_date).total_seconds())
                
                if min_time_diff is None or time_diff < min_time_diff:
                    min_time_diff = time_diff
                    target_flight = flight
            
            if not target_flight:
                return None
            
            # Extract flight information
            flight_id = f"{flight_number}_{departure_date.strftime('%Y%m%d')}"
            status = target_flight.get("status", "Unknown")
            
            # Parse timestamps
            scheduled_departure = self._parse_timestamp(target_flight.get("scheduled_out"))
            actual_departure = self._parse_timestamp(target_flight.get("actual_out"))
            scheduled_arrival = self._parse_timestamp(target_flight.get("scheduled_in"))
            actual_arrival = self._parse_timestamp(target_flight.get("actual_in"))
            
            # Calculate delay
            delay_minutes = 0
            if actual_departure and scheduled_departure:
                delay_minutes = int((actual_departure - scheduled_departure).total_seconds() / 60)
            
            # Determine disruption status
            is_disrupted = False
            disruption_type = None
            
            if target_flight.get("cancelled"):
                is_disrupted = True
                disruption_type = "CANCELLED"
            elif delay_minutes > 15:  # More than 15 minutes late
                is_disrupted = True
                disruption_type = "DELAYED"
            elif target_flight.get("diverted"):
                is_disrupted = True
                disruption_type = "DIVERTED"
            
            return FlightStatusData(
                flight_id=flight_id,
                status=status,
                delay_minutes=delay_minutes,
                scheduled_departure=scheduled_departure,
                actual_departure=actual_departure,
                scheduled_arrival=scheduled_arrival,
                actual_arrival=actual_arrival,
                gate=target_flight.get("gate_dest"),
                terminal=target_flight.get("terminal_dest"),
                is_disrupted=is_disrupted,
                disruption_type=disruption_type,
                last_updated=datetime.now(timezone.utc),
                source=self.name,
                confidence_score=0.95,  # FlightAware is generally reliable
                raw_data=target_flight
            )
            
        except Exception as e:
            logger.error(f"Error parsing FlightAware response: {e}")
            return None
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse FlightAware timestamp string to datetime"""
        if not timestamp_str:
            return None
            
        try:
            # FlightAware uses ISO format with Z suffix
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except Exception:
            return None
    
    def _update_rate_limit_info(self, headers: dict):
        """Update rate limiting information from response headers"""
        try:
            remaining = headers.get("X-RateLimit-Remaining")
            reset = headers.get("X-RateLimit-Reset")
            
            if remaining:
                self.rate_limit_remaining = int(remaining)
                
                # If we're getting low on requests, set degraded status
                if self.rate_limit_remaining < 10:
                    self.set_status(ProviderStatus.DEGRADED, "Rate limit approaching")
            
            if reset:
                self.rate_limit_reset = datetime.fromtimestamp(int(reset), timezone.utc)
                
        except (ValueError, TypeError):
            pass  # Ignore parsing errors
    
    @property
    def rate_limit_status(self) -> dict:
        """Get current rate limiting status"""
        return {
            "remaining": self.rate_limit_remaining,
            "reset_time": self.rate_limit_reset,
            "status": self.status.value
        }