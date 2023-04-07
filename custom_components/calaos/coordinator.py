import asyncio
import logging
from http.client import RemoteDisconnected
from urllib.error import URLError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry

from pycalaos import Client, ClickType, NbClicks
from pycalaos.item import Item

from .const import DOMAIN, EVENT_DOMAIN, POLL_INTERVAL
from .entity import CalaosEntity

_LOGGER = logging.getLogger(__name__)


class CalaosCoordinator:
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.client = None
        self.entry_id = config_entry.entry_id
        self.calaos_url = config_entry.data["url"]
        self.calaos_username = config_entry.data["username"]
        self.calaos_password = config_entry.data["password"]
        self._entity_by_id = {}
        self._device_id_by_id = {}
        self.item_type_by_device_id = {}
        self._running = False

    async def connect(self) -> None:
        _LOGGER.debug("Connecting to %s", self.calaos_url)
        self._running = True
        self.client = await self.hass.async_add_executor_job(
            Client,
            self.calaos_url,
            self.calaos_username,
            self.calaos_password
        )

    @callback
    def stop(self, *args) -> None:
        _LOGGER.debug("Disconnecting and stopping the pushing poller")
        self._running = False
        self.client = None

    async def declare_noentity_devices(self) -> None:
        dev_registry = device_registry.async_get(self.hass)
        dev_registry.async_get_or_create(
            config_entry_id=self.entry_id,
            identifiers={(DOMAIN, self.entry_id)},
            name="Calaos server",
            manufacturer="Calaos",
            model="Calaos v3",
        )
        for item in self.client.items_by_gui_type("switch"):
            await self.declare_device(dev_registry, self.entry_id, item)
        for item in self.client.items_by_gui_type("switch3"):
            await self.declare_device(dev_registry, self.entry_id, item)
        for item in self.client.items_by_gui_type("switch_long"):
            await self.declare_device(dev_registry, self.entry_id, item)

    @callback
    def register(self, item_id: str, entity: CalaosEntity) -> None:
        self._entity_by_id[item_id] = entity

    async def pushing_poll(self) -> None:
        _LOGGER.debug("Starting the pushing poller for %s", self.calaos_url)
        while self._running:
            asyncio.sleep(POLL_INTERVAL)
            try:
                events = await self.hass.async_add_executor_job(self.client.poll)
            except (RemoteDisconnected, URLError) as ex:
                _LOGGER.error(f"could not poll: {ex}")
                await self.connect()
                continue
            except Exception as ex:
                _LOGGER.error(f"could not poll: {ex}")
                continue
            if len(events) > 0:
                _LOGGER.debug(f"Calaos events: {events}")
                for evt in events:
                    event_type = None
                    if evt.item.id in self._entity_by_id:
                        self._entity_by_id[evt.item.id].async_schedule_update_ha_state(
                        )
                    elif evt.item.gui_type == "switch" and evt.state == True:
                        event_type = "click"
                    elif evt.item.gui_type == "switch3" and evt.state != NbClicks.NONE:
                        if evt.state == NbClicks.SINGLE:
                            event_type = "single_click"
                        elif evt.state == NbClicks.DOUBLE:
                            event_type = "double_click"
                        elif evt.state == NbClicks.TRIPLE:
                            event_type = "triple_click"
                    elif evt.item.gui_type == "switch_long" and evt.state != ClickType.NONE:
                        if evt.state == ClickType.SHORT:
                            event_type = "short_click"
                        elif evt.state == ClickType.LONG:
                            event_type = "long_click"
                    if event_type != None:
                        if evt.item.id in self._device_id_by_id:
                            self.hass.bus.async_fire(
                                EVENT_DOMAIN,
                                {
                                    CONF_DEVICE_ID: self._device_id_by_id[evt.item.id],
                                    CONF_TYPE: event_type
                                }
                            )

    async def declare_device(self, registry: device_registry.DeviceRegistry, entry_id: str, item: Item) -> None:
        device = registry.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(DOMAIN, entry_id, item.id)},
            name=item.name,
            manufacturer="Calaos",
            model="Calaos v3",
            suggested_area=item.room.name,
            via_device=(DOMAIN, entry_id),
        )
        self._device_id_by_id[item.id] = device.id
        self.item_type_by_device_id[device.id] = item.gui_type
