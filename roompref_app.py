import base64
import io
from pathlib import Path

import pandas as pd
import streamlit as st

from roompref_core import (prepare, group, allocate, NOISE, LIGHT, TEMP, CHRONO_CATS)

APP_DIR = Path(__file__).parent
EXAMPLE_FILE = APP_DIR / "ROOMPREF_example_120.csv"
TEMPLATE_URL = "https://www.siestaresearch.com/roompref"
REPO_URL = "https://github.com/drillz77/roompref-clustering"

# short labels per question (noise and lighting share the wording "Doesn't Matter", so keep them separate)
SHORT = {
    "Noise": {NOISE[0]: "Silence", NOISE[1]: "Low noise", NOISE[2]: "Any noise"},
    "Lighting": {LIGHT[0]: "Dark", LIGHT[1]: "Dim light", LIGHT[2]: "Any light"},
    "Temperature": {TEMP[0]: "Cool", TEMP[1]: "Moderate", TEMP[2]: "Warm"},
    "ChronoTypeCategory": {c: c for c in CHRONO_CATS},
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
    return " · ".join(SHORT[c][gdf[c].mode().iloc[0]] for c in ["Noise", "Lighting", "Temperature"])


def match_mark(members, col):
    if len(members) < 2:
        return "—"
    return "✓" if len({m[col] for m in members}) == 1 else "✗"


def _nice_max(v):
    """A round axis maximum just above v, with 5 equal ticks."""
    for step in (1, 2, 3, 4, 5, 6, 8, 10, 15, 20, 25, 30, 40, 50, 100, 200, 250, 500):
        if v <= step * 5:
            return step * 5, step
    return v, max(1, v // 5)


def bar_chart_svg(df, col, order, title):
    """Horizontal stacked bar chart (one bar per response, split by sex) as an SVG string.
    Drawn directly rather than with Altair so it renders the same in every Streamlit version."""
    sexes = sorted(df["Sex"].unique())
    colour = dict(zip(sexes, SEX_COLOURS))
    counts = df.groupby([col, "Sex"]).size()
    rows = [(SHORT[col].get(o, o), [int(counts.get((o, s), 0)) for s in sexes]) for o in order]
    xmax, step = _nice_max(max(1, max(sum(v) for _, v in rows)))
    W, lx, top, bh, gap = 520, 84, 48, 26, 10
    pw = W - lx - 34
    H = top + len(rows) * (bh + gap) + 42
    grey = "#808495"
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" '
         f'font-family="&apos;Source Sans Pro&apos;, &apos;Source Sans 3&apos;, &apos;Segoe UI&apos;, Helvetica, Arial, sans-serif" font-size="13">',
         f'<text x="0" y="16" font-size="16" font-weight="600" fill="{grey}">{title}</text>']
    lgx = lx
    for sx in sexes:
        s.append(f'<rect x="{lgx}" y="27" width="10" height="10" rx="2" fill="{colour[sx]}"/>'
                 f'<text x="{lgx + 15}" y="36" fill="{grey}">{sx}</text>')
        lgx += 15 + 8 * len(sx) + 22
    for t in range(0, xmax + 1, step):
        x = lx + pw * t / xmax
        s.append(f'<line x1="{x:.1f}" y1="{top - 4}" x2="{x:.1f}" y2="{H - 38}" stroke="{grey}" stroke-opacity="0.25"/>'
                 f'<text x="{x:.1f}" y="{H - 22}" text-anchor="middle" fill="{grey}" font-size="12">{t}</text>')
    s.append(f'<text x="{lx + pw / 2:.1f}" y="{H - 3}" text-anchor="middle" fill="{grey}" font-size="11">People</text>')
    for i, (label, vals) in enumerate(rows):
        y = top + i * (bh + gap)
        x = lx
        s.append(f'<text x="{lx - 8}" y="{y + bh / 2 + 4.5}" text-anchor="end" fill="{grey}">{label}</text>')
        for sx, v in zip(sexes, vals):
            w = pw * v / xmax
            if v:
                s.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{bh}" fill="{colour[sx]}">'
                         f'<title>{label} · {sx}: {v}</title></rect>')
            x += w
        s.append(f'<text x="{x + 6:.1f}" y="{y + bh / 2 + 4.5}" fill="{grey}" font-size="12">{sum(vals)}</text>')
    s.append("</svg>")
    return "".join(s)


def show_svg(container, svg):
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    container.markdown(f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;max-width:640px" '
                       f'alt="bar chart"/>', unsafe_allow_html=True)


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
c1.caption(" · ".join(f"{sex_counts[k]} {k[0]}" for k in sorted(sex_counts.index)))
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
    show_svg(left, bar_chart_svg(df, "ChronoTypeCategory", CHRONO_CATS, "Chronotype"))
    show_svg(right, bar_chart_svg(df, "Noise", NOISE, "Noise"))
    show_svg(left, bar_chart_svg(df, "Lighting", LIGHT, "Lighting"))
    show_svg(right, bar_chart_svg(df, "Temperature", TEMP, "Temperature"))
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
                    show[c] = show[c].map(SHORT[c])
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
