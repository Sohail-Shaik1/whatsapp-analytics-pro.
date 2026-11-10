import io
import re
import zipfile
from collections import Counter

import emoji
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from wordcloud import WordCloud, STOPWORDS


# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="WhatsApp Analytics Pro",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =====================================================
# PINK AND WHITE THEME
# =====================================================

# MAIN HEADER

st.markdown(
    """
    <div style="
        background: linear-gradient(135deg, #FF0000, #B30000);
        padding: 35px;
        border-radius: 20px;
        margin-bottom: 25px;
        text-align: center;
    ">

        <div style="
            color: #FFFFFF;
            font-size: 13px;
            font-weight: bold;
            letter-spacing: 3px;
        ">
            CONVERSATION INTELLIGENCE · INTERACTIVE DASHBOARD
        </div>

        <h1 style="
            color: #FFFFFF;
            font-size: 38px;
            font-weight: 900;
            margin: 15px 0;
        ">
            💬 WhatsApp Analytics Pro
        </h1>

        <p style="
            color: #FFFFFF;
            font-size: 16px;
            margin-bottom: 0;
        ">
            Discover the people, patterns and moments
            behind your conversations.
        </p>

    </div>
    """,
    unsafe_allow_html=True
)

# =====================================================
# CHAT PARSING
# =====================================================

TIMESTAMP_PATTERNS = [

    re.compile(
        r"^\[(\d{1,2}[/-]\d{1,2}[/-]\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?)\]\s?(.*)$",
        re.I
    ),

    re.compile(
        r"^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?)\s-\s(.*)$",
        re.I
    ),

    re.compile(
        r"^(\d{4}-\d{1,2}-\d{1,2},\s*\d{1,2}:\d{2}(?::\d{2})?)\s-\s(.*)$",
        re.I
    )

]

MEDIA_RE = re.compile(
    r"<(?:media|image|video|audio|document|sticker|gif|voice message|attached):?\s*omitted>|<attached:[^>]+>",
    re.I
)

URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)

WORD_RE = re.compile(
    r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*|[\u0900-\u097F]+"
)


# =====================================================
# READ TXT OR ZIP FILE
# =====================================================

def read_chat(uploaded):

    raw = uploaded.getvalue()

    if uploaded.name.lower().endswith(".zip"):

        with zipfile.ZipFile(io.BytesIO(raw)) as zf:

            names = [
                n for n in zf.namelist()
                if n.lower().endswith(".txt") and not n.endswith("/")
            ]

            if not names:
                raise ValueError(
                    "No TXT chat file found inside ZIP."
                )

            preferred = [
                n for n in names
                if n.rsplit("/", 1)[-1].lower()
                in ("chat.txt", "_chat.txt")
            ]

            chosen = (
                preferred[0]
                if preferred
                else max(names, key=lambda n: zf.getinfo(n).file_size)
            )

            raw = zf.read(chosen)

    for encoding in (
        "utf-8-sig",
        "utf-8",
        "utf-16",
        "cp1252"
    ):

        try:
            return raw.decode(encoding)

        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace")


# =====================================================
# SPLIT USER AND MESSAGE
# =====================================================

def split_sender(body):

    first = body.split("\n", 1)[0]

    if ": " in first:

        sender, first_text = first.split(": ", 1)

        sender = sender.strip()

        if (
            0 < len(sender) <= 70
            and not sender.lower().startswith(("http", "www"))
        ):

            rest = body.split("\n", 1)

            text = first_text + (
                "\n" + rest[1]
                if len(rest) > 1
                else ""
            )

            return sender, text

    return "Group Notification", body


# =====================================================
# PARSE WHATSAPP CHAT
# =====================================================

def parse_chat(raw_text, dayfirst=False):

    rows = []

    current_dt = None
    current_body = None

    for line in raw_text.splitlines():

        match = None

        for pattern in TIMESTAMP_PATTERNS:

            match = pattern.match(line)

            if match:
                break

        if match:

            if current_dt is not None:

                rows.append(
                    (current_dt, current_body or "")
                )

            current_dt = match.group(1).strip()
            current_body = match.group(2).strip()

        elif current_dt is not None:

            current_body += "\n" + line

    if current_dt is not None:

        rows.append(
            (current_dt, current_body or "")
        )

    if not rows:

        raise ValueError(
            "No WhatsApp timestamps detected. Upload the original exported chat TXT or ZIP."
        )

    df = pd.DataFrame(
        rows,
        columns=["date_raw", "raw_message"]
    )

    df["date"] = pd.to_datetime(
        df["date_raw"],
        dayfirst=dayfirst,
        errors="coerce",
        format="mixed"
    )

    df = df.dropna(subset=["date"]).copy()

    if df.empty:

        raise ValueError(
            "Messages found, but dates could not be interpreted."
        )

    split = df["raw_message"].apply(split_sender)

    df["user"] = split.map(lambda x: x[0])
    df["message"] = split.map(lambda x: x[1])

    forwarded = df["message"].str.match(
        r"^\s*\[(?:Forwarded|Forward)\]",
        case=False,
        na=False
    )

    df["message_type"] = forwarded.map({
        True: "Forwarded",
        False: "Normal"
    })

    df["message"] = df["message"].str.replace(
        r"^\s*\[(?:Forwarded|Forward)\]\s*",
        "",
        regex=True,
        case=False
    )

    df["message"] = df["message"].str.replace(
        r"^\s*Forwarded(?:\s+many\s+times)?\s*:\s*",
        "",
        regex=True,
        case=False
    )

    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month_name()
    df["month_period"] = df["date"].dt.to_period("M").astype(str)
    df["day"] = df["date"].dt.day
    df["hour"] = df["date"].dt.hour
    df["minute"] = df["date"].dt.minute
    df["seconds"] = df["date"].dt.second
    df["weekday"] = df["date"].dt.day_name()

    df["word_count"] = df["message"].apply(
        lambda x: len(WORD_RE.findall(x or ""))
    )

    df["media_count"] = df["message"].apply(
        lambda x: int(bool(MEDIA_RE.search(x or "")))
    )

    df["link_count"] = df["message"].apply(
        lambda x: len(URL_RE.findall(x or ""))
    )

    return df.sort_values("date").reset_index(drop=True)


# =====================================================
# WORD AND EMOJI ANALYSIS
# =====================================================

STOP_WORDS = set(STOPWORDS) | {
    "https", "http", "www", "com",
    "omitted", "media", "okay", "ok",
    "yeah", "yes", "no", "bro",
    "hmm", "hai", "hi", "hello"
}


def get_words(df):

    words = []

    for message in df["message"].fillna(""):

        words.extend(
            w.lower()
            for w in WORD_RE.findall(message)
        )

    return [
        w for w in words
        if len(w) > 1 and w not in STOP_WORDS
    ]


def get_emoji_counts(df):

    counts = Counter()

    for message in df["message"].fillna(""):

        counts.update(
            x["emoji"]
            for x in emoji.emoji_list(message)
        )

    return counts


# =====================================================
# CHART STYLE
# =====================================================

def style_chart(fig):

    fig.update_layout(

        template="plotly_white",

        paper_bgcolor="rgba(0,0,0,0)",

        plot_bgcolor="rgba(0,0,0,0)",

        font=dict(
            family="Arial",
            size=12,
            color="#5b2340"
        ),

        margin=dict(
            l=12,
            r=12,
            t=55,
            b=15
        ),

        hovermode="x unified",

        legend_title_text=""

    )

    return fig


def show_chart(fig, height=None):

    if height:
        fig.update_layout(height=height)

    fig = style_chart(fig)

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": True}
    )


# =====================================================
# WEEKLY ACTIVITY HEATMAP
# =====================================================

def render_heatmap(df):

    daily = (
        df.groupby(df["date"].dt.date)
        .size()
        .rename("Messages")
        .reset_index()
    )

    daily.columns = ["Date", "Messages"]

    if daily.empty:
        st.info("No activity found.")
        return

    daily["Date"] = pd.to_datetime(daily["Date"])

    first_monday = (
        daily["Date"].min()
        - pd.to_timedelta(
            daily["Date"].min().weekday(),
            unit="D"
        )
    )

    daily["Week"] = (
        (daily["Date"] - first_monday).dt.days // 7
    ) + 1

    daily["Weekday"] = daily["Date"].dt.day_name()

    order = [
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    ]

    pivot = daily.pivot_table(
        index="Weekday",
        columns="Week",
        values="Messages",
        aggfunc="sum",
        fill_value=0
    )

    pivot = pivot.reindex(order)

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=[f"Week {int(c)}" for c in pivot.columns],
            y=pivot.index,

            colorscale=[
                [0, "#fff0f6"],
                [0.35, "#f9a8d4"],
                [0.7, "#ec4899"],
                [1, "#9d174d"]
            ],

            hovertemplate=(
                "%{y} · %{x}<br>"
                "Messages: %{z}<extra></extra>"
            ),

            colorbar=dict(title="Messages")
        )
    )

    fig.update_layout(
        title="Weekly activity map",
        height=340
    )

    show_chart(fig)


# =====================================================
# WORD CLOUD
# =====================================================

def render_wordcloud(words):

    if not words:

        st.info(
            "Not enough words to generate a word cloud."
        )

        return

    cloud = WordCloud(
        width=1400,
        height=520,
        background_color="white",
        colormap="RdPu",
        stopwords=STOP_WORDS,
        collocations=False,
        max_words=120,
        prefer_horizontal=0.9
    ).generate(" ".join(words))

    st.image(
        cloud.to_array(),
        use_container_width=True
    )


# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    st.markdown("## 💬 WhatsApp Analytics")

    st.caption(
        "Conversation intelligence dashboard"
    )

    uploaded = st.file_uploader(
        "Upload WhatsApp chat",
        type=["txt", "zip"]
    )

    dayfirst = st.checkbox(
        "Use day/month/year date format",
        value=True
    )

    analyze = st.button(
        "🚀 Analyze chat",
        type="primary",
        use_container_width=True
    )

    if "chat_df" not in st.session_state:

        st.markdown("---")

        st.caption(
            "Upload a WhatsApp TXT or ZIP export to explore messages, activity, people, words and emojis."
        )

    else:

        st.markdown("---")

        st.success(
            f"Loaded: {st.session_state.get('chat_name', 'WhatsApp chat')}"
        )

        if st.button(
            "Clear current chat",
            use_container_width=True
        ):

            st.session_state.pop("chat_df", None)
            st.session_state.pop("chat_name", None)

            st.rerun()


# =====================================================
# ANALYZE UPLOADED CHAT
# =====================================================

if analyze:

    if uploaded is None:

        st.sidebar.warning(
            "Choose a TXT or ZIP file first."
        )

    else:

        try:

            with st.spinner(
                "Analyzing your WhatsApp conversation..."
            ):

                st.session_state["chat_df"] = parse_chat(
                    read_chat(uploaded),
                    dayfirst=dayfirst
                )

                st.session_state["chat_name"] = uploaded.name

            st.rerun()

        except Exception as exc:

            st.sidebar.error(str(exc))


# =====================================================
# MAIN HEADER
# =====================================================

st.markdown("""
<div class="hero">

    <div class="eyebrow">
        CONVERSATION INTELLIGENCE · INTERACTIVE DASHBOARD
    </div>

    <div class="hero-title">
        💬 WhatsApp Analytics Pro
    </div>

    <p class="hero-sub">
        Discover the people, patterns and moments
        behind your conversations.
    </p>

</div>
""", unsafe_allow_html=True)


if "chat_df" not in st.session_state:

    st.info(
        "Upload your WhatsApp exported TXT or ZIP file from the left sidebar, then click Analyze chat."
    )

    st.markdown("""
    **Your dashboard includes:**

    - Message statistics
    - Monthly and daily timelines
    - Activity heatmaps
    - Participant rankings
    - Word cloud
    - Common words
    - Emoji insights
    """)

    st.stop()


full_df = st.session_state["chat_df"].copy()


# =====================================================
# FILTERS
# =====================================================

st.markdown(
    '<div class="section-title">🎛️ Explore your conversation</div>',
    unsafe_allow_html=True
)

users = sorted(
    full_df.loc[
        full_df["user"] != "Group Notification",
        "user"
    ].dropna().unique()
)

f1, f2, f3 = st.columns([1.5, 1, 1])

with f1:

    selected_user = st.selectbox(
        "Show analysis for",
        ["Overall Group"] + users
    )

with f2:

    min_date = full_df["date"].min().date()
    max_date = full_df["date"].max().date()

    start_date = st.date_input(
        "From date",
        value=min_date,
        min_value=min_date,
        max_value=max_date
    )

with f3:

    end_date = st.date_input(
        "To date",
        value=max_date,
        min_value=min_date,
        max_value=max_date
    )


if start_date > end_date:

    st.error(
        "The start date must be before or equal to the end date."
    )

    st.stop()


filtered = full_df[
    (full_df["date"].dt.date >= start_date)
    &
    (full_df["date"].dt.date <= end_date)
].copy()


if selected_user != "Overall Group":

    filtered = filtered[
        filtered["user"] == selected_user
    ]


if filtered.empty:

    st.warning(
        "No messages match the selected filters."
    )

    st.stop()


# =====================================================
# TOP STATISTICS
# =====================================================

st.markdown(
    '<div class="section-title">📊 Top Statistics</div>',
    unsafe_allow_html=True
)

total_messages = len(filtered)

total_words = int(
    filtered["word_count"].sum()
)

media_shared = int(
    filtered["media_count"].sum()
)

links_shared = int(
    filtered["link_count"].sum()
)

participants = filtered.loc[
    filtered["user"] != "Group Notification",
    "user"
].nunique()


m1, m2, m3, m4, m5 = st.columns(5)

m1.metric(
    "💬 Total Messages",
    f"{total_messages:,}"
)

m2.metric(
    "🔤 Total Words",
    f"{total_words:,}"
)

m3.metric(
    "🖼️ Media Shared",
    f"{media_shared:,}"
)

m4.metric(
    "🔗 Links Shared",
    f"{links_shared:,}"
)

m5.metric(
    "👥 Participants",
    f"{participants:,}"
)


# =====================================================
# MONTHLY AND DAILY TIMELINES
# =====================================================

st.markdown(
    '<div class="section-title">📈 Conversation Timeline</div>',
    unsafe_allow_html=True
)

left, right = st.columns(2)

with left:

    monthly = (
        filtered.set_index("date")
        .resample("MS")
        .size()
        .rename("Messages")
        .reset_index()
    )

    monthly["Month"] = monthly["date"].dt.strftime(
        "%b %Y"
    )

    fig = px.line(
        monthly,
        x="Month",
        y="Messages",
        markers=True,
        title="Monthly Timeline"
    )

    fig.update_traces(
        line=dict(color="#e83e8c", width=3),
        marker=dict(size=8)
    )

    show_chart(fig, 370)


with right:

    daily = (
        filtered.groupby(
            filtered["date"].dt.date
        )
        .size()
        .rename("Messages")
        .reset_index()
    )

    daily.columns = ["Date", "Messages"]

    fig = px.line(
        daily,
        x="Date",
        y="Messages",
        markers=True,
        title="Daily Timeline"
    )

    fig.update_traces(
        line=dict(color="#c02670", width=2)
    )

    show_chart(fig, 370)


# =====================================================
# ACTIVITY MAP
# =====================================================

st.markdown(
    '<div class="section-title">🗓️ Activity Map</div>',
    unsafe_allow_html=True
)

daily_counts = filtered.groupby(
    filtered["date"].dt.date
).size()

monthly_counts = filtered.groupby(
    filtered["date"].dt.to_period("M")
).size()

weekday_order = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday"
]

weekday_counts = (
    filtered["weekday"]
    .value_counts()
    .reindex(weekday_order, fill_value=0)
)


a, b, c = st.columns(3)

if not daily_counts.empty:

    a.metric(
        "🔥 Most Busy Day",
        str(daily_counts.idxmax()),
        f"{daily_counts.max():,} messages"
    )

if not monthly_counts.empty:

    b.metric(
        "📅 Most Busy Month",
        monthly_counts.idxmax().strftime("%B %Y"),
        f"{monthly_counts.max():,} messages"
    )

if not weekday_counts.empty:

    c.metric(
        "⚡ Most Active Weekday",
        weekday_counts.idxmax(),
        f"{weekday_counts.max():,} messages"
    )


# =====================================================
# WEEKDAY AND MONTHLY CHARTS
# =====================================================

d1, d2 = st.columns(2)

with d1:

    weekday_df = (
        weekday_counts
        .rename_axis("Weekday")
        .reset_index(name="Messages")
    )

    fig = px.bar(
        weekday_df,
        x="Weekday",
        y="Messages",
        title="Messages by Weekday",
        color="Messages",
        color_continuous_scale="RdPu"
    )

    show_chart(fig, 340)


with d2:

    month_df = (
        monthly_counts
        .rename_axis("Month")
        .reset_index(name="Messages")
    )

    month_df["Month"] = (
        month_df["Month"].dt.strftime("%b %Y")
    )

    fig = px.bar(
        month_df,
        x="Month",
        y="Messages",
        title="Messages by Month",
        color="Messages",
        color_continuous_scale="RdPu"
    )

    show_chart(fig, 340)


# =====================================================
# WEEKLY ACTIVITY HEATMAP
# =====================================================

st.markdown(
    '<div class="section-title">🌡️ Weekly Activity Heatmap</div>',
    unsafe_allow_html=True
)

render_heatmap(filtered)


# =====================================================
# HOUR AND WEEKDAY ACTIVITY
# =====================================================

hour_pivot = filtered.pivot_table(
    index="weekday",
    columns="hour",
    values="message",
    aggfunc="count",
    fill_value=0
)

hour_pivot = (
    hour_pivot
    .reindex(weekday_order)
    .reindex(columns=range(24), fill_value=0)
)

fig = px.imshow(
    hour_pivot,
    aspect="auto",
    title="Activity by Weekday and Hour",
    labels={
        "x": "Hour of Day",
        "y": "Weekday",
        "color": "Messages"
    },
    color_continuous_scale="RdPu"
)

fig.update_xaxes(
    tickmode="linear",
    dtick=1
)

show_chart(fig, 390)


# =====================================================
# MOST BUSY USERS
# =====================================================

st.markdown(
    '<div class="section-title">👥 Most Busy Users</div>',
    unsafe_allow_html=True
)

people = filtered[
    filtered["user"] != "Group Notification"
]

if people.empty:

    st.info(
        "No participant messages in this selection."
    )

else:

    p1, p2 = st.columns([1.2, 1])

    with p1:

        top_users = (
            people["user"]
            .value_counts()
            .head(15)
            .sort_values()
            .reset_index()
        )

        top_users.columns = [
            "User",
            "Messages"
        ]

        fig = px.bar(
            top_users,
            x="Messages",
            y="User",
            orientation="h",
            title="Top Participants by Messages",
            color="Messages",
            color_continuous_scale="RdPu"
        )

        show_chart(fig, 440)


    with p2:

        top_words_users = (
            people.groupby("user")["word_count"]
            .sum()
            .sort_values(ascending=False)
            .head(12)
            .reset_index()
        )

        top_words_users.columns = [
            "User",
            "Words"
        ]

        fig = px.bar(
            top_words_users.sort_values("Words"),
            x="Words",
            y="User",
            orientation="h",
            title="Top Participants by Words",
            color="Words",
            color_continuous_scale="RdPu"
        )

        show_chart(fig, 440)


    summary = people.groupby("user").agg(

        Messages=("message", "size"),

        Words=("word_count", "sum"),

        Media=("media_count", "sum"),

        Links=("link_count", "sum")

    ).sort_values(
        "Messages",
        ascending=False
    ).reset_index()

    st.markdown("#### Participant Summary")

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )


# =====================================================
# WORD CLOUD
# =====================================================

st.markdown(
    '<div class="section-title">☁️ Word Cloud</div>',
    unsafe_allow_html=True
)

words = get_words(filtered)

render_wordcloud(words)


# =====================================================
# COMMON WORDS AND EMOJI ANALYSIS
# =====================================================

w1, w2 = st.columns(2)

with w1:

    st.markdown("#### 🔤 Most Common Words")

    common = Counter(words).most_common(20)

    if common:

        common_df = pd.DataFrame(
            common,
            columns=["Word", "Count"]
        ).sort_values("Count")

        fig = px.bar(
            common_df,
            x="Count",
            y="Word",
            orientation="h",
            title="Top 20 Words",
            color="Count",
            color_continuous_scale="RdPu"
        )

        show_chart(fig, 480)

    else:

        st.info("No common words found.")


with w2:

    st.markdown("#### 😍 Emoji Analysis")

    emoji_counts = get_emoji_counts(filtered)

    if emoji_counts:

        emoji_df = pd.DataFrame(
            emoji_counts.most_common(20),
            columns=["Emoji", "Count"]
        )

        fig = px.pie(
            emoji_df.head(8),
            names="Emoji",
            values="Count",
            title="Most Used Emojis",
            hole=0.5
        )

        show_chart(fig, 340)

        st.dataframe(
            emoji_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No emojis found in the selected messages."
        )


# =====================================================
# SEARCH MESSAGES
# =====================================================

st.markdown(
    '<div class="section-title">💬 Search Messages</div>',
    unsafe_allow_html=True
)

query = st.text_input(
    "Search message text",
    placeholder="Search for a word, phrase or link..."
)

message_view = filtered.copy()

if query:

    message_view = message_view[
        message_view["message"].str.contains(
            query,
            case=False,
            na=False,
            regex=False
        )
    ]

st.caption(
    f"{len(message_view):,} matching messages"
)

show_cols = [
    "date",
    "user",
    "message",
    "message_type",
    "word_count",
    "media_count",
    "link_count"
]

st.dataframe(
    message_view[show_cols].sort_values(
        "date",
        ascending=False
    ),
    use_container_width=True,
    hide_index=True,
    height=430
)


# =====================================================
# DOWNLOAD CSV FILES
# =====================================================

st.markdown("---")

x1, x2 = st.columns(2)

with x1:

    st.download_button(
        "⬇️ Download All Chat Data (CSV)",

        full_df.to_csv(
            index=False
        ).encode("utf-8-sig"),

        "whatsapp_all_messages.csv",

        "text/csv",

        use_container_width=True
    )


with x2:

    st.download_button(
        "⬇️ Download Filtered Data (CSV)",

        filtered.to_csv(
            index=False
        ).encode("utf-8-sig"),

        "whatsapp_filtered_messages.csv",

        "text/csv",

        use_container_width=True
    )


# =====================================================
# FOOTER
# =====================================================

st.markdown("---")

st.markdown(
    """
    <center>
        <p style="color:#c02670;font-weight:700;">
            💗 WhatsApp Analytics Pro
        </p>
        <p style="color:#95677d;font-size:13px;">
            Conversation Intelligence Dashboard
        </p>
    </center>
    """,
    unsafe_allow_html=True
)
