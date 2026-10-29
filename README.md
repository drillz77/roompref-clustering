# ROOMPREF – Roommate Sleep Preference Questionnaire and roommate-matching tool

ROOMPREF is a free tool that helps coordinators allocate shared rooms so that people with compatible sleep preferences room together. It was designed for athletes at training camps and major competitions, and also suits boarding schools, university residences, military units and other group-living settings.

It has two parts:

1. **The ROOMPREF questionnaire**, a short Google Form that takes less than two minutes to complete.
2. **The ROOMPREF app**, a web app that reads the form responses, groups compatible people and, if requested, allocates rooms automatically.

- **Live app and Google Form template:** https://www.siestaresearch.com/roompref
- **Developed by:** the SIESTA Research Group, La Trobe University, Melbourne, Australia

> ROOMPREF supports, but does not replace, coordinator judgement. Always review the suggested allocations alongside what you know about the people involved, such as personalities, team dynamics and accessibility needs.

---

## Contents

- [The questionnaire](#the-questionnaire)
- [Quick start for coordinators](#quick-start-for-coordinators)
- [How the matching works](#how-the-matching-works)
- [Understanding the output](#understanding-the-output)
- [CSV file requirements](#csv-file-requirements)
- [Running the app on your own computer](#running-the-app-on-your-own-computer)
- [Files in this repository](#files-in-this-repository)
- [Privacy](#privacy)
- [Limitations](#limitations)
- [Version history](#version-history)
- [How to cite](#how-to-cite)
- [Contact](#contact)

---

## The questionnaire

| Item | Response options |
|---|---|
| Full name | Free text |
| Sex (if non-binary, select preferred roommate sex) | Female; Male |
| What level of noise can you tolerate while sleeping? | Absolute Silence; Low Background Noise; Doesn’t Matter |
| Preferred lighting conditions for sleeping? | Complete Darkness; Dim Light; Doesn’t Matter |
| Preferred room temperature for sleeping? | Cool (20°C, 68°F); Moderate (21–24°C, 70–75°F); Warm (25°C, 77°F) |
| Do you snore or have been told that you snore? | Yes; No |
| One hears about “morning” and “evening” types of people. Which one of these types do you consider yourself to be? | Definitely a ‘morning’ type; Rather more a ‘morning’ than ‘evening’ type; Rather more an ‘evening’ than ‘morning’ type; Definitely an ‘evening’ type |
| Any other information or preferences you would like to share about your sleeping habits or needs? | Free text (optional) |

The chronotype item is the self-assessment item from the Morningness–Eveningness Questionnaire (Horne & Östberg, 1976). The rationale for each item is described in the accompanying paper (see [How to cite](#how-to-cite)).

---

## Quick start for coordinators

1. **Copy the Google Form.** Go to https://www.siestaresearch.com/roompref and make a copy of the ROOMPREF Google Form template. Keep the questions and response options exactly as they are, because the app relies on them.
2. **Send the form.** Email or message the form link to everyone who needs a room.
3. **Download the responses.** Once responses are in, open the form’s **Responses** tab and choose **Link to Sheets**. In the Google Sheet, go to **File → Download → Comma-separated values (.csv)**.
4. **Upload to the app.** Open the ROOMPREF app and upload the CSV file.
5. **Review the summaries.** The app shows the distribution of chronotypes and of noise, lighting and temperature preferences, followed by a **Participant Grouping Summary**: groups of people who would be suitable to room together.
6. **Choose how to allocate rooms.**
   - **Manually:** use the groups to allocate rooms yourself, drawing on your own knowledge of the people involved.
   - **Automatically:** switch on **Enable automatic roommate allocation** and select the room size (2, 3 or 4). The app suggests specific room allocations and flags any issues.
7. **Download the allocations.** Click **Download Room Allocations** to save the suggested rooms as a CSV file, then make any final adjustments.

**To try it first**, upload `ROOMPREF_example_120.csv` from this repository. It contains 120 fictional respondents.

---

## How the matching works

1. **Data cleaning.** Responses are read and standardised. The app tolerates small formatting differences such as curly or straight quotes and minor encoding problems. Any response that can’t be interpreted is excluded, and the app lists those people by name.
2. **Grouping by sex and chronotype.** Participants are grouped by sex (or preferred roommate sex). Chronotype responses are then sorted into three categories:

   | Response | Category |
   |---|---|
   | Definitely a ‘morning’ type | Morning |
   | Rather more a ‘morning’ than ‘evening’ type | Neutral |
   | Rather more an ‘evening’ than ‘morning’ type | Neutral |
   | Definitely an ‘evening’ type | Evening |

   Because everything that follows happens within these sex × chronotype subgroups, the automatic allocation never places Morning and Evening types in the same room.
3. **People who both snore and need silence.** Anyone who reports snoring *and* needing absolute silence is set aside (within their own sex × chronotype subgroup) in a separate, clearly labelled group for the coordinator to review. These people are hard to place in any shared room, because they may disturb a silence-sensitive roommate and be disturbed by a snoring one.
4. **Clustering on sleep-environment preferences.** Noise, lighting and temperature preferences are converted to ordered numbers (e.g., Absolute Silence = 0, Low Background Noise = 1, Doesn’t Matter = 2). They are then standardised so that each preference counts equally. Within each subgroup, K-Means clustering splits people into groups with similar preferences: one cluster for subgroups of three or fewer people, and two clusters for subgroups of four or more. This keeps groups at a practical size for room allocation.
5. **Nearest-neighbour room allocation** (when automatic allocation is switched on). Within each cluster, the app works out how different every pair of people is in their noise, lighting and temperature preferences. Any pairing of a snorer with someone who needs absolute silence receives a large penalty. Each room is started with the most similar available pair; for rooms of three or four, further occupants are added one at a time, choosing whoever is most similar to the people already in the room. Anyone left over goes into an underfilled room.
6. **Snore–silence swapping.** If a room still contains a snorer and a different person who needs absolute silence, the app tests exchanging occupants with other rooms in the same cluster. It applies the exchange that removes the most conflicts, preferring exchanges that keep roommates’ preferences similar. Rooms never exceed the chosen size.

---

## Understanding the output

| Output | What it means |
|---|---|
| Distribution charts | How many people fall into each chronotype category and each noise, lighting and temperature option |
| Participant Grouping Summary | Groups of people who would be suitable to room together (same sex and chronotype category, similar environmental preferences) |
| Room Allocations table | The suggested room for each person (automatic allocation only) |
| ⚠️ Snore–Silence conflict | The room contains someone who snores and someone who needs absolute silence. This includes a person who reported both, even if they are alone in the room. Review these rooms manually, for example by pairing snorers together, using a single room or providing earplugs. |
| Underfilled room | The room has fewer people than the selected room size, usually because a group had an odd number of people or contained only one person (e.g., the only Evening type of one sex). Combine underfilled rooms manually where appropriate. For an unmatched Morning or Evening type, a Neutral type of the same sex with similar preferences is usually the best match. |
| Download Room Allocations | Saves the allocations table as a CSV file |

Use the optional comments column (e.g., preferred roommate, accessibility needs, competition schedule) when finalising rooms.

---

## CSV file requirements

The app finds columns by keywords in the column headings, so the order of the columns doesn’t matter. Each required heading must contain:

| Information | Heading must contain |
|---|---|
| Name | “full name” (or the heading is exactly “name”) |
| Sex | “sex” |
| Noise | “noise” |
| Lighting | “lighting” |
| Temperature | “temperature” |
| Snoring | “snore” |
| Chronotype | both “morning” and “evening” |

Response options must follow the wording of the template, although capitalisation, quotes and punctuation don’t need to match exactly. Extra columns, such as Timestamp and comments, are ignored.

---

## Running the app on your own computer

You need Python 3.9 or later.

```bash
git clone https://github.com/drillz77/roompref-clustering.git
cd roompref-clustering
pip install -r requirements.txt
streamlit run roompref_app.py
```

The app opens in your web browser at http://localhost:8501.

You can also click **Code → Codespaces → Create codespace on main** on this page. The included dev-container configuration installs the requirements and starts the app automatically.

### Reproducing the concordance analysis

`roompref_concordance.py` re-runs the allocation on a ROOMPREF CSV file. It reports how often roommates’ responses match, comparing the earlier (pilot) allocation, the current nearest-neighbour allocation and random allocation within sex (1,000 simulations).

```bash
python roompref_concordance.py ROOMPREF_example_120.csv 2 1000
#                              <csv file>               <room size> <number of random simulations>
```

---

## Files in this repository

| File | Purpose |
|---|---|
| `roompref_app.py` | The Streamlit web app (user interface) |
| `roompref_core.py` | Matching logic: data cleaning, grouping, clustering, nearest-neighbour allocation and swapping |
| `roompref_concordance.py` | Analysis script comparing allocation methods (used for the accompanying paper) |
| `requirements.txt` | Python packages the app needs |
| `ROOMPREF_example_120.csv` | Example data with 120 fictional respondents |
| `.devcontainer/` | Configuration for running the app in GitHub Codespaces |

---

## Privacy

The app processes the uploaded file in memory for the current session only. It doesn’t save uploaded files or results. Questionnaire responses include names and personal preferences, so store downloaded CSV files securely and delete them when they are no longer needed. **Don’t upload real response files to this repository.**

---

## Limitations

- ROOMPREF targets a few sleep-related characteristics most likely to cause conflict between roommates: chronotype, noise, lighting, temperature and snoring. It doesn’t assess other aspects of sleep health such as sleep duration or regularity, or pre-bedtime behaviours.
- Chronotype is a self-reported preference, which doesn’t always match actual sleep and wake times.
- All responses are self-reported. Snoring in particular may be under-reported.
- Differences in noise, lighting and temperature preferences are reduced through clustering and allocation but aren’t individually flagged.
- Underfilled rooms aren’t automatically combined across groups.
- The questionnaire hasn’t yet been formally validated. Whether ROOMPREF-guided allocation improves sleep compared with usual allocation has not yet been tested.

---

## Version history

| Version | Changes |
|---|---|
| 2.1 (October 2026) | Redesigned interface (sidebar, summary tiles, charts by sex, group cards, room table with match markers and notes, Excel download, example data); people who both snore and need silence are now kept within their sex × chronotype subgroup. Matching results are otherwise unchanged. |
| 2.0 (October 2026) | Nearest-neighbour room allocation within clusters; improved snore–silence swapping; ordered encoding of preferences; more robust CSV reading; underfilled rooms labelled in the output; logic moved to `roompref_core.py`. |
| 1.0 (2024–2025) | Original version, used in the pilot with Paralympic athletes before the Paris 2024 Paralympic Games. Rooms within each cluster were filled in the order in which responses were received. |

---

## How to cite

Driller, M. W., & Suppiah, H. (under review). A roommate at the Olympics? Proposing the Roommate Sleep Preference Questionnaire (ROOMPREF). *Journal of Sport and Exercise Science*.

---

## Contact

Professor Matthew Driller, SIESTA Research Group, School of Allied Health, Human Services and Sport, La Trobe University, Melbourne, Australia – m.driller@latrobe.edu.au
