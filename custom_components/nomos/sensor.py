"""Sensor platform for Nomos Energy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import NomosDataCoordinator


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_current_price_item(data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the price item that covers the current UTC hour."""
    items: list[dict[str, Any]] = (data.get("prices") or {}).get("items") or []
    now_utc = dt_util.utcnow()
    for item in items:
        ts = dt_util.parse_datetime(item["timestamp"])
        if ts is None:
            continue
        if ts <= now_utc < ts + timedelta(minutes=15):
            return item
    return None


def _get_component_amount(
    item: dict[str, Any] | None, component_type: str
) -> float | None:
    """Extract a named price component from a price item."""
    if item is None:
        return None
    for comp in item.get("components") or []:
        if comp.get("type") == component_type:
            return comp.get("amount")
    return None


def _get_today_prices(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all price items whose local date matches today."""
    items: list[dict[str, Any]] = (data.get("prices") or {}).get("items") or []
    today_local = dt_util.now().date()
    result = []
    for item in items:
        ts = dt_util.parse_datetime(item["timestamp"])
        if ts is None:
            continue
        if dt_util.as_local(ts).date() == today_local:
            result.append(item)
    return result


def _current_price_value(data: dict[str, Any]) -> float | None:
    item = _get_current_price_item(data)
    if item is None:
        return None
    return item.get("amount")


def _current_price_electricity(data: dict[str, Any]) -> float | None:
    return _get_component_amount(_get_current_price_item(data), "electricity")


def _current_price_grid(data: dict[str, Any]) -> float | None:
    return _get_component_amount(_get_current_price_item(data), "grid")


def _current_price_levies(data: dict[str, Any]) -> float | None:
    return _get_component_amount(_get_current_price_item(data), "levies")


def _average_price_today(data: dict[str, Any]) -> float | None:
    today_items = _get_today_prices(data)
    amounts = [i["amount"] for i in today_items if i.get("amount") is not None]
    if not amounts:
        return None
    return round(sum(amounts) / len(amounts), 4)


def _daily_consumption_value(data: dict[str, Any]) -> float | None:
    items: list[dict[str, Any]] = (
        (data.get("consumption") or {}).get("data") or []
    )
    if not items:
        return None
    return items[-1].get("usage")


def _current_price_extra_attrs(data: dict[str, Any]) -> dict[str, Any]:
    today_items = _get_today_prices(data)
    valid = [i for i in today_items if i.get("amount") is not None]
    cheapest = min(valid, key=lambda x: x["amount"]) if valid else None
    most_expensive = max(valid, key=lambda x: x["amount"]) if valid else None
    return {
        "today_prices": [
            {"timestamp": i["timestamp"], "amount": i.get("amount")}
            for i in today_items
        ],
        "cheapest_hour": cheapest["timestamp"] if cheapest else None,
        "most_expensive_hour": most_expensive["timestamp"] if most_expensive else None,
    }


def _daily_consumption_extra_attrs(data: dict[str, Any]) -> dict[str, Any]:
    consumption = data.get("consumption") or {}
    items: list[dict[str, Any]] = consumption.get("data") or []
    last = items[-1] if items else {}
    return {
        "meter_type": consumption.get("meter_type"),
        "data_type": last.get("type"),
        "period_start": last.get("start"),
    }


# ---------------------------------------------------------------------------
# Sensor descriptions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class NomosSensorEntityDescription(SensorEntityDescription):
    """Describes a Nomos sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] = field(
        default=lambda _: None
    )
    extra_attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = field(
        default=None
    )


SENSOR_DESCRIPTIONS: tuple[NomosSensorEntityDescription, ...] = (
    NomosSensorEntityDescription(
        key="current_price",
        translation_key="current_price",
        native_unit_of_measurement="ct/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_current_price_value,
        extra_attrs_fn=_current_price_extra_attrs,
    ),
    NomosSensorEntityDescription(
        key="current_price_electricity",
        translation_key="current_price_electricity",
        native_unit_of_measurement="ct/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_current_price_electricity,
    ),
    NomosSensorEntityDescription(
        key="current_price_grid",
        translation_key="current_price_grid",
        native_unit_of_measurement="ct/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_current_price_grid,
    ),
    NomosSensorEntityDescription(
        key="current_price_levies",
        translation_key="current_price_levies",
        native_unit_of_measurement="ct/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_current_price_levies,
    ),
    NomosSensorEntityDescription(
        key="average_price_today",
        translation_key="average_price_today",
        native_unit_of_measurement="ct/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_average_price_today,
    ),
    NomosSensorEntityDescription(
        key="daily_consumption",
        translation_key="daily_consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=_daily_consumption_value,
        extra_attrs_fn=_daily_consumption_extra_attrs,
    ),
)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nomos sensors from a config entry."""
    coordinator: NomosDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NomosSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class NomosSensor(CoordinatorEntity[NomosDataCoordinator], SensorEntity):
    """Representation of a Nomos Energy sensor."""

    entity_description: NomosSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NomosDataCoordinator,
        description: NomosSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.subscription_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.subscription_id)},
            name=f"Nomos Energy {coordinator.subscription_id}",
            manufacturer="Nomos Energy",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if (
            self.entity_description.extra_attrs_fn is None
            or self.coordinator.data is None
        ):
            return {}
        return self.entity_description.extra_attrs_fn(self.coordinator.data)
