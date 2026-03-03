"""Config flow for Nomos Energy integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_SUBSCRIPTION_ID,
    DOMAIN,
    NOMOS_API_BASE,
)

_LOGGER = logging.getLogger(__name__)


class InvalidAuth(Exception):
    """Raised when the client credentials are invalid."""


class CannotConnect(Exception):
    """Raised when connection to the Nomos API fails."""


class NoSubscriptions(Exception):
    """Raised when no subscriptions are found."""


class NomosConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nomos Energy."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client_id: str | None = None
        self._client_secret: str | None = None
        self._subscriptions: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step – ask for client credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID]
            client_secret = user_input[CONF_CLIENT_SECRET]
            try:
                subscriptions = await self._validate_credentials(
                    client_id, client_secret
                )
            except InvalidAuth:
                errors["base"] = "invalid_credentials"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except NoSubscriptions:
                errors["base"] = "no_subscriptions"
            else:
                self._client_id = client_id
                self._client_secret = client_secret
                self._subscriptions = subscriptions

                if len(subscriptions) == 1:
                    return await self._create_entry(subscriptions[0]["id"])

                return await self.async_step_subscription()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            errors=errors,
        )

    async def async_step_subscription(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick which subscription to integrate."""
        if user_input is not None:
            return await self._create_entry(user_input[CONF_SUBSCRIPTION_ID])

        subscription_options = {
            sub["id"]: f"{sub.get('number') or sub['id']} ({sub['status']})"
            for sub in self._subscriptions
        }

        return self.async_show_form(
            step_id="subscription",
            data_schema=vol.Schema(
                {vol.Required(CONF_SUBSCRIPTION_ID): vol.In(subscription_options)}
            ),
        )

    async def _create_entry(self, subscription_id: str) -> ConfigFlowResult:
        """Create the config entry for a specific subscription."""
        await self.async_set_unique_id(subscription_id)
        self._abort_if_unique_id_configured()

        sub = next(
            (s for s in self._subscriptions if s["id"] == subscription_id), None
        )
        title = (
            f"Nomos {sub.get('number') or subscription_id}"
            if sub
            else f"Nomos {subscription_id}"
        )

        return self.async_create_entry(
            title=title,
            data={
                CONF_CLIENT_ID: self._client_id,
                CONF_CLIENT_SECRET: self._client_secret,
                CONF_SUBSCRIPTION_ID: subscription_id,
            },
        )

    async def _validate_credentials(
        self, client_id: str, client_secret: str
    ) -> list[dict[str, Any]]:
        """Obtain an access token and return available subscriptions."""
        session = async_get_clientsession(self.hass)

        # Exchange client credentials for an access token
        try:
            async with session.post(
                f"{NOMOS_API_BASE}/oauth/token",
                auth=aiohttp.BasicAuth(client_id, client_secret),
                json={"grant_type": "client_credentials"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuth
                resp.raise_for_status()
                token_data = await resp.json()
        except InvalidAuth:
            raise
        except aiohttp.ClientResponseError as err:
            raise CannotConnect from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect from err

        access_token: str = token_data["access_token"]

        # List subscriptions to confirm the account has at least one
        try:
            async with session.get(
                f"{NOMOS_API_BASE}/subscriptions",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuth
                resp.raise_for_status()
                data = await resp.json()
        except InvalidAuth:
            raise
        except aiohttp.ClientResponseError as err:
            raise CannotConnect from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect from err

        subscriptions = data.get("items", [])
        if not subscriptions:
            raise NoSubscriptions

        return subscriptions
