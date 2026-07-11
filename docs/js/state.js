export function createState(allYears) {
  const listeners = new Set();
  const state = {
    allYears: [...allYears],
    selectedYears: new Set(allYears),
    nameQuery: "",
    sortField: "points",
    sortDir: "desc",
    showYearColumns: false,
    chartSelection: new Set(),
    maxChartSelection: 6,
  };

  function notify() {
    for (const fn of listeners) fn(state);
  }

  return {
    state,
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    setYears(years) {
      state.selectedYears = new Set(years);
      notify();
    },
    setAllYears() {
      state.selectedYears = new Set(state.allYears);
      notify();
    },
    setNoYears() {
      state.selectedYears = new Set();
      notify();
    },
    setNameQuery(q) {
      state.nameQuery = q;
      notify();
    },
    setSort(field) {
      if (state.sortField === field) {
        state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
      } else {
        state.sortField = field;
        state.sortDir = "desc";
      }
      notify();
    },
    setShowYearColumns(v) {
      state.showYearColumns = v;
      notify();
    },
    toggleChartSelection(name) {
      if (state.chartSelection.has(name)) {
        state.chartSelection.delete(name);
      } else if (state.chartSelection.size < state.maxChartSelection) {
        state.chartSelection.add(name);
      } else {
        return false;
      }
      notify();
      return true;
    },
    clearChartSelection() {
      state.chartSelection.clear();
      notify();
    },
  };
}
