// Your existing label maps and stats extraction (keep all of this)
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

// Common father/son player mappings for quick reference
const COMMON_FATHER_SON_PLAYERS = {
  'ken griffey': ['Ken Griffey Sr.', 'Ken Griffey Jr.'],
  'fernando tatis': ['Fernando Tatis Sr.', 'Fernando Tatis Jr.'],
  'cal ripken': ['Cal Ripken Sr.', 'Cal Ripken Jr.'],
  'bobby bonds': ['Bobby Bonds', 'Barry Bonds'],
  'cecil fielder': ['Cecil Fielder', 'Prince Fielder'],
  'tim raines': ['Tim Raines Sr.', 'Tim Raines Jr.'],
  'sandy alomar': ['Sandy Alomar Sr.', 'Sandy Alomar Jr.'],
  'pete rose': ['Pete Rose Sr.', 'Pete Rose Jr.']
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

// ENHANCED FETCH WITH DISAMBIGUATION AND TWO-WAY HANDLING
async function fetchStats(name, mode, playerType = null) {
  try {
    let backendMode = mode;
    if (mode === "newest" || mode === "oldest") {
      backendMode = "season";
    }
    
    // Build URL with player_type parameter if specified
    let url = `/player-two-way?name=${encodeURIComponent(name)}&mode=${backendMode}`;
    if (playerType) {
      url += `&player_type=${playerType}`;
    }

    // Use the two-way endpoint instead of disambiguate
    const response = await fetch(url);
    
    if (response.status === 422) {
      // Multiple players found - handle disambiguation
      const data = await response.json();
      return await handleDisambiguation(name, data.suggestions, backendMode);
    }

    if (response.status === 423) {
      // Two-way player found - handle player type selection
      const data = await response.json();
      return await handleTwoWayPlayerSelection(name, data.options, backendMode);
    }
    
    if (response.ok) {
      return await response.json();
    }
    
    // If 404 or other error, try the disambiguate endpoint
    const fallbackUrl = `/player-disambiguate?name=${encodeURIComponent(name)}&mode=${backendMode}`;
    const fallbackResponse = await fetch(fallbackUrl);
    
    if (fallbackResponse.status === 422) {
      const data = await fallbackResponse.json();
      return await handleDisambiguation(name, data.suggestions, backendMode);
    }
    
    if (fallbackResponse.ok) {
      return await fallbackResponse.json();
    }
    
    // Final fallback to original endpoint
    const originalResponse = await fetch(`/player?name=${encodeURIComponent(name)}&mode=${backendMode}`);
    return await originalResponse.json();
    
  } catch (e) {
    console.error('Fetch error:', e);
    return { error: "Failed to fetch data" };
  }
}

async function handleTwoWayPlayerSelection(originalName, options, mode) {
  return new Promise((resolve) => {
    showTwoWaySelectionModal(options, originalName, resolve, mode);
  });
}

function showTwoWaySelectionModal(options, originalName, callback, mode) {
  // Remove any existing modal
  const existingModal = document.getElementById('two-way-modal');
  if (existingModal) {
    existingModal.remove();
  }

  const modal = document.createElement('div');
  modal.id = 'two-way-modal';
  modal.className = 'modal';
  modal.style.cssText = `
    display: block;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.5);
  `;

  const html = `
    <div class="modal-content" style="
      background-color: #fff;
      margin: 15% auto;
      padding: 24px;
      border-radius: 8px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.15);
      width: 90%;
      max-width: 500px;
    ">
      <h3 style="margin-top: 0; margin-bottom: 16px; color: #333; font-size: 20px;">
        Two-Way Player Detected
      </h3>
      <p style="margin-bottom: 20px; color: #666; line-height: 1.5;">
        ${originalName} was both a significant pitcher and hitter. Please select which stats to display:
      </p>
      <div class="player-type-options" style="margin-bottom: 24px;">
        ${options.map(option => `
          <div class="player-type-option" data-type="${option.type}" style="
            padding: 16px;
            border: 2px solid #e9ecef;
            border-radius: 6px;
            margin-bottom: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: center;
          " onmouseover="this.style.borderColor='#007bff'; this.style.backgroundColor='#f8f9ff';" 
             onmouseout="this.style.borderColor='#e9ecef'; this.style.backgroundColor='white';">
            <div class="option-content">
              <strong style="display: block; font-size: 16px; color: #333; margin-bottom: 4px;">
                ${option.label}
              </strong>
              <div style="font-size: 13px; color: #666;">
                ${option.type === 'pitcher' ? 'Wins, Losses, ERA, Strikeouts, etc.' : 'Batting Average, Home Runs, RBIs, etc.'}
              </div>
            </div>
          </div>
        `).join('')}
      </div>
      <button class="modal-close" style="
        background-color: #6c757d;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
      " onmouseover="this.style.backgroundColor='#5a6268';" 
         onmouseout="this.style.backgroundColor='#6c757d';">
        Cancel
      </button>
    </div>
  `;
  
  modal.innerHTML = html;
  document.body.appendChild(modal);
  
  // Add event handlers
  modal.querySelectorAll('.player-type-option').forEach(option => {
    option.addEventListener('click', async function() {
      const selectedType = this.dataset.type;
      modal.remove();
      
      // Fetch stats for selected player type using the two-way endpoint
      try {
        const response = await fetch(`/player-two-way?name=${encodeURIComponent(originalName)}&mode=${mode}&player_type=${selectedType}`);
        const result = await response.json();
        callback(result);
      } catch (error) {
        callback({ error: "Failed to fetch selected player type data" });
      }
    });
  });
  
  modal.querySelector('.modal-close').addEventListener('click', function() {
    modal.remove();
    callback({ error: "User cancelled two-way selection" });
  });
  
  // Close modal when clicking outside
  modal.addEventListener('click', function(e) {
    if (e.target === modal) {
      modal.remove();
      callback({ error: "User cancelled two-way selection" });
    }
  });
}

async function handleDisambiguation(originalName, suggestions, mode) {
  return new Promise((resolve) => {
    showDisambiguationModal(suggestions, originalName, resolve, mode);
  });
}

function showDisambiguationModal(suggestions, originalName, callback, mode) {
  // Remove any existing modal
  const existingModal = document.getElementById('disambiguation-modal');
  if (existingModal) {
    existingModal.remove();
  }
  
  const modal = document.createElement('div');
  modal.id = 'disambiguation-modal';
  modal.className = 'modal';
  modal.style.cssText = `
    display: block;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.5);
  `;
  
  const cleanName = originalName.split(' Jr.')[0].split(' Sr.')[0];
  
  const html = `
    <div class="modal-content" style="
      background-color: #fff;
      margin: 15% auto;
      padding: 24px;
      border-radius: 8px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.15);
      width: 90%;
      max-width: 500px;
    ">
      <h3 style="margin-top: 0; margin-bottom: 16px; color: #333; font-size: 20px;">
        Multiple Players Found
      </h3>
      <p style="margin-bottom: 20px; color: #666; line-height: 1.5;">
        Found multiple players named "${cleanName}". Please select which player:
      </p>
      <div class="player-options" style="margin-bottom: 24px;">
        ${suggestions.map(player => `
          <div class="player-option" data-name="${player.name}" style="
            padding: 16px;
            border: 2px solid #e9ecef;
            border-radius: 6px;
            margin-bottom: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
          " onmouseover="this.style.borderColor='#007bff'; this.style.backgroundColor='#f8f9ff';" 
             onmouseout="this.style.borderColor='#e9ecef'; this.style.backgroundColor='white';">
            <div class="player-details">
              <strong style="display: block; font-size: 16px; color: #333; margin-bottom: 4px;">
                ${player.name}
              </strong>
              <div class="player-meta" style="font-size: 13px; color: #666;">
                Debut: ${player.debut_year} | Born: ${player.birth_year}
              </div>
            </div>
          </div>
        `).join('')}
      </div>
      <button class="modal-close" style="
        background-color: #6c757d;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
      " onmouseover="this.style.backgroundColor='#5a6268';" 
         onmouseout="this.style.backgroundColor='#6c757d';">
        Cancel
      </button>
    </div>
  `;
  
  modal.innerHTML = html;
  document.body.appendChild(modal);
  
  // Add event handlers
  modal.querySelectorAll('.player-option').forEach(option => {
    option.addEventListener('click', async function() {
      const selectedName = this.dataset.name;
      modal.remove();
      
      // Fetch stats for selected player using the two-way endpoint
      try {
        const response = await fetch(`/player-two-way?name=${encodeURIComponent(selectedName)}&mode=${mode}`);
        const result = await response.json();
        callback(result);
      } catch (error) {
        callback({ error: "Failed to fetch selected player data" });
      }
    });
  });
  
  modal.querySelector('.modal-close').addEventListener('click', function() {
    modal.remove();
    callback({ error: "User cancelled disambiguation" });
  });
  
  // Close modal when clicking outside
  modal.addEventListener('click', function(e) {
    if (e.target === modal) {
      modal.remove();
      callback({ error: "User cancelled disambiguation" });
    }
  });
}

async function comparePlayers() {
  const nameA = document.getElementById("playerA").value.trim();
  const nameB = document.getElementById("playerB").value.trim();
  const mode = document.getElementById("viewMode").value;

  if (!nameA || !nameB) {
    alert("Please enter both player names (first and last).");
    return;
  }

  // Hide any open dropdowns
  hideAllDropdowns();

  // Show loading indicator
  const tbody = document.getElementById("comparisonBody");
  tbody.innerHTML = `<tr><td colspan='4' style='text-align: center; padding: 20px;'>Loading player data...</td></tr>`;

  const [resA, resB] = await Promise.all([
    fetchStats(nameA, mode),
    fetchStats(nameB, mode),
  ]);

  updateComparisonTable(resA, resB, nameA, nameB);
}

document.getElementById("viewMode").addEventListener("change", comparePlayers);

// CUSTOM DROPDOWN FUNCTIONALITY
let searchTimeout;
let popularPlayersCache = null;
let currentDropdown = null;
const SEARCH_DELAY = 300;

// Show dropdown with players
function showDropdown(inputId, players) {
  const dropdownId = inputId === 'playerA' ? 'dropdownA' : 'dropdownB';
  const dropdown = document.getElementById(dropdownId);
  
  // Hide other dropdowns first
  hideAllDropdowns();
  
  dropdown.innerHTML = '';
  
  if (!players || players.length === 0) {
    dropdown.innerHTML = '<div class="dropdown-item" style="color: #999; cursor: default;">No players found</div>';
  } else {
    players.forEach(player => {
      const item = document.createElement('div');
      item.className = 'dropdown-item';
      
      if (typeof player === 'string') {
        item.textContent = player;
        item.dataset.value = player;
      } else {
        const name = player.name || player.display;
        const display = player.display || player.name;
        
        item.innerHTML = `${name}${display !== name ? `<span class="player-years">${display}</span>` : ''}`;
        item.dataset.value = name;
      }
      
      item.addEventListener('click', () => {
        document.getElementById(inputId).value = item.dataset.value;
        hideDropdown(dropdownId);
        // Auto-compare if both fields are filled
        const otherInput = inputId === 'playerA' ? 'playerB' : 'playerA';
        if (document.getElementById(otherInput).value.trim()) {
          comparePlayers();
        }
      });
      
      dropdown.appendChild(item);
    });
  }
  
  dropdown.classList.add('show');
  currentDropdown = dropdownId;
}

// Hide specific dropdown
function hideDropdown(dropdownId) {
  const dropdown = document.getElementById(dropdownId);
  dropdown.classList.remove('show');
  if (currentDropdown === dropdownId) {
    currentDropdown = null;
  }
}

// Hide all dropdowns
function hideAllDropdowns() {
  ['dropdownA', 'dropdownB'].forEach(id => {
    const dropdown = document.getElementById(id);
    if (dropdown) {
      dropdown.classList.remove('show');
    }
  });
  currentDropdown = null;
}

// Load popular players
async function loadPopularPlayers(inputId) {
  if (popularPlayersCache) {
    showDropdown(inputId, popularPlayersCache);
    return;
  }
  
  try {
    const response = await fetch('/popular-players');
    if (response.ok) {
      const players = await response.json();
      popularPlayersCache = players;
      showDropdown(inputId, players);
    } else {
      const fallback = [
        "Mike Trout", "Aaron Judge", "Mookie Betts", "Ronald Acuña",
        "Juan Soto", "Gerrit Cole", "Jacob deGrom", "Clayton Kershaw",
        "Vladimir Guerrero Jr.", "Fernando Tatis Jr.", "Shane Bieber", 
        "Freddie Freeman", "Manny Machado", "Jose Altuve", "Kyle Tucker"
      ];
      showDropdown(inputId, fallback);
    }
  } catch (error) {
    console.error('Error loading popular players:', error);
    const fallback = [
      "Mike Trout", "Aaron Judge", "Mookie Betts", "Ronald Acuña",
      "Juan Soto", "Gerrit Cole", "Jacob deGrom", "Clayton Kershaw"
    ];
    showDropdown(inputId, fallback);
  }
}

// Search players
async function searchPlayersEnhanced(query, inputId) {
  try {
    const response = await fetch(`/search-players-enhanced?q=${encodeURIComponent(query)}`);
    if (response.ok) {
      const players = await response.json();
      const formattedPlayers = players.map(player => ({
        name: player.original_name || player.name,
        display: player.display
      }));
      showDropdown(inputId, formattedPlayers);
    } else {
      const fallbackResponse = await fetch(`/search-players?q=${encodeURIComponent(query)}`);
      if (fallbackResponse.ok) {
        const players = await fallbackResponse.json();
        showDropdown(inputId, players);
      }
    }
  } catch (error) {
    console.error('Enhanced search error:', error);
    if (popularPlayersCache) {
      showDropdown(inputId, popularPlayersCache);
    }
  }
}

// Input event handler
function handlePlayerInput(e) {
  const query = e.target.value.trim();
  const inputId = e.target.id;
  
  clearTimeout(searchTimeout);
  
  if (query.length < 2) {
    searchTimeout = setTimeout(() => {
      loadPopularPlayers(inputId);
    }, 100);
    return;
  }
  
  searchTimeout = setTimeout(() => {
    searchPlayersEnhanced(query, inputId);
  }, SEARCH_DELAY);
}

// Click event handler
function handlePlayerClick(e) {
  const inputId = e.target.id;
  const query = e.target.value.trim();
  
  if (query.length < 2) {
    loadPopularPlayers(inputId);
  } else {
    searchPlayersEnhanced(query, inputId);
  }
}

// Focus event handler
function handlePlayerFocus(e) {
  const inputId = e.target.id;
  const query = e.target.value.trim();
  
  if (query.length < 2) {
    loadPopularPlayers(inputId);
  } else {
    searchPlayersEnhanced(query, inputId);
  }
}

// Handle keyboard navigation
function handleEnterKey(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    const dropdownId = e.target.id === 'playerA' ? 'dropdownA' : 'dropdownB';
    hideDropdown(dropdownId);
    comparePlayers();
  } else if (e.key === 'Escape') {
    const dropdownId = e.target.id === 'playerA' ? 'dropdownA' : 'dropdownB';
    hideDropdown(dropdownId);
  }
}

// Setup event listeners
function setupPlayerAutofill() {
  const playerAInput = document.getElementById('playerA');
  const playerBInput = document.getElementById('playerB');
  
  if (playerAInput) {
    playerAInput.addEventListener('input', handlePlayerInput);
    playerAInput.addEventListener('click', handlePlayerClick);
    playerAInput.addEventListener('focus', handlePlayerFocus);
    playerAInput.addEventListener('keydown', handleEnterKey);
  }
  
  if (playerBInput) {
    playerBInput.addEventListener('input', handlePlayerInput);
    playerBInput.addEventListener('click', handlePlayerClick);
    playerBInput.addEventListener('focus', handlePlayerFocus);
    playerBInput.addEventListener('keydown', handleEnterKey);
  }
  
  // Hide dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (currentDropdown && !e.target.closest('.input-container')) {
      hideAllDropdowns();
    }
  });
}

// Initialize everything when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  // Set default values
  document.getElementById("playerA").value = "Kyle Schwarber";
  document.getElementById("playerB").value = "Kyle Tucker";
  document.getElementById("viewMode").value = "combined";
  
  // Initialize custom dropdown functionality
  setupPlayerAutofill();
  
  // Run initial comparison
  comparePlayers();
});