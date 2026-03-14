"""Sensor platform for the Tripp Lite PDU integration."""

from typing import NamedTuple

from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorEntityDescription,
                                             SensorStateClass)
from homeassistant.const import (UnitOfElectricCurrent,
                                 UnitOfElectricPotential, UnitOfPower)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TrippliteConfigEntry
from .coordinator import TrippliteCoordinator
from .entity import TrippliteEntity
from .utils import get_pdu_slug


class TrippliteSensorSpec(NamedTuple):
    """Definition for a Tripp Lite sensor."""

    description: SensorEntityDescription
    variable_id: int


SENSORS: tuple[TrippliteSensorSpec, ...] = (
    TrippliteSensorSpec(
        description=SensorEntityDescription(
            key="output_voltage",
            name="Output Voltage",
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        ),
        variable_id=24,
    ),
    TrippliteSensorSpec(
        description=SensorEntityDescription(
            key="output_current",
            name="Output Current",
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
        ),
        variable_id=25,
    ),
    TrippliteSensorSpec(
        description=SensorEntityDescription(
            key="output_power",
            name="Output Power",
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
        variable_id=26,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TrippliteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tripp Lite sensors."""
    coordinator = entry.runtime_data
    host = entry.data["host"]

    async_add_entities(
        [
            TrippliteSensorEntity(
                coordinator,
                host,
                entry.entry_id,
                spec,
            )
            for spec in SENSORS
        ],
        update_before_add=True,
    )


class TrippliteSensorEntity(TrippliteEntity, SensorEntity):
    """Representation of a Tripp Lite sensor."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: TrippliteCoordinator,
        host: str,
        entry_id: str,
        spec: TrippliteSensorSpec,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, host)
        self.entity_description = spec.description
        self._variable_id = spec.variable_id
        self._attr_unique_id = f"{entry_id}_{self.entity_description.key}"
        self._attr_translation_key = self.entity_description.key

    @property
    def suggested_object_id(self) -> str:
        """Return suggested entity object id."""
        slug = get_pdu_slug(self._host, self.coordinator.device_info_data)
        return f"{slug}_{self.entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        raw_value = self._get_raw_value()
        return self._coerce_float(raw_value)

    def _get_raw_value(self) -> object | None:
        """Return the raw variable value for this sensor."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None

        variables = data.get("variables")
        if not isinstance(variables, dict):
            return None

        variable = variables.get(self._variable_id)
        if not isinstance(variable, dict):
            return None

        return variable.get("value")

    @staticmethod
    def _coerce_float(raw_value: object) -> float | None:
        """Convert a raw value to float when possible."""
        if raw_value is None:
            return None

        if isinstance(raw_value, (int, float)):
            return float(raw_value)

        if not isinstance(raw_value, str):
            return None

        raw_value = raw_value.strip()
        if not raw_value:
            return None

        try:
            return float(raw_value)
        except ValueError:
            return None
