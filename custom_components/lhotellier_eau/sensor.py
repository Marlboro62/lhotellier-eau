"""Capteurs L'Hotellier Eau."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import LhotellierData
from .const import DOMAIN, MANUFACTURER
from .coordinator import LhotellierConfigEntry, LhotellierCoordinator
from .statistics import statistic_ids


@dataclass(frozen=True, kw_only=True)
class LhotellierSensorDescription(SensorEntityDescription):
    value_fn: Callable[[LhotellierData], Any]
    attr_fn: Callable[[LhotellierData], dict[str, Any] | None] = lambda _: None


def _read_attrs(d: LhotellierData) -> dict[str, Any] | None:
    r = d.last_read
    if not r:
        return None
    return {
        "date_releve": r.date.isoformat(),
        "type_releve": r.kind,
        "historique": [
            {"date": x.date.date().isoformat(), "index": x.index, "consommation": x.consumption}
            for x in d.reads
        ],
    }


def _bill_attrs(d: LhotellierData) -> dict[str, Any] | None:
    b = d.last_bill
    if not b:
        return None
    return {
        "date_facture": b.date.isoformat(),
        "reference": b.reference,
        "duplicata_disponible": b.has_pdf,
        "historique": [
            {"date": x.date.isoformat(), "reference": x.reference, "montant": x.amount}
            for x in d.bills
        ],
    }


SENSORS: tuple[LhotellierSensorDescription, ...] = (
    LhotellierSensorDescription(
        key="index",
        translation_key="index",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=0,
        value_fn=lambda d: d.last_read.index if d.last_read else None,
        attr_fn=_read_attrs,
    ),
    LhotellierSensorDescription(
        key="derniere_consommation",
        translation_key="derniere_consommation",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=0,
        value_fn=lambda d: d.last_read.consumption if d.last_read else None,
        attr_fn=lambda d: {"par_annee": {y: v for y, v in d.yearly}} if d.yearly else None,
    ),
    LhotellierSensorDescription(
        key="dernier_releve",
        translation_key="dernier_releve",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.last_read.date if d.last_read else None,
    ),
    LhotellierSensorDescription(
        key="derniere_facture",
        translation_key="derniere_facture",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
        value_fn=lambda d: d.last_bill.amount if d.last_bill else None,
        attr_fn=_bill_attrs,
    ),
    LhotellierSensorDescription(
        key="date_derniere_facture",
        translation_key="date_derniere_facture",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: d.last_bill.date if d.last_bill else None,
    ),
    LhotellierSensorDescription(
        key="mode_paiement",
        translation_key="mode_paiement",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.subscription.get("mode_paiement"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LhotellierConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(LhotellierSensor(coordinator, desc) for desc in SENSORS)


class LhotellierSensor(CoordinatorEntity[LhotellierCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: LhotellierSensorDescription

    def __init__(self, coordinator: LhotellierCoordinator, description: LhotellierSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        sub = coordinator.data.subscription
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.unique_id))},
            name="Compteur d'eau",
            manufacturer=MANUFACTURER,
            model="Agence en ligne",
            serial_number=sub.get("compteur"),
            configuration_url="https://serviceclients.lhotellier-eau.fr/wp/",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attrs = self.entity_description.attr_fn(self.coordinator.data)
        key = self.entity_description.key
        if key in ("index", "derniere_facture"):
            # Statistique longue durée avec tout l'historique (tableau Énergie, cartes)
            consumption_id, cost_id = statistic_ids(str(self.coordinator.config_entry.unique_id))
            attrs = {**(attrs or {}), "statistique": consumption_id if key == "index" else cost_id}
        return attrs
