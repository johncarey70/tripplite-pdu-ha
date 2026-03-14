"""Base entity for the Tripp Lite PDU integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TrippliteCoordinator
from .utils import build_device_info


class TrippliteEntity(CoordinatorEntity[TrippliteCoordinator]):
    """Base entity for Tripp Lite devices."""

    _attr_should_poll = False

    def __init__(self, coordinator: TrippliteCoordinator, host: str) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._host = host

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        data = self.coordinator.data
        firmware = data.get("firmware") if isinstance(data, dict) else None

        return build_device_info(
            self._host,
            self.coordinator.device_info_data,
            firmware,
        )
