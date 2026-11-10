
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import zipfile
import io
from collections import Counter
from datetime import datetime

# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="WhatsApp Analytics Pro",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# PURE RED THEME
# =========================================================

st.markdown("""
<style>

/* Main background */
.stApp {
    background-color: #FFFFFF;
    color: #222222;
}

/* Main content */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #FFF5F5;
    border-right: 2px solid #FF0000;
}

/* Main headings */
h1, h2, h3 {
    color: #CC0000 !important;
    font-weight: 800 !important;
}

/* Normal text */
p, label, span {
    color: #333333;
}

/* Buttons */
.stButton > button {
    background: #FF0000 !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: bold !important;
    padding: 10px 22px !important;
}

.stButton > button:hover {
    background: #CC0000 !important;
    color: white !important;
}

/* Download buttons */
.stDownloadButton > button {
    background: #FF0000 !important;
    color: white !important;
    border: none !important;
    border-radius: 9px !important;
}

/* Input fields */
.stTextInput input,
.stDateInput input,
.stSelectbox div[data-baseweb="select"] {
    background: #FFFFFF !important;
    border: 1px solid #FF9999 !important;
    border-radius: 8px !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: #FFF5F5;
    border: 2px dashed #FF0000;
    border-radius: 12px;
    padding: 15px;
}

/* Metric cards */
[data-testid="stMetric"] {
    background: #FFF3F3;
    border: 1px solid #FFCCCC;
    padding: 18px;
    border-radius: 12px;
}

[data-testid="stMetricLabel"] {
    color: #990000 !important;
    font-weight: bold !important;
}

[data-testid="stMetricValue"] {
    color: #FF0000 !important;
    font-weight: 900 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab"] {
    color: #990000;
    font-weight: bold;
}

.stTabs [aria-selected="true"] {
    color: #FF0000 !important;
    border-bottom-color: #FF0000 !important;
}

/* Dataframes */
[data-testid="stDataFrame"] {
    border: 1px solid #FFCCCC;
    border-radius: 10px;
}

/* Header */
.hero {
    background: linear-gradient(135deg, #FF0000, #B30000);
    padding: 35px 25px;
    border-radius: 18px;
    text-align: center;
    margin-bottom: 25px;
    box-shadow: 0 5px 18px rgba(255, 0, 0, 0.18);
}

.hero h1 {
    color: white !important;
    font-size: 38px !important;
    margin: 12px 0;
}

.hero p {
    color: white !important;
    font-size: 16px;
    margin-bottom: 0;
}

.hero-label {
    color: white;
    letter-spacing: 3px;
    font-size: 12px;
    font-weight: bold;
}

/* Section headings */
.section-title {
    color: #CC0000;
    font-size: 22px;
    font-weight: 800;
    border-left: 5px solid #FF0000;
    padding-left: 12px;
    margin-top: 25px;
    margin-bottom: 15px;
}

/* Info cards */
.info-card {
    background: #FFF5F5;
    border: 1px solid #FFCCCC;
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 12px;
}

/* Footer */
.footer {
    text-align: center;
    color: #990000;
    padding: 25px;
    border-top: 1px solid #FFCCCC;
    margin-top: 40px;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# HERO HEADER
# =========================================================

st.markdown("""
<div class="hero">
    <div class="hero-label">
        CONVERSATION INTELLIGENCE · INTERACTIVE DASHBOARD
    </div>

    <h1>💬 WhatsApp Analytics Pro</h1>

    <p>
        Discover the people, patterns and moments
        behind your conversations.
    </p>
</div>
""", unsafe_allow_html=True)


# =========================================================
# CONSTANTS
# =========================================================

MEDIA_RE = re.compile(
    r"<media omitted>|<image omitted>|<video omitted>|"
    r"<audio omitted>|<document omitted>|<sticker omitted>|"
    r"<gif omitted>|<attached:[^>]+>|"
    r"\bfile attached\b",
    re.IGNORECASE
)

LINK_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)

STOP_WORDS = {
    "the", "and", "you", "are", "for", "that", "this",
    "with", "have", "was", "but", "not", "your", "what",
    "when", "where", "how", "why", "from", "they", "them",
    "then", "there", "their", "will", "would", "could",
    "should", "can", "all", "just", "like", "its", "it's",
    "our", "out", "get", "got", "has", "had", "his", "her",
    "she", "him", "who", "one", "yes", "yeah", "okay",
    "ok", "bro", "lol", "hmm", "oh", "in", "on", "to",
    "of", "is", "it", "a", "an", "i", "me", "my", "we",
    "be", "do", "so", "if", "or", "at", "as", "by"
}


# =========================================================
# READ TXT OR ZIP FILE
# =========================================================

def read_chat(uploaded_file):

    file_name = uploaded_file.name.lower()

    if file_name.endswith(".zip"):

        with zipfile.ZipFile(uploaded_file) as archive:

            txt_files = [
                name for name in archive.namelist()
                if name.lower().endswith(".txt")
                and not name.startswith("__MACOSX/")
            ]

            if not txt_files:
                raise ValueError("No TXT file found inside ZIP.")

            # Prefer the first TXT file
            raw_bytes = archive.read(txt_files[0])

    else:
        raw_bytes = uploaded_file.getvalue()

    encodings = [
        "utf-8-sig",
        "utf-8",
        "utf-16",
        "utf-16-le",
        "cp1252",
        "latin-1"
    ]

    for encoding in encodings:
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError("Unable to decode this chat file.")


# =========================================================
# WHATSAPP MESSAGE PARSING
# =========================================================

TIMESTAMP_PATTERNS = [

    # Android: [10/4/26, 6:20:58 PM] Name: message
    re.compile(
        r"^\[(\d{1,2}/\d{1,2}/\d{2,4},\s*"
        r"\d{1,2}:\d{2}(?::\d{2})?\s*[APMapm]{0,2})\]\s?(.*)$"
    ),

    # iPhone: 10/4/26, 6:20 PM - Name: message
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4},\s*"
        r"\d{1,2}:\d{2}(?::\d{2})?\s*[APMapm]{0,2})\s-\s(.*)$"
    ),

    # ISO-style: [2026-10-04, 18:20:58] Name: message
    re.compile(
        r"^\[(\d{4}-\d{1,2}-\d{1,2},?\s*"
        r"\d{1,2}:\d{2}(?::\d{2})?)\]\s?(.*)$"
    ),

    # ISO-style without brackets
    re.compile(
        r"^(\d{4}-\d{1,2}-\d{1,2},?\s*"
        r"\d{1,2}:\d{2}(?::\d{2})?)\s-\s(.*)$"
    )
]


def split_sender(body):

    if ": " in body:

        sender, message = body.split(": ", 1)

        sender = sender.strip()

        # Avoid treating a long notification as a sender
        if sender and len(sender) <= 100:
            return sender, message.strip()

    return "Group Notification", body.strip()


def parse_chat(raw_text, dayfirst=False):

    rows = []
    current_message = None

    for line in raw_text.splitlines():

        matched = False

        for pattern in TIMESTAMP_PATTERNS:

            match = pattern.match(line)

            if match:

                matched = True

                if current_message:
                    rows.append(current_message)

                timestamp_text = match.group(1).strip()
                body = match.group(2).strip()

                user, message = split_sender(body)

                current_message = {
                    "timestamp_text": timestamp_text,
                    "user": user,
                    "message": message
                }

                break

        # Multiline messages
        if not matched and current_message:

            current_message["message"] += "\n" + line

    if current_message:
        rows.append(current_message)

    if not rows:
        raise ValueError(
            "No WhatsApp messages detected. "
            "Please upload a standard WhatsApp TXT export."
        )

    df = pd.DataFrame(rows)

    # Convert timestamp
    df["date_time"] = pd.to_datetime(
        df["timestamp_text"],
        dayfirst=dayfirst,
        errors="coerce",
        format="mixed"
    )

    df = df.dropna(subset=["date_time"]).copy()

    if df.empty:
        raise ValueError("Could not understand the date format.")

    # Date and time columns
    df["date"] = df["date_time"].dt.date
    df["year"] = df["date_time"].dt.year
    df["month"] = df["date_time"].dt.month
    df["month_name"] = df["date_time"].dt.strftime("%B")
    df["month_period"] = df["date_time"].dt.to_period("M").astype(str)
    df["day"] = df["date_time"].dt.day
    df["hour"] = df["date_time"].dt.hour
    df["minute"] = df["date_time"].dt.minute
    df["weekday"] = df["date_time"].dt.day_name()
    df["weekday_number"] = df["date_time"].dt.dayofweek

    # Message analysis
    df["message"] = df["message"].fillna("").astype(str)

    df["word_count"] = df["message"].apply(
        lambda x: len(WORD_RE.findall(x))
    )

    df["media_count"] = df["message"].apply(
        lambda x: len(MEDIA_RE.findall(x))
    )

    df["link_count"] = df["message"].apply(
        lambda x: len(LINK_RE.findall(x))
    )

    df["message_type"] = df.apply(
        lambda row: (
            "Media" if row["media_count"] > 0
            else "Text"
        ),
        axis=1
    )

    return df


# =========================================================
# WORD ANALYSIS
# =========================================================

def get_common_words(messages):

    all_words = []

    for message in messages:

        words = WORD_RE.findall(str(message).lower())

        for word in words:

            if (
                len(word) > 2
                and word not in STOP_WORDS
                and not word.isdigit()
            ):
                all_words.append(word)

    return Counter(all_words).most_common(15)


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.markdown(
    "<h2 style='color:#FF0000;'>💬 WhatsApp Pro</h2>",
    unsafe_allow_html=True
)

st.sidebar.markdown("---")

st.sidebar.markdown("### 📁 Upload Your Chat")

uploaded_file = st.sidebar.file_uploader(
    "Upload WhatsApp TXT or ZIP",
    type=["txt", "zip"]
)

dayfirst = st.sidebar.checkbox(
    "My date format is DD/MM/YYYY",
    value=False
)

if "chat_df" not in st.session_state:
    st.session_state.chat_df = None

if uploaded_file:

    if st.sidebar.button(
        "🚀 ANALYZE CHAT",
        use_container_width=True
    ):

        try:

            with st.spinner("Analyzing your WhatsApp conversation..."):

                raw_text = read_chat(uploaded_file)

                parsed_df = parse_chat(
                    raw_text,
                    dayfirst=dayfirst
                )

                st.session_state.chat_df = parsed_df

            st.sidebar.success("Chat analyzed successfully!")

        except Exception as error:

            st.sidebar.error(str(error))


# =========================================================
# CHECK DATA
# =========================================================

if st.session_state.chat_df is None:

    st.info(
        "👈 Upload your WhatsApp exported TXT or ZIP file "
        "from the sidebar and click ANALYZE CHAT."
    )

    st.markdown("### ✨ What you can explore")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="info-card">
            <h3>📊 Statistics</h3>
            Messages, words, media, links and participants.
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="info-card">
            <h3>📈 Activity</h3>
            Monthly, daily and hourly conversation patterns.
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="info-card">
            <h3>👥 People</h3>
            Most active members and individual analysis.
        </div>
        """, unsafe_allow_html=True)

    st.stop()


# =========================================================
# MAIN DATA
# =========================================================

df = st.session_state.chat_df.copy()

# =========================================================
# FILTERS
# =========================================================

st.markdown('<div class="section-title">🎯 Dashboard Filters</div>',
            unsafe_allow_html=True)

filter_col1, filter_col2 = st.columns(2)

users = sorted(df["user"].unique().tolist())

with filter_col1:

    selected_user = st.selectbox(
        "Select conversation",
        ["Overall Chat"] + users
    )

with filter_col2:

    date_range = st.date_input(
        "Select date range",
        value=(
            df["date"].min(),
            df["date"].max()
        ),
        min_value=df["date"].min(),
        max_value=df["date"].max()
    )


# Apply participant filter
if selected_user == "Overall Chat":
    filtered_df = df.copy()
else:
    filtered_df = df[df["user"] == selected_user].copy()


# Apply date filter
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:

    start_date, end_date = date_range

    filtered_df = filtered_df[
        (filtered_df["date"] >= start_date)
        & (filtered_df["date"] <= end_date)
    ]


if filtered_df.empty:

    st.warning("No messages found for the selected filters.")
    st.stop()


# =========================================================
# TOP STATISTICS
# =========================================================

st.markdown(
    '<div class="section-title">📊 Top Statistics</div>',
    unsafe_allow_html=True
)

total_messages = len(filtered_df)

total_words = int(filtered_df["word_count"].sum())

total_media = int(filtered_df["media_count"].sum())

total_links = int(filtered_df["link_count"].sum())

total_participants = filtered_df["user"].nunique()

average_words = (
    round(total_words / total_messages, 2)
    if total_messages else 0
)

m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("💬 Messages", f"{total_messages:,}")
m2.metric("📝 Words", f"{total_words:,}")
m3.metric("📷 Media", f"{total_media:,}")
m4.metric("🔗 Links", f"{total_links:,}")
m5.metric("👥 Participants", f"{total_participants:,}")

st.caption(f"Average words per message: {average_words}")


# =========================================================
# NAVIGATION
# =========================================================

st.markdown("---")

page = st.radio(
    "Navigate Dashboard",
    [
        "Overview",
        "Timeline",
        "Activity Map",
        "Participants",
        "Words & Emojis",
        "Message Explorer"
    ],
    horizontal=True,
    label_visibility="collapsed"
)

st.markdown("---")


# =========================================================
# OVERVIEW PAGE
# =========================================================

if page == "Overview":

    st.markdown(
        '<div class="section-title">📈 Conversation Overview</div>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    # Message type
    with col1:

        type_counts = filtered_df["message_type"].value_counts()

        fig = px.pie(
            names=type_counts.index,
            values=type_counts.values,
            hole=0.55,
            title="Message Type Distribution",
            color_discrete_sequence=["#FF0000", "#FF9999"]
        )

        fig.update_layout(
            template="plotly_white",
            legend_title="Message Type"
        )

        st.plotly_chart(fig, use_container_width=True)

    # Hourly activity
    with col2:

        hourly = (
            filtered_df.groupby("hour")
            .size()
            .reset_index(name="messages")
        )

        fig = px.bar(
            hourly,
            x="hour",
            y="messages",
            title="Messages by Hour",
            labels={
                "hour": "Hour of Day",
                "messages": "Messages"
            },
            color="messages",
            color_continuous_scale=["#FFCCCC", "#FF0000"]
        )

        fig.update_layout(template="plotly_white")

        st.plotly_chart(fig, use_container_width=True)

    # Busy day
    st.markdown(
        '<div class="section-title">🔥 Conversation Highlights</div>',
        unsafe_allow_html=True
    )

    weekday_counts = (
        filtered_df["weekday"]
        .value_counts()
        .reindex([
            "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday", "Sunday"
        ])
        .fillna(0)
    )

    busiest_day = weekday_counts.idxmax()

    busiest_date = (
        filtered_df["date"].value_counts().idxmax()
    )

    busiest_hour = (
        filtered_df["hour"].value_counts().idxmax()
    )

    h1, h2, h3 = st.columns(3)

    h1.metric("📅 Busiest Weekday", busiest_day)
    h2.metric("🚀 Busiest Date", str(busiest_date))
    h3.metric("⏰ Busiest Hour", f"{busiest_hour}:00")


# =========================================================
# TIMELINE PAGE
# =========================================================

elif page == "Timeline":

    st.markdown(
        '<div class="section-title">📅 Message Timeline</div>',
        unsafe_allow_html=True
    )

    monthly = (
        filtered_df.groupby("month_period")
        .size()
        .reset_index(name="messages")
    )

    fig = px.bar(
        monthly,
        x="month_period",
        y="messages",
        title="Monthly Message Activity",
        text="messages",
        color="messages",
        color_continuous_scale=["#FFCCCC", "#FF0000"]
    )

    fig.update_layout(
        template="plotly_white",
        xaxis_title="Month",
        yaxis_title="Messages"
    )

    st.plotly_chart(fig, use_container_width=True)

    daily = (
        filtered_df.groupby("date")
        .size()
        .reset_index(name="messages")
    )

    fig = px.line(
        daily,
        x="date",
        y="messages",
        title="Daily Message Timeline",
        markers=True
    )

    fig.update_traces(
        line=dict(color="#FF0000", width=3),
        marker=dict(color="#FF0000", size=7)
    )

    fig.update_layout(template="plotly_white")

    st.plotly_chart(fig, use_container_width=True)


# =========================================================
# ACTIVITY MAP PAGE
# =========================================================

elif page == "Activity Map":

    st.markdown(
        '<div class="section-title">🗓️ Weekly Activity Map</div>',
        unsafe_allow_html=True
    )

    weekday_order = [
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    ]

    heatmap_data = (
        filtered_df.pivot_table(
            index="weekday",
            columns="hour",
            values="message",
            aggfunc="count",
            fill_value=0
        )
        .reindex(weekday_order)
    )

    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale=[
                [0, "#FFF0F0"],
                [0.5, "#FF7777"],
                [1, "#FF0000"]
            ],
            hoverongaps=False,
            colorbar=dict(title="Messages")
        )
    )

    fig.update_layout(
        title="Messages by Weekday and Hour",
        xaxis_title="Hour of Day",
        yaxis_title="Weekday",
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Weekday chart
    weekday_counts = (
        filtered_df["weekday"]
        .value_counts()
        .reindex(weekday_order)
        .fillna(0)
        .reset_index()
    )

    weekday_counts.columns = ["weekday", "messages"]

    fig = px.bar(
        weekday_counts,
        x="weekday",
        y="messages",
        title="Activity by Weekday",
        color="messages",
        color_continuous_scale=["#FFCCCC", "#FF0000"]
    )

    fig.update_layout(template="plotly_white")

    st.plotly_chart(fig, use_container_width=True)


# =========================================================
# PARTICIPANTS PAGE
# =========================================================

elif page == "Participants":

    st.markdown(
        '<div class="section-title">👥 Participant Analysis</div>',
        unsafe_allow_html=True
    )

    user_counts = (
        filtered_df["user"]
        .value_counts()
        .reset_index()
    )

    user_counts.columns = ["Participant", "Messages"]

    top_users = user_counts.head(15)

    fig = px.bar(
        top_users.sort_values("Messages"),
        x="Messages",
        y="Participant",
        orientation="h",
        title="Most Active Participants",
        color="Messages",
        color_continuous_scale=["#FFCCCC", "#FF0000"]
    )

    fig.update_layout(
        template="plotly_white",
        yaxis_title="Participant"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Participant Statistics")

    participant_stats = (
        filtered_df.groupby("user")
        .agg(
            Messages=("message", "count"),
            Words=("word_count", "sum"),
            Media=("media_count", "sum"),
            Links=("link_count", "sum")
        )
        .sort_values("Messages", ascending=False)
        .reset_index()
    )

    st.dataframe(
        participant_stats,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# WORDS & EMOJIS PAGE
# =========================================================

elif page == "Words & Emojis":

    st.markdown(
        '<div class="section-title">📝 Word Analysis</div>',
        unsafe_allow_html=True
    )

    common_words = get_common_words(
        filtered_df["message"]
    )

    if common_words:

        words_df = pd.DataFrame(
            common_words,
            columns=["Word", "Count"]
        )

        fig = px.bar(
            words_df.sort_values("Count"),
            x="Count",
            y="Word",
            orientation="h",
            title="Most Common Words",
            color="Count",
            color_continuous_scale=["#FFCCCC", "#FF0000"]
        )

        fig.update_layout(template="plotly_white")

        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            words_df,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("Not enough text messages to analyze words.")

    # Emoji analysis
    st.markdown(
        '<div class="section-title">😀 Emoji Analysis</div>',
        unsafe_allow_html=True
    )

    try:

        import emoji

        emoji_counter = Counter()

        for message in filtered_df["message"]:

            for character in str(message):

                if character in emoji.EMOJI_DATA:
                    emoji_counter[character] += 1

        if emoji_counter:

            emoji_df = pd.DataFrame(
                emoji_counter.most_common(15),
                columns=["Emoji", "Count"]
            )

            fig = px.bar(
                emoji_df,
                x="Emoji",
                y="Count",
                title="Most Used Emojis",
                color="Count",
                color_continuous_scale=["#FFCCCC", "#FF0000"]
            )

            fig.update_layout(template="plotly_white")

            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                emoji_df,
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("No emojis found in the selected messages.")

    except ImportError:
        st.info(
            "Install the emoji package to enable emoji analysis."
        )


# =========================================================
# MESSAGE EXPLORER PAGE
# =========================================================

elif page == "Message Explorer":

    st.markdown(
        '<div class="section-title">🔎 Search Messages</div>',
        unsafe_allow_html=True
    )

    search_text = st.text_input(
        "Search for a word or phrase",
        placeholder="Example: hello, meeting, good morning..."
    )

    if search_text:

        search_results = filtered_df[
            filtered_df["message"].str.contains(
                search_text,
                case=False,
                na=False,
                regex=False
            )
        ]

        st.success(
            f"Found {len(search_results):,} matching messages."
        )

        st.dataframe(
            search_results[
                ["date_time", "user", "message"]
            ],
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("Enter a word or phrase to search the conversation.")

    st.markdown("### Recent Messages")

    recent_messages = filtered_df.sort_values(
        "date_time",
        ascending=False
    ).head(100)

    st.dataframe(
        recent_messages[
            ["date_time", "user", "message"]
        ],
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# DOWNLOAD SECTION
# =========================================================

st.markdown("---")

st.markdown(
    '<div class="section-title">⬇️ Download Your Analysis</div>',
    unsafe_allow_html=True
)

download_col1, download_col2 = st.columns(2)

with download_col1:

    csv_data = filtered_df.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        label="📥 Download Messages CSV",
        data=csv_data,
        file_name="whatsapp_messages_analysis.csv",
        mime="text/csv",
        use_container_width=True
    )

with download_col2:

    stats_data = (
        filtered_df.groupby("user")
        .agg(
            Messages=("message", "count"),
            Words=("word_count", "sum"),
            Media=("media_count", "sum"),
            Links=("link_count", "sum")
        )
        .reset_index()
        .to_csv(index=False)
        .encode("utf-8-sig")
    )

    st.download_button(
        label="📊 Download Participant Statistics",
        data=stats_data,
        file_name="whatsapp_participant_statistics.csv",
        mime="text/csv",
        use_container_width=True
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown("""
<div class="footer">
    <h3>💬 WhatsApp Analytics Pro</h3>
    <p>Turn your conversations into meaningful insights.</p>
    <p>Built with Python · Streamlit · Plotly</p>
</div>
""", unsafe_allow_html=True)
