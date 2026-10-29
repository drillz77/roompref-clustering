import pandas as pd
import streamlit as st

from roompref_core import (prepare, group, allocate, NOISE, LIGHT, TEMP, CHRONO_CATS)

st.title("ROOMPREF – Roommate Compatibility Clustering")
st.markdown("Upload the CSV downloaded from the ROOMPREF Google Form.")

uploaded_file = st.file_uploader("Upload ROOMPREF CSV", type="csv")

if uploaded_file:
    try:
        raw = pd.read_csv(uploaded_file)
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        raw = pd.read_csv(uploaded_file, encoding="latin-1")

    try:
        df, bad = prepare(raw)
    except ValueError as e:
        st.error(str(e))
        st.stop()
    if len(bad):
        st.warning(f"{len(bad)} response(s) could not be read and were excluded: " + "; ".join(bad["Name"]))

    grouped = group(df)

    # Summary charts
    st.subheader("Chronotype Distribution")
    st.bar_chart(grouped["ChronoTypeCategory"].value_counts().reindex(CHRONO_CATS, fill_value=0))
    st.subheader("Noise Sensitivity Distribution")
    st.bar_chart(df["Noise"].value_counts().reindex(NOISE, fill_value=0))
    st.subheader("Lighting Preference Distribution")
    st.bar_chart(df["Lighting"].value_counts().reindex(LIGHT, fill_value=0))
    st.subheader("Temperature Preference Distribution")
    st.bar_chart(df["Temperature"].value_counts().reindex(TEMP, fill_value=0))

    # Grouping summary
    st.subheader("Participant Grouping Summary")
    summary = grouped.groupby("RoomGroup")["Name"].apply(lambda names: "; ".join(names)).reset_index(name="Participants")
    st.dataframe(summary[["Participants"]])

    # Automatic allocation: nearest-neighbour rooms within each group, then snore-silence swap fallback
    st.markdown("### Room Allocation")
    auto = st.toggle("Enable automatic roommate allocation", key="auto_alloc")
    if auto:
        room_size = st.selectbox("Select room size", [2, 3, 4], index=0)
        df_alloc = pd.DataFrame(allocate(grouped, room_size))[["Participants", "Warnings"]]
        st.subheader("Room Allocations")
        st.dataframe(df_alloc)
        csv = df_alloc.to_csv(index=False).encode("utf-8")
        st.download_button("Download Room Allocations", csv,
                           file_name="roompref_room_allocations.csv", mime="text/csv")
