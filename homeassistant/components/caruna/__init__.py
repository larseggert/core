"""The Caruna integration."""
from datetime import datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .pycaruna.pycaruna import (
    get_cons_hours,
    get_metering_points,
    login_caruna,
    logout_caruna,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class Caruna:
    """The Caruna integration."""

    def __init__(self, hass: HomeAssistant, conf) -> None:
        """Initialize."""
        self.conf = conf
        self.hass = hass

    async def get_latest_data(self):
        """Retrieve latest consumption data."""
        yesterday = dt_util.now() - timedelta(days=2)
        try:
            (session, info) = await self.hass.async_add_executor_job(
                login_caruna, self.conf["username"], self.conf["password"]
            )
            # _LOGGER.debug("session %s info %s", session, info)

            data = {}
            for customer in info["user"]["ownCustomerNumbers"]:
                # _LOGGER.debug("customer %s", customer)
                token = info["token"]
                # _LOGGER.debug("token %s", token)

                metering_points = await self.hass.async_add_executor_job(
                    get_metering_points, session, token, customer
                )
                # _LOGGER.debug("metering_points %s", metering_points)

                for mp_id, mp_name in metering_points:
                    # _LOGGER.debug("metering_point %s", mp_id)
                    consumption = await self.hass.async_add_executor_job(
                        get_cons_hours,
                        session,
                        token,
                        customer,
                        mp_id,
                        str(yesterday.year),
                        str(yesterday.month),
                        str(yesterday.day),
                    )
                    # _LOGGER.debug(consumption)

                    if consumption and "temperature" in consumption[0]:
                        latest = max(
                            consumption,
                            key=lambda d: datetime.fromisoformat(d["timestamp"]),
                        )
                        _LOGGER.debug(latest)
                        latest["meteringPointID"] = mp_id
                        latest["meteringPointName"] = mp_name
                        if customer not in data:
                            data[customer] = {}
                        data[customer][mp_id] = latest

            await self.hass.async_add_executor_job(logout_caruna, session)
            _LOGGER.debug(data)
            return data

        except Exception as e:
            _LOGGER.exception(e)
            raise


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Caruna integration."""
    conf = config[DOMAIN]
    caruna = Caruna(hass, conf)
    coordinator = DataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        name=DOMAIN,
        update_method=caruna.get_latest_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=conf["scan_interval"]),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN] = {
        "conf": conf,
        "coordinator": coordinator,
    }
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, conf))
    return True
