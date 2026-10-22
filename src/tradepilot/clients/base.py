"""Base HTTP client with rate-limiting, retries, and telemetry."""

import asyncio
import logging
import time
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger("tradepilot.clients")


class BaseApiClient:
    """Base API client implementing token bucket rate limiting and jittered backoff."""
    
    def __init__(
        self,
        base_url: str,
        rate_limit_per_second: float = 2.0,
        timeout: float = 15.0,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.rate_limit_interval = 1.0 / rate_limit_per_second if rate_limit_per_second > 0 else 0
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = headers or {}
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None
        
    async def get_client(self) -> httpx.AsyncClient:
        """Get or initialize the persistent async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self.headers
            )
        return self._client
        
    async def close(self):
        """Close the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            
    async def _throttle(self):
        """Enforce rate limits across concurrent requests."""
        if self.rate_limit_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.rate_limit_interval:
                await asyncio.sleep(self.rate_limit_interval - elapsed)
            self._last_request_time = time.monotonic()

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Execute HTTP request with exponential backoff and rate limit handling."""
        await self._throttle()
        client = await self.get_client()
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}/{endpoint.lstrip('/')}"
        
        attempt = 0
        while attempt <= self.max_retries:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=headers
                )
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", 2 ** attempt))
                    logger.warning(f"Rate limited (429) on {url}. Retrying after {retry_after}s.")
                    await asyncio.sleep(retry_after)
                    attempt += 1
                    continue
                    
                response.raise_for_status()
                return response.json()
                
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                attempt += 1
                if attempt > self.max_retries:
                    logger.error(f"Request failed after {self.max_retries} retries: {url} -> {e}")
                    raise
                backoff = (2 ** attempt) * 0.5
                logger.warning(f"Request error: {e}. Backing off for {backoff:.2f}s (Attempt {attempt}/{self.max_retries})")
                await asyncio.sleep(backoff)
                
        raise RuntimeError(f"Unexpected termination of request retry loop for {url}")
