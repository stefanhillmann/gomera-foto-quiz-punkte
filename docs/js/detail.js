import { filteredMetrics } from "./data.js";

export function openDetail(store, data, name) {
  const dialog = document.getElementById("detail-dialog");
  const years = [...store.state.selectedYears];

  const participant = data.participants.find((p) => p.name === name);
  const metrics = participant ? filteredMetrics(participant, years) : { points: 0, wins: 0, sonderpunkte: 0 };

  document.getElementById("detail-name").textContent = name;
  document.getElementById("detail-summary").textContent =
    `${metrics.wins} gelöste Rätsel · ${metrics.points.toLocaleString("de-DE")} Punkte ` +
    `(davon ${metrics.sonderpunkte.toLocaleString("de-DE")} Sonderpunkte)`;

  const yearSet = new Set(years);
  const events = data.events
    .filter((e) => e.empfaenger === name && yearSet.has(e.year))
    .sort((a, b) => Number(a.post_id) - Number(b.post_id));

  const tbody = document.getElementById("detail-table-body");
  tbody.innerHTML = "";
  for (const e of events) {
    const tr = document.createElement("tr");

    const dateTd = document.createElement("td");
    dateTd.textContent = e.date;
    tr.appendChild(dateTd);

    const melderTd = document.createElement("td");
    melderTd.textContent = e.melder;
    tr.appendChild(melderTd);

    const pointsTd = document.createElement("td");
    pointsTd.className = "num";
    pointsTd.textContent = e.gesamtpunkte.toLocaleString("de-DE");
    tr.appendChild(pointsTd);

    const sonderTd = document.createElement("td");
    sonderTd.className = "num";
    sonderTd.textContent = e.davon_sonderpunkte.toLocaleString("de-DE");
    tr.appendChild(sonderTd);

    const linkTd = document.createElement("td");
    const a = document.createElement("a");
    a.href = e.permalink;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = "Beitrag ansehen";
    linkTd.appendChild(a);
    tr.appendChild(linkTd);

    tbody.appendChild(tr);
  }

  dialog.showModal();
}
