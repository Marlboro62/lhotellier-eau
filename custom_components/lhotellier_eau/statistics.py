"""Import des relevés et factures dans les statistiques longue durée (tableau Énergie)."""
from __future__ import annotations

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.unit_conversion import VolumeConverter

from .api import LhotellierData
from .const import DOMAIN
from .history import HistoryPoint, consumption_points, cost_points


def statistic_ids(key: str) -> tuple[str, str]:
    """Identifiants des statistiques (consommation, coût) d'un abonnement."""
    base = slugify(key) or "abonnement"
    return f"{DOMAIN}:{base}_consommation", f"{DOMAIN}:{base}_cout"


def _rows(points: list[HistoryPoint]) -> list[StatisticData]:
    return [StatisticData(start=p.start, state=p.state, sum=p.sum) for p in points]


def async_import_history(hass: HomeAssistant, key: str, data: LhotellierData) -> None:
    """Écrit (ou réécrit) tout l'historique connu : les points existants sont mis à jour."""
    consumption_id, cost_id = statistic_ids(key)
    consumption = consumption_points(data.reads)
    if consumption:
        async_add_external_statistics(
            hass,
            StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name="L'Hotellier Eau – Consommation",
                source=DOMAIN,
                statistic_id=consumption_id,
                unit_class=VolumeConverter.UNIT_CLASS,
                unit_of_measurement=UnitOfVolume.CUBIC_METERS,
            ),
            _rows(consumption),
        )
    cost = cost_points(data.bills, dt_util.get_default_time_zone())
    if cost:
        async_add_external_statistics(
            hass,
            StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name="L'Hotellier Eau – Factures",
                source=DOMAIN,
                statistic_id=cost_id,
                unit_class=None,
                unit_of_measurement=None,
            ),
            _rows(cost),
        )
