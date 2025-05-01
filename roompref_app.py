
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.cluster import KMeans

st.set_page_config(layout="wide")
st.title("ROOMPREF App (Google Form Column Names)")

uploaded_file = st.file_uploader("Upload your ROOMPREF CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    st.subheader("Raw Data Preview")
    st.write(df.head())

    # Drop timestamp if present
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

        # Conflict rule: don’t cluster snorers with people who prefer silence
        group["Snorer"] = group[snore_col].str.lower().str.contains("yes", na=False)
        group["Needs Silence"] = group[noise_col].str.lower().str.contains("absolute silence", na=False)

        if group["Snorer"].any() and group["Needs Silence"].any():
            conflict_free = group[~(group["Snorer"] | group["Needs Silence"])].copy()
            subset = subset.loc[conflict_free.index]
        else:
            conflict_free = group.copy()

        group_size = len(conflict_free)
        if group_size <= 2:
            num_clusters = 1
        elif group_size == 3:
            num_clusters = 1
        else:
            num_clusters = 2

        if group_size > 0:
            X = StandardScaler().fit_transform(subset)
            kmeans = KMeans(n_clusters=num_clusters, random_state=42)
            conflict_free["Cluster"] = kmeans.fit_predict(X)
            conflict_free["Group Label"] = f"{gender} - {chrono} - Cluster " + conflict_free["Cluster"].astype(str)
            all_results.append(conflict_free)

    if all_results:
        final_df = pd.concat(all_results)
        st.subheader("Grouped Output Table")
        st.write(final_df[[name_col, gender_col, "ChronoTypeCategory", "Group Label"]])

        st.subheader("📋 Room Assignments by Group")
        group_table = final_df.groupby([gender_col, "ChronoTypeCategory", "Cluster"])[name_col].apply(list).reset_index()
        st.dataframe(group_table.rename(columns={name_col: "Participants"}))

        st.subheader("📊 Group Sizes by Gender and Chronotype")
        group_counts = final_df.groupby([gender_col, "ChronoTypeCategory", "Cluster"]).size().reset_index(name="Count")
        fig1, ax = plt.subplots(figsize=(10, 5))
        sns.barplot(data=group_counts, x="ChronoTypeCategory", y="Count", hue=gender_col, ax=ax)
        ax.set_title("Participants per Group")
        st.pyplot(fig1)

        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download Clustered CSV", csv, "roompref_clusters_final.csv", "text/csv")
    else:
        st.warning("No participants matched criteria for clustering.")
