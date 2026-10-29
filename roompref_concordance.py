"""
ROOMPREF pilot - allocation concordance summary (for reviewer response).

Reports (a) the allocation logic used in the pilot (rooms filled in response order)
and (b) the updated nearest-neighbour allocation in roompref_core.py
(place roompref_core.py in the same folder).

Re-runs the ROOMPREF allocation logic (identical to roompref_app.py on GitHub)
on the pilot CSV and reports the numbers needed for the new
'Allocation outcomes' Results paragraph, including a random-allocation
(within-sex) baseline for comparison.

Usage:
    pip install pandas scikit-learn
    python roompref_concordance.py roompref_final.csv [room_size] [n_random]
"""
import re
import sys
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.cluster import KMeans

path = sys.argv[1]
room_size = int(sys.argv[2]) if len(sys.argv) > 2 else 2
n_random = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

try:
    df = pd.read_csv(path)
except UnicodeDecodeError:
    df = pd.read_csv(path, encoding='latin-1')
sex_col = [c for c in df.columns if "sex" in c.lower()][0]
noise_col = [c for c in df.columns if "noise" in c.lower()][0]
light_col = [c for c in df.columns if "lighting" in c.lower()][0]
temp_col = [c for c in df.columns if "temperature" in c.lower()][0]
snore_col = [c for c in df.columns if "snore" in c.lower()][0]
chrono_col = [c for c in df.columns if "morning" in c.lower() and "evening" in c.lower()][0]
name_col = [c for c in df.columns if "full name" in c.lower() or c.lower() == "name"][0]
for c in df.select_dtypes("object").columns:
    df[c] = df[c].astype(str).str.strip().where(df[c].notna())

chrono_map = {
    "Definitely a morning type": "Morning",
    "Rather more a morning than evening type": "Neutral",
    "Rather more an evening than morning type": "Neutral",
    "Definitely an evening type": "Evening",
}
# normalise quote characters so "Rather more a 'morning' than 'evening' type" also maps
_norm = lambda v: re.sub(r"\s+", " ", re.sub(r"[\'\u2018\u2019\"\u201c\u201d]", "", str(v))).strip().lower()
chrono_map = {_norm(k): v for k, v in chrono_map.items()}
df["Chrono"] = df[chrono_col].map(lambda v: chrono_map.get(_norm(v)))
df["SelfConflict"] = (df[snore_col] == "Yes") & (df[noise_col] == "Absolute Silence")

print(f"N respondents in CSV: {len(df)}")
print("Sex:", df[sex_col].value_counts().to_dict())
print("Chronotype category:", df["Chrono"].value_counts(dropna=False).to_dict())
unmapped = df[df["Chrono"].isna()]
if len(unmapped):
    print(f"!! {len(unmapped)} chronotype responses did not map to a category "
          f"(these are silently dropped by the app unless self-conflicted):")
    print(unmapped[chrono_col].value_counts(dropna=False).to_dict())
print("By sex x chronotype:")
print(pd.crosstab(df[sex_col], df["Chrono"].fillna("UNMAPPED")))
print(f"Snorers: {(df[snore_col]=='Yes').sum()}; 'Absolute Silence': "
      f"{(df[noise_col]=='Absolute Silence').sum()}; both (self-conflict): {df['SelfConflict'].sum()}")

# ---------- replicate app grouping ----------
prefs = [noise_col, light_col, temp_col]
base = df[~df["SelfConflict"]].copy()
enc = base.copy()
for c in prefs:
    enc[c] = LabelEncoder().fit_transform(enc[c])
enc[prefs] = StandardScaler().fit_transform(enc[prefs])
pieces = []
for sex in df[sex_col].unique():
    for chrono in ["Morning", "Neutral", "Evening"]:
        mask = (enc[sex_col] == sex) & (enc["Chrono"] == chrono)
        sub = base[mask].copy()
        if sub.empty:
            continue
        k = 1 if len(sub) <= 3 else 2
        sub["ClusterID"] = KMeans(n_clusters=k, random_state=42).fit_predict(enc.loc[mask, prefs])
        sub["RoomGroup"] = sub[sex_col] + " | " + chrono + " | Cluster " + sub["ClusterID"].astype(str)
        pieces.append(sub)
conf = df[df["SelfConflict"]].copy()
if not conf.empty:
    conf["ClusterID"] = -1
    conf["RoomGroup"] = conf[sex_col] + " | Conflict"
    pieces.append(conf)
final = pd.concat(pieces, ignore_index=True)
print(f"\nParticipants carried into grouping/allocation: {len(final)} of {len(df)}")
print("Group sizes:")
print(final["RoomGroup"].value_counts().sort_index().to_string())

# ---------- replicate app allocation (with swap) ----------
def allocate(final):
    rooms_out = []
    for grp, gdf in final.groupby("RoomGroup"):
        parts = gdf.to_dict("records")
        rooms = [parts[i:i + room_size] for i in range(0, len(parts), room_size)]
        for i, room in enumerate(rooms):
            if any(p[snore_col] == "Yes" for p in room) and any(p[noise_col] == "Absolute Silence" for p in room):
                for j, other in enumerate(rooms):
                    if j == i:
                        continue
                    if not any(p2[snore_col] == "Yes" for p2 in other):
                        a = next((k for k, p in enumerate(room) if p[noise_col] == "Absolute Silence"), None)
                        b = next((k for k, p in enumerate(other) if p[noise_col] != "Absolute Silence"), None)
                        if a is not None and b is not None:
                            room[a], other[b] = other[b], room[a]
                        break
        rooms_out.extend(rooms)
    return rooms_out

def room_metrics(rooms):
    full = [r for r in rooms if len(r) == room_size]
    m = {
        "rooms": len(rooms),
        "full": len(full),
        "underfilled": len(rooms) - len(full),
        "snore_silence_warn": sum(
            any(p[snore_col] == "Yes" for p in r) and any(p[noise_col] == "Absolute Silence" for p in r)
            for r in rooms),
        "snore_silence_between_people": sum(
            any(p[snore_col] == "Yes" and q[noise_col] == "Absolute Silence"
                for p in r for q in r if p is not q) for r in full),
    }
    if full:
        same = lambda col: np.mean([len({p[col] for p in r}) == 1 for r in full]) * 100
        m["same_chrono_%"] = np.mean([len({p["Chrono"] for p in r}) == 1 for r in full]) * 100
        m["M_and_E_together_%"] = np.mean([{"Morning", "Evening"} <= {p["Chrono"] for p in r} for r in full]) * 100
        m["same_noise_%"] = same(noise_col)
        m["same_light_%"] = same(light_col)
        m["same_temp_%"] = same(temp_col)
        m["same_all3_%"] = np.mean([all(len({p[c] for p in r}) == 1 for c in prefs) for r in full]) * 100
    return m

rooms = allocate(final)
obs = room_metrics(rooms)
print(f"\n=== ROOMPREF allocation (room size {room_size}) ===")
for k, v in obs.items():
    print(f"{k:32s} {v:.1f}" if isinstance(v, float) else f"{k:32s} {v}")
print("\nRoom list:")
for i, r in enumerate(rooms):
    warn = any(p[snore_col] == "Yes" for p in r) and any(p[noise_col] == "Absolute Silence" for p in r)
    print(f"{i:3d}  " + "; ".join(f"{p[name_col]} [{p['Chrono']}]" for p in r) + ("   <- snore-silence warning" if warn else ""))

# ---------- random within-sex baseline ----------
rng = np.random.default_rng(2024)
rand = []
pool = df.dropna(subset=["Chrono"]).copy()
for _ in range(n_random):
    rr = []
    for sex, sdf in pool.groupby(sex_col):
        recs = sdf.sample(frac=1, random_state=int(rng.integers(1e9))).to_dict("records")
        rr.extend([recs[i:i + room_size] for i in range(0, len(recs), room_size)])
    rand.append(room_metrics(rr))
rand = pd.DataFrame(rand)
print(f"\n=== Random allocation within sex ({n_random} iterations): mean [2.5th-97.5th percentile] ===")
for c in ["same_chrono_%", "M_and_E_together_%", "same_noise_%", "same_light_%", "same_temp_%",
          "same_all3_%", "snore_silence_between_people"]:
    if c in rand:
        lo, hi = np.percentile(rand[c], [2.5, 97.5])
        print(f"{c:32s} {rand[c].mean():.1f} [{lo:.1f}-{hi:.1f}]   ROOMPREF: {obs.get(c, float('nan')):.1f}")

# ---------- updated algorithm (nearest-neighbour allocation, roompref_core.py) ----------
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roompref_core as core
tidy, bad = core.prepare(df)
new_rooms_raw = core.allocate(core.group(tidy), room_size)
conv = lambda p: {noise_col: p["Noise"], light_col: p["Lighting"], temp_col: p["Temperature"],
                  snore_col: p["Snore"], "Chrono": p["ChronoTypeCategory"], name_col: p["Name"]}
new_rooms = [[conv(p) for p in r["_members"]] for r in new_rooms_raw]
new = room_metrics(new_rooms)
print(f"\n=== Summary (room size {room_size}) ===")
summ = pd.DataFrame({"Pilot version (response order)": obs, "Updated (nearest neighbour)": new})
rnd = rand.mean().rename("Random within sex (mean)")
print(pd.concat([summ, rnd], axis=1).round(1).to_string())
