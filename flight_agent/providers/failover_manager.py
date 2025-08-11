"""
Failover Manager for flight data providers.

Implements REQ-7.2: Add failover logic between primary and secondary sources
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .interfaces import (
    FlightDataProvider, 
    FlightStatusData, 
    ProviderStatus,
    ProviderError,
    RateLimitError,
    TimeoutError
)

logger = logging.getLogger(__name__)


@dataclass
class FailoverConfig:
    """Configuration for failover behavior"""
    max_retries_per_provider: int = 2
    timeout_between_retries: float = 1.0
    health_check_interval: int = 300  # seconds
    degraded_provider_retry_interval: int = 600  # seconds
    circuit_breaker_threshold: int = 5  # consecutive failures
    circuit_breaker_timeout: int = 300  # seconds
    prefer_cached_over_degraded: bool = True


@dataclass 
class CircuitBreaker:
    """Circuit breaker state for a provider"""
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    is_open: bool = False
    last_success: Optional[datetime] = None


class FailoverManager:
    """
    Manages failover logic between multiple flight data providers.
    
    Implements REQ-7.2: Add failover logic between primary and secondary sources
    
    Features:
    - Automatic failover to backup providers
    - Circuit breaker pattern for failing providers
    - Health monitoring and recovery
    - Performance-based provider selection
    - Retry logic with exponential backoff
    """
    
    def __init__(
        self, 
        providers: List[FlightDataProvider],
        config: Optional[FailoverConfig] = None
    ):
        """
        Initialize failover manager.
        
        Args:
            providers: List of providers (ordered by priority)
            config: Failover configuration
        """
        self.providers = sorted(providers, key=lambda p: p.priority, reverse=True)
        self.config = config or FailoverConfig()
        
        # Circuit breaker state per provider
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            provider.name: CircuitBreaker() for provider in self.providers
        }
        
        # Last health check times
        self.last_health_checks: Dict[str, datetime] = {}
        
        # Performance tracking
        self.provider_performance: Dict[str, List[float]] = {
            provider.name: [] for provider in self.providers
        }
        
        logger.info(f"Failover manager initialized with {len(self.providers)} providers")
    
    async def get_flight_status(
        self, 
        flight_number: str, 
        departure_date: datetime
    ) -> Optional[FlightStatusData]:
        """
        Get flight status with automatic failover.
        
        Tries providers in order of priority with circuit breaker protection.
        """
        
        last_error = None
        
        # Try each provider in priority order
        for provider in self._get_available_providers():
            
            # Skip if circuit breaker is open
            circuit_breaker = self.circuit_breakers[provider.name]
            if self._is_circuit_breaker_open(circuit_breaker):
                logger.debug(f"Circuit breaker open for {provider.name}, skipping")
                continue
            
            # Attempt to get data with retries
            for attempt in range(self.config.max_retries_per_provider):
                try:
                    logger.debug(f"Attempting {provider.name} (attempt {attempt + 1})")
                    
                    result = await provider.get_flight_status(flight_number, departure_date)
                    
                    if result:
                        # Success - reset circuit breaker
                        self._record_success(provider.name)
                        self._update_performance(provider.name, result)
                        logger.info(f"Successfully got flight data from {provider.name}")
                        return result
                    else:
                        # Provider returned None - try next attempt or provider
                        logger.debug(f"{provider.name} returned no data")
                        
                except RateLimitError as e:
                    logger.warning(f"{provider.name} rate limited, trying next provider")
                    self._record_failure(provider.name, str(e))
                    break  # Don't retry rate-limited provider
                    
                except TimeoutError as e:
                    logger.warning(f"{provider.name} timed out (attempt {attempt + 1})")
                    last_error = e
                    
                    if attempt < self.config.max_retries_per_provider - 1:
                        # Wait before retry
                        wait_time = self.config.timeout_between_retries * (2 ** attempt)
                        await asyncio.sleep(wait_time)
                    else:
                        self._record_failure(provider.name, str(e))
                        
                except ProviderError as e:
                    logger.error(f"{provider.name} error: {e}")
                    self._record_failure(provider.name, str(e))
                    last_error = e
                    break  # Don't retry on provider errors
                    
                except Exception as e:
                    logger.exception(f"Unexpected error with {provider.name}")
                    self._record_failure(provider.name, str(e))
                    last_error = e
                    break
        
        # All providers failed
        logger.error(f"All providers failed for {flight_number}")
        if last_error:
            logger.error(f"Last error: {last_error}")
        
        return None
    
    async def get_multiple_flights(
        self, 
        flight_requests: List[tuple[str, datetime]]
    ) -> Dict[str, Optional[FlightStatusData]]:
        """
        Get multiple flights with intelligent provider selection.
        
        Uses the best performing provider for batch requests.
        """
        
        if not flight_requests:
            return {}
        
        # Select best provider for batch operation
        best_provider = self._select_best_provider_for_batch()
        
        if best_provider:
            try:
                logger.info(f"Using {best_provider.name} for batch of {len(flight_requests)} flights")
                results = await best_provider.get_multiple_flights(flight_requests)
                
                # Record success for batch operation
                self._record_success(best_provider.name)
                
                return results
                
            except Exception as e:
                logger.error(f"Batch operation failed on {best_provider.name}: {e}")
                self._record_failure(best_provider.name, str(e))
        
        # Fallback: process individually with failover
        logger.info("Falling back to individual flight requests")
        results = {}
        
        # Process in smaller batches to avoid overwhelming single provider
        batch_size = 10
        for i in range(0, len(flight_requests), batch_size):
            batch = flight_requests[i:i + batch_size]
            
            # Use individual failover for each flight
            tasks = [
                self.get_flight_status(flight_number, departure_date)
                for flight_number, departure_date in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for (flight_number, _), result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results[flight_number] = None
                else:
                    results[flight_number] = result
        
        return results
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Perform health checks on all providers"""
        
        results = {}
        tasks = []
        
        for provider in self.providers:
            # Skip recent health checks
            last_check = self.last_health_checks.get(provider.name)
            if last_check and (datetime.utcnow() - last_check).seconds < 60:
                results[provider.name] = provider.is_available
                continue
            
            tasks.append(self._health_check_provider(provider))
        
        if tasks:
            health_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for provider, result in zip(self.providers, health_results):
                if isinstance(result, bool):
                    results[provider.name] = result
                else:
                    logger.error(f"Health check error for {provider.name}: {result}")
                    results[provider.name] = False
        
        return results
    
    async def _health_check_provider(self, provider: FlightDataProvider) -> bool:
        """Perform health check on a single provider"""
        try:
            is_healthy = await provider.health_check()
            self.last_health_checks[provider.name] = datetime.utcnow()
            
            if is_healthy:
                # If provider was degraded but is now healthy, reset circuit breaker
                circuit_breaker = self.circuit_breakers[provider.name]
                if circuit_breaker.is_open:
                    logger.info(f"Provider {provider.name} recovered, resetting circuit breaker")
                    circuit_breaker.is_open = False
                    circuit_breaker.failure_count = 0
            
            return is_healthy
            
        except Exception as e:
            logger.error(f"Health check failed for {provider.name}: {e}")
            self.last_health_checks[provider.name] = datetime.utcnow()
            return False
    
    def _get_available_providers(self) -> List[FlightDataProvider]:
        """Get list of available providers, checking circuit breakers"""
        available = []
        
        for provider in self.providers:
            circuit_breaker = self.circuit_breakers[provider.name]
            
            if not self._is_circuit_breaker_open(circuit_breaker):
                # Check if degraded provider should be retried
                if provider.status == ProviderStatus.DEGRADED:
                    last_check = self.last_health_checks.get(provider.name)
                    if (last_check and 
                        (datetime.utcnow() - last_check).seconds > self.config.degraded_provider_retry_interval):
                        available.append(provider)
                else:
                    available.append(provider)
        
        return available
    
    def _select_best_provider_for_batch(self) -> Optional[FlightDataProvider]:
        """Select the best provider for batch operations based on performance"""
        
        available_providers = self._get_available_providers()
        if not available_providers:
            return None
        
        # Score providers based on success rate and response time
        best_provider = None
        best_score = 0
        
        for provider in available_providers:
            metrics = provider.metrics
            
            # Skip providers with no history
            if metrics.total_requests == 0:
                continue
            
            # Calculate composite score
            success_weight = 0.7
            speed_weight = 0.3
            
            success_score = metrics.success_rate * success_weight
            
            # Speed score (inverse of response time, capped at 10 seconds)
            if metrics.average_response_time > 0:
                speed_score = (1 / min(metrics.average_response_time, 10)) * speed_weight
            else:
                speed_score = speed_weight  # Perfect score for no recorded time
            
            total_score = success_score + speed_score
            
            if total_score > best_score:
                best_score = total_score
                best_provider = provider
        
        # If no provider has history, use highest priority available
        if not best_provider:
            best_provider = available_providers[0]
        
        return best_provider
    
    def _is_circuit_breaker_open(self, circuit_breaker: CircuitBreaker) -> bool:
        """Check if circuit breaker is open"""
        
        if not circuit_breaker.is_open:
            return False
        
        # Check if timeout has passed
        if (circuit_breaker.last_failure and 
            (datetime.utcnow() - circuit_breaker.last_failure).seconds > self.config.circuit_breaker_timeout):
            circuit_breaker.is_open = False
            circuit_breaker.failure_count = 0
            logger.info("Circuit breaker timeout passed, allowing retry")
            return False
        
        return True
    
    def _record_success(self, provider_name: str):
        """Record successful provider operation"""
        circuit_breaker = self.circuit_breakers.get(provider_name)
        if circuit_breaker:
            circuit_breaker.failure_count = 0
            circuit_breaker.last_success = datetime.utcnow()
            circuit_breaker.is_open = False
    
    def _record_failure(self, provider_name: str, error_message: str):
        """Record provider failure and update circuit breaker"""
        circuit_breaker = self.circuit_breakers.get(provider_name)
        if not circuit_breaker:
            return
        
        circuit_breaker.failure_count += 1
        circuit_breaker.last_failure = datetime.utcnow()
        
        # Open circuit breaker if threshold reached
        if circuit_breaker.failure_count >= self.config.circuit_breaker_threshold:
            circuit_breaker.is_open = True
            logger.warning(f"Circuit breaker opened for {provider_name} after {circuit_breaker.failure_count} failures")
    
    def _update_performance(self, provider_name: str, result: FlightStatusData):
        """Update performance metrics for provider"""
        performance_list = self.provider_performance.get(provider_name, [])
        
        # Add confidence score to performance tracking
        performance_list.append(result.confidence_score)
        
        # Keep only recent performance data (last 100 results)
        if len(performance_list) > 100:
            performance_list.pop(0)
        
        self.provider_performance[provider_name] = performance_list
    
    def get_provider_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all providers"""
        
        stats = {
            "providers": {},
            "circuit_breakers": {},
            "performance_summary": {}
        }
        
        for provider in self.providers:
            name = provider.name
            
            # Provider stats
            stats["providers"][name] = {
                "priority": provider.priority,
                "status": provider.status.value,
                "is_available": provider.is_available,
                "metrics": {
                    "success_rate": provider.metrics.success_rate,
                    "average_response_time": provider.metrics.average_response_time,
                    "total_requests": provider.metrics.total_requests,
                    "failed_requests": provider.metrics.failed_requests,
                    "rate_limit_hits": provider.metrics.rate_limit_hits,
                    "last_successful_call": provider.metrics.last_successful_call.isoformat() if provider.metrics.last_successful_call else None,
                    "last_error": provider.metrics.last_error
                }
            }
            
            # Circuit breaker stats
            circuit_breaker = self.circuit_breakers[name]
            stats["circuit_breakers"][name] = {
                "is_open": circuit_breaker.is_open,
                "failure_count": circuit_breaker.failure_count,
                "last_failure": circuit_breaker.last_failure.isoformat() if circuit_breaker.last_failure else None,
                "last_success": circuit_breaker.last_success.isoformat() if circuit_breaker.last_success else None
            }
            
            # Performance summary
            performance_data = self.provider_performance.get(name, [])
            if performance_data:
                stats["performance_summary"][name] = {
                    "average_confidence": sum(performance_data) / len(performance_data),
                    "recent_operations": len(performance_data)
                }
            else:
                stats["performance_summary"][name] = {
                    "average_confidence": 0.0,
                    "recent_operations": 0
                }
        
        return stats
    
    def add_provider(self, provider: FlightDataProvider):
        """Add a new provider to the failover manager"""
        self.providers.append(provider)
        self.providers.sort(key=lambda p: p.priority, reverse=True)
        
        self.circuit_breakers[provider.name] = CircuitBreaker()
        self.provider_performance[provider.name] = []
        
        logger.info(f"Added provider {provider.name} with priority {provider.priority}")
    
    def remove_provider(self, provider_name: str):
        """Remove a provider from the failover manager"""
        self.providers = [p for p in self.providers if p.name != provider_name]
        
        self.circuit_breakers.pop(provider_name, None)
        self.provider_performance.pop(provider_name, None)
        self.last_health_checks.pop(provider_name, None)
        
        logger.info(f"Removed provider {provider_name}")