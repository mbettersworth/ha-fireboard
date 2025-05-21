# Fireboard Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

This integration connects your Fireboard 2 temperature sensors to Home Assistant, providing temperature data, charts, and alert management for your cooking sessions and BBQ monitoring.

## Features

- Display real-time temperature readings from all connected Fireboard devices
- Track temperature history with interactive charts
- Create and manage temperature alerts (minimum and maximum thresholds)
- Monitor cooking sessions and receive notifications
- Support for multiple devices and temperature probes
- Automatic sensor data updates at configurable intervals

## Prerequisites

- A Fireboard thermometer device (Drive, Drive 2, or FBX2)
- Fireboard Cloud account credentials (username and password)
- Home Assistant installation (version 2021.12 or newer)

## Installation

### HACS (Recommended)

1. Ensure that [HACS](https://hacs.xyz/) is installed.
2. Add this repository as a custom repository in HACS:
   - Go to HACS > Integrations > ⋮ > Custom repositories
   - Add URL `https://github.com/mbettersworth/ha-fireboard`
   - Category: Integration
3. Search for "Fireboard" in the HACS Integrations page and install it.
4. Restart Home Assistant.

### Manual Installation

1. Download the latest release.
2. Copy the `custom_components/fireboard` directory to your Home Assistant's `custom_components` directory.
3. Restart Home Assistant.

## Configuration

1. Go to Settings > Devices & Services.
2. Click "Add Integration" and search for "Fireboard".
3. Enter your Fireboard account credentials:
   - Username (required)
   - Password (required)
   - API key (optional)
4. Set the update interval (default: 60 seconds).
5. Click Submit to complete the setup.

## Available Entities

After configuration, the following entities will be created for each Fireboard device:

- **Device Sensors**: Main device information including battery level and connection status
- **Temperature Sensors**: One sensor per temperature probe/channel
- **Session Status**: Information about active cooking sessions

## Services

This integration provides the following services:

### `fireboard.create_alert`

Create a temperature alert for a specific device and channel.

Parameters:
- `device_id`: The ID of the Fireboard device
- `channel_id`: The ID of the temperature channel
- `min_temp`: Minimum temperature threshold (optional)
- `max_temp`: Maximum temperature threshold (optional)

### `fireboard.delete_alert`

Delete a temperature alert.

Parameters:
- `alert_id`: The ID of the alert to delete

## Example Automations

### Notify when meat is done

```yaml
automation:
  - alias: "Notify when meat is done"
    trigger:
      platform: numeric_state
      entity_id: sensor.fireboard_device_123_probe_1
      above: 145
    action:
      service: notify.mobile_app
      data:
        title: "BBQ Monitor"
        message: "Your meat has reached the target temperature of 145°F!"
```

### Low battery alert

```yaml
automation:
  - alias: "Fireboard Low Battery Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.fireboard_device_123_battery
      below: 20
    action:
      service: notify.mobile_app
      data:
        title: "Fireboard Battery Low"
        message: "Your Fireboard battery is at {{ states('sensor.fireboard_device_123_battery') }}%. Please charge soon."
```

## Dashboard Examples

Add these cards to your Lovelace dashboard for a comprehensive BBQ monitoring system:

### Temperature Gauge

```yaml
type: gauge
entity: sensor.fireboard_device_123_probe_1
name: Brisket Temperature
min: 32
max: 300
needle: true
severity:
  green: 0
  yellow: 180
  red: 210
```

### Temperature History Chart

```yaml
type: history-graph
entities:
  - entity: sensor.fireboard_device_123_probe_1
    name: Brisket
  - entity: sensor.fireboard_device_123_probe_2
    name: Ambient
hours_to_show: 12
refresh_interval: 60
```

## Troubleshooting

If you experience issues with the integration:

1. Enable debug logging by adding this to your `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.fireboard: debug
   ```

2. Check the Home Assistant logs for error messages related to the Fireboard integration.

3. Verify your Fireboard account credentials are correct and that you can log in to the Fireboard Cloud website.

4. If you receive API connection errors, try using your Fireboard API key instead of username/password authentication.

5. If problems persist, open an issue on GitHub with your logs and details about your setup.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This integration is not officially affiliated with or endorsed by Fireboard Labs.