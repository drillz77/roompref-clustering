import streamlit as st
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.cluster import KMeans

st.title("ROOMPREF – Roommate Compatibility Clustering")
st.markdown("Upload the CSV downloaded from the ROOMPREF Google Form.")

uploaded_file = st.file_uploader("Upload ROOMPREF CSV", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Dynamic column detection
    sex_col    = [c for c in df.columns if "sex" in c.lower()][0]
    noise_col  = [c for c in df.columns if "noise" in c.lower()][0]
    light_col  = [c for c in df.columns if "lighting" in c.lower()][0]
    temp_col   = [c for c in df.columns if "temperature" in c.lower()][0]
    snore_col  = [c for c in df.columns if "snore" in c.lower()][0]
    chrono_col = [c for c in df.columns if "morning" in c.lower() and "evening" in c.lower()][0]
    name_col   = [c for c in df.columns if "full name" in c.lower() or c.lower()=="name"][0]

    # Chronotype mapping
    chrono_map = {
        "Definitely a morning type": "Morning",
        "Rather more a morning than evening type": "Neutral",
        "Rather more an evening than morning type": "Neutral",
        "Definitely an evening type": "Evening"
    }
    df["ChronoTypeCategory"] = df[chrono_col].map(chrono_map)

    # Flag conflicts
    df["Conflict"] = (df[snore_col]=="Yes") & (df[noise_col]=="Absolute Silence")

    # Prepare for clustering
    df_base = df[~df["Conflict"]].copy()
    prefs = [noise_col, light_col, temp_col]
    df_enc = df_base.copy()
    for c in prefs:
        df_enc[c] = LabelEncoder().fit_transform(df_enc[c])
    scaler = StandardScaler()
    df_enc[prefs] = scaler.fit_transform(df_enc[prefs])

    # Cluster within sex + chronotype
    pieces = []
    for sex in df[sex_col].unique():
        for chrono in ["Morning","Neutral","Evening"]:
            sub = df_enc[(df_enc[sex_col]==sex)&(df_enc["ChronoTypeCategory"]==chrono)].copy()
            if sub.empty: continue
            k = 1 if len(sub)<=3 else 2
            sub["ClusterID"] = KMeans(n_clusters=k, random_state=42).fit_predict(sub[prefs])
            sub["RoomGroup"] = sub[sex_col] + " | " + chrono + " | Cluster " + sub["ClusterID"].astype(str)
            pieces.append(sub)
    df_conf = df[df["Conflict"]].copy()
    if not df_conf.empty:
        df_conf["ClusterID"] = -1
        df_conf["RoomGroup"] = df_conf[sex_col] + " | Conflict"
        pieces.append(df_conf)
    df_final = pd.concat(pieces, ignore_index=True)

    # Summary charts
    st.subheader("Chronotype Distribution")
    st.bar_chart(df_final["ChronoTypeCategory"].value_counts().reindex(["Morning","Neutral","Evening"],fill_value=0))
    st.subheader("Noise Sensitivity Distribution")
    st.bar_chart(df[noise_col].value_counts().reindex(
        ["Absolute Silence","Low Background Noise","Doesn’t Matter"], fill_value=0))
    st.subheader("Lighting Preference Distribution")
    st.bar_chart(df[light_col].value_counts().reindex(
        ["Complete Darkness","Dim Light","Doesn’t Matter"], fill_value=0))
    st.subheader("Temperature Preference Distribution")
    st.bar_chart(df[temp_col].value_counts().reindex(
        ["Cool (20°C, 68°F)","Moderate (21–24°C, 70–75°F)","Warm (25°C, 77°F)"], fill_value=0))

    # Grouping summary
    st.subheader("Participant Grouping Summary")
    summary = df_final.groupby("RoomGroup")[name_col].apply(lambda names: "; ".join(names)).reset_index(name="Participants")
    st.dataframe(summary[["Participants"]])

    # Automatic allocation with post-cluster swap
    st.markdown("### Room Allocation")
    auto = auto = st.toggle("Enable automatic roommate allocation", key="auto_alloc")
    if auto:
        room_size = st.selectbox("Select room size", [2,3,4], index=0)
        allocations = []
        for grp, grp_df in df_final.groupby("RoomGroup"):
            parts = []
            for _,r in grp_df.iterrows():
                parts.append({"name": r[name_col], "noise": r[noise_col], "snore": r[snore_col]})
            rooms = [parts[i:i+room_size] for i in range(0,len(parts),room_size)]
            # Swap to avoid snore+silence conflict
            for i, room in enumerate(rooms):
                if any(p["snore"]=="Yes" for p in room) and any(p["noise"]=="Absolute Silence" for p in room):
                    for j, other in enumerate(rooms):
                        if j==i: continue
                        if not any(p2["snore"]=="Yes" for p2 in other):
                            idx_sil = next((k for k,p in enumerate(room) if p["noise"]=="Absolute Silence"),None)
                            idx_tol = next((k for k,p in enumerate(other) if p["noise"]!="Absolute Silence"),None)
                            if idx_sil is not None and idx_tol is not None:
                                room[idx_sil], other[idx_tol] = other[idx_tol], room[idx_sil]
                            break
            # finalize
            for room in rooms:
                names = [p["name"] for p in room]
                warn = "⚠️ Snore–Silence conflict" if any(p["snore"]=="Yes" for p in room) and any(p["noise"]=="Absolute Silence" for p in room) else ""
                allocations.append({"Participants": "; ".join(names), "Warnings": warn})
        df_alloc = pd.DataFrame(allocations)
        st.subheader("Room Allocations")
        st.dataframe(df_alloc)
        csv = df_alloc.to_csv(index=False).encode("utf-8")
        st.download_button("Download Room Allocations", csv, file_name="roompref_room_allocations.csv", mime="text/csv")
