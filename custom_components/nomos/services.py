"""Services for the Nomos Energy integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, NOMOS_API_BASE

_LOGGER = logging.getLogger(__name__)

SERVICE_SUBMIT_METER_READING = "submit_meter_reading"

SUBMIT_METER_READING_SCHEMA = vol.Schema(
    {
        vol.Required("subscription_id"): cv.string,
        vol.Required("value"): vol.Coerce(float),
        vol.Required("timestamp"): cv.string,
        vol.Optional("message"): cv.string,
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register Nomos services."""

    async def handle_submit_meter_reading(call: ServiceCall) -> None:
        """Submit an analog meter reading to Nomos."""
        subscription_id: str = call.data["subscription_id"]
        value: float = call.data["value"]
        timestamp: str = call.data["timestamp"]
        message: str | None = call.data.get("message")

        # Look up the coordinator that owns this subscription
        coordinator = None
        for entry_coordinator in hass.data.get(DOMAIN, {}).values():
            if entry_coordinator.subscription_id == subscription_id:
                coordinator = entry_coordinator
                break

        if coordinator is None:
            _LOGGER.error(
                "submit_meter_reading: no Nomos entry found for subscription '%s'",
                subscription_id,
            )
            return

        payload: dict[str, Any] = {"value": value, "timestamp": timestamp}
        if message:
            payload["message"] = message

        session = async_get_clientsession(hass)
        try:
            token = await coordinator.async_get_access_token()
            async with session.post(
                f"{NOMOS_API_BASE}/subscriptions/{subscription_id}/meter_readings",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            ) as resp:
                if not resp.ok:
                    body = await resp.text()
                    _LOGGER.error(
                        "Failed to submit meter reading for subscription %s: HTTP %s, payload=%s, response=%s",
                        subscription_id,
                        resp.status,
                        payload,
                        body,
                    )
                    return
                resp.raise_for_status()
                _LOGGER.info(
                    "Meter reading submitted for subscription %s (value=%s)",
                    subscription_id,
                    value,
                )
        except aiohttp.ClientResponseError as err:
            _LOGGER.error(
                "Failed to submit meter reading for subscription %s: HTTP %s",
                subscription_id,
                err.status,
            )
        except aiohttp.ClientError as err:
            _LOGGER.error(
                "Failed to submit meter reading for subscription %s: %s",
                subscription_id,
                err,
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SUBMIT_METER_READING,
        handle_submit_meter_reading,
        schema=SUBMIT_METER_READING_SCHEMA,
    )
