import { filteredMetrics } from "./data.js";

const PALETTE = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2"];

let barChart = null;
let lineChart = null;

function currentYears(store) {
  return [...store.state.selectedYears];
}

export function renderBarChart(store, data) {
  const metricField = document.getElementById("bar-metric").value;
  const topNRaw = document.getElementById("bar-topn").value;
  const query = store.state.nameQuery.trim().toLowerCase();
  const years = currentYears(store);

  let rows = data.participants
    .map((p) => ({ name: p.name, ...filteredMetrics(p, years) }))
    .filter((r) => !query || r.name.toLowerCase().includes(query));

  const key = metricField === "total_wins" ? "wins" : "points";
  rows.sort((a, b) => b[key] - a[key]);

  const topN = topNRaw === "all" ? rows.length : parseInt(topNRaw, 10);
  rows = rows.slice(0, topN);

  const ctx = document.getElementById("bar-chart");
  const chartData = {
    labels: rows.map((r) => r.name),
    datasets: [{
      label: metricField === "total_wins" ? "Siege" : "Punkte",
      data: rows.map((r) => r[key]),
      backgroundColor: PALETTE[0],
    }],
  };

  if (barChart) {
    barChart.data = chartData;
    barChart.update();
  } else {
    barChart = new Chart(ctx, {
      type: "bar",
      data: chartData,
      options: {
        indexAxis: "y",
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } },
      },
    });
  }
}

export function renderLineChart(store, data) {
  const years = data.meta.years;
  let names = [...store.state.chartSelection];
  if (names.length === 0) {
    names = [...data.participants]
      .sort((a, b) => b.total_points - a.total_points)
      .slice(0, 5)
      .map((p) => p.name);
  }

  const byName = new Map(data.participants.map((p) => [p.name, p]));
  const datasets = names.map((name, i) => {
    const p = byName.get(name);
    return {
      label: name,
      data: years.map((y) => p?.years[y]?.points || 0),
      borderColor: PALETTE[i % PALETTE.length],
      backgroundColor: PALETTE[i % PALETTE.length],
      tension: 0.15,
      fill: false,
    };
  });

  const ctx = document.getElementById("line-chart");
  const chartData = { labels: years, datasets };

  if (lineChart) {
    lineChart.data = chartData;
    lineChart.update();
  } else {
    lineChart = new Chart(ctx, {
      type: "line",
      data: chartData,
      options: {
        responsive: true,
        scales: { y: { beginAtZero: true } },
      },
    });
  }
}
