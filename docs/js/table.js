import { filteredMetrics } from "./data.js";

const BASE_COLUMNS = [
  { field: "rank", label: "Rang", sortable: false },
  { field: "name", label: "Teilnehmer", sortable: true },
  { field: "points", label: "Punkte", sortable: true, numeric: true },
  { field: "wins", label: "Siege", sortable: true, numeric: true },
  { field: "sonderpunkte", label: "Sonderpunkte", sortable: true, numeric: true },
  { field: "chart", label: "Diagramm", sortable: false },
];

function yearLabel(selectedYears, allYears) {
  if (selectedYears.size === 0) {
    return "keine Jahre ausgewählt";
  }
  if (selectedYears.size === allYears.length) {
    return "alle Jahre";
  }
  const sorted = [...selectedYears].sort();
  return sorted.length === 1 ? sorted[0] : `${sorted[0]}–${sorted[sorted.length - 1]}`;
}

export function renderTableHead(store, data, onNameClick) {
  const row = document.getElementById("table-head-row");
  row.innerHTML = "";

  const label = yearLabel(store.state.selectedYears, data.meta.years);
  const columns = [...BASE_COLUMNS];
  if (store.state.showYearColumns) {
    const idx = columns.findIndex((c) => c.field === "chart");
    const yearCols = data.meta.years.map((y) => ({ field: `year:${y}`, label: y, sortable: false, numeric: true }));
    columns.splice(idx, 0, ...yearCols);
  }

  for (const col of columns) {
    const th = document.createElement("th");
    let text = col.label;
    if (col.field === "points") text = `Punkte (${label})`;
    if (col.field === "wins") text = `Siege (${label})`;
    if (col.field === "sonderpunkte") text = `Sonderpunkte (${label})`;
    th.textContent = text;
    if (col.sortable) {
      th.addEventListener("click", () => store.setSort(col.field));
      if (store.state.sortField === col.field) {
        th.classList.add(store.state.sortDir === "desc" ? "sorted-desc" : "sorted-asc");
      }
    }
    row.appendChild(th);
  }
}

export function renderTableBody(store, data, onNameClick) {
  const tbody = document.getElementById("table-body");
  const emptyState = document.getElementById("empty-state");
  tbody.innerHTML = "";

  const query = store.state.nameQuery.trim().toLowerCase();
  const years = [...store.state.selectedYears];

  let rows = data.participants
    .map((p) => ({ p, m: filteredMetrics(p, years) }))
    .filter(({ p }) => !query || p.name.toLowerCase().includes(query));

  const field = store.state.sortField;
  const dir = store.state.sortDir === "desc" ? -1 : 1;
  rows.sort((a, b) => {
    if (field === "name") return dir * a.p.name.localeCompare(b.p.name);
    const av = field === "points" ? a.m.points : field === "wins" ? a.m.wins : a.m.sonderpunkte;
    const bv = field === "points" ? b.m.points : field === "wins" ? b.m.wins : b.m.sonderpunkte;
    return dir * (av - bv);
  });

  emptyState.hidden = rows.length > 0;

  rows.forEach(({ p, m }, i) => {
    const tr = document.createElement("tr");

    const rankTd = document.createElement("td");
    rankTd.textContent = String(i + 1);
    tr.appendChild(rankTd);

    const nameTd = document.createElement("td");
    const nameBtn = document.createElement("button");
    nameBtn.className = "name-btn";
    nameBtn.type = "button";
    nameBtn.textContent = p.name;
    nameBtn.addEventListener("click", () => onNameClick(p.name));
    nameTd.appendChild(nameBtn);
    tr.appendChild(nameTd);

    const pointsTd = document.createElement("td");
    pointsTd.className = "num";
    pointsTd.textContent = m.points.toLocaleString("de-DE");
    tr.appendChild(pointsTd);

    const winsTd = document.createElement("td");
    winsTd.className = "num";
    winsTd.textContent = m.wins.toLocaleString("de-DE");
    tr.appendChild(winsTd);

    const sonderTd = document.createElement("td");
    sonderTd.className = "num";
    sonderTd.textContent = m.sonderpunkte.toLocaleString("de-DE");
    tr.appendChild(sonderTd);

    if (store.state.showYearColumns) {
      for (const y of data.meta.years) {
        const td = document.createElement("td");
        td.className = "num";
        td.textContent = (p.years[y]?.points || 0).toLocaleString("de-DE");
        tr.appendChild(td);
      }
    }

    const chartTd = document.createElement("td");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = store.state.chartSelection.has(p.name);
    checkbox.addEventListener("change", () => {
      const ok = store.toggleChartSelection(p.name);
      if (!ok) {
        checkbox.checked = false;
        alert(`Maximal ${store.state.maxChartSelection} Teilnehmer im Diagramm auswaehlbar.`);
      }
    });
    chartTd.appendChild(checkbox);
    tr.appendChild(chartTd);

    tbody.appendChild(tr);
  });
}
