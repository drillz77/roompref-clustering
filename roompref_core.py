"""
ROOMPREF core logic: data cleaning, grouping/clustering and room allocation.

Used by roompref_app.py (Streamlit interface). Kept separate so the same
logic can be run and tested outside the web app.
"""
import re
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

# ---------------------------------------------------------------- labels
NOISE = ["Absolute Silence", "Low Background Noise", "Doesn’t Matter"]
LIGHT = ["Complete Darkness", "Dim Light", "Doesn’t Matter"]
TEMP = ["Cool (20°C, 68°F)", "Moderate (21–24°C, 70–75°F)", "Warm (25°C, 77°F)"]
CHRONO_CATS = ["Morning", "Neutral", "Evening"]

# ordinal codes used for clustering and similarity
NOISE_CODE = {NOISE[0]: 0, NOISE[1]: 1, NOISE[2]: 2}
LIGHT_CODE = {LIGHT[0]: 0, LIGHT[1]: 1, LIGHT[2]: 2}
TEMP_CODE = {TEMP[0]: 0, TEMP[1]: 1, TEMP[2]: 2}

SNORE_SILENCE_PENALTY = 100.0  # added to the distance of any snorer / silence-sensitive pairing


def _norm(v):
    """lower-case, strip quotes/punctuation and collapse spaces (robust to curly quotes and encoding issues)"""
    v = str(v).lower()
    v = re.sub(r"[^a-z0-9 ]", " ", v)
    return re.sub(r"\s+", " ", v).strip()


def canon_noise(v):
    n = _norm(v)
    if "silence" in n:
        return NOISE[0]
    if "low" in n or "background" in n:
        return NOISE[1]
    if "matter" in n:
        return NOISE[2]
    return np.nan


def canon_light(v):
    n = _norm(v)
    if "dark" in n:
        return LIGHT[0]
    if "dim" in n:
        return LIGHT[1]
    if "matter" in n:
        return LIGHT[2]
    return np.nan


def canon_temp(v):
    n = _norm(v)
    if n.startswith("cool"):
        return TEMP[0]
    if n.startswith("moderate"):
        return TEMP[1]
    if n.startswith("warm"):
        return TEMP[2]
    return np.nan


def canon_chrono(v):
    """MEQ self-assessment item -> Morning / Neutral / Evening"""
    n = _norm(v)
    if n.startswith("definitely a morning"):
        return "Morning"
    if n.startswith("definitely an evening"):
        return "Evening"
    if n.startswith("rather more a morning") or n.startswith("rather more an evening"):
        return "Neutral"
    return np.nan


def find_columns(df):
    def first(pred, label):
        cols = [c for c in df.columns if pred(c.lower())]
        if not cols:
            raise ValueError(f"Could not find the {label} column in the uploaded file.")
        return cols[0]
    return {
        "name": first(lambda c: "full name" in c or c == "name", "name"),
        "sex": first(lambda c: "sex" in c, "sex"),
        "noise": first(lambda c: "noise" in c, "noise"),
        "light": first(lambda c: "lighting" in c, "lighting"),
        "temp": first(lambda c: "temperature" in c, "temperature"),
        "snore": first(lambda c: "snore" in c, "snoring"),
        "chrono": first(lambda c: "morning" in c and "evening" in c, "chronotype"),
    }


def prepare(df):
    """Return a tidy dataframe with standard columns, plus a list of rows that could not be processed."""
    cols = find_columns(df)
    out = pd.DataFrame({
        "Name": df[cols["name"]].astype(str).str.strip(),
        "Sex": df[cols["sex"]].astype(str).str.strip(),
        "Noise": df[cols["noise"]].map(canon_noise),
        "Lighting": df[cols["light"]].map(canon_light),
        "Temperature": df[cols["temp"]].map(canon_temp),
        "Snore": df[cols["snore"]].map(lambda v: "Yes" if _norm(v).startswith("yes") else "No"),
        "ChronoTypeCategory": df[cols["chrono"]].map(canon_chrono),
    })
    bad = out[out[["Noise", "Lighting", "Temperature", "ChronoTypeCategory"]].isna().any(axis=1)]
    return out.dropna(subset=["Noise", "Lighting", "Temperature", "ChronoTypeCategory"]).reset_index(drop=True), bad


def encode(df):
    """Ordinal-code and z-score the three environmental preferences."""
    X = np.column_stack([
        df["Noise"].map(NOISE_CODE).values,
        df["Lighting"].map(LIGHT_CODE).values,
        df["Temperature"].map(TEMP_CODE).values,
    ]).astype(float)
    sd = X.std(axis=0)
    sd[sd == 0] = 1.0
    return (X - X.mean(axis=0)) / sd


def group(df):
    """Flag self-conflicts, then K-Means within sex x chronotype subgroups (k=1 if n<=3, else k=2)."""
    df = df.copy()
    df["SelfConflict"] = (df["Snore"] == "Yes") & (df["Noise"] == NOISE[0])
    Z = encode(df)
    df[["zNoise", "zLight", "zTemp"]] = Z
    pieces = []
    base = df[~df["SelfConflict"]]
    for sex in sorted(df["Sex"].unique()):
        for chrono in CHRONO_CATS:
            sub = base[(base["Sex"] == sex) & (base["ChronoTypeCategory"] == chrono)].copy()
            if sub.empty:
                continue
            k = 1 if len(sub) <= 3 else 2
            sub["ClusterID"] = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(
                sub[["zNoise", "zLight", "zTemp"]])
            sub["RoomGroup"] = sub["Sex"] + " | " + chrono + " | Cluster " + sub["ClusterID"].astype(str)
            pieces.append(sub)
    conf = df[df["SelfConflict"]].copy()
    if not conf.empty:
        conf["ClusterID"] = -1
        conf["RoomGroup"] = conf["Sex"] + " | Conflict (snores and requires silence)"
        pieces.append(conf)
    return pd.concat(pieces, ignore_index=True)


def _snore_silence(a, b):
    return (a["Snore"] == "Yes" and b["Noise"] == NOISE[0]) or (b["Snore"] == "Yes" and a["Noise"] == NOISE[0])


def room_has_conflict(room):
    """Snore-silence warning: any snorer and any silence-sensitive occupant (including the same person)."""
    return any(p["Snore"] == "Yes" for p in room) and any(p["Noise"] == NOISE[0] for p in room)


def _nearest_neighbour_rooms(gdf, room_size):
    """Greedy nearest-neighbour allocation within one group.

    Distance = Euclidean distance between standardised noise, lighting and temperature
    responses, plus a large penalty for pairing a snorer with a silence-sensitive participant.
    Each room starts from the most similar available pair; for rooms of 3-4, further occupants
    are added one at a time, choosing the participant with the smallest total distance to the
    current occupants. Any remaining participants (< room_size) form one underfilled room.
    """
    recs = gdf.to_dict("records")
    n = len(recs)
    Z = gdf[["zNoise", "zLight", "zTemp"]].values
    D = np.linalg.norm(Z[:, None, :] - Z[None, :, :], axis=2)
    for i in range(n):
        for j in range(n):
            if i != j and _snore_silence(recs[i], recs[j]):
                D[i, j] += SNORE_SILENCE_PENALTY
    avail = list(range(n))
    rooms = []
    while len(avail) >= room_size and len(avail) >= 2:
        best = min(((D[a, b], a, b) for ai, a in enumerate(avail) for b in avail[ai + 1:]))
        room = [best[1], best[2]]
        while len(room) < room_size:
            cand = [c for c in avail if c not in room]
            nxt = min(cand, key=lambda c: (sum(D[c, r] for r in room), c))
            room.append(nxt)
        rooms.append(room)
        avail = [a for a in avail if a not in room]
    if avail:
        rooms.append(avail)
    return [[recs[i] for i in r] for r in rooms]


def _n_conflicts(room):
    """number of snorer / different silence-sensitive participant pairs in a room"""
    return sum(_snore_silence(a, b) for ai, a in enumerate(room) for b in room[ai + 1:])


def _spread(room):
    """sum of pairwise distances between occupants' standardised preferences"""
    z = [np.array([p["zNoise"], p["zLight"], p["zTemp"]]) for p in room]
    return sum(np.linalg.norm(z[a] - z[b]) for a in range(len(z)) for b in range(a + 1, len(z)))


def _swap(rooms, max_iter=100):
    """Swap fallback: while any room (within the same group) contains a snorer and a different
    silence-sensitive participant, test every exchange of one occupant with an occupant of another
    room in the group, and apply the exchange that most reduces the number of snore-silence pairings
    (ties broken by keeping roommates' preferences most similar). Stops when no exchange helps."""
    for _ in range(max_iter):
        if not any(_n_conflicts(r) for r in rooms):
            break
        best = None
        for i, room in enumerate(rooms):
            if not _n_conflicts(room):
                continue
            for j, other in enumerate(rooms):
                if j == i:
                    continue
                before_c = _n_conflicts(room) + _n_conflicts(other)
                before_s = _spread(room) + _spread(other)
                for a in range(len(room)):
                    for b in range(len(other)):
                        r2, o2 = room.copy(), other.copy()
                        r2[a], o2[b] = other[b], room[a]
                        gain = before_c - (_n_conflicts(r2) + _n_conflicts(o2))
                        if gain <= 0:
                            continue
                        key = (-gain, _spread(r2) + _spread(o2) - before_s)
                        if best is None or key < best[0]:
                            best = (key, i, j, a, b)
        if best is None:
            break
        _, i, j, a, b = best
        rooms[i][a], rooms[j][b] = rooms[j][b], rooms[i][a]
    return rooms


def allocate(grouped, room_size=2):
    """Nearest-neighbour allocation within each group, then the snore-silence swap fallback."""
    out = []
    for grp, gdf in grouped.groupby("RoomGroup", sort=True):
        rooms = _swap(_nearest_neighbour_rooms(gdf, room_size))
        for r in rooms:
            out.append({
                "Group": grp,
                "Participants": "; ".join(p["Name"] for p in r),
                "Occupants": len(r),
                "Warnings": "; ".join(filter(None, [
                    "⚠️ Snore–Silence conflict" if room_has_conflict(r) else "",
                    "Underfilled room" if len(r) < room_size else "",
                ])),
                "_members": r,
            })
    return out
