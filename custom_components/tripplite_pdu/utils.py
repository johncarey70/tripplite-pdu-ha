"""Utility helpers for the Tripp Lite PDU integration."""

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def build_device_info(
    host: str,
    raw_info: dict | None,
    firmware: str | None,
) -> DeviceInfo:
    """Build Home Assistant device info."""
    manufacturer = "Tripp Lite"
    model = None
    serial_number = None
    name = f"Tripp Lite® PDU {host}"

    if isinstance(raw_info, dict):
        manufacturer = raw_info.get("manufacturer") or manufacturer
        model = raw_info.get("model")
        serial_number = raw_info.get("serial_number")

        api_name = raw_info.get("name")
        if api_name and not api_name.startswith("Device"):
            name = api_name

    return DeviceInfo(
        identifiers={(DOMAIN, host)},
        name=name,
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        sw_version=firmware,
    )


def extract_firmware(variables: dict | None) -> str | None:
    """Extract firmware version from variables."""
    if not isinstance(variables, dict):
        return None

    variable = variables.get(3)
    if not isinstance(variable, dict):
        return None

    value = variable.get("value")
    if value is None:
        return None

    return str(value)


def get_pdu_slug(host: str, raw_info: dict | None) -> str:
    """Return a short stable slug for the PDU."""

    if isinstance(raw_info, dict):
        name = raw_info.get("name")

        if isinstance(name, str) and name.startswith("Device"):
            digits = name[6:]
            if digits.isdigit():
                return f"pdu_{digits}"

    return f"pdu_{host.rsplit('.', maxsplit=1)[-1]}"
