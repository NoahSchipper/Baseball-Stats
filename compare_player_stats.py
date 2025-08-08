import sqlite3
import pandas as pd
from pybaseball import playerid_lookup, batting_stats
import tkinter as tk
from tkinter import messagebox

# Load full current season stats
current_season_stats = batting_stats(2024)

# Connect to Lahman database
conn = sqlite3.connect(r"C:\Users\noahs\OneDrive\Documents\Baseball Stats\lahman2024.db")

def lookup_player():
    name = entry.get().strip()
    if not name or ' ' not in name:
        messagebox.showerror("Error", "Enter a full player name (e.g. Mike Trout)")
        return

    first, last = name.split(' ', 1)

    try:
        # Get playerID from Lahman
        lahman_query = f"""
        SELECT playerid, namefirst, namelast
        FROM lahman_people
        WHERE LOWER(namefirst) = ? AND LOWER(namelast) = ?
        LIMIT 1
        """
        cur = conn.cursor()
        cur.execute(lahman_query, (first.lower(), last.lower()))
        result = cur.fetchone()

        if not result:
            messagebox.showinfo("Result", f"No historical data found for {name}")
            return

        playerid = result[0]

        # Get career batting stats from Lahman
        hist_query = f"""
        SELECT yearid, teamid, g AS games, ab AS at_bats, h AS hits, hr AS home_runs, rbi
        FROM lahman_batting
        WHERE playerid = ?
        ORDER BY yearid DESC
        """
        hist_df = pd.read_sql_query(hist_query, conn, params=(playerid,))
        hist_summary = hist_df.agg({
            'games': 'sum',
            'at_bats': 'sum',
            'hits': 'sum',
            'home_runs': 'sum',
            'rbi': 'sum'
        })

        # Show career stats
        hist_output = "\n".join([f"{k.replace('_', ' ').title()}: {int(v)}" for k, v in hist_summary.items()])
        text_lahman.delete(1.0, tk.END)
        text_lahman.insert(tk.END, f"Career stats (Lahman)\n{hist_output}")

        # Get MLBAM ID using pybaseball
        lookup = playerid_lookup(last, first)
        if lookup.empty:
            text_pybaseball.delete(1.0, tk.END)
            text_pybaseball.insert(tk.END, "No current season data found.")
            return

        mlbam_id = lookup.iloc[0]['key_mlbam']
        current_stats = current_season_stats[current_season_stats['IDfg'] == mlbam_id]

        if current_stats.empty:
            text_pybaseball.delete(1.0, tk.END)
            text_pybaseball.insert(tk.END, "No current season data found.")
            return

        row = current_stats.iloc[0]
        curr_output = f"2024 stats (PyBaseball)\n" \
                      f"AVG: {row['AVG']}\nHR: {row['HR']}\nRBI: {row['RBI']}\nOPS: {row['OPS']}"
        text_pybaseball.delete(1.0, tk.END)
        text_pybaseball.insert(tk.END, curr_output)

    except Exception as e:
        messagebox.showerror("Error", str(e))


# ---------------- UI ----------------
root = tk.Tk()
root.title("Player Stat Comparison")
root.geometry("650x400")

tk.Label(root, text="Enter Player Name (e.g. Mike Trout):").pack()
entry = tk.Entry(root, width=40)
entry.pack(pady=5)

tk.Button(root, text="Compare Stats", command=lookup_player).pack(pady=10)

frame = tk.Frame(root)
frame.pack(fill="both", expand=True)

text_lahman = tk.Text(frame, width=40, height=15)
text_lahman.pack(side="left", fill="both", expand=True, padx=5)

text_pybaseball = tk.Text(frame, width=40, height=15)
text_pybaseball.pack(side="right", fill="both", expand=True, padx=5)

root.mainloop()
