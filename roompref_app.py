import io
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from roompref_core import (prepare, group, allocate, NOISE, LIGHT, TEMP, CHRONO_CATS)

APP_DIR = Path(__file__).parent
EXAMPLE_FILE = APP_DIR / "ROOMPREF_example_120.csv"
TEMPLATE_URL = "https://www.siestaresearch.com/roompref"
REPO_URL = "https://github.com/drillz77/roompref-clustering"

SHORT = {
    NOISE[0]: "Silence", NOISE[1]: "Low noise", NOISE[2]: "Any noise",
    LIGHT[0]: "Dark", LIGHT[1]: "Dim light", LIGHT[2]: "Any light",
    TEMP[0]: "Cool", TEMP[1]: "Moderate", TEMP[2]: "Warm",
}
SEX_COLOURS = ["#7F77DD", "#1D9E75", "#D85A30", "#378ADD"]

st.set_page_config(page_title="ROOMPREF", page_icon="🛏️", layout="wide")


# ---------------------------------------------------------------- helpers
def read_csv(file_or_path):
    try:
        return pd.read_csv(file_or_path)
    except UnicodeDecodeError:
        if hasattr(file_or_path, "seek"):
            file_or_path.seek(0)
        return pd.read_csv(file_or_path, encoding="latin-1")


def group_label(raw_label):
    """'Female | Neutral | Cluster 1' -> ('Female · Neutral', 'B')"""
    parts = [p.strip() for p in raw_label.split("|")]
    if "Conflict" in parts[-1]:
        return f"{parts[0]} · {parts[1]} · snores and needs silence", ""
    sub = chr(ord("A") + int(parts[2].split()[-1]))
    return f"{parts[0]} · {parts[1]}", sub


def profile(gdf):
    return " · ".join(SHORT[gdf[c].mode().iloc[0]] for c in ["Noise", "Lighting", "Temperature"])


def match_mark(members, col):
    if len(members) < 2:
        return "—"
    return "✓" if len({m[col] for m in members}) == 1 else "✗"


def bar_chart(df, col, order, title):
    data = (df.groupby([col, "Sex"]).size().reset_index(name="People")
              .rename(columns={col: "Response"}))
    data["Response"] = data["Response"].map(lambda v: SHORT.get(v, v))
    order = [SHORT.get(o, o) for o in order]
    sexes = sorted(df["Sex"].unique())
    return (alt.Chart(data, title=title)
            .mark_bar()
            .encode(
                y=alt.Y("Response:N", sort=order, title=None),
                x=alt.X("sum(People):Q", title="People"),
                color=alt.Color("Sex:N", scale=alt.Scale(domain=sexes, range=SEX_COLOURS[:len(sexes)]),
                                legend=alt.Legend(orient="top", title=None)),
                tooltip=["Response", "Sex", "People"])
            .properties(height=150, width="container"))


def rooms_table(rooms):
    rows = []
    for i, r in enumerate(rooms, start=1):
        m = r["_members"]
        label, _ = group_label(r["Group"])
        notes = "; ".join(f"{p['Name'].split()[0]}: {p['Comments']}" for p in m if p.get("Comments"))
        status = []
        if "Snore" in r["Warnings"]:
            status.append("Snore–silence conflict")
        if "Underfilled" in r["Warnings"]:
            status.append("Underfilled")
        rows.append({
            "Room": i,
            "Roommates": " / ".join(p["Name"] for p in m),
            "Group": label,
            "Noise": match_mark(m, "Noise"),
            "Light": match_mark(m, "Lighting"),
            "Temp": match_mark(m, "Temperature"),
            "Notes": notes,
            "Status": " · ".join(status) if status else "OK",
        })
    return pd.DataFrame(rows)


def style_rooms(df):
    def row_style(row):
        if "Snore" in row["Status"]:
            colour = "background-color: rgba(226, 75, 74, 0.16)"
        elif "Underfilled" in row["Status"]:
            colour = "background-color: rgba(239, 159, 39, 0.18)"
        else:
            colour = ""
        return [colour] * len(row)
    return df.style.apply(row_style, axis=1)


def to_excel(rooms_df, people_df, groups_df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        rooms_df.to_excel(xw, sheet_name="Rooms", index=False)
        people_df.to_excel(xw, sheet_name="Name to room", index=False)
        groups_df.to_excel(xw, sheet_name="Groups", index=False)
    return buf.getvalue()


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("ROOMPREF")
    st.caption("Roommate Sleep Preference Questionnaire · SIESTA Research Group")

    st.subheader("1. Upload responses")
    uploaded = st.file_uploader("CSV downloaded from the ROOMPREF Google Form", type="csv")
    if EXAMPLE_FILE.exists() and st.button("Try example data (120 fictional people)"):
        st.session_state["use_example"] = True
    if uploaded is not None:
        st.session_state["use_example"] = False

    st.subheader("2. Allocate rooms")
    auto = st.toggle("Allocate rooms automatically", key="auto_alloc")
    room_size = st.radio("People per room", [2, 3, 4], horizontal=True, index=0)

    download_area = st.container()

    st.divider()
    st.caption("🔒 Files are processed in memory for this session only and are not stored.")
    st.caption(f"[Get the Google Form template]({TEMPLATE_URL}) · [Source code]({REPO_URL})")

# ---------------------------------------------------------------- load data
source = uploaded if uploaded is not None else (EXAMPLE_FILE if st.session_state.get("use_example") else None)

if source is None:
    st.title("ROOMPREF – roommate matching")
    st.markdown(
        "Group people with compatible sleep preferences and, if you like, allocate rooms automatically.\n\n"
        "1. Send your team the ROOMPREF Google Form.\n"
        "2. Download the responses as a CSV file.\n"
        "3. Upload the file in the sidebar, or try the example data first.")
    st.info("Upload a CSV file in the sidebar to get started.")
    st.stop()

try:
    df, bad = prepare(read_csv(source))
except ValueError as e:
    st.error(f"{e} Check that the file was downloaded from the ROOMPREF Google Form.")
    st.stop()

if len(bad):
    st.warning(f"{len(bad)} response(s) couldn't be read and were left out: " + "; ".join(bad["Name"]))
if df.empty:
    st.info("The uploaded file contains no usable responses yet. Once people have completed the form, "
            "download the responses again and upload the new file.")
    st.stop()

grouped = group(df)
rooms = allocate(grouped, room_size) if auto else []
self_conflict = grouped[grouped["SelfConflict"]]

# ---------------------------------------------------------------- header + metrics
st.title("ROOMPREF – roommate matching")
sex_counts = df["Sex"].value_counts()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Respondents", len(df), help=" · ".join(f"{k}: {v}" for k, v in sex_counts.items()))
c1.caption(" · ".join(f"{v} {k[0]}" for k, v in sex_counts.items()))
if auto:
    n_conf = sum("Snore" in r["Warnings"] for r in rooms)
    n_under = sum("Underfilled" in r["Warnings"] for r in rooms)
    c2.metric("Rooms", len(rooms))
    c2.caption(f"{room_size} per room")
    c3.metric("Snore–silence", n_conf)
    c3.caption("to review" if n_conf else "none")
    c4.metric("Underfilled", n_under)
    c4.caption("pair manually" if n_under else "none")
else:
    c2.metric("Groups", grouped["RoomGroup"].nunique())
    c3.metric("Snore and need silence", len(self_conflict))
    c4.metric("Rooms", "–")
    c4.caption("turn on automatic allocation")

tab_overview, tab_groups, tab_rooms, tab_help = st.tabs(["Overview", "Groups", "Rooms", "Help"])

# ---------------------------------------------------------------- overview
with tab_overview:
    left, right = st.columns(2)
    left.altair_chart(bar_chart(df, "ChronoTypeCategory", CHRONO_CATS, "Chronotype"))
    right.altair_chart(bar_chart(df, "Noise", NOISE, "Noise"))
    left.altair_chart(bar_chart(df, "Lighting", LIGHT, "Lighting"))
    right.altair_chart(bar_chart(df, "Temperature", TEMP, "Temperature"))
    st.caption(f"Snoring: {int((df['Snore'] == 'Yes').sum())} of {len(df)} people.")

# ---------------------------------------------------------------- groups
groups_rows = []
with tab_groups:
    st.caption("People in the same group have the same sex and chronotype category and similar "
               "noise, lighting and temperature preferences, so they are suitable to room together.")
    if len(self_conflict):
        st.error(f"{len(self_conflict)} {'person snores' if len(self_conflict) == 1 else 'people snore'} "
                 "and also need silence: " + ", ".join(self_conflict["Name"]) +
                 ". Consider a single room, earplugs, or pairing with another snorer.")
    cols = st.columns(2)
    ordered = sorted(grouped.groupby("RoomGroup"), key=lambda kv: ("Conflict" in kv[0], kv[0]))
    for i, (raw, gdf) in enumerate(ordered):
        label, sub = group_label(raw)
        title = f"{label}" + (f" · group {sub}" if sub else "")
        groups_rows.append({"Group": title, "People": len(gdf), "Typical preferences": profile(gdf),
                            "Names": "; ".join(gdf["Name"])})
        with cols[i % 2].container(border=True):
            st.markdown(f"**{title}** · {len(gdf)} {'person' if len(gdf) == 1 else 'people'}")
            st.caption(f"Mostly {profile(gdf)}")
            with st.expander("Show people"):
                show = gdf[["Name", "Noise", "Lighting", "Temperature", "Snore", "Comments"]].copy()
                for c in ["Noise", "Lighting", "Temperature"]:
                    show[c] = show[c].map(SHORT)
                st.dataframe(show, hide_index=True)
groups_df = pd.DataFrame(groups_rows)

# ---------------------------------------------------------------- rooms
with tab_rooms:
    if not auto:
        st.info("Turn on **Allocate rooms automatically** in the sidebar to see suggested rooms. "
                "Or use the Groups tab to allocate rooms yourself.")
    else:
        rooms_df = rooms_table(rooms)
        attention = rooms_df[rooms_df["Status"] != "OK"]
        if len(attention):
            with st.expander(f"⚠️ {len(attention)} room(s) need your attention", expanded=True):
                for _, r in attention.iterrows():
                    if "Snore" in r["Status"]:
                        tip = "pair snorers together, use a single room, or provide earplugs"
                    else:
                        tip = "combine with another underfilled room of the same sex, ideally a similar chronotype"
                    st.markdown(f"- **Room {r['Room']}** ({r['Roommates']}): {r['Status'].lower()}. Suggestion: {tip}.")
        st.caption("✓ = roommates gave the same answer · ✗ = answers differ · — = only one person in the room")
        st.dataframe(style_rooms(rooms_df), hide_index=True, height=min(38 + 35 * len(rooms_df), 700))

        people_df = pd.DataFrame([
            {"Name": p["Name"], "Room": i, "Roommates": "; ".join(q["Name"] for q in r["_members"] if q is not p)}
            for i, r in enumerate(rooms, start=1) for p in r["_members"]
        ]).sort_values("Name")

        with download_area:
            st.subheader("3. Download")
            st.download_button("Rooms (Excel)", to_excel(rooms_df, people_df, groups_df),
                               file_name="roompref_rooms.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.download_button("Rooms (CSV)", rooms_df.to_csv(index=False).encode("utf-8"),
                               file_name="roompref_room_allocations.csv", mime="text/csv")

# ---------------------------------------------------------------- help
with tab_help:
    st.markdown(f"""
**How to use ROOMPREF**

1. Make a copy of the [ROOMPREF Google Form]({TEMPLATE_URL}) and send it to everyone who needs a room.
2. In the form's **Responses** tab, choose **Link to Sheets**, then in Google Sheets go to **File → Download → Comma-separated values (.csv)**.
3. Upload the CSV file in the sidebar.
4. Check the **Overview** and **Groups** tabs. Either allocate rooms yourself from the groups, or turn on automatic allocation and choose the room size.
5. Review rooms that need attention, then download the allocations.

**How matching works**

People are grouped by sex and chronotype (Morning, Neutral or Evening), so Morning and Evening types are never placed together automatically. Within each group, people with similar noise, lighting and temperature preferences are clustered, and rooms are formed by putting the most similar people together. Snorers are kept apart from people who need silence wherever possible.

**Warnings**

- **Snore–silence conflict**: someone who snores shares a room with someone who needs silence, or one person reported both.
- **Underfilled**: the room has fewer people than the chosen room size, usually because a group had an odd number of people.

ROOMPREF supports, but does not replace, your judgement. Check the suggested rooms against what you know about the people involved, including the notes they gave.

Full details: [source code and documentation]({REPO_URL}).
""")
