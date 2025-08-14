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
  whip: "WHIP",
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
  ops: "OPS",
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
  whip: "WHIP",
};

// Common father/son player mappings for quick reference
const COMMON_FATHER_SON_PLAYERS = {
  "ken griffey": ["Ken Griffey Sr.", "Ken Griffey Jr."],
  "fernando tatis": ["Fernando Tatis Sr.", "Fernando Tatis Jr."],
  "cal ripken": ["Cal Ripken Sr.", "Cal Ripken Jr."],
  "bobby bonds": ["Bobby Bonds", "Barry Bonds"],
  "cecil fielder": ["Cecil Fielder", "Prince Fielder"],
  "tim raines": ["Tim Raines Sr.", "Tim Raines Jr."],
  "sandy alomar": ["Sandy Alomar Sr.", "Sandy Alomar Jr."],
  "pete rose": ["Pete Rose Sr.", "Pete Rose Jr."],
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

function formatAwardsForStructuredDisplay(awards) {
  console.log("formatAwardsForStructuredDisplay called with:", awards);

  // Handle null/undefined awards
  if (!awards) {
    console.log("No awards data provided");
    return {
      championships: 0,
      tsnAllStar: 0,      // Separate TSN All-Star count
      mlbAllStar: 0,      // MLB All-Star Game appearances (if available)
      goldGlove: 0,
      silverSlugger: 0,
      mvp: 0,
      cyYoung: 0,
      royAward: 0,
      worldSeriesMvp: 0,
      relieverAward: 0,
      otherMajor: [],
    };
  }

  // Handle case where awards.summary doesn't exist but awards.awards might
  let summary = awards.summary;

  if (!summary && awards.awards && Array.isArray(awards.awards)) {
    console.log("No summary found, creating from awards array");
    // Create summary from awards array if summary is missing
    summary = {};
    awards.awards.forEach((award) => {
      const awardId = award.award_id || award.award;
      if (!summary[awardId]) {
        summary[awardId] = {
          count: 0,
          display_name: award.award,
          years: [],
        };
      }
      summary[awardId].count += 1;
      summary[awardId].years.push(award.year);
    });
    console.log("Created summary from awards array:", summary);
  }

  if (!summary) {
    console.log("No summary or awards array found");
    return {
      championships: 0,
      tsnAllStar: 0,
      mlbAllStar: 0,
      goldGlove: 0,
      silverSlugger: 0,
      mvp: 0,
      cyYoung: 0,
      royAward: 0,
      worldSeriesMvp: 0,
      relieverAward: 0,
      otherMajor: [],
    };
  }

  console.log("Processing summary:", summary);

  // Enhanced mapping to properly distinguish TSN All-Stars from MLB All-Star Games
  const result = {
    championships:
      summary["WS"]?.count || summary["World Series Champion"]?.count || 0,
    
    // TSN All-Star team selections (from awards table)
    tsnAllStar:
      summary["AS"]?.count || 
      summary["TSN All-Star"]?.count || 
      summary["The Sporting News All-Star"]?.count || 
      0,
    
    // MLB All-Star Game appearances
    mlbAllStar: awards.mlbAllStar || 0,
    
    goldGlove: summary["GG"]?.count || summary["Gold Glove"]?.count || 0,
    silverSlugger:
      summary["SS"]?.count || summary["Silver Slugger"]?.count || 0,
    mvp: summary["MVP"]?.count || summary["Most Valuable Player"]?.count || 0,
    cyYoung:
      summary["CYA"]?.count ||
      summary["CY"]?.count ||
      summary["Cy Young Award"]?.count ||
      0,
    royAward:
      summary["ROY"]?.count || summary["Rookie of the Year"]?.count || 0,
    worldSeriesMvp:
      summary["WSMVP"]?.count || summary["World Series MVP"]?.count || 0,
    relieverAward:
      summary["Reliever"]?.count || summary["Reliever of the Year"]?.count || 0,
    otherMajor: getOtherMajorAwards(summary),
  };

  console.log("formatAwardsForStructuredDisplay result:", result);
  return result;
}

function getOtherMajorAwards(summary) {
  const majorAwardTypes = [
    "ALCS MVP",
    "NLCS MVP", 
    "ASG MVP",
    "COMEB",
    "Hutch",
    "Roberto Clemente",
    "Hank Aaron",
    "Edgar Martinez",
    "Lou Gehrig",
    "Branch Rickey",
    "All-MLB Team - First Team",
    "All-MLB Team - Second Team",
    "Player of the Month",
    "Player of the Week",
  ];

  const other = [];

  // Check each award type in the summary
  Object.keys(summary).forEach((awardKey) => {
    const awardData = summary[awardKey];

    // Skip awards we've already categorized in the main function
    const mainAwards = [
      "WS", "World Series Champion",
      "AS", "TSN All-Star", "The Sporting News All-Star", "MLB All-Star", "All-Star Game",
      "GG", "Gold Glove",
      "SS", "Silver Slugger",
      "MVP", "Most Valuable Player",
      "CYA", "CY", "Cy Young Award",
      "ROY", "Rookie of the Year",
      "WSMVP", "World Series MVP",
      "Reliever", "Reliever of the Year",
    ];

    if (!mainAwards.includes(awardKey)) {
      // Include this as an "other major award"
      other.push({
        name: awardData.display_name || awardKey,
        count: awardData.count,
      });
    }
  });

  return other;
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
    tbody.innerHTML = `<tr><td colspan='4'>${
      resA.error || resB.error
    }</td></tr>`;
    return;
  }

  if (resA.player_type !== resB.player_type) {
    tbody.innerHTML = `<tr><td colspan='4'>Cannot compare pitcher and hitter statistics.</td></tr>`;
    return;
  }

  const mode = resA.mode;
  const playerType = resA.player_type || "hitter";

  // Debug logging for awards
  console.log("=== AWARDS DEBUG ===");
  console.log("Player A awards:", resA.awards);
  console.log("Player B awards:", resB.awards);

  if (["career", "combined", "live"].includes(mode)) {
    const statsA = extractStats(resA);
    const statsB = extractStats(resB);

    const currentLabelMap =
      playerType === "pitcher" ? pitcherLabelMap : hitterLabelMap;

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
        const decimalStats = [
          "war",
          "batting_average",
          "on_base_percentage",
          "slugging_percentage",
          "ops",
        ];
        if (decimalStats.includes(key)) {
          if (key === "war") {
            valA = valA ? Number(valA).toFixed(1) : "0.0";
            valB = valB ? Number(valB).toFixed(1) : "0.0";
          } else {
            valA = valA ? Number(valA).toFixed(3).replace(/^0/, "") : ".000";
            valB = valB ? Number(valB).toFixed(3).replace(/^0/, "") : ".000";
          }
        } else if (key === "ops_plus") {
          valA = valA ? Math.round(valA) : 0;
          valB = valB ? Math.round(valB) : 0;
        }
      }

      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${valA}</td>
        <td style="background-color: #f1f3f4;"><strong>${statName}</strong></td>
        <td>${valB}</td>
      `;
      tbody.appendChild(row);
    }
  }

  // AWARDS SECTION - Fixed to properly check for awards
  console.log("Checking awards existence...");
  const hasAwardsA = resA.awards && (resA.awards.summary || resA.awards.awards);
  const hasAwardsB = resB.awards && (resB.awards.summary || resB.awards.awards);

  console.log("Has awards A:", hasAwardsA);
  console.log("Has awards B:", hasAwardsB);

  if (hasAwardsA || hasAwardsB) {
    console.log("Processing awards data...");

    const awardsA = formatAwardsForStructuredDisplay(resA.awards);
    const awardsB = formatAwardsForStructuredDisplay(resB.awards);

    console.log("Formatted awards A:", awardsA);
    console.log("Formatted awards B:", awardsB);

    // Define award rows to display (only show if at least one player has the award)
    const awardRows = [
      {
        key: "championships",
        label: "Championships",
        valueA: awardsA.championships,
        valueB: awardsB.championships,
      },
      { key: "mvp", label: "MVP", valueA: awardsA.mvp, valueB: awardsB.mvp },
      {
        key: "cyYoung",
        label: "Cy Young",
        valueA: awardsA.cyYoung,
        valueB: awardsB.cyYoung,
      },
      {
        key: "royAward",
        label: "Rookie of Year",
        valueA: awardsA.royAward,
        valueB: awardsB.royAward,
      },
      {
        key: "worldSeriesMvp",
        label: "World Series MVP",
        valueA: awardsA.worldSeriesMvp,
        valueB: awardsB.worldSeriesMvp,
      },
      {
        key: "mlbAllStar",
        label: "All-Star Games",
        valueA: awardsA.mlbAllStar,
        valueB: awardsB.mlbAllStar,
      },
      {
        key: "TSNAllStar",
        label: "TSN All-Star Games",
        valueA: awardsA.tsnAllStar,
        valueB: awardsB.tsnAllStar,
      },
      {
        key: "goldGlove",
        label: "Gold Glove",
        valueA: awardsA.goldGlove,
        valueB: awardsB.goldGlove,
      },
      {
        key: "silverSlugger",
        label: "Silver Slugger",
        valueA: awardsA.silverSlugger,
        valueB: awardsB.silverSlugger,
      },
      {
        key: "relieverAward",
        label: "Reliever of Year",
        valueA: awardsA.relieverAward,
        valueB: awardsB.relieverAward,
      },
    ];

    // Track if any awards were added
    let awardsAdded = 0;

    // Add Awards & Honors header before the first award (only if we have awards to show)
    let hasAnyAwards = awardRows.some(
      (row) => row.valueA > 0 || row.valueB > 0
    );
    if (hasAnyAwards && awardsAdded === 0) {
      const headerRow = document.createElement("tr");
      headerRow.innerHTML = `<th colspan="3" class="stat-header">Awards & Honors <br> (Through 2024 Season)</th>`;
      tbody.appendChild(headerRow);
    }
    
    // Only show awards where at least one player has a non-zero value
    awardRows.forEach((awardRow, index) => {
      if (awardRow.valueA > 0 || awardRow.valueB > 0) {
        const row = document.createElement("tr");

        // Display values - show 0 for players without awards, actual count for those with awards
        const displayA = awardRow.valueA > 0 ? awardRow.valueA : "0";
        const displayB = awardRow.valueB > 0 ? awardRow.valueB : "0";

        row.innerHTML = `
          <td style="text-align: center; padding: 8px;">${displayA}</td>
          <td style="text-align: center; padding: 8px; font-weight: bold; background-color: #f1f3f4;">${awardRow.label}</td>
          <td style="text-align: center; padding: 8px;">${displayB}</td>
        `;
        tbody.appendChild(row);
        awardsAdded++;

        console.log(
          `Added award row: ${awardRow.label} - A: ${displayA}, B: ${displayB}`
        );
      }
    });

    // Add other major awards if any
    const allOtherAwards = [
      ...(awardsA.otherMajor || awardsA.awards || []),
      ...(awardsB.otherMajor || awardsB.awards || []),
    ];
    const uniqueOtherAwards = [...new Set(allOtherAwards.map((a) => a.name))];

    uniqueOtherAwards.forEach((awardName) => {
      const countA =
        (awardsA.otherMajor || awardsA.awards || []).find(
          (a) => a.name === awardName
        )?.count || 0;
      const countB =
        (awardsB.otherMajor || awardsB.awards || []).find(
          (a) => a.name === awardName
        )?.count || 0;

      if (countA > 0 || countB > 0) {
        const row = document.createElement("tr");

        // Show actual count or 0, not empty
        const displayA = countA > 0 ? countA : "0";
        const displayB = countB > 0 ? countB : "0";

        row.innerHTML = `
          <td style="text-align: center; padding: 8px;">${displayA}</td>
          <td style="text-align: center; padding: 8px; font-weight: bold; background-color: #f1f3f4;">${awardName}</td>
          <td style="text-align: center; padding: 8px;">${displayB}</td>
        `;
        tbody.appendChild(row);
        awardsAdded++;
      }
    });

    // If no awards were added, show a debug message
    if (awardsAdded === 0) {
      console.log("No awards found to display");
      const row = document.createElement("tr");
      row.innerHTML = `<td colspan="3" style="text-align: center; padding: 12px; color: #666; font-style: italic;">No major awards found for either player</td>`;
      tbody.appendChild(row);
    } else {
      console.log(`Successfully added ${awardsAdded} award rows`);
    }
  } else {
    console.log("No awards data found for either player");
    console.log("resA.awards:", resA.awards);
    console.log("resB.awards:", resB.awards);
  }

  // SEASON MODE HANDLING (unchanged)
  if (mode === "season") {
    const statsA = extractStats(resA);
    const statsB = extractStats(resB);

    const years = new Set();
    statsA.forEach((s) => years.add(s.year));
    statsB.forEach((s) => years.add(s.year));

    let yearsArray = Array.from(years);
    const sortOrder = document.getElementById("viewMode").value;
    if (sortOrder === "oldest") {
      yearsArray.sort((a, b) => a - b);
    } else {
      yearsArray.sort((a, b) => b - a);
    }

    const seasonLabelMap =
      playerType === "pitcher" ? pitcherSeasonLabelMap : hitterSeasonLabelMap;

    yearsArray.forEach((year) => {
      const playerAStat = statsA.find((s) => s.year === year) || {};
      const playerBStat = statsB.find((s) => s.year === year) || {};

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
              valA = valA ? Number(valA).toFixed(3).replace(/^0/, "") : ".000";
              valB = valB ? Number(valB).toFixed(3).replace(/^0/, "") : ".000";
            }
          }
        }

        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${valA}</td>
          <td style="background-color: #f1f3f4;"><strong>${statName}</strong></td>
          <td>${valB}</td>
        `;
        tbody.appendChild(row);
      }
    });
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
    let url = `/player-two-way?name=${encodeURIComponent(
      name
    )}&mode=${backendMode}`;
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
    const fallbackUrl = `/player-disambiguate?name=${encodeURIComponent(
      name
    )}&mode=${backendMode}`;
    const fallbackResponse = await fetch(fallbackUrl);

    if (fallbackResponse.status === 422) {
      const data = await fallbackResponse.json();
      return await handleDisambiguation(name, data.suggestions, backendMode);
    }

    if (fallbackResponse.ok) {
      return await fallbackResponse.json();
    }

    // Final fallback to original endpoint
    const originalResponse = await fetch(
      `/player?name=${encodeURIComponent(name)}&mode=${backendMode}`
    );
    return await originalResponse.json();
  } catch (e) {
    console.error("Fetch error:", e);
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
  const existingModal = document.getElementById("two-way-modal");
  if (existingModal) {
    existingModal.remove();
  }

  const modal = document.createElement("div");
  modal.id = "two-way-modal";
  modal.className = "modal";
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
        ${options
          .map(
            (option) => `
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
                ${
                  option.type === "pitcher"
                    ? "Wins, Losses, ERA, Strikeouts, etc."
                    : "Batting Average, Home Runs, RBIs, etc."
                }
              </div>
            </div>
          </div>
        `
          )
          .join("")}
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
  modal.querySelectorAll(".player-type-option").forEach((option) => {
    option.addEventListener("click", async function () {
      const selectedType = this.dataset.type;
      modal.remove();

      // Fetch stats for selected player type using the two-way endpoint
      try {
        const response = await fetch(
          `/player-two-way?name=${encodeURIComponent(
            originalName
          )}&mode=${mode}&player_type=${selectedType}`
        );
        const result = await response.json();
        callback(result);
      } catch (error) {
        callback({ error: "Failed to fetch selected player type data" });
      }
    });
  });

  modal.querySelector(".modal-close").addEventListener("click", function () {
    modal.remove();
    callback({ error: "User cancelled two-way selection" });
  });

  // Close modal when clicking outside
  modal.addEventListener("click", function (e) {
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

let currentDisambiguationPlayer = null;

function showDisambiguationModal(suggestions, originalName, callback, mode) {
  // Remove any existing modal
  const existingModal = document.getElementById("disambiguation-modal");
  if (existingModal) {
    existingModal.remove();
  }

  const modal = document.createElement("div");
  modal.id = "disambiguation-modal";
  modal.className = "modal";
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

  const cleanName = originalName.split(" Jr.")[0].split(" Sr.")[0];

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
        ${suggestions
          .map(
            (player, index) => `
          <div class="player-option" data-name="${
            player.name
          }" data-playerid="${player.playerid}" style="
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
                ${player.playerid ? ` | ID: ${player.playerid}` : ""}
              </div>
            </div>
          </div>
        `
          )
          .join("")}
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
  modal.querySelectorAll(".player-option").forEach((option) => {
    option.addEventListener("click", async function () {
      const selectedName = this.dataset.name;
      const selectedPlayerId = this.dataset.playerid;
      console.log(`User selected: ${selectedName} (ID: ${selectedPlayerId})`);
      modal.remove();

      // Hide any open dropdowns to prevent interference
      hideAllDropdowns();

      // Fetch stats for selected player using the exact name from suggestions
      try {
        console.log(`Fetching stats for selected player: ${selectedName}`);
        const response = await fetch(
          `/player-two-way?name=${encodeURIComponent(
            selectedName
          )}&mode=${mode}`
        );
        console.log(`Response status for selected player: ${response.status}`);

        if (response.ok) {
          const result = await response.json();
          console.log("Successfully fetched selected player data:", result);
          // Add the selected name to the result so we can use it in the display
          result.selected_name = selectedName;
          result.original_search_name = originalName;
          callback(result);
        } else {
          const errorData = await response
            .json()
            .catch(() => ({ error: `HTTP ${response.status}` }));
          console.error("Error fetching selected player:", errorData);
          callback(errorData);
        }
      } catch (error) {
        console.error("Error in disambiguation selection:", error);
        callback({ error: "Failed to fetch selected player data" });
      }
    });
  });

  modal.querySelector(".modal-close").addEventListener("click", function () {
    modal.remove();
    callback({ error: "User cancelled disambiguation" });
  });

  // Close modal when clicking outside
  modal.addEventListener("click", function (e) {
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

  console.log(`=== COMPARING PLAYERS ===`);
  console.log(`Player A: ${nameA}`);
  console.log(`Player B: ${nameB}`);
  console.log(`Mode: ${mode}`);

  const [resA, resB] = await Promise.all([
    fetchStats(nameA, mode),
    fetchStats(nameB, mode),
  ]);

  // Use the selected names if available, otherwise use the input names
  const displayNameA = resA?.selected_name || nameA;
  const displayNameB = resB?.selected_name || nameB;

  updateComparisonTable(resA, resB, displayNameA, displayNameB);
}

document.getElementById("viewMode").addEventListener("change", comparePlayers);

// CUSTOM DROPDOWN FUNCTIONALITY
let searchTimeout;
let popularPlayersCache = null;
let currentDropdown = null;
const SEARCH_DELAY = 500;

// Show dropdown with players
function showDropdown(inputId, players) {
  const dropdownId = inputId === "playerA" ? "dropdownA" : "dropdownB";
  const dropdown = document.getElementById(dropdownId);

  // Hide other dropdowns first
  hideAllDropdowns();

  dropdown.innerHTML = "";

  if (!players || players.length === 0) {
    dropdown.innerHTML =
      '<div class="dropdown-item" style="color: #999; cursor: default;">No players found</div>';
  } else {
    players.forEach((player) => {
      const item = document.createElement("div");
      item.className = "dropdown-item";

      if (typeof player === "string") {
        item.textContent = player;
        item.dataset.value = player;
      } else {
        const name = player.name || player.display;
        const display = player.display || player.name;

        item.innerHTML = `${name}${
          display !== name ? `<span class="player-years">${display}</span>` : ""
        }`;
        item.dataset.value = name;
      }

      item.addEventListener("click", () => {
        document.getElementById(inputId).value = item.dataset.value;
        hideDropdown(dropdownId);
        // Auto-compare if both fields are filled
        const otherInput = inputId === "playerA" ? "playerB" : "playerA";
        if (document.getElementById(otherInput).value.trim()) {
          comparePlayers();
        }
      });

      dropdown.appendChild(item);
    });
  }

  dropdown.classList.add("show");
  currentDropdown = dropdownId;
}

// Hide specific dropdown
function hideDropdown(dropdownId) {
  const dropdown = document.getElementById(dropdownId);
  dropdown.classList.remove("show");
  if (currentDropdown === dropdownId) {
    currentDropdown = null;
  }
}

// Hide all dropdowns
function hideAllDropdowns() {
  ["dropdownA", "dropdownB"].forEach((id) => {
    const dropdown = document.getElementById(id);
    if (dropdown) {
      dropdown.classList.remove("show");
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
    const response = await fetch("/popular-players");
    if (response.ok) {
      const players = await response.json();
      popularPlayersCache = players;
      showDropdown(inputId, players);
    } else {
      const fallback = [
        "Mike Trout",
        "Aaron Judge",
        "Mookie Betts",
        "Ronald Acuña",
        "Juan Soto",
        "Gerrit Cole",
        "Jacob deGrom",
        "Clayton Kershaw",
        "Vladimir Guerrero Jr.",
        "Fernando Tatis Jr.",
        "Shane Bieber",
        "Freddie Freeman",
        "Manny Machado",
        "Jose Altuve",
        "Kyle Tucker",
      ];
      showDropdown(inputId, fallback);
    }
  } catch (error) {
    console.error("Error loading popular players:", error);
    const fallback = [
      "Mike Trout",
      "Aaron Judge",
      "Mookie Betts",
      "Ronald Acuña",
      "Juan Soto",
      "Gerrit Cole",
      "Jacob deGrom",
      "Clayton Kershaw",
    ];
    showDropdown(inputId, fallback);
  }
}

// Search players
async function searchPlayersEnhanced(query, inputId) {
  try {
    const response = await fetch(
      `/search-players?q=${encodeURIComponent(query)}`
    );
    if (response.ok) {
      const players = await response.json();
      const formattedPlayers = players.map((player) => ({
        name: player.original_name || player.name,
        display: player.display,
      }));
      showDropdown(inputId, formattedPlayers);
    } 
  } catch (error) {
    console.error("Enhanced search error:", error);
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
  if (e.key === "Enter") {
    e.preventDefault();
    const dropdownId = e.target.id === "playerA" ? "dropdownA" : "dropdownB";
    hideDropdown(dropdownId);
    comparePlayers();
  } else if (e.key === "Escape") {
    const dropdownId = e.target.id === "playerA" ? "dropdownA" : "dropdownB";
    hideDropdown(dropdownId);
  }
}

// Setup event listeners
function setupPlayerAutofill() {
  const playerAInput = document.getElementById("playerA");
  const playerBInput = document.getElementById("playerB");

  if (playerAInput) {
    playerAInput.addEventListener("input", handlePlayerInput);
    playerAInput.addEventListener("click", handlePlayerClick);
    playerAInput.addEventListener("focus", handlePlayerFocus);
    playerAInput.addEventListener("keydown", handleEnterKey);
  }

  if (playerBInput) {
    playerBInput.addEventListener("input", handlePlayerInput);
    playerBInput.addEventListener("click", handlePlayerClick);
    playerBInput.addEventListener("focus", handlePlayerFocus);
    playerBInput.addEventListener("keydown", handleEnterKey);
  }

  // Hide dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (currentDropdown && !e.target.closest(".input-container")) {
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
