
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.cluster import KMeans

st.set_page_config(layout="wide")
st.title("ROOMPREF App (Final Logic – May 1 Update)")

uploaded_file = st.file_uploader("Upload your ROOMPREF CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    st.subheader("Raw Data Preview")
    st.write(df.head())

    name_col = "Full Name"
    gender_col = "Preferred Roommate Sex"
    chrono_col = "Chronotype (self-assessed)"
    noise_col = "What level of noise can you tolerate while sleeping?"  # Q3
    light_col = "Preferred lighting conditions for sleeping:"  # Q4
    temp_col = "Preferred room temperature for sleeping:"  # Q5
    snore_col = "Do you snore or have been told that you snore?"  # Q6

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
    k = 2
    all_results = []
    grouped = df.groupby([gender_col, "ChronoTypeCategory"])

    for (gender, chrono), group in grouped:
        group = group.copy()
        subset = group[preference_columns].fillna("Unknown")

        # Encode categorical responses
        for col in subset.columns:
            le = LabelEncoder()
            subset[col] = le.fit_transform(subset[col].astype(str))

        # Identify risky pairing: light sleeper requiring silence + snorer
        
        # Label who snores and who prefers absolute silence
        group["Snorer"] = group[snore_col].str.lower().str.contains("yes", na=False)
        group["Needs Silence"] = group[noise_col].str.lower().str.contains("absolute silence", na=False)

        # Remove both snorers and silence-needing individuals if both exist in the same group
        if group["Snorer"].any() and group["Needs Silence"].any():
            conflict_free = group[~(group["Snorer"] | group["Needs Silence"])].copy()
            subset = subset.loc[conflict_free.index]
        else:
            conflict_free = group.copy()
    

        # Proceed with clustering on lighting and temperature
        X = StandardScaler().fit_transform(subset)
        
        group_size = len(conflict_free)
        if group_size <= 2:
            num_clusters = 1
        elif group_size == 3:
            num_clusters = 1
        else:
            num_clusters = 2
    

        if num_clusters > 1:
            kmeans = KMeans(n_clusters=num_clusters, random_state=42)
            conflict_free["Cluster"] = kmeans.fit_predict(X)
        else:
            conflict_free["Cluster"] = 0

        conflict_free["Group Label"] = f"{gender} - {chrono} - Cluster " + conflict_free["Cluster"].astype(str)
        all_results.append(conflict_free)

    final_df = pd.concat(all_results)
    st.subheader("Grouped Output Table")
    st.write(final_df[[name_col, gender_col, "ChronoTypeCategory", "Group Label"]])

    st.subheader("📋 Room Assignments by Group")
    group_table = final_df.groupby(["Preferred Roommate Sex", "ChronoTypeCategory", "Cluster"])[name_col].apply(list).reset_index()
    st.dataframe(group_table.rename(columns={name_col: "Participants"}))

    st.subheader("📊 Group Sizes by Gender and Chronotype")
    group_counts = final_df.groupby(["Preferred Roommate Sex", "ChronoTypeCategory", "Cluster"]).size().reset_index(name="Count")
    fig1, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=group_counts, x="ChronoTypeCategory", y="Count", hue="Preferred Roommate Sex", ax=ax)
    ax.set_title("Participants per Group")
    st.pyplot(fig1)

    csv = final_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download Clustered CSV", csv, "roompref_clusters_may1_final.csv", "text/csv")
