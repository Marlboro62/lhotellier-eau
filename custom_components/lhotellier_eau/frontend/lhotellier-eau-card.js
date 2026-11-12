/**
 * lhotellier-eau-card — « Carte Eau L'Hotellier »
 *
 * Carte Lovelace fournie avec l'intégration L'Hotellier Eau (chargée automatiquement).
 * Même style que les cartes Enedis Linky New et Gazpar (MyElectricalData).
 *
 * type: custom:lhotellier-eau-card
 * entity: sensor.compteur_d_eau_index_compteur          (trouvé seul si absent)
 * bill_entity: sensor.compteur_d_eau_derniere_facture    (trouvé seul si absent)
 */

const CARD_VERSION = "1.1.0-beta.2";

/* ---------------------------------------------------------------- données */

const WATER = {
  /** "2025-12-08" -> date locale (new Date() la lirait en UTC) */
  date(v) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(v || ""));
    return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
  },
  num(v) {
    if (v === undefined || v === null || v === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  },
  list(v) { return Array.isArray(v) ? v : []; },
  /** Relevés du plus récent au plus ancien, avec la période et la moyenne par jour. */
  reads(attr) {
    const rows = WATER.list(attr?.historique)
      .map((r) => ({ date: WATER.date(r.date), index: WATER.num(r.index), m3: WATER.num(r.consommation) }))
      .filter((r) => r.date)
      .sort((a, b) => b.date - a.date);
    rows.forEach((r, i) => {
      const prev = rows[i + 1];
      if (r.m3 === null && prev && r.index !== null && prev.index !== null) r.m3 = r.index - prev.index;
      r.from = prev ? prev.date : null;
      r.startIndex = prev ? prev.index : r.index !== null && r.m3 !== null ? r.index - r.m3 : null;
      r.days = prev ? Math.round((r.date - prev.date) / 86400000) : null;
      r.perDay = r.m3 !== null && r.days ? (r.m3 * 1000) / r.days : null; // litres par jour
      r.i = i;
    });
    if (rows[0] && attr?.type_releve) rows[0].kind = String(attr.type_releve);
    return rows;
  },
  /** Factures de la plus récente à la plus ancienne. */
  bills(attr) {
    return WATER.list(attr?.historique)
      .map((b) => ({ date: WATER.date(b.date), amount: WATER.num(b.montant) }))
      .filter((b) => b.date && b.amount !== null)
      .sort((a, b) => b.date - a.date);
  },
  est(r) { return /estim/i.test(r.kind || ""); },
};

/* ------------------------------------------------------------- affichage */

const fmt = (n, digits = 1) =>
  n === null || n === undefined
    ? "—"
    : Number(n).toLocaleString("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const euro = (n) =>
  n === null || n === undefined ? "—" : Number(n).toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const longDate = (d) => (d ? d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" }) : "—");
const shortDate = (d) => (d ? d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" }).replace(".", "") : "");

/** Classe de thème, comme les cartes Linky New : v2 (bleu nuit), auto (clair ou sombre selon HA), ha (thème HA). */
const themeClass = (theme, hass) => {
  const light = hass?.themes?.darkMode === false;
  if (theme === "ha") return `th-ha${light ? " light" : ""}`;
  if (theme === "auto") return `th-v2${light ? " light" : ""}`;
  return "th-v2";
};

/** Taille de la police (100 % = taille d'origine). */
const sizeStyle = (c) => {
  const fs = Number(c.font_size);
  return Number.isFinite(fs) && fs >= 50 && fs <= 200 && fs !== 100 ? ` style="--fs: ${fs / 100}"` : "";
};

/** Évolution en % : une hausse de consommation est en orange, une baisse en vert. */
const evo = (cur, prev, suffix) => {
  if (cur === null || prev === null || !prev) return "";
  const e = ((cur - prev) / Math.abs(prev)) * 100;
  return `<div class="evo ${e > 0 ? "up" : "down"}">${e > 0 ? "+" : ""}${fmt(e, 1)} %${suffix}</div>`;
};

const DROP_ICON = `<svg viewBox="0 0 32 32" aria-hidden="true"><path class="drop" d="M16 3.2c4.6 6 9.2 11 9.2 16.1a9.2 9.2 0 0 1-18.4 0C6.8 14.2 11.4 9.2 16 3.2z"/><path class="shine" d="M11.6 19.6a4.6 4.6 0 0 0 3.4 4.6"/></svg>`;

const DEFAULTS = {
  title: "Eau",
  reads: 6,
  bills: 4,
  show_bills: true,
  theme: "v2",
  font_size: 100,
};

/** Capteurs de l'intégration : attribut historique avec des index (relevés) ou des montants (factures). */
const isReadSensor = (st) => WATER.list(st?.attributes?.historique).some((r) => r && "index" in r);
const isBillSensor = (st) => WATER.list(st?.attributes?.historique).some((r) => r && "montant" in r);
const findSensor = (hass, test, near) => {
  const states = hass?.states || {};
  const ids = Object.keys(states).filter((id) => id.startsWith("sensor.") && test(states[id]));
  const dev = near && hass?.entities?.[near]?.device_id;
  return (dev && ids.find((id) => hass.entities?.[id]?.device_id === dev)) || ids[0] || null;
};

class LhotellierEauCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("lhotellier-eau-card-editor");
  }

  static getStubConfig(hass) {
    return { entity: findSensor(hass, isReadSensor) || "sensor.compteur_d_eau_index_compteur" };
  }

  setConfig(config) {
    this._config = { ...DEFAULTS, ...(config || {}) };
    this._config.reads = Number(this._config.reads) || DEFAULTS.reads;
    this._config.bills = Number(this._config.bills) || DEFAULTS.bills;
    this._selected = 0;
    this._sig = null;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => {
        const t = ev.target.closest?.("[data-i]");
        if (!t) return;
        this._selected = Number(t.dataset.i);
        this._render(true);
      });
    }
    this._render(true);
  }

  set hass(hass) {
    this._hass = hass;
    this._render(false);
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  _entities() {
    const c = this._config, hass = this._hass;
    const read = c.entity && hass.states[c.entity] ? c.entity : findSensor(hass, isReadSensor);
    const bill = c.bill_entity && hass.states[c.bill_entity] ? c.bill_entity : findSensor(hass, isBillSensor, read);
    return { read, bill };
  }

  _render(force) {
    if (!this._config || !this._hass || !this.shadowRoot) return;
    const c = this._config;
    const ids = this._entities();
    const rs = ids.read ? this._hass.states[ids.read] : null;
    const bs = ids.bill ? this._hass.states[ids.bill] : null;
    const sig = `${c.theme}|${this._hass.themes?.darkMode}|${rs?.last_updated || "-"}|${bs?.last_updated || "-"}`;
    if (!force && sig === this._sig) return;
    this._sig = sig;
    const theme = themeClass(c.theme, this._hass);
    if (!rs) {
      this.shadowRoot.innerHTML = `${STYLE}<ha-card class="${theme}"${sizeStyle(c)}><div class="empty">
        <strong>Capteur introuvable${c.entity ? ` : ${esc(c.entity)}` : ""}</strong>
        <span>La carte lit le capteur <b>Index compteur</b> de l'intégration L'Hotellier Eau
        (par défaut <code>sensor.compteur_d_eau_index_compteur</code>).</span></div></ha-card>`;
      return;
    }
    const reads = WATER.reads(rs.attributes);
    const bills = bs ? WATER.bills(bs.attributes) : [];
    const shown = reads.slice(0, Math.max(1, Math.min(c.reads, reads.length)));
    if (this._selected >= shown.length) this._selected = 0;
    const body = reads.length
      ? `${this._hero(reads, rs)}${this._tiles(reads, bills)}${this._chart(shown)}${this._selected > 0 ? this._detail(shown[this._selected]) : ""}${c.show_bills !== false ? this._bills(bills) : ""}`
      : `<div class="empty"><span>Pas encore de relevé dans <code>${esc(ids.read)}</code>.</span></div>`;
    this.shadowRoot.innerHTML = `${STYLE}<ha-card class="${theme} water"${sizeStyle(c)}>${this._header(reads)}${body}${this._footer(reads)}</ha-card>`;
  }

  _header(reads) {
    const c = this._config;
    const last = reads[0];
    return `<header>
      <div class="brand">${DROP_ICON}
        <div><div class="title">${esc(c.title || DEFAULTS.title)}</div>
        <div class="sub">L'Hotellier Eau${last ? ` · relevé du ${esc(longDate(last.date))}` : ""}</div></div>
      </div>
    </header>`;
  }

  _hero(reads, st) {
    const r = reads[0], prev = reads[1];
    const index = WATER.num(st.state);
    return `<section class="hero">
      <div>
        <div class="hero-l">Dernier relevé${r.days ? ` · ${fmt(r.days, 0)} jours` : ""}</div>
        <div class="hero-v">${fmt(r.m3, 0)}<span>m³</span></div>
        ${evo(r.m3, prev ? prev.m3 : null, " par rapport au relevé précédent")}
      </div>
      <div class="hero-r">
        <div class="peak">${fmt(index !== null ? index : r.index, 0)}<span>m³</span></div><div class="cost-l">index du compteur</div>
        <div class="hero-p">${WATER.est(r) ? "relevé estimé" : "relevé réel"}${r.from ? ` · depuis le ${esc(shortDate(r.from))}` : ""}</div>
      </div>
    </section>`;
  }

  _tiles(reads, bills) {
    const now = new Date();
    const r = reads[0], prev = reads[1];
    // moyenne annuelle : consommation ramenée à 365 jours, sur les périodes connues
    const known = reads.filter((x) => x.m3 !== null && x.days);
    const span = known.reduce((s, x) => s + x.days, 0);
    const perYear = span ? (known.reduce((s, x) => s + x.m3, 0) / span) * 365 : null;
    const billed = (y) => {
      const rows = bills.filter((b) => b.date.getFullYear() === y);
      return rows.length ? rows.reduce((s, b) => s + b.amount, 0) : null;
    };
    const bNow = billed(now.getFullYear()), bPrev = billed(now.getFullYear() - 1);
    const lastBill = bills[0];
    const tile = (label, value, unit, evoHtml, notes) => `<div class="tile">
      <div class="tile-l">${label}</div><div class="tile-v">${value}${unit ? `<span>${unit}</span>` : ""}</div>
      ${evoHtml}${notes.filter(Boolean).length ? `<div class="tile-n">${notes.filter(Boolean).join("<br>")}</div>` : ""}</div>`;
    const tiles = [
      tile("Moyenne par jour", fmt(r.perDay, 0), "L/jour", evo(r.perDay, prev ? prev.perDay : null, " sur la période d'avant"),
        [prev && prev.perDay !== null ? `Période d'avant : ${fmt(prev.perDay, 0)} L/jour` : ""]),
      tile("Moyenne par an", fmt(perYear, 0), "m³", "",
        [known.length ? `sur ${known.length} période${known.length > 1 ? "s" : ""} de relevé` : "", perYear !== null ? `≈ ${fmt(perYear * 1000 / 365, 0)} L/jour` : ""]),
    ];
    if (bills.length) {
      tiles.push(
        tile("Dernière facture", euro(lastBill.amount), "", "", [esc(shortDate(lastBill.date)), lastBill.amount < 0 ? "avoir en votre faveur" : ""]),
        tile(`Facturé en ${now.getFullYear()}`, bNow !== null ? euro(bNow) : "—", "", "", [bPrev !== null ? `${now.getFullYear() - 1} : ${euro(bPrev)}` : ""]),
      );
    }
    return `<section class="tiles">${tiles.join("")}</section>`;
  }

  _chart(reads) {
    const chrono = [...reads].reverse();
    const n = chrono.length;
    const max = Math.max(0.1, ...chrono.map((r) => r.m3 || 0)) * 1.08;
    const H = 100, slot = 100 / n, w = slot * (n <= 3 ? 0.42 : 0.62);
    const bars = chrono.map((r, k) => {
      const x = k * slot + (slot - w) / 2;
      const sel = r.i === this._selected ? `<rect class="sel" x="${k * slot}" y="0" width="${slot}" height="${H}"/>` : "";
      const h = r.m3 !== null ? (r.m3 / max) * H : 0;
      const bar = r.m3 !== null ? `<rect class="wb${WATER.est(r) ? " est" : ""}" x="${x}" y="${H - h}" width="${w}" height="${h}"/>` : "";
      return `${sel}${bar}<rect class="hit" data-i="${r.i}" x="${k * slot}" y="0" width="${slot}" height="${H}"/>`;
    }).join("");
    const labels = chrono.map((r) => `<button class="day ${r.i === this._selected ? "on" : ""}" data-i="${r.i}">
      <span>${esc(r.date.toLocaleDateString("fr-FR", { month: "short" }).replace(".", ""))}</span><b>${r.date.getFullYear()}</b></button>`).join("");
    return `<section class="chart">
      <div class="chart-h"><span>${n} dernier${n > 1 ? "s" : ""} relevé${n > 1 ? "s" : ""}</span><span class="legend"><i class="k-w"></i>Consommation (m³)</span></div>
      <svg viewBox="0 0 100 ${H}" preserveAspectRatio="none" role="img" aria-label="Consommation d'eau des ${n} derniers relevés">${bars}</svg>
      <div class="days" style="grid-template-columns:repeat(${n},1fr)">${labels}</div>
    </section>`;
  }

  _detail(r) {
    if (!r) return "";
    const parts = [`<b>${fmt(r.m3, 0)} m³</b>`];
    if (r.perDay !== null) parts.push(`${fmt(r.perDay, 0)} L/jour`);
    if (r.days) parts.push(`${fmt(r.days, 0)} jours`);
    const more = [
      r.from ? `du ${longDate(r.from)} au ${longDate(r.date)}` : "",
      r.startIndex !== null && r.index !== null ? `index ${fmt(r.startIndex, 0)} → ${fmt(r.index, 0)} m³` : "",
    ].filter(Boolean);
    return `<section class="detail">
      <div class="detail-h"><span>Relevé du ${esc(longDate(r.date))}</span></div>
      <div class="detail-v">${parts.join('<span class="sep"></span>')}</div>
      ${more.length ? `<div class="detail-p">${esc(more.join(" · "))}</div>` : ""}
    </section>`;
  }

  _bills(bills) {
    if (!bills.length) return "";
    const rows = bills.slice(0, this._config.bills).map((b) => `<div class="bill">
      <span>${esc(longDate(b.date))}</span><b class="${b.amount < 0 ? "credit" : ""}">${euro(b.amount)}</b></div>`).join("");
    return `<section class="bills"><div class="chart-h"><span>Factures</span></div>${rows}</section>`;
  }

  _footer(reads) {
    const last = reads[0];
    return `<footer>${last ? `Données L'Hotellier Eau jusqu'au ${esc(last.date.toLocaleDateString("fr-FR"))}, ` : ""}relevé du compteur environ une fois par an.</footer>`;
  }
}

/* -------------------------------------------------------------------- style */

const STYLE_BASE = `<style>
:host {
  --med-bg: #1a2434; --med-surface: #212d40; --med-line: #2f3d55;
  --med-text: #e7edf5; --med-muted: #8fa0b8;
  --med-green: #96d21f; --med-blue: #1d93e3;
  --med-up: #f08a4b; --med-down: #5fcf8a;
  --med-water: #3fb6f2; --med-water-2: #bfe7fb; --t-red: #ee4a4a;
}
ha-card { display: block; background: var(--med-bg); color: var(--med-text); border: 1px solid var(--med-line);
  border-radius: 18px; overflow: hidden; font-variant-numeric: tabular-nums; container-type: inline-size; }
header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 18px 8px; flex-wrap: wrap; }
.brand { display: flex; align-items: center; gap: 10px; }
.brand svg { width: 34px; height: 34px; fill: none; }
.brand .drop { fill: var(--med-water); }
.brand .shine { stroke: var(--med-water-2); stroke-width: 2.2; stroke-linecap: round; }
.title { font-size: 1.15rem; font-weight: 700; letter-spacing: .2px; }
.sub { font-size: .78rem; color: var(--med-muted); }

.hero { margin: 4px 12px 0; padding: 16px; border-radius: 14px; background: var(--med-surface);
  border: 1px solid var(--med-line); display: grid; grid-template-columns: 1fr auto; gap: 6px 16px; }
.hero-l { color: var(--med-muted); font-size: .85rem; }
.hero-v { font-size: 2.4rem; font-weight: 700; line-height: 1.1; }
.hero-v span, .tile-v span { font-size: .9rem; font-weight: 500; color: var(--med-muted); margin-left: 4px; }
.hero-r { text-align: right; align-self: center; }
.peak { font-size: 1.6rem; font-weight: 700; color: var(--med-water); }
.peak span { font-size: .85rem; font-weight: 500; color: var(--med-muted); margin-left: 3px; }
.hero-p { font-size: .75rem; color: var(--med-muted); margin-top: 6px; }
.cost-l { font-size: .75rem; color: var(--med-muted); max-width: 160px; }
.evo { font-size: .8rem; font-weight: 600; margin-top: 2px; }
.evo.up { color: var(--med-up); } .evo.down { color: var(--med-down); }

.tiles { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 10px 12px 0; }
@container (min-width: 620px) { .tiles { grid-template-columns: repeat(4, 1fr); } }
.tile { padding: 12px; border-radius: 12px; border: 1px solid var(--med-line); min-width: 0; }
.tile-l { font-size: .78rem; color: var(--med-muted); }
.tile-v { font-size: 1.35rem; font-weight: 700; margin-top: 2px; }
.tile-n { font-size: .72rem; color: var(--med-muted); margin-top: 4px; }

.chart, .bills { margin: 14px 12px 0; }
.chart-h { display: flex; justify-content: space-between; flex-wrap: wrap; row-gap: 4px; font-size: .82rem; color: var(--med-muted); margin: 0 4px 6px; }
.legend { display: flex; align-items: center; gap: 6px; }
.legend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; margin-left: 6px; background: var(--med-water); }
.chart svg { width: 100%; height: 130px; display: block; }
.chart rect.wb { fill: var(--med-water); } .chart rect.wb.est { opacity: .45; }
.chart rect.sel { fill: rgba(255,255,255,.06); }
.chart rect.hit { fill: transparent; cursor: pointer; }
.days { display: grid; margin-top: 4px; }
.day { all: unset; cursor: pointer; display: flex; flex-direction: column; align-items: center; gap: 1px;
  padding: 4px 0; border-radius: 8px; font-size: .68rem; color: var(--med-muted); }
.day b { color: var(--med-text); font-size: .78rem; }
.day.on { background: var(--med-surface); }
.day:focus-visible { outline: 2px solid var(--med-accent, var(--med-blue)); }

.detail { margin: 8px 12px 0; padding: 10px 12px; border-radius: 12px; background: var(--med-surface); border: 1px solid var(--med-line); }
.detail-h { font-size: .8rem; color: var(--med-muted); }
.detail-v { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; margin-top: 4px; font-size: .9rem; }
.sep { width: 1px; height: 12px; background: var(--med-line); }
.detail-p { font-size: .78rem; color: var(--med-muted); margin-top: 4px; }

.bill { display: flex; justify-content: space-between; gap: 12px; padding: 8px 12px; border: 1px solid var(--med-line);
  border-radius: 10px; font-size: .85rem; margin-top: 6px; }
.bill span { color: var(--med-muted); }
.bill b.credit { color: var(--med-down); }

footer { padding: 10px 18px 14px; font-size: .7rem; color: var(--med-muted); }
.empty { padding: 18px; display: flex; flex-direction: column; gap: 6px; font-size: .9rem; }
.empty span { color: var(--med-muted); }
ha-card.th-ha {
  --med-accent: var(--primary-color, #1d93e3);
  --med-bg: var(--ha-card-background, var(--card-background-color, #fff));
  --med-surface: color-mix(in srgb, var(--primary-text-color, #000) 5%, transparent);
  --med-line: var(--divider-color, rgba(127, 127, 127, .25));
  --med-text: var(--primary-text-color, #1f2937);
  --med-muted: var(--secondary-text-color, #6b7280);
  border-radius: var(--ha-card-border-radius, 12px);
  border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
}
ha-card.th-ha.light { --med-green: #4c8a0b; --med-up: #c2560f; --med-down: #1d8a4b; --med-water: #0b8fd3; }
ha-card.th-v2.light {
  --med-bg: #ffffff; --med-surface: #f2f5f9; --med-line: #dbe2ec;
  --med-text: #1a2434; --med-muted: #5b6b82;
  --med-green: #4c8a0b; --med-blue: #1673b8; --med-up: #c2560f; --med-down: #1d8a4b; --med-water: #0b8fd3;
  box-shadow: 0 1px 3px rgba(26, 36, 52, .08);
}
ha-card.light .chart rect.sel { fill: rgba(0, 0, 0, .05); }
@media (max-width: 420px) { .hero-v { font-size: 2rem; } }
</style>`;
// Variable --fs (réglage « taille de la police ») : sans réglage elle vaut 1 et rien ne change.
const STYLE = STYLE_BASE.replace(/(-?\d*\.?\d+)rem/g, "calc($1rem * var(--fs, 1))");

/* ----------------------------------------------------------------- éditeur */

const SCHEMA = [
  { name: "entity", selector: { entity: { domain: "sensor" } } },
  { name: "bill_entity", selector: { entity: { domain: "sensor" } } },
  { name: "title", selector: { text: {} } },
  {
    name: "reads",
    selector: { select: { mode: "dropdown", options: [3, 6, 10].map((n) => ({ value: String(n), label: `${n} relevés` })) } },
  },
  { name: "show_bills", selector: { boolean: {} } },
  {
    name: "bills",
    selector: { select: { mode: "dropdown", options: [2, 4, 8].map((n) => ({ value: String(n), label: `${n} factures` })) } },
  },
  {
    name: "theme",
    selector: {
      select: {
        mode: "dropdown",
        options: [
          { value: "v2", label: "Style MyElectricalData (bleu nuit)" },
          { value: "auto", label: "Style MyElectricalData, clair ou sombre selon Home Assistant" },
          { value: "ha", label: "Thème Home Assistant (clair ou sombre)" },
        ],
      },
    },
  },
  { name: "font_size", selector: { number: { min: 70, max: 150, step: 5, mode: "slider", unit_of_measurement: "%" } } },
];

const LABELS = {
  entity: "Relevés (capteur Index compteur, trouvé seul si vide)",
  bill_entity: "Factures (capteur Dernière facture, trouvé seul si vide)",
  title: "Titre",
  reads: "Relevés dans le graphique",
  show_bills: "Afficher la liste des factures",
  bills: "Factures affichées",
  theme: "Couleurs de la carte",
  font_size: "Taille du texte (100 % = taille d'origine)",
};

class LhotellierEauCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._draw();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._draw();
  }

  _draw() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => LABELS[s.name] || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        const v = { ...ev.detail.value };
        for (const k of ["reads", "bills"]) if (v[k] !== undefined) v[k] = Number(v[k]);
        for (const k of ["entity", "bill_entity"]) if (!v[k]) delete v[k];
        this._config = v;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: v }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = SCHEMA;
    this._form.data = {
      ...DEFAULTS,
      ...this._config,
      reads: String(this._config.reads || DEFAULTS.reads),
      bills: String(this._config.bills || DEFAULTS.bills),
    };
  }
}

/* ---------------------------------------------------------- enregistrement */

if (typeof customElements !== "undefined") {
  const define = (name, cls) => { if (!customElements.get(name)) customElements.define(name, cls); };
  define("lhotellier-eau-card", LhotellierEauCard);
  define("lhotellier-eau-card-editor", LhotellierEauCardEditor);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === "lhotellier-eau-card")) {
    window.customCards.push({
      type: "lhotellier-eau-card",
      name: "Carte Eau L'Hotellier",
      description: "Relevés du compteur d'eau, consommation par an, moyenne par jour et factures (intégration L'Hotellier Eau).",
      preview: true,
    });
  }
  console.info(`%c LHOTELLIER-EAU-CARD %c ${CARD_VERSION} `, "color:#fff;background:#0b8fd3;font-weight:700", "color:#0b8fd3");
}
