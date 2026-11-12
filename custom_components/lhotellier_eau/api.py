"""Client asynchrone pour l'Agence en ligne L'Hotellier Eau (portail INCOM)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, tzinfo
import html
import json
import re

import aiohttp

from .const import BASE_URL

_TIMEOUT = aiohttp.ClientTimeout(total=30)


class LhotellierApiError(Exception):
    """Erreur de communication avec le portail."""


class LhotellierAuthError(LhotellierApiError):
    """Identifiants refusés."""


@dataclass
class Bill:
    date: date
    reference: str
    amount: float | None
    has_pdf: bool


@dataclass
class MeterRead:
    date: datetime
    index: float | None
    consumption: float | None
    unit: str
    meter: str
    kind: str


@dataclass
class LhotellierData:
    subscription: dict[str, str | None] = field(default_factory=dict)
    bills: list[Bill] = field(default_factory=list)  # plus récente en premier
    reads: list[MeterRead] = field(default_factory=list)  # plus récent en premier
    yearly: list[tuple[str, float]] = field(default_factory=list)  # (année, m³)

    @property
    def last_bill(self) -> Bill | None:
        return self.bills[0] if self.bills else None

    @property
    def last_read(self) -> MeterRead | None:
        return self.reads[0] if self.reads else None


def _strip(fragment: str) -> str:
    txt = html.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", txt).strip()


def _float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def parse_subscription(raw: str) -> dict[str, str | None]:
    txt = _strip(raw)

    def find(pattern: str) -> str | None:
        m = re.search(pattern, txt)
        return m.group(1).strip() if m else None

    return {
        "abonnement": find(r"Abonnement = (\S+)"),
        "reference": find(r"Référence abonnement : (\S+)"),
        "adresse": find(r"Adresse (.+?) Souscrit"),
        "souscrit_le": find(r"Souscrit le (.+?) \|"),
        "mode_paiement": find(r"Mode de paiement : (.+?) \|"),
        "compteur": find(r"Numéro de compteur (\S+)"),
        "compteur_pose_le": find(r"posé le (.+)$"),
    }


def parse_bills(raw: str) -> list[Bill]:
    tbody = re.search(r'<table id="billTable">.*?<tbody>(.*?)</tbody>', raw, re.S)
    bills: list[Bill] = []
    if not tbody:
        return bills
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody.group(1), re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 3:
            continue
        try:
            bill_date = datetime.strptime(_strip(cells[0]), "%d/%m/%Y").date()
        except ValueError:
            continue
        bills.append(
            Bill(
                date=bill_date,
                reference=_strip(cells[1]),
                amount=_float(_strip(cells[2])),
                has_pdf="buildBillPdf.action" in row,
            )
        )
    bills.sort(key=lambda b: b.date, reverse=True)
    return bills


def parse_reads(data: dict | None, tz: tzinfo) -> list[MeterRead]:
    reads: list[MeterRead] = []
    for row in (data or {}).get("rows", []):
        c = row.get("cell", [])
        if len(c) < 7:
            continue
        try:
            when = datetime.strptime(c[1].split(".")[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
        except ValueError:
            continue
        reads.append(
            MeterRead(
                date=when,
                index=_float(c[2]),
                consumption=_float(c[3]),
                unit=c[4],
                meter=c[5],
                kind=c[6],
            )
        )
    reads.sort(key=lambda r: r.date, reverse=True)
    return reads


def parse_yearly(data: dict | None) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for fluid in (data or {}).values():
        gy = (fluid or {}).get("gy") or {}
        for point in gy.get("xdatas", []):
            try:
                out.append((str(point[1]), float(point[2])))
            except (IndexError, TypeError, ValueError):
                continue
        break  # un seul fluide (eau)
    return out


class LhotellierApi:
    """Accès au portail. La session doit avoir son propre CookieJar."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str, tz: tzinfo) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._tz = tz

    async def _text(self, path: str) -> str:
        try:
            async with self._session.get(BASE_URL + path, timeout=_TIMEOUT) as resp:
                resp.raise_for_status()
                return await resp.text(encoding="utf-8", errors="replace")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LhotellierApiError(f"Erreur sur {path} : {err}") from err

    async def _json(self, path: str):
        txt = (await self._text(path)).strip()
        if not txt:
            return None
        try:
            return json.loads(txt)
        except ValueError as err:
            if 'name="loginForm"' in txt:
                raise LhotellierAuthError("Session expirée") from err
            raise LhotellierApiError(f"Réponse non JSON sur {path}") from err

    async def login(self) -> None:
        self._session.cookie_jar.clear()
        page = await self._text("showDisplayBills.action")
        m = re.search(r'action="(encryptionCheck\.external[^"]*)"', page)
        action = html.unescape(m.group(1)) if m else "encryptionCheck.external"
        form = {"j_username": self._username, "password": "", "j_password": self._password}
        try:
            async with self._session.post(BASE_URL + action, data=form, timeout=_TIMEOUT) as resp:
                await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LhotellierApiError(f"Connexion impossible : {err}") from err
        if 'name="loginForm"' in await self._text("showDisplayBills.action"):
            raise LhotellierAuthError("Identifiant ou mot de passe incorrect")

    async def logout(self) -> None:
        try:
            await self._text("logout.external")
        except LhotellierApiError:
            pass

    async def fetch_all(self) -> LhotellierData:
        await self.login()
        try:
            subscription = parse_subscription(await self._text("home/servicePointInfo.action"))
            bills = parse_bills(await self._text("displayBills.action"))
            reads = parse_reads(
                await self._json(
                    "data-meterread-grid.action?_search=false&rows=50&page=1"
                    "&sidx=meterRead.meterReadDate&sord=desc"
                ),
                self._tz,
            )
            yearly = parse_yearly(await self._json("charts.action"))
        finally:
            await self.logout()
        return LhotellierData(subscription=subscription, bills=bills, reads=reads, yearly=yearly)
