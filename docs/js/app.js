import { loadData } from "./data.js";
import { createState } from "./state.js";
import { renderTableHead, renderTableBody } from "./table.js";
import { renderBarChart, renderLineChart } from "./charts.js";
import { openDetail } from "./detail.js";

function renderYearCheckboxes(store, data) {
  const container = document.getElementById("year-checkboxes");
  container.innerHTML = "";
  for (const y of data.meta.years) {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = y;
    checkbox.checked = store.state.selectedYears.has(y);
    checkbox.addEventListener("change", () => {
      const next = new Set(store.state.selectedYears);
      if (checkbox.checked) next.add(y); else next.delete(y);
      store.setYears(next);
    });
    label.appendChild(checkbox);
    label.append(y);
    container.appendChild(label);
  }
}

function syncYearCheckboxes(store) {
  const boxes = document.querySelectorAll("#year-checkboxes input[type=checkbox]");
  boxes.forEach((box) => {
    box.checked = store.state.selectedYears.has(box.value);
  });
}

function renderAll(store, data) {
  renderTableHead(store, data, (name) => openDetail(store, data, name));
  renderTableBody(store, data, (name) => openDetail(store, data, name));
  renderBarChart(store, data);
  renderLineChart(store, data);
  syncYearCheckboxes(store);
}

async function main() {
  let data;
  try {
    data = await loadData();
  } catch (err) {
    document.querySelector("main").innerHTML =
      `<p class="empty-state">Daten konnten nicht geladen werden: ${err.message}</p>`;
    return;
  }

  document.getElementById("thread-link").href = data.meta.thread_url || "#";
  document.getElementById("thread-link").textContent = data.meta.thread_title || "Foto-Ratespiel-Thread";
  document.getElementById("generated-info").textContent =
    `${data.meta.participant_count} Teilnehmer · ${data.meta.event_count} Punkte-Ereignisse · ` +
    `Stand: ${new Date(data.meta.generated_at).toLocaleString("de-DE")}`;

  const store = createState(data.meta.years);
  renderYearCheckboxes(store, data);

  document.getElementById("name-search").addEventListener("input", (e) => {
    store.setNameQuery(e.target.value);
  });

  document.getElementById("years-all").addEventListener("click", () => store.setAllYears());
  document.getElementById("years-none").addEventListener("click", () => store.setNoYears());

  document.getElementById("toggle-year-columns").addEventListener("change", (e) => {
    store.setShowYearColumns(e.target.checked);
  });

  document.getElementById("bar-metric").addEventListener("change", () => renderBarChart(store, data));
  document.getElementById("bar-topn").addEventListener("change", () => renderBarChart(store, data));
  document.getElementById("clear-selection").addEventListener("click", () => store.clearChartSelection());

  store.subscribe(() => renderAll(store, data));
  renderAll(store, data);
}

main();
