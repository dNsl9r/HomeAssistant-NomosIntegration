# Development Guide – Nomos Energy Integration

This is a Home Assistant **custom component** written in pure Python. There is nothing to compile – Home Assistant loads the Python files directly. This guide covers how to set up a development environment, validate the code, and install the integration.

---

## Prerequisites

| Tool | Minimum version | Purpose |
|---|---|---|
| Python | 3.12 | HA runtime requirement |
| Git | any | Source control |
| Home Assistant | 2024.1.0 | Runtime |

---

## Repository layout

```
HomeAssistant-NomosIntegration/
├── custom_components/
│   └── nomos/                  ← drop this folder into HA's config dir
│       ├── __init__.py
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── manifest.json
│       ├── sensor.py
│       ├── services.py
│       ├── services.yaml
│       ├── strings.json
│       └── translations/
│           └── en.json
├── hacs.json
├── README.md
└── DEVELOPMENT.md
```

---

## Option A – Manual installation (simplest)

1. **Copy** the `custom_components/nomos` folder into your Home Assistant config directory:

   ```
   /config/custom_components/nomos/
   ```

   On a typical Home Assistant OS installation the config directory is at `/homeassistant/` or `/config/` (accessible via the **File editor** or **SSH add-on**).

2. **Restart** Home Assistant.

3. Go to **Settings → Devices & Services → Add Integration**, search for **Nomos Energy**, and follow the setup wizard.

---

## Option B – HACS custom repository

1. Open HACS in Home Assistant.
2. Click **Integrations** → ⋮ (three dots) → **Custom repositories**.
3. Add `https://github.com/dNsl9r/HomeAssistant-NomosIntegration` with category **Integration**.
4. Click **Download** on the **Nomos Energy** card.
5. **Restart** Home Assistant.
6. Add the integration via **Settings → Devices & Services**.

---

## Option C – Development setup (for contributors)

### 1. Clone the repository

```bash
git clone https://github.com/dNsl9r/HomeAssistant-NomosIntegration.git
cd HomeAssistant-NomosIntegration
```

### 2. Create a virtual environment (optional but recommended)

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install Home Assistant for local testing

```bash
pip install homeassistant
```

> **Tip:** Pin to the same version you run in production (e.g. `pip install homeassistant==2024.12.0`).

### 4. Symlink the custom component into a local HA config

```bash
mkdir -p /tmp/ha-config/custom_components
ln -s "$(pwd)/custom_components/nomos" /tmp/ha-config/custom_components/nomos
```

### 5. Run Home Assistant with the dev config

```bash
hass -c /tmp/ha-config
```

Open `http://localhost:8123` and set up the integration there.

---

## Linting and type-checking

The integration follows the [Home Assistant code style](https://developers.home-assistant.io/docs/development_guidelines).

```bash
pip install ruff mypy
```

**Ruff (linter + formatter):**
```bash
ruff check custom_components/nomos/
ruff format --check custom_components/nomos/
```

**Mypy (static type checking):**
```bash
mypy custom_components/nomos/ --ignore-missing-imports
```

There is no test suite yet. Unit tests can be added under a `tests/` directory using `pytest-homeassistant-custom-component`:

```bash
pip install pytest pytest-homeassistant-custom-component
pytest tests/
```

---

## Validating the manifest

Use the official [HACS Action](https://github.com/hacs/action) or the HA integration validator:

```bash
pip install homeassistant-stubs
python -c "
import json, sys
m = json.load(open('custom_components/nomos/manifest.json'))
required = {'domain','name','config_flow','documentation','iot_class','version','codeowners'}
missing = required - m.keys()
if missing:
    sys.exit(f'Missing manifest keys: {missing}')
print('manifest.json OK')
"
```

---

## Making changes

1. Edit files under `custom_components/nomos/`.
2. Restart Home Assistant (or use the **Developer Tools → YAML → Reload** option for some changes).
3. Check **Settings → System → Logs** for errors from the `custom_components.nomos` logger.

### Useful HA log filter

Add to your `configuration.yaml` to get verbose logs from this integration:

```yaml
logger:
  default: warning
  logs:
    custom_components.nomos: debug
```

---

## Releasing a new version

1. Bump `"version"` in `custom_components/nomos/manifest.json`.
2. Commit and push to `main` / `master`.
3. Create a GitHub Release with a tag matching the version (e.g. `v1.1.0`).
4. HACS will detect the new release automatically.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "Integration not found" in HA | Files not in the right path | Check `config/custom_components/nomos/__init__.py` exists |
| "Invalid client credentials" | Wrong `client_id` / `client_secret` | Re-check credentials from the e-mail you received |
| Sensors show `unknown` | First data fetch failed | Check HA logs; the API may be temporarily unavailable |
| Entity names show raw keys (e.g. `current_price`) | Missing `translations/en.json` | Ensure the `translations/` folder was copied along with the rest of the component |
| Token errors in logs | API credentials expired or revoked | Contact Nomos support for new credentials |
