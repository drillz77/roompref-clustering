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

    # Conflict-prevention logic
    df["Conflict"] = (df[snore_col] == "Yes") & (df[noise_col] == "Absolute Silence")
    df["Warnings"] = df["Conflict"].map({True: "⚠️ Snore–Silence conflict", False: ""})

    # Prepare base for clustering: exclude conflicts
    df_base = df[~df["Conflict"]].copy()

    # Encode and standardize preferences
    prefs = [noise_col, light_col, temp_col]
    df_enc = df_base.copy()
    for c in prefs:
        df_enc[c] = LabelEncoder().fit_transform(df_enc[c])
    scaler = StandardScaler()
    df_enc[prefs] = scaler.fit_transform(df_enc[prefs])

    # Clustering within sex + chronotype
    pieces = []
    for sex in df[sex_col].unique():
        for chrono in ["Morning", "Neutral", "Evening"]:
            sub = df_enc[(df_enc[sex_col] == sex) & (df_enc["ChronoTypeCategory"] == chrono)].copy()
            if sub.empty:
                continue
            k = 1 if len(sub) <= 3 else 2
            sub["ClusterID"] = KMeans(n_clusters=k, random_state=42).fit_predict(sub[prefs])
            sub["RoomGroup"] = sub[sex_col] + " | " + chrono + " | Cluster " + sub["ClusterID"].astype(str)
            pieces.append(sub)

    # Re-add conflicts as their own group
    df_conf = df[df["Conflict"]].copy()
    if not df_conf.empty:
        df_conf["ClusterID"] = -1
        df_conf["RoomGroup"] = df_conf[sex_col] + " | Conflict"
        pieces.append(df_conf)

    df_final = pd.concat(pieces, ignore_index=True)

    # Visualisations using full df for distributions
    st.subheader("Chronotype Distribution")
    chrono_counts = df["ChronoTypeCategory"].value_counts().reindex(["Morning","Neutral","Evening"], fill_value=0)
    st.bar_chart(chrono_counts)

    st.subheader("Noise Sensitivity Distribution")
    noise_categories = ["Absolute Silence", "Low Background Noise", "Doesn’t Matter"]
    noise_counts = df[noise_col].value_counts().reindex(noise_categories, fill_value=0)
    st.bar_chart(noise_counts)

    st.subheader("Lighting Preference Distribution")
    light_categories = ["Complete Darkness", "Dim Light", "Doesn’t Matter"]
    light_counts = df[light_col].value_counts().reindex(light_categories, fill_value=0)
    st.bar_chart(light_counts)

    st.subheader("Temperature Preference Distribution")
    temp_categories = ["Cool (20°C, 68°F)", "Moderate (21–24°C, 70–75°F)", "Warm (25°C, 77°F)"]
    temp_counts = df[temp_col].value_counts().reindex(temp_categories, fill_value=0)
    st.bar_chart(temp_counts)

    # Participant Grouping Summary
    st.subheader("Participant Grouping Summary")
    group_summary = (
        df_final.groupby("RoomGroup")[name_col]
        .apply(lambda names: "; ".join(names))
        .reset_index(name="Participants")
    )
    st.dataframe(group_summary[["Participants"]])

    # Automatic allocation toggle
    st.markdown("### Room Allocation")
    auto = st.checkbox("Enable automatic roommate allocation")
    if auto:
        room_size = st.selectbox("Select room size", [2, 3, 4], index=0)
        allocations = []
        for sex in df[sex_col].unique():
            for chrono in ["Morning", "Neutral", "Evening"]:
                grp_df = df_final[(df_final[sex_col] == sex) & (df_final["ChronoTypeCategory"] == chrono)]
                if grp_df.empty:
                    continue
                names = grp_df[name_col].tolist()
                warns = grp_df["Warnings"].tolist()
                rooms = [names[i:i+room_size] for i in range(0, len(names), room_size)]
                warn_rooms = [warns[i:i+room_size] for i in range(0, len(warns), room_size)]
                for room_chunk, warn_chunk in zip(rooms, warn_rooms):
                    allocations.append({
                        "Participants": "; ".join(room_chunk),
                        "Warnings": "; ".join([w for w in warn_chunk if w])
                    })
        df_alloc = pd.DataFrame(allocations)

        st.subheader("Room Allocations")
        st.dataframe(df_alloc)

        csv = df_alloc.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Room Allocations",
            data=csv,
            file_name="roompref_room_allocations.csv",
            mime="text/csv"
        )
