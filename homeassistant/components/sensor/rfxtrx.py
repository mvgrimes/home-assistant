"""
Support for RFXtrx sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rfxtrx/
"""
import logging

import voluptuous as vol

import homeassistant.components.rfxtrx as rfxtrx
import homeassistant.helpers.config_validation as cv
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.rfxtrx import (
    ATTR_NAME, ATTR_FIRE_EVENT, ATTR_DATA_TYPE, CONF_AUTOMATIC_ADD,
    CONF_FIRE_EVENT, CONF_DEVICES, DATA_TYPES, CONF_DATA_TYPE)

DEPENDENCIES = ['rfxtrx']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {
        cv.string: vol.Schema({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
            vol.Optional(CONF_DATA_TYPE, default=[]):
            vol.All(cv.ensure_list, [vol.In(DATA_TYPES.keys())]),
        })
    },
    vol.Optional(CONF_AUTOMATIC_ADD, default=False):  cv.boolean,
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the RFXtrx platform."""
    from RFXtrx import SensorEvent
    sensors = []
    for packet_id, entity_info in config[CONF_DEVICES].items():
        event = rfxtrx.get_rfx_object(packet_id)
        device_id = "sensor_" + slugify(event.device.id_string.lower())
        if device_id in rfxtrx.RFX_DEVICES:
            continue
        _LOGGER.info("Add %s rfxtrx.sensor", entity_info[ATTR_NAME])

        sub_sensors = {}
        data_types = entity_info[ATTR_DATA_TYPE]
        if not data_types:
            data_types = ['']
            for data_type in DATA_TYPES:
                if data_type in event.values:
                    data_types = [data_type]
                    break
        for _data_type in data_types:
            new_sensor = RfxtrxSensor(None, entity_info[ATTR_NAME],
                                      _data_type, entity_info[ATTR_FIRE_EVENT])
            sensors.append(new_sensor)
            sub_sensors[_data_type] = new_sensor
        rfxtrx.RFX_DEVICES[device_id] = sub_sensors
    add_devices_callback(sensors)

    def sensor_update(event):
        """Handle sensor updates from the RFXtrx gateway."""
        if not isinstance(event, SensorEvent):
            return

        device_id = "sensor_" + slugify(event.device.id_string.lower())

        if device_id in rfxtrx.RFX_DEVICES:
            sensors = rfxtrx.RFX_DEVICES[device_id]
            for key in sensors:
                sensor = sensors[key]
                sensor.event = event
                # Fire event
                if sensors[key].should_fire_event:
                    sensor.hass.bus.fire(
                        "signal_received", {
                            ATTR_ENTITY_ID:
                                sensors[key].entity_id,
                        }
                    )
            return

        # Add entity if not exist and the automatic_add is True
        if not config[CONF_AUTOMATIC_ADD]:
            return

        pkt_id = "".join("{0:02x}".format(x) for x in event.data)
        _LOGGER.info("Automatic add rfxtrx.sensor: %s", pkt_id)

        data_type = ''
        for _data_type in DATA_TYPES:
            if _data_type in event.values:
                data_type = _data_type
                break
        new_sensor = RfxtrxSensor(event, pkt_id, data_type)
        sub_sensors = {}
        sub_sensors[new_sensor.data_type] = new_sensor
        rfxtrx.RFX_DEVICES[device_id] = sub_sensors
        add_devices_callback([new_sensor])

    if sensor_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(sensor_update)


class RfxtrxSensor(Entity):
    """Representation of a RFXtrx sensor."""

    def __init__(self, event, name, data_type, should_fire_event=False):
        """Initialize the sensor."""
        self.event = event
        self._name = name
        self.should_fire_event = should_fire_event
        self.data_type = data_type
        self._unit_of_measurement = DATA_TYPES.get(data_type, '')

    def __str__(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.event:
            return None
        return self.event.values.get(self.data_type)

    @property
    def name(self):
        """Get the name of the sensor."""
        return "{} {}".format(self._name, self.data_type)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if not self.event:
            return None
        return self.event.values

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement
