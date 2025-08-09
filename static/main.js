// Your existing code (keep all of this)
const hitterLabelMap = {
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

const pitcherLabelMap = {
  war: "WAR",
  wins: "W",
  losses: "L",
  games: "G",
  games_started: "GS",
  complete_games: "CG",
  shutouts: "SHO",
  saves: "SV",
  innings_pitched: "IP",
  hits_allowed: "H",
  earned_runs: "ER",
  home_runs_allowed: "HR",
  walks: "BB",
  strikeouts: "SO",
  era: "ERA",
  whip: "WHIP"
};

const hitterSeasonLabelMap = {
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

const pitcherSeasonLabelMap = {
  war: "WAR",
  wins: "W",
  losses: "L",
  games: "G",
  games_started: "GS",
  complete_games: "CG",
  shutouts: "SHO",
  saves: "SV",
  innings_pitched: "IP",
  hits_allowed: "H",
  earned_runs: "ER",
  home_runs_allowed: "HR",
  walks: "BB",
  strikeouts: "SO",
  era: "ERA",
  whip: "WHIP"
};

function extractStats(res) {
  if (res.error) return null;

  if (["career", "combined", "live"].includes(res.mode)) {
    return res.totals || res.stats;
  } else if (res.mode === "season") {
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
    tbody.innerHTML = `<tr><td colspan='4'>Error loading player data.</td></tr>`;
    return;
  }
  if (resA.error || resB.error) {
    tbody.innerHTML = `<tr><td colspan='4'>${resA.error || resB.error}</td></tr>`;
    return;
  }

  if (resA.player_type !== resB.player_type) {
    tbody.innerHTML = `<tr><td colspan='4'>Cannot compare pitcher and hitter statistics.</td></tr>`;
    return;
  }

  const mode = resA.mode;
  const playerType = resA.player_type || "hitter";

  if (["career", "combined", "live"].includes(mode)) {
    const statsA = extractStats(resA);
    const statsB = extractStats(resB);

    const currentLabelMap = playerType === "pitcher" ? pitcherLabelMap : hitterLabelMap;

    for (const key of Object.keys(currentLabelMap)) {
      const statName = currentLabelMap[key];
      let valA = statsA[key] ?? 0;
      let valB = statsB[key] ?? 0;

      if (playerType === "pitcher") {
        const decimalStats = ["war", "era", "whip", "innings_pitched"];
        if (decimalStats.includes(key)) {
          if (key === "war") {
            valA = valA ? Number(valA).toFixed(1) : "0.0";
            valB = valB ? Number(valB).toFixed(1) : "0.0";
          } else if (key === "innings_pitched") {
            valA = valA ? Number(valA).toFixed(1) : "0.0";
            valB = valB ? Number(valB).toFixed(1) : "0.0";
          } else {
            valA = valA ? Number(valA).toFixed(2) : "0.00";
            valB = valB ? Number(valB).toFixed(2) : "0.00";
          }
        }
      } else {
        const decimalStats = ["war", "batting_average", "on_base_percentage", "slugging_percentage", "ops"];
        if (decimalStats.includes(key)) {
          if (key === "war") {
            valA = valA ? Number(valA).toFixed(1) : "0.0";
            valB = valB ? Number(valB).toFixed(1) : "0.0";
          } else {
            valA = valA ? Number(valA).toFixed(3).replace(/^0/, '') : ".000";
            valB = valB ? Number(valB).toFixed(3).replace(/^0/, '') : ".000";
          }
        } else if (key === "ops_plus") {
          valA = valA ? Math.round(valA) : 0;
          valB = valB ? Math.round(valB) : 0;
        }
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
    const sortOrder = document.getElementById("viewMode").value;
    if (sortOrder === "oldest") {
      yearsArray.sort((a, b) => a - b);
    } else {
      yearsArray.sort((a, b) => b - a);
    }

    const seasonLabelMap = playerType === "pitcher" ? pitcherSeasonLabelMap : hitterSeasonLabelMap;

    yearsArray.forEach(year => {
      const playerAStat = statsA.find(s => s.year === year) || {};
      const playerBStat = statsB.find(s => s.year === year) || {};

      const yearRow = document.createElement("tr");
      yearRow.innerHTML = `<td colspan="3" style="text-align: center; font-weight: bold; background-color: #f0f0f0; padding: 8px;">${year}</td>`;
      tbody.appendChild(yearRow);

      for (const key of Object.keys(seasonLabelMap)) {
        const statName = seasonLabelMap[key];

        let valA = playerAStat[key] ?? 0;
        let valB = playerBStat[key] ?? 0;

        if (playerType === "pitcher") {
          const decimalStats = ["war", "era", "whip", "innings_pitched"];
          if (decimalStats.includes(key)) {
            if (key === "war") {
              valA = valA ? Number(valA).toFixed(1) : "0.0";
              valB = valB ? Number(valB).toFixed(1) : "0.0";
            } else if (key === "innings_pitched") {
              valA = valA ? Number(valA).toFixed(1) : "0.0";
              valB = valB ? Number(valB).toFixed(1) : "0.0";
            } else {
              valA = valA ? Number(valA).toFixed(2) : "0.00";
              valB = valB ? Number(valB).toFixed(2) : "0.00";
            }
          }
        } else {
          const decimalStats = ["war", "ba", "obp", "slg", "ops"];
          if (decimalStats.includes(key)) {
            if (key === "war") {
              valA = valA ? Number(valA).toFixed(1) : "0.0";
              valB = valB ? Number(valB).toFixed(1) : "0.0";
            } else {
              valA = valA ? Number(valA).toFixed(3).replace(/^0/, '') : ".000";
              valB = valB ? Number(valB).toFixed(3).replace(/^0/, '') : ".000";
            }
          }
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

// ENHANCED AUTO-FILL FUNCTIONALITY STARTS HERE
let searchTimeout;
let popularPlayersCache = null;
const SEARCH_DELAY = 300;

console.log('Enhanced auto-fill script loading...'); // Debug log

async function loadPopularPlayers() {
  console.log('Loading popular players...'); // Debug log
  if (popularPlayersCache) {
    console.log('Using cached popular players');
    updateDatalistOptions(popularPlayersCache);
    return;
  }
  
  try {
    const response = await fetch('/popular-players');
    console.log('Popular players response:', response.status); // Debug log
    if (response.ok) {
      const players = await response.json();
      console.log('Popular players loaded:', players.length, 'players'); // Debug log
      popularPlayersCache = players; // Cache the results
      updateDatalistOptions(players);
    } else {
      console.error('Failed to load popular players:', response.status, response.statusText);
      // Fallback to some basic options
      const fallback = [
        "Mike Trout", "Aaron Judge", "Mookie Betts", "Ronald Acuna Jr.",
        "Juan Soto", "Gerrit Cole", "Jacob deGrom", "Clayton Kershaw",
        "Vladimir Guerrero Jr.", "Fernando Tatis Jr.", "Shane Bieber", 
        "Freddie Freeman", "Manny Machado", "Jose Altuve", "Kyle Tucker"
      ];
      updateDatalistOptions(fallback);
    }
  } catch (error) {
    console.error('Error loading popular players:', error);
    // Fallback to basic options
    const fallback = [
      "Mike Trout", "Aaron Judge", "Mookie Betts", "Ronald Acuna Jr.",
      "Juan Soto", "Gerrit Cole", "Jacob deGrom", "Clayton Kershaw"
    ];
    updateDatalistOptions(fallback);
  }
}

async function searchPlayers(query) {
  console.log('Searching for:', query); // Debug log
  try {
    const response = await fetch(`/search-players?q=${encodeURIComponent(query)}`);
    console.log('Search response:', response.status); // Debug log
    if (response.ok) {
      const players = await response.json();
      console.log('Search results:', players.length, 'players'); // Debug log
      updateDatalistOptions(players);
    } else {
      console.error('Search failed:', response.status, response.statusText);
      // Fallback to popular players if search fails
      if (popularPlayersCache) {
        updateDatalistOptions(popularPlayersCache);
      }
    }
  } catch (error) {
    console.error('Search error:', error);
    // Fallback to popular players if search fails
    if (popularPlayersCache) {
      updateDatalistOptions(popularPlayersCache);
    }
  }
}

function updateDatalistOptions(players) {
  const datalist = document.getElementById('players');
  console.log('Updating datalist, found element:', !!datalist); // Debug log
  
  if (!datalist) {
    console.error('Datalist element not found!');
    return;
  }
  
  datalist.innerHTML = '';
  console.log('Updating datalist with', players.length, 'players'); // Debug log
  
  players.forEach(player => {
    const option = document.createElement('option');
    if (typeof player === 'string') {
      option.value = player;
    } else {
      option.value = player.name;
      if (player.display) {
        option.textContent = player.display;
      }
    }
    datalist.appendChild(option);
  });
  
  console.log('Datalist updated, now has', datalist.children.length, 'options'); // Debug log
}

function handlePlayerInput(e) {
  const query = e.target.value.trim();
  console.log('Input changed:', query); // Debug log
  
  if (query.length < 2) {
    console.log('Query too short, loading popular players'); // Debug log
    loadPopularPlayers();
    return;
  }
  
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    searchPlayers(query);
  }, SEARCH_DELAY);
}

function handlePlayerClick(e) {
  console.log('Input clicked, forcing suggestion list...');
  
  loadPopularPlayers(); // make sure the list is up-to-date

  // Temporarily set a space to trigger suggestions
  e.target.value = " ";
  e.target.dispatchEvent(new Event('input', { bubbles: true }));

  // Wait a little before clearing it so dropdown stays open
  setTimeout(() => {
    e.target.value = "";
  }, 300); // 300ms works well in Chrome/Edge
}


function handlePlayerFocus(e) {
  console.log('Input focused'); // Debug log
  const query = e.target.value.trim();
  
  if (query.length < 2) {
    // Show popular players when focused and no/short query
    loadPopularPlayers();
  }
  // If there's already a longer query, keep current suggestions
}

function handleEnterKey(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    comparePlayers();
  }
}

function setupPlayerAutofill() {
  console.log('Setting up enhanced autofill...'); // Debug log
  
  const playerAInput = document.getElementById('playerA');
  const playerBInput = document.getElementById('playerB');
  
  console.log('Found inputs:', !!playerAInput, !!playerBInput); // Debug log
  
  if (playerAInput) {
    playerAInput.addEventListener('input', handlePlayerInput);
    playerAInput.addEventListener('click', handlePlayerClick);
    playerAInput.addEventListener('focus', handlePlayerFocus);
    playerAInput.addEventListener('keydown', handleEnterKey);
    console.log('Added event listeners to playerA'); // Debug log
  } else {
    console.error('playerA input not found!');
  }
  
  if (playerBInput) {
    playerBInput.addEventListener('input', handlePlayerInput);
    playerBInput.addEventListener('click', handlePlayerClick);
    playerBInput.addEventListener('focus', handlePlayerFocus);
    playerBInput.addEventListener('keydown', handleEnterKey);
    console.log('Added event listeners to playerB'); // Debug log
  } else {
    console.error('playerB input not found!');
  }
  
  // Load popular players initially and cache them
  loadPopularPlayers();
}

// Updated DOMContentLoaded event listener
document.addEventListener("DOMContentLoaded", () => {
  console.log('DOM loaded, initializing enhanced autofill...'); // Debug log
  
  // Your existing code
  document.getElementById("playerA").value = "Kyle Schwarber";
  document.getElementById("playerB").value = "Kyle Tucker";
  document.getElementById("viewMode").value = "combined";
  
  // Initialize enhanced autofill
  setupPlayerAutofill();
  
  // Your existing comparison call
  comparePlayers();
  
  console.log('Enhanced initialization complete'); // Debug log
});