
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.cluster import KMeans

st.title("ROOMPREF Clustering (2 Clusters per Gender)")

uploaded_file = st.file_uploader("Upload your ROOMPREF CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    st.subheader("Raw Data Preview")
    st.write(df.head())

    name_col = "Full Name"
    gender_col = "Gender"
    chronotype_col = "One hears about 'morning' and 'evening' types of people. Which one of these types do you consider yourself to be?"

    def map_chronotype(x):
        if isinstance(x, str):
            x = x.lower()
            if "definitely a 'morning'" in x:
                return "Morning"
            elif "rather more a 'morning'" in x:
                return "Morning"
            elif "rather more an 'evening'" in x:
                return "Evening"
            elif "definitely an 'evening'" in x:
                return "Evening"
        return "Neutral"

    df["ChronoTypeCategory"] = df[chronotype_col].fillna("Neutral").apply(map_chronotype)

    preference_columns = [
        "Do you consider yourself a light or heavy sleeper?",
        "What level of noise do you prefer while sleeping? ",
        "What is your preferred lighting conditions for sleep?",
        "What is your preferred room temperature for sleeping?",
        "Do you use electronic devices in bed before sleep? ",
        "Do you get up during the night?",
        "Do you snore or have been told that you snore? ",
        "How flexible are you with your sleeping habits and environment? ",
    ]

    k = 2  # Fixed number of clusters per gender/chronotype group

    all_results = []
    grouped = df.groupby([gender_col, "ChronoTypeCategory"])

    for (gender, chrono), group in grouped:
        group = group.copy()
        subset = group[preference_columns].fillna("Unknown")

        for col in subset.columns:
            if subset[col].dtype == "object":
                le = LabelEncoder()
                subset[col] = le.fit_transform(subset[col].astype(str))

        X = StandardScaler().fit_transform(subset)
        num_clusters = min(k, len(group))

        if num_clusters > 1:
            kmeans = KMeans(n_clusters=num_clusters, random_state=42)
            group["Cluster"] = kmeans.fit_predict(X)
        else:
            group["Cluster"] = 0

        group["Group Label"] = f"{gender} - {chrono}" + " - Cluster " + group["Cluster"].astype(str)
        all_results.append(group)

    final_df = pd.concat(all_results)
    st.subheader("Grouped Output")
    st.write(final_df[[name_col, gender_col, "ChronoTypeCategory", "Group Label"]])

    st.subheader("📊 Visual Summary of Groupings")
    group_counts = final_df.groupby(["Gender", "ChronoTypeCategory", "Cluster"]).size().reset_index(name="Count")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=group_counts, x="ChronoTypeCategory", y="Count", hue="Gender", ax=ax)
    plt.title("Group Sizes by Gender and Chronotype")
    st.pyplot(fig)

    csv = final_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download Clustered CSV", csv, "roompref_gender_clusters_fixed2.csv", "text/csv")
