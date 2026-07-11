export async function loadData() {
  const res = await fetch("data/data.json");
  if (!res.ok) {
    throw new Error(`data.json konnte nicht geladen werden: ${res.status}`);
  }
  return res.json();
}

/** Summiert points/sonderpunkte/wins eines Teilnehmers ueber eine Menge Jahre. */
export function sumYears(participant, selectedYears, field) {
  let total = 0;
  for (const y of selectedYears) {
    const yearData = participant.years[y];
    if (yearData) total += yearData[field] || 0;
  }
  return total;
}

export function filteredMetrics(participant, selectedYears) {
  return {
    points: sumYears(participant, selectedYears, "points"),
    sonderpunkte: sumYears(participant, selectedYears, "sonderpunkte"),
    wins: sumYears(participant, selectedYears, "wins"),
  };
}
