import sqlite3
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox

# Connect to your Lahman database
conn = sqlite3.connect(r"C:\Users\noahs\OneDrive\Documents\Baseball Stats\lahman2024.db")

def get_stats_by_name(first, last):
    cur = conn.cursor()
    cur.execute("""
        SELECT playerid FROM lahman_people
        WHERE LOWER(namefirst) = ? AND LOWER(namelast) = ?
        LIMIT 1
    """, (first.lower(), last.lower()))
    row = cur.fetchone()
    if not row:
        return None, None
    playerid = row[0]
    df = pd.read_sql(f"""
        SELECT yearid, teamid, g AS games, ab AS at_bats, h AS hits, hr AS home_runs, rbi
        FROM lahman_batting WHERE playerid = ? ORDER BY yearid
    """, conn, params=(playerid,))
    return playerid, df

def compare_players():
    playerA_name = entryA.get().strip()
    playerB_name = entryB.get().strip()

    if ' ' not in playerA_name or ' ' not in playerB_name:
        messagebox.showerror("Input Error", "Please enter both first and last names for both players.")
        return

    firstA, lastA = playerA_name.split(' ', 1)
    firstB, lastB = playerB_name.split(' ', 1)

    idA, statsA = get_stats_by_name(firstA, lastA)
    idB, statsB = get_stats_by_name(firstB, lastB)

    if statsA is None or statsA.empty:
        messagebox.showinfo("Missing", f"No stats found for {playerA_name}")
        return
    if statsB is None or statsB.empty:
        messagebox.showinfo("Missing", f"No stats found for {playerB_name}")
        return

    global dfA, dfB
    dfA, dfB = statsA, statsB

    update_display()

def update_display(*args):
    mode = display_var.get()

    def format_season_stats(df, newest_first):
        df_sorted = df.sort_values('yearid', ascending=not newest_first)
        return "\n".join([
            f"{int(row.yearid)} | {row.teamid or '---'} | G:{row.games} | AB:{row.at_bats} | H:{row.hits} | HR:{row.home_runs} | RBI:{row.rbi}"
            for _, row in df_sorted.iterrows()
        ])

    def format_totals(df):
        totals = df.agg({
            'games': 'sum',
            'at_bats': 'sum',
            'hits': 'sum',
            'home_runs': 'sum',
            'rbi': 'sum'
        })
        return "\n".join([
            f"{stat.replace('_', ' ').title()}: {int(val)}"
            for stat, val in totals.items()
        ])

    if mode == "Career Totals":
        outA = f"Career Totals\n{format_totals(dfA)}"
        outB = f"Career Totals\n{format_totals(dfB)}"
    elif mode == "Season-by-Season (Newest First)":
        outA = f"Season Stats (Newest → Oldest)\n{format_season_stats(dfA, newest_first=True)}"
        outB = f"Season Stats (Newest → Oldest)\n{format_season_stats(dfB, newest_first=True)}"
    elif mode == "Season-by-Season (Oldest First)":
        outA = f"Season Stats (Oldest → Newest)\n{format_season_stats(dfA, newest_first=False)}"
        outB = f"Season Stats (Oldest → Newest)\n{format_season_stats(dfB, newest_first=False)}"
    else:
        outA = outB = "Invalid option."

    textA.delete(1.0, tk.END)
    textA.insert(tk.END, outA)

    textB.delete(1.0, tk.END)
    textB.insert(tk.END, outB)

# --- GUI Setup ---
root = tk.Tk()
root.title("Compare Two Players (Lahman Historical Stats)")
root.geometry("950x600")

frame_top = tk.Frame(root)
frame_top.pack(pady=10)

tk.Label(frame_top, text="Player A (e.g. Mike Trout):").grid(row=0, column=0, padx=5)
entryA = tk.Entry(frame_top, width=25)
entryA.grid(row=0, column=1, padx=5)

tk.Label(frame_top, text="Player B (e.g. Mookie Betts):").grid(row=0, column=2, padx=5)
entryB = tk.Entry(frame_top, width=25)
entryB.grid(row=0, column=3, padx=5)

tk.Button(frame_top, text="Compare", command=compare_players).grid(row=0, column=4, padx=10)

# Dropdown for what to show
display_var = tk.StringVar()
display_var.set("Career Totals")
display_var.trace("w", update_display)

tk.Label(frame_top, text="Show:").grid(row=1, column=1, sticky='e')
display_menu = ttk.OptionMenu(frame_top, display_var,
    "Career Totals",
    "Career Totals",
    "Season-by-Season (Newest First)",
    "Season-by-Season (Oldest First)"
)
display_menu.grid(row=1, column=2, columnspan=2, sticky='w', padx=5)

# Text areas
frame_mid = tk.Frame(root)
frame_mid.pack(fill="both", expand=True, padx=20, pady=10)

textA = tk.Text(frame_mid, width=50, height=25)
textA.pack(side="left", fill="both", expand=True, padx=10)

textB = tk.Text(frame_mid, width=50, height=25)
textB.pack(side="right", fill="both", expand=True, padx=10)

root.mainloop()
