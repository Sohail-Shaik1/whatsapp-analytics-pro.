
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import zipfile
from collections import Counter

# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="WhatsApp Analytics Pro",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

RED = "#FF0000"
DARK_RED = "#B30000"
LIGHT_RED = "#FFF0F0"

# =========================================================
# 2. PURE RED THEME
# =========================================================

st.markdown("""
<style>
.stApp {
    background: #FFFFFF;
    color: #222222;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

[data-testid="stSidebar"] {
    background: #FFF5F5;
    border-right: 2px solid #FF0000;
}

h1, h2, h3 {
    color: #CC0000 !important;
    font-weight: 800 !important;
}

p, label {
    color: #333333;
}

.stButton > button,
.stDownloadButton > button {
    background: #FF0000 !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: bold !important;
    padding: 10px 18px !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    background: #B30000 !important;
    color: white !important;
}

[data-testid="stMetric"] {
    background: #FFF0F0;
    border: 1px solid #FFCCCC;
    border-radius: 12px;
    padding: 18px;
}

[data-testid="stMetricLabel"] {
    color: #990000 !important;
    font-weight: bold !important;
}

[data-testid="stMetricValue"] {
    color: #FF0000 !important;
    font-weight: 900 !important;
}

[data-testid="stFileUploader"] {
    background: #FFF5F5;
    border: 2px dashed #FF0000;
    border-radius: 12px;
    padding: 15px;
}

.stTabs [aria-selected="true"] {
    color: #FF0000 !important;
    border-bottom-color: #FF0000 !important;
}

.hero {
    background: linear-gradient(135deg, #FF0000, #B30000);
    padding: 35px 25px;
    border-radius: 18px;
    text-align: center;
    margin-bottom: 25px;
    box-shadow: 0 5px 18px rgba(255,0,0,0.18);
}

.hero-label {
    color: #FFFFFF;
    letter-spacing: 3px;
    font-size: 12px;
    font-weight: bold;
}

.hero h1 {
    color: #FFFFFF !important;
    font-size: 38px !important;
    margin: 14px 0;
}

.hero p {
    color: #FFFFFF !important;
    font-size: 16px;
    margin-bottom: 0;
}

.section-title {
    color: #CC0000;
    font-size: 22px;
    font-weight: 800;
    border-left: 5px solid #FF0000;
    padding-left: 12px;
    margin: 25px 0 15px 0;
}

.info-card {
    background: #FFF5F5;
    border: 1px solid #FFCCCC;
    border-radius: 12px;
    padding: 18px;
    min-height: 125px;
}

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
# 3. HERO HEADER
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
# 4. CONSTANTS
# =========================================================

WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)

LINK_RE = re.compile(
    r"https?://\S+|www\.\S+",
    re.IGNORECASE
)

MEDIA_RE = re.compile(
    r"<(?:media|image|video|audio|document|sticker|gif|voice message|attached):?\s*omitted>|<attached:[^>]+>",
    re.IGNORECASE
)

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
# 5. READ WHATSAPP TXT OR ZIP
# =========================================================

def read_chat(uploaded_file):

    if uploaded_file.name.lower().endswith(".zip"):

        with zipfile.ZipFile(uploaded_file) as archive:

            txt_files = [
                name for name in archive.namelist()
                if name.lower().endswith(".txt")
                and not name.startswith("__MACOSX/")
            ]

            if not txt_files:
                raise ValueError("No TXT file found inside ZIP.")

            raw_bytes = archive.read(txt_files[0])

    else:
        raw_bytes = uploaded_file.getvalue()

    for encoding in [
        "utf-8-sig",
        "utf-8",
        "utf-16",
        "utf-16-le",
        "cp1252",
        "latin-1"
    ]:

        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError("Unable to decode this chat file.")


# =========================================================
# 6. WHATSAPP DATE PATTERNS
# =========================================================

PATTERNS = [

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

    # ISO format
    re.compile(
        r"^\[(\d{4}-\d{1,2}-\d{1,2},?\s*"
        r"\d{1,2}:\d{2}(?::\d{2})?)\]\s?(.*)$"
    ),

    re.compile(
        r"^(\d{4}-\d{1,2}-\d{1,2},?\s*"
        r"\d{1,2}:\d{2}(?::\d{2})?)\s-\s(.*)$"
    )
]


# =========================================================
# 7. SPLIT USER AND MESSAGE
# =========================================================

def split_sender(body):

    if ": " in body:

        sender, message = body.split(": ", 1)

        sender = sender.strip()

        if sender and len(sender) <= 100:
            return sender, message.strip()

    return "Group Notification", body.strip()


# =========================================================
# 8. PARSE WHATSAPP CHAT
# =========================================================

def parse_chat(raw_text, dayfirst=False):

    rows = []
    current_message = None

    for line in raw_text.splitlines():

        matched = False

        for pattern in PATTERNS:

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

        # Continue multiline messages
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

    # Convert timestamps
    df["date_time"] = pd.to_datetime(
        df["timestamp_text"],
        dayfirst=dayfirst,
        errors="coerce",
        format="mixed"
    )

    df = df.dropna(subset=["date_time"]).copy()

    if df.empty:
        raise ValueError(
            "Could not understand the date format. "
            "Check your date format setting."
        )

    # IMPORTANT FIX:
    # Store date as pandas datetime64[ns], not Python date objects.
    df["date"] = df["date_time"].dt.normalize()

    df["year"] = df["date_time"].dt.year
    df["month"] = df["date_time"].dt.month
    df["month_name"] = df["date_time"].dt.strftime("%B")
    df["month_period"] = df["date_time"].dt.to_period("M").astype(str)
    df["day"] = df["date_time"].dt.day
    df["hour"] = df["date_time"].dt.hour
    df["minute"] = df["date_time"].dt.minute
    df["weekday"] = df["date_time"].dt.day_name()
    df["weekday_number"] = df["date_time"].dt.dayofweek

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

    df["message_type"] = df["media_count"].apply(
        lambda x: "Media" if x > 0 else "Text"
    )

    return df


# =========================================================
# 9. COMMON WORDS
# =========================================================

def get_common_words(messages):

    words_list = []

    for message in messages:

        words = WORD_RE.findall(str(message).lower())

        for word in words:

            if (
                len(word) > 2
                and word not in STOP_WORDS
                and not word.isdigit()
            ):
                words_list.append(word)

    return Counter(words_list).most_common(15)


# =========================================================
# 10. SIDEBAR
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

            with st.spinner("Analyzing your conversation..."):

                raw_text = read_chat(uploaded_file)

                chat_df = parse_chat(
                    raw_text,
                    dayfirst=dayfirst
                )

                st.session_state.chat_df = chat_df

            st.sidebar.success("Analysis completed!")

        except Exception as error:
            st.sidebar.error(str(error))


# =========================================================
# 11. CHECK IF CHAT IS UPLOADED
# =========================================================

if st.session_state.chat_df is None:

    st.markdown("### ✨ What you can explore")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
        <div class="info-card">
            <h3>📊 Statistics</h3>
            Messages, words, media, links and participants.
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="info-card">
            <h3>📈 Activity</h3>
            Monthly, daily and hourly conversation patterns.
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="info-card">
            <h3>👥 People</h3>
            Most active members and individual analysis.
        </div>
        """, unsafe_allow_html=True)

    st.info("Upload your WhatsApp chat from the sidebar to begin.")
    st.stop()


# =========================================================
# 12. LOAD DATA
# =========================================================

df = st.session_state.chat_df.copy()

# Ensure date column remains pandas datetime
df["date"] = pd.to_datetime(df["date"])


# =========================================================
# 13. DASHBOARD FILTERS
# =========================================================

st.markdown(
    '<div class="section-title">🎯 Dashboard Filters</div>',
    unsafe_allow_html=True
)

filter_col1, filter_col2 = st.columns(2)

users = sorted(df["user"].unique().tolist())

with filter_col1:

    selected_user = st.selectbox(
        "Select conversation",
        ["Overall Chat"] + users
    )

with filter_col2:

    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    selected_dates = st.date_input(
        "Select date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )


# =========================================================
# 14. APPLY FILTERS - DATE ERROR FIXED
# =========================================================

if selected_user == "Overall Chat":
    filtered_df = df.copy()
else:
    filtered_df = df[df["user"] == selected_user].copy()


# Handle date range safely
if isinstance(selected_dates, (tuple, list)):

    if len(selected_dates) == 2:

        start_date = pd.Timestamp(selected_dates[0])
        end_date = pd.Timestamp(selected_dates[1])

    elif len(selected_dates) == 1:

        start_date = pd.Timestamp(selected_dates[0])
        end_date = start_date

    else:

        start_date = pd.Timestamp(min_date)
        end_date = pd.Timestamp(max_date)

else:

    start_date = pd.Timestamp(selected_dates)
    end_date = start_date


# Normalize both selected dates
start_date = start_date.normalize()
end_date = end_date.normalize()

filtered_df = filtered_df[
    (filtered_df["date"] >= start_date)
    & (filtered_df["date"] <= end_date)
].copy()


if filtered_df.empty:

    st.warning("No messages found for the selected filters.")
    st.stop()


# =========================================================
# 15. TOP STATISTICS
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

avg_words = round(
    total_words / total_messages,
    2
) if total_messages else 0

m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("💬 Messages", f"{total_messages:,}")
m2.metric("📝 Words", f"{total_words:,}")
m3.metric("📷 Media", f"{total_media:,}")
m4.metric("🔗 Links", f"{total_links:,}")
m5.metric("👥 Participants", f"{total_participants:,}")

st.caption(f"Average words per message: {avg_words}")


# =========================================================
# 16. NAVIGATION
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
# 17. OVERVIEW
# =========================================================

if page == "Overview":

    st.markdown(
        '<div class="section-title">📈 Conversation Overview</div>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:

        type_counts = filtered_df["message_type"].value_counts()

        fig = px.pie(
            names=type_counts.index,
            values=type_counts.values,
            hole=0.55,
            title="Message Type Distribution",
            color_discrete_sequence=["#FF0000", "#FF9999"]
        )

        fig.update_layout(template="plotly_white")

        st.plotly_chart(fig, use_container_width=True)

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
            color="messages",
            color_continuous_scale=["#FFCCCC", "#FF0000"]
        )

        fig.update_layout(template="plotly_white")

        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div class="section-title">🔥 Conversation Highlights</div>',
        unsafe_allow_html=True
    )

    weekday_order = [
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    ]

    weekday_counts = (
        filtered_df["weekday"]
        .value_counts()
        .reindex(weekday_order)
        .fillna(0)
    )

    busiest_day = weekday_counts.idxmax()
    busiest_date = filtered_df["date"].value_counts().idxmax()
    busiest_hour = filtered_df["hour"].value_counts().idxmax()

    h1, h2, h3 = st.columns(3)

    h1.metric("📅 Busiest Weekday", busiest_day)
    h2.metric("🚀 Busiest Date", busiest_date.strftime("%d-%m-%Y"))
    h3.metric("⏰ Busiest Hour", f"{busiest_hour}:00")


# =========================================================
# 18. TIMELINE
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
# 19. ACTIVITY MAP
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

    heatmap_data = filtered_df.pivot_table(
        index="weekday",
        columns="hour",
        values="message",
        aggfunc="count",
        fill_value=0
    ).reindex(weekday_order)

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
# 20. PARTICIPANTS
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

    fig.update_layout(template="plotly_white")

    st.plotly_chart(fig, use_container_width=True)

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

    st.markdown("### Participant Statistics")

    st.dataframe(
        participant_stats,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 21. WORDS AND EMOJIS
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
        st.info("Install emoji using: pip install emoji")


# =========================================================
# 22. MESSAGE EXPLORER
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
        st.info("Enter a word or phrase to search messages.")

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
# 23. DOWNLOAD REPORTS
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
        "📥 Download Messages CSV",
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
        "📊 Download Participant Statistics",
        data=stats_data,
        file_name="whatsapp_participant_statistics.csv",
        mime="text/csv",
        use_container_width=True
    )


# =========================================================
# 24. FOOTER
# =========================================================

st.markdown("""
<div class="footer">
    <h3>💬 WhatsApp Analytics Pro</h3>
    <p>Turn your conversations into meaningful insights.</p>
    <p>Built with Python · Streamlit · Plotly</p>
</div>
""", unsafe_allow_html=True)
