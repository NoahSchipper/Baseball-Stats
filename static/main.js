const labelMap = {
  war: "WAR",
  games: "G",
  plate_appearances: "PA",
  hits: "H",
  home_runs: "HR",
  rbi: "RBI",
  stolen_bases: "SB",
  batting_average: "BA",
  on_base_percentage: "OBP",
  slugging_percentage: "SLG",
  ops: "OPS",
  ops_plus: "OPS+",
};

// Same label map for all modes now that we have career fWAR
const liveLabelMap = labelMap;

function extractStats(res) {
  if (res.error) return null;

  if (["career", "combined", "live"].includes(res.mode)) {
    // career and combined use totals; live uses stats object
    return res.totals || res.stats;
  } else if (res.mode === "season") {
    // array of season objects
    return res.stats;
  }
  return null;
}

function updateComparisonTable(resA, resB, nameA, nameB) {
  const tbody = document.getElementById("comparisonBody");
  const thA = document.getElementById("playerAName");
  const thB = document.getElementById("playerBName");
  const photoA = document.getElementById("photoA");
  const photoB = document.getElementById("photoB");

  thA.querySelector(".player-name").textContent = nameA || "Player A";
  thB.querySelector(".player-name").textContent = nameB || "Player B";

  photoA.src = resA?.photo_url || "";
  photoB.src = resB?.photo_url || "";

  if (resA?.photo_url) photoA.style.display = "block";
  else photoA.style.display = "none";
  if (resB?.photo_url) photoB.style.display = "block";
  else photoB.style.display = "none";

  tbody.innerHTML = "";

  if (!resA || !resB) {
    tbody.innerHTML = "<tr><td colspan='4'>Error loading player data.</td></tr>";
    return;
  }
  if (resA.error || resB.error) {
    tbody.innerHTML = `<tr><td colspan='4'>${resA.error || resB.error}</td></tr>`;
    return;
  }

  const mode = resA.mode;

  if (["career", "combined", "live"].includes(mode)) {
    const statsA = extractStats(resA);
    const statsB = extractStats(resB);

    // Use the same label map for all modes now that we have career fWAR
    const currentLabelMap = labelMap;

    for (const key of Object.keys(currentLabelMap)) {
      const statName = currentLabelMap[key];
      let valA = statsA[key] ?? 0;
      let valB = statsB[key] ?? 0;

      const decimalStats = ["war", "batting_average", "on_base_percentage", "slugging_percentage", "ops"];
      if (decimalStats.includes(key)) {
        valA = valA ? Number(valA).toFixed(3).replace(/^0/, '') : ".000";
        valB = valB ? Number(valB).toFixed(3).replace(/^0/, '') : ".000";
      } else if (key === "ops_plus") {
        valA = valA ? Math.round(valA) : 0;
        valB = valB ? Math.round(valB) : 0;
      }

      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${valA}</td>
        <td><strong>${statName}</strong></td>
        <td>${valB}</td>
      `;
      tbody.appendChild(row);
    }
  } else if (mode === "season") {
    const statsA = extractStats(resA);
    const statsB = extractStats(resB);

    const years = new Set();
    statsA.forEach(s => years.add(s.year));
    statsB.forEach(s => years.add(s.year));

    let yearsArray = Array.from(years);
    // Sort by newest or oldest - get the sort order from the dropdown value
    const sortOrder = document.getElementById("viewMode").value;
    if (sortOrder === "oldest") {
      yearsArray.sort((a, b) => a - b);
    } else {
      yearsArray.sort((a, b) => b - a); // newest first for both "newest" and default
    }

    // Include WAR in season view since we have historical WAR data
    // Note: Flask backend returns pa, ba, obp, slg (not renamed)
    const seasonLabelMap = {
      war: "WAR",
      games: "G", 
      pa: "PA",
      hits: "H",
      home_runs: "HR",
      rbi: "RBI",
      stolen_bases: "SB",
      ba: "BA",
      obp: "OBP",
      slg: "SLG",
      ops: "OPS"
    };

    yearsArray.forEach(year => {
      const playerAStat = statsA.find(s => s.year === year) || {};
      const playerBStat = statsB.find(s => s.year === year) || {};

      // Create year header row
      const yearRow = document.createElement("tr");
      yearRow.innerHTML = `<td colspan="3" style="text-align: center; font-weight: bold; background-color: #f0f0f0; padding: 8px;">${year}</td>`;
      tbody.appendChild(yearRow);

      // Create stats for this year
      for (const key of Object.keys(seasonLabelMap)) {
        const statName = seasonLabelMap[key];

        let valA = playerAStat[key] ?? 0;
        let valB = playerBStat[key] ?? 0;

        const decimalStats = ["war", "ba", "obp", "slg", "ops"];
        if (decimalStats.includes(key)) {
          valA = valA ? Number(valA).toFixed(3).replace(/^0/, '') : ".000";
          valB = valB ? Number(valB).toFixed(3).replace(/^0/, '') : ".000";
        }

        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${valA}</td>
          <td><strong>${statName}</strong></td>
          <td>${valB}</td>
        `;
        tbody.appendChild(row);
      }
    });
  } else {
    tbody.innerHTML = `<tr><td colspan='4'>Unsupported mode for comparison</td></tr>`;
  }
}

async function fetchStats(name, mode) {
  try {
    // Map frontend dropdown values to backend expected values
    let backendMode = mode;
    if (mode === "newest" || mode === "oldest") {
      backendMode = "season";
    }
    
    const res = await fetch(`/player?name=${encodeURIComponent(name)}&mode=${backendMode}`);
    return await res.json();
  } catch (e) {
    return { error: "Failed to fetch data" };
  }
}

async function comparePlayers() {
  const nameA = document.getElementById("playerA").value.trim();
  const nameB = document.getElementById("playerB").value.trim();
  const mode = document.getElementById("viewMode").value;

  if (!nameA || !nameB) {
    alert("Please enter both player names (first and last).");
    return;
  }

  const [resA, resB] = await Promise.all([
    fetchStats(nameA, mode),
    fetchStats(nameB, mode),
  ]);

  updateComparisonTable(resA, resB, nameA, nameB);
}

document.getElementById("viewMode").addEventListener("change", comparePlayers);

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("playerA").value = "Mike Trout";
  document.getElementById("playerB").value = "Mookie Betts";
  document.getElementById("viewMode").value = "combined"; // default mode
  comparePlayers();
});