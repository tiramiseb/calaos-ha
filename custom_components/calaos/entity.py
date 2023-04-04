from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


class CalaosEntity:
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass, entry_id, item):
        self.entry_id = entry_id
        self.item = item
        self.hass = hass
        self._attr_unique_id = f"{DOMAIN}_{self.item.id}"
        self.entity_id = f"{self.platform}.{self.unique_id}"
        self.schedule_update_ha_state()

    @property
    def device_info(self):
        return DeviceInfo(
            config_entry_id=self.entry_id,
            identifiers={(DOMAIN, self.entry_id, self.item.id)},
            name=self.item.name,
            manufacturer="Calaos",
            model="Calaos v3",
            suggested_area=self.item.room.name,
            via_device=(DOMAIN, self.entry_id)
        )