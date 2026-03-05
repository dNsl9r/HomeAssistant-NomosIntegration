"""Data coordinator for Nomos Energy."""

from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_SUBSCRIPTION_ID, DOMAIN, NOMOS_API_BASE

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=30)
# Refresh the token this many seconds before it actually expires
_TOKEN_REFRESH_BUFFER = 60


class NomosDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage fetching Nomos Energy data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.entry_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self._client_id: str = entry.data[CONF_CLIENT_ID]
        self._client_secret: str = entry.data[CONF_CLIENT_SECRET]
        self.subscription_id: str = entry.data[CONF_SUBSCRIPTION_ID]

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def async_get_access_token(self) -> str:
        """Return a valid access token, refreshing via client_credentials if needed."""
        if (
            self._access_token is None
            or time.monotonic() >= self._token_expires_at - _TOKEN_REFRESH_BUFFER
        ):
            await self._async_refresh_token()
        assert self._access_token is not None
        return self._access_token

    async def _async_refresh_token(self) -> None:
        """Obtain a new access token using the client_credentials grant."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"{NOMOS_API_BASE}/oauth/token",
                auth=aiohttp.BasicAuth(self._client_id, self._client_secret),
                data={"grant_type": "client_credentials"},
            ) as resp:
                if resp.status == 401:
                    raise ConfigEntryAuthFailed("Invalid client credentials")
                resp.raise_for_status()
                data = await resp.json()
        except ConfigEntryAuthFailed:
            raise
        except aiohttp.ClientResponseError as err:
            raise UpdateFailed(
                f"Could not obtain access token: HTTP {err.status}"
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Could not obtain access token: {err}") from err

        self._access_token = data["access_token"]
        expires_in: int = data.get("expires_in", 3600)
        self._token_expires_at = time.monotonic() + expires_in
        _LOGGER.debug("Access token refreshed, expires in %s seconds", expires_in)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch prices and consumption from the Nomos API."""
        token = await self.async_get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        today = dt_util.now().strftime("%Y-%m-%d")
        tomorrow = (dt_util.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        seven_days_ago = (dt_util.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        session = async_get_clientsession(self.hass)

        # Fetch prices for today and tomorrow
        prices_data: dict[str, Any] = {}
        try:
            async with session.get(
                f"{NOMOS_API_BASE}/subscriptions/{self.subscription_id}/prices",
                headers=headers,
                params={"start": today, "end": tomorrow},
            ) as resp:
                if resp.status == 401:
                    raise ConfigEntryAuthFailed("Access token rejected by prices endpoint")
                resp.raise_for_status()
                prices_data = await resp.json()
        except ConfigEntryAuthFailed:
            raise
        except aiohttp.ClientResponseError as err:
            raise UpdateFailed(f"Error fetching prices: {err}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Connection error fetching prices: {err}") from err

        # Fetch consumption for the last 7 days at daily resolution
        consumption_data: dict[str, Any] = {}
        try:
            async with session.get(
                f"{NOMOS_API_BASE}/subscriptions/{self.subscription_id}/consumption",
                headers=headers,
                params={
                    "start": seven_days_ago,
                    "end": today,
                },
            ) as resp:
                resp.raise_for_status()
                consumption_data = await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.warning("Could not fetch consumption data: %s", err)

        return {
            "prices": prices_data,
            "consumption": consumption_data,
        }
