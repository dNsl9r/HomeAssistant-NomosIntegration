# Nomos Energy – HomeAssistant HACS Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A [Home Assistant](https://www.home-assistant.io/) integration for the [Nomos Energy](https://nomos.energy) API.  
Track your dynamic electricity prices, monitor consumption, and submit meter readings – all from within Home Assistant.

---

## Features

| Sensor | Unit | Description |
|---|---|---|
| Current Electricity Price | ct/kWh | Total variable price for the current hour |
| Current Electricity Component | ct/kWh | EPEX Day-Ahead energy share |
| Current Grid Component | ct/kWh | Grid-fee share |
| Current Levies Component | ct/kWh | Taxes & levies share |
| Average Price Today | ct/kWh | Mean of all hourly prices for today |
| Daily Consumption | kWh | Latest available daily consumption |

The **Current Electricity Price** sensor also exposes extra attributes:

- `today_prices` – list of `{timestamp, amount}` for every hour today (great for Apex Charts)
- `cheapest_hour` – ISO timestamp of today's cheapest hour
- `most_expensive_hour` – ISO timestamp of today's most expensive hour

### Service

`nomos.submit_meter_reading` – Send an analog meter reading to Nomos.

| Field | Required | Description |
|---|---|---|
| `subscription_id` | ✅ | Your Nomos subscription ID (e.g. `sub_…`) |
| `value` | ✅ | Cumulative meter reading in kWh |
| `timestamp` | ✅ | ISO 8601 timestamp (e.g. `2024-03-14T12:00:00+00:00`) |
| `message` | ❌ | Optional note |

---

## Installation

### HACS (recommended)

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/dNsl9r/HomeAssistant-NomosIntegration` with category **Integration**
3. Install **Nomos Energy** and restart Home Assistant

### Manual

Copy the `custom_components/nomos` folder into your `config/custom_components/` directory and restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration** and search for **Nomos Energy**
2. Enter your **Client ID** and **Client Secret**
3. If you have multiple subscriptions, select the one you want to integrate

### Getting client credentials

Register an OAuth2 application in the Nomos Dashboard to obtain a `client_id` and `client_secret`.  
The integration uses the **client_credentials** grant type to obtain and automatically renew short-lived access tokens – no manual token management required.

---

## Data refresh

The integration polls the Nomos API every **30 minutes**. Prices update hourly; consumption data is typically available from the previous day (smart meters) or monthly (analog meters).

---

## API Reference

Full Nomos API specification: `https://api.nomos.energy/openapi.2025-12-16.batman.json`
