"""Caruna sensor platform."""

from datetime import datetime
import logging
import re

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Caruna sensor platform."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    sensors = []

    for customer, metering_points in coordinator.data.items():
        for metering_point, data in metering_points.items():
            for key, val in data.items():
                if (
                    "ByTransferProductParts" in key
                    or "meteringPoint" in key
                    or key == "timestamp"
                ):
                    continue

                device_class = None
                native_unit_of_measurement: UnitOfTemperature | UnitOfEnergy | str | None = (
                    None
                )
                state_class = None
                last_reset = None
                if key.endswith("Consumption") or key.endswith("Production"):
                    device_class = SensorDeviceClass.ENERGY
                    native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
                    state_class = SensorStateClass.TOTAL
                    last_reset = datetime.fromisoformat(data["timestamp"])
                elif key.endswith("Fee") or key.endswith("Tax"):
                    device_class = SensorDeviceClass.MONETARY
                    native_unit_of_measurement = CURRENCY_EURO
                elif key == "temperature":
                    device_class = SensorDeviceClass.TEMPERATURE
                    native_unit_of_measurement = UnitOfTemperature.CELSIUS

                name = f"{data['meteringPointName']} {key}"
                name = f"{re.sub(r'(?<!^)(?=[A-Z])', ' ', name).title()}"
                key = f"{customer}_{metering_point}_{key}"

                sensor = CarunaSensor(
                    coordinator,
                    SensorEntityDescription(
                        key=key,
                        name=name,
                        native_unit_of_measurement=native_unit_of_measurement,
                        device_class=device_class,
                        state_class=state_class,
                        last_reset=last_reset,
                    ),
                    val,
                )
                sensors.append(sensor)
    async_add_entities(sensors)


class CarunaSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
        val,
    ) -> None:
        """Initialize Caruna sensor."""
        super().__init__(coordinator)
        self._attr_native_value = val
        self.entity_description = description
        self._attr_name = f"Caruna {description.name}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.entity_description.key

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for customer, metering_points in self.coordinator.data.items():
            for metering_point, data in metering_points.items():
                for key, val in data.items():
                    if (
                        f"{customer}_{metering_point}_{key}"
                        == self.entity_description.key
                        and self._attr_native_value != val
                    ):
                        _LOGGER.debug("%s = %s", key, val)
                        self._attr_native_value = val

        self.async_write_ha_state()
