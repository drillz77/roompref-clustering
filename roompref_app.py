
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import euclidean_distances
import numpy as np

st.set_page_config(layout="wide")
st.title("ROOMPREF App – Roommate Allocation + Dashboard")

uploaded_file = st.file_uploader("Upload your ROOMPREF CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    if "Timestamp" in df.columns:
        df = df.drop(columns=["Timestamp"])

    name_col = "Full Name"
    gender_col = "Sex (if non-binary, select preferred roommate sex)"
    noise_col = "What level of noise can you tolerate while sleeping?"
    light_col = "Preferred lighting conditions for sleeping?"
    temp_col = "Preferred room temperature for sleeping?"
    snore_col = "Do you snore or have been told that you snore?"
    chrono_col = "One hears about “morning” and “evening” types of people. Which one of these types do you consider yourself to be?"

    def map_chronotype(x):
        if isinstance(x, str):
            x = x.lower()
            if "definitely a morning" in x:
                return "Morning"
            elif "definitely an evening" in x:
                return "Evening"
            elif "rather more" in x:
                return "Neutral"
        return "Neutral"

    df["ChronoTypeCategory"] = df[chrono_col].fillna("Neutral").apply(map_chronotype)

    preference_columns = [noise_col, light_col, temp_col]
    all_results = []
    grouped = df.groupby([gender_col, "ChronoTypeCategory"])

    for (gender, chrono), group in grouped:
        group = group.copy()
        subset = group[preference_columns].fillna("Unknown")

        for col in subset.columns:
            le = LabelEncoder()
            subset[col] = le.fit_transform(subset[col].astype(str))

        group["Snorer"] = group[snore_col].str.lower().str.contains("yes", na=False)
        group["Needs Silence"] = group[noise_col].str.lower().str.contains("absolute silence", na=False)

        if group["Snorer"].any() and group["Needs Silence"].any():
            conflict_free = group[~(group["Snorer"] | group["Needs Silence"])].copy()
            subset = subset.loc[conflict_free.index]
        else:
            conflict_free = group.copy()

        group_size = len(conflict_free)
        num_clusters = 1 if group_size <= 3 else 2

        if group_size > 0:
            X = StandardScaler().fit_transform(subset)
            kmeans = KMeans(n_clusters=num_clusters, random_state=42)
            conflict_free["Cluster"] = kmeans.fit_predict(X)
            conflict_free["Group Label"] = f"{gender} - {chrono} - Cluster " + conflict_free["Cluster"].astype(str)
            all_results.append(conflict_free)

    if all_results:
        final_df = pd.concat(all_results)

        st.subheader("Room Assignments by Group")
        group_table = final_df.groupby([gender_col, "ChronoTypeCategory", "Cluster"])[name_col].apply(list).reset_index().rename(columns={name_col: "Participants"})
        st.dataframe(group_table)

        st.subheader("🚪 Automatically Allocate Roommates")
        auto_alloc = st.toggle("Enable automatic roommate allocation")
        if auto_alloc:
            room_size = st.selectbox("Select room size", [2, 3, 4])
            st.markdown(f"📌 Allocating in groups of **{room_size}**")

            allocations = []
            singleton_names = []
            singleton_features = []
            group_features = []

            for idx, group in group_table.iterrows():
                names = group["Participants"]
                rows = final_df[final_df[name_col].isin(names)]
                features = rows[[noise_col, light_col, temp_col]].fillna("Unknown").copy()
                for col in features.columns:
                    le = LabelEncoder()
                    features[col] = le.fit_transform(features[col].astype(str))
                X = StandardScaler().fit_transform(features)

                if len(names) == 1:
                    singleton_names.append(names[0])
                    singleton_features.append(X[0])
                else:
                    allocations.append({"Room Group": f"{group[gender_col]} - {group['ChronoTypeCategory']}", "Names": names})
                    group_features.append(X.mean(axis=0))

            for i, singleton in enumerate(singleton_names):
                placed = False
                if group_features:
                    distances = euclidean_distances([singleton_features[i]], group_features)
                    sorted_indices = np.argsort(distances[0])
                    for idx in sorted_indices:
                        if len(allocations[idx]["Names"]) < room_size:
                            allocations[idx]["Names"].append(singleton)
                            placed = True
                            break
                if not placed:
                    allocations.append({"Room Group": f"Extra - R{len(allocations)+1}", "Names": [singleton]})

            # Slice allocations into exact room sizes
            final_allocations = []
            remainders = []
            for group in allocations:
                names = group["Names"]
                for i in range(0, len(names), room_size):
                    chunk = names[i:i+room_size]
                    if len(chunk) == room_size:
                        final_allocations.append({"Room Group": f"{group['Room Group']} - Sub{i//room_size+1}", "Participants": chunk})
                    else:
                        remainders.append((group['Room Group'], chunk))

            for label, remaining in remainders:
                for person in remaining:
                    placed = False
                    for alloc in final_allocations:
                        if len(alloc["Participants"]) < room_size:
                            alloc["Participants"].append(person)
                            placed = True
                            break
                    if not placed:
                        final_allocations.append({"Room Group": f"{label} - Extra", "Participants": [person]})

            # Add warnings
            warning_allocations = []
            for room in final_allocations:
                room_participants = room["Participants"]
                subset = final_df[final_df[name_col].isin(room_participants)]
                has_snorer = subset[snore_col].str.lower().str.contains("yes", na=False).any()
                needs_silence = subset[noise_col].str.lower().str.contains("absolute silence", na=False).any()
                chronotypes = subset["ChronoTypeCategory"].unique().tolist()
                warning = ""
                if has_snorer and needs_silence:
                    warning += "⚠️ Snorer + silence-sensitive\n"
                if "Morning" in chronotypes and "Evening" in chronotypes:
                    warning += "⚠️ Morning + Evening mix\n"
                if len(room_participants) < room_size:
                    warning += "⚠️ Underfilled room\n"

                warning_allocations.append({
                    "Room Group": room["Room Group"],
                    "Participants": ", ".join(room_participants),
                    "Warnings": warning.strip()
                })

            
            filtered_allocations = []
            for room in final_allocations:
                room_participants = room["Participants"]
                subset = final_df[final_df[name_col].isin(room_participants)]
                chronotypes = subset["ChronoTypeCategory"].unique().tolist()
                if "Morning" in chronotypes and "Evening" in chronotypes:
                    continue
                filtered_allocations.append(room)

            warning_allocations = []
            for room in filtered_allocations:
                room_participants = room["Participants"]
                subset = final_df[final_df[name_col].isin(room_participants)]
                has_snorer = subset[snore_col].str.lower().str.contains("yes", na=False).any()
                needs_silence = subset[noise_col].str.lower().str.contains("absolute silence", na=False).any()
                chronotypes = subset["ChronoTypeCategory"].unique().tolist()
                warning = ""
                if has_snorer and needs_silence:
                    warning += "⚠️ Snorer + silence-sensitive\n"
                if "Morning" in chronotypes and "Evening" in chronotypes:
                    warning += "⚠️ Morning + Evening mix\n"
                if len(room_participants) < room_size:
                    warning += "⚠️ Underfilled room\n"

                warning_allocations.append({
                    "Room Group": room["Room Group"],
                    "Participants": ", ".join(room_participants),
                    "Warnings": warning.strip()
                })

            df_alloc = pd.DataFrame(warning_allocations)
            st.dataframe(df_alloc)
            total_warnings = df_alloc["Warnings"].apply(lambda x: x.count("⚠️")).sum()
            st.markdown(f"**⚠️ Total Warnings Across All Rooms: {total_warnings}**")
            csv = df_alloc.to_csv(index=False).encode("utf-8")
            st.download_button("Download Room Allocations", csv, "roompref_room_allocations.csv", "text/csv", key="download_btn_unique_1")


            # Dashboard
            st.subheader("📊 Room Allocation Summary Dashboard")
            st.markdown("**Room Size Distribution**")

            if "ChronoTypeCategory" in final_df.columns:
                st.markdown("**Chronotype Distribution**")
                chrono_counts = final_df["ChronoTypeCategory"].value_counts()
                st.bar_chart(chrono_counts)

            total_warnings = df_alloc["Warnings"].apply(lambda x: x.count("⚠️")).sum()

            # Export
            csv = df_alloc.to_csv(index=False).encode("utf-8")
