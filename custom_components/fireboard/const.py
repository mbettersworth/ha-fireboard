"""Constants for the Fireboard integration."""

DOMAIN = "fireboard"
COORDINATOR = "coordinator"
API = "api"

# Configuration
CONF_API_KEY = "api_key"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_API_URL = "api_url"

# Default values
DEFAULT_API_URL = "https://fireboard.io/api"
SCAN_INTERVAL = 60  # seconds

# Attributes
ATTR_DEVICE_ID = "device_id"
ATTR_CHANNEL = "channel"
ATTR_CHANNEL_ID = "channel_id"
ATTR_TEMPERATURE = "temperature"
ATTR_MIN_TEMP = "min_temp"
ATTR_MAX_TEMP = "max_temp"
ATTR_LAST_UPDATED = "last_updated"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_MODEL = "model"
ATTR_BATTERY_LEVEL = "battery_level"
ATTR_SESSION_ID = "session_id"
ATTR_SESSION_TITLE = "session_title"
ATTR_ALERT_ID = "alert_id"

# Units
TEMP_FAHRENHEIT = "°F"
TEMP_CELSIUS = "°C"