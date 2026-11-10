import io
import re
import zipfile
from collections import Counter
from datetime import date

import emoji
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from wordcloud import WordCloud, STOPWORDS


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="WhatsApp Analytics Pro",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# THEME
# ============================================================
def apply_theme(theme_name: str) -> None:
    if theme_name == "Dark":
        bg = "#0B1220"
        panel = "#131F32"
        panel2 = "#1A2940"
        text = "#F3F6FC"
        muted = "#A7B5CA"
        border = "#263750"
        accent = "#32D6A0"
    else:
        bg = "#F4F7FB"
        panel = "#FFFFFF"
        panel2 = "#EEF3FA"
        text = "#172338"
        muted = "#5D6B82"
        border = "#DCE4EF"
        accent = "#087F67"

    st.markdown(
        f"""
        <style>
        :root {{
          --wa-bg: {bg};
          --wa-panel: {panel};
          --wa-panel2: {panel2};
          --wa-text: {text};
          --wa-muted: {muted};
          --wa-border: {border};
          --wa-accent: {accent};
        }}
        .stApp {{ background: var(--wa-bg); color: var(--wa-text); }}
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stToolbar"] {{ right: 1rem; }}
        .block-container {{ max-width: 100%; padding-top: 1.4rem; padding-bottom: 2rem; }}
        h1, h2, h3, h4, p, label, .stMarkdown {{ color: var(--wa-text); }}
        .hero {{
          padding: 1.25rem 1.5rem; border-radius: 18px;
          background: linear-gradient(120deg, var(--wa-panel), var(--wa-panel2));
          border: 1px solid var(--wa-border); margin-bottom: 1rem;
        }}
        .hero-kicker {{ color: var(--wa-accent); font-size: .76rem; font-weight: 800; letter-spacing: .14em; }}
        .hero-title {{ color: var(--wa-text); font-size: 2rem; font-weight: 850; margin: .2rem 0; }}
        .hero-sub {{ color: var(--wa-muted); margin: 0; }}
        div[data-testid="stMetric"] {{
          background: var(--wa-panel); border: 1px solid var(--wa-border);
          border-radius: 14px; padding: 14px 16px;
        }}
        div[data-testid="stMetricLabel"] {{ color: var(--wa-muted); }}
        div[data-testid="stMetricValue"] {{ color: var(--wa-text); }}
        div[data-testid="stTabs"] button {{ font-weight: 700; }}
        div[data-testid="stDataFrame"] {{ border: 1px solid var(--wa-border); border-radius: 12px; }}
        .small-note {{ color: var(--wa-muted); font-size: .85rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# WHATSAPP FILE READING + PARSING
# ============================================================
TIMESTAMP_PATTERNS = [
    # Android-style: [10/4/26, 6:20:58 PM] Name: message
    re.compile(
        r"^\[(\d{1,2}[/-]\d{1,2}[/-]\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?)\]\s?(.*)$",
        re.IGNORECASE,
    ),
    # iOS-style: 10/4/26, 6:20 PM - Name: message
    re.compile(
        r"^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?)\s-\s(.*)$",
        re.IGNORECASE,
    ),
    # Some exports use YYYY-MM-DD, HH:MM - Name: message
    re.compile(
        r"^(\d{4}-\d{1,2}-\d{1,2},\s*\d{1,2}:\d{2}(?::\d{2})?)\s-\s(.*)$",
        re.IGNORECASE,
    ),
]

MEDIA_PATTERN = re.compile(
    r"<(?:media|image|video|audio|document|sticker|gif|voice message|attached):?\s*omitted>|<attached:[^>]+>",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*|[\u0900-\u097F]+")

SYSTEM_PREFIXES = (
    "messages and calls are end-to-end encrypted",
    "you created group",
    "you changed the group",
    "you added",
    "you removed",
    "left",
    "joined using this group's invite link",
    "changed the group description",
    "changed this group's icon",
    "changed the subject",
    "changed the group name",
    "security code changed",
    "this message was deleted",
    "waiting for this message",
)


def read_uploaded_chat(uploaded_file) -> str:
    """Read .txt or find the most likely chat .txt inside a .zip."""
    name = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()

    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            txt_names = [
                n for n in archive.namelist()
                if n.lower().endswith(".txt") and not n.endswith("/")
            ]
            if not txt_names:
                raise ValueError("The ZIP file does not contain a .txt chat export.")

            preferred = [
                n for n in txt_names
                if n.rsplit("/", 1)[-1].lower() in ("chat.txt", "_chat.txt")
            ]
            chosen = preferred[0] if preferred else max(
                txt_names, key=lambda n: archive.getinfo(n).file_size
            )
            raw = archive.read(chosen)

    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_chat(text: str, dayfirst: bool = False) -> pd.DataFrame:
    """Turn timestamped WhatsApp lines and their continuation lines into rows."""
    records = []
    current_timestamp = None
    current_body = None

    for line in text.splitlines():
        found = None
        for pattern in TIMESTAMP_PATTERNS:
            found = pattern.match(line)
            if found:
                break

        if found:
            if current_timestamp is not None:
                records.append((current_timestamp, current_body or ""))

            current_timestamp = found.group(1).strip()
            current_body = found.group(2).strip()
        elif current_timestamp is not None:
            # Continuation of the previous multiline message
            current_body += "\n" + line

    if current_timestamp is not None:
        records.append((current_timestamp, current_body or ""))

    if not records:
        raise ValueError(
            "No timestamped WhatsApp messages were detected. "
            "Please upload the original WhatsApp .txt export."
        )

    df = pd.DataFrame(records, columns=["date_raw", "raw_message"])
    df["date"] = pd.to_datetime(
        df["date_raw"],
        dayfirst=dayfirst,
        errors="coerce",
        format="mixed",
    )
    df = df.dropna(subset=["date"]).copy()

    if df.empty:
        raise ValueError("Messages were found, but their dates could not be parsed.")

    sender_data = df["raw_message"].apply(split_sender_and_text)
    df["user"] = sender_data.map(lambda x: x[0])
    df["message"] = sender_data.map(lambda x: x[1])

    forward_data = df["message"].apply(remove_forward_label)
    df["message_type"] = forward_data.map(lambda x: x[0])
    df["message"] = forward_data.map(lambda x: x[1])

    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month_name()
    df["month_period"] = df["date"].dt.to_period("M").astype(str)
    df["day"] = df["date"].dt.day
    df["hour"] = df["date"].dt.hour
    df["minute"] = df["date"].dt.minute
    df["seconds"] = df["date"].dt.second
    df["weekday"] = df["date"].dt.day_name()
    df["word_count"] = df["message"].apply(count_words)
    df["link_count"] = df["message"].apply(lambda x: len(URL_PATTERN.findall(x)))
    df["media_count"] = df["message"].apply(lambda x: 1 if MEDIA_PATTERN.search(x) else 0)

    return df.sort_values("date").reset_index(drop=True)


def split_sender_and_text(body: str):
    """
    Split 'sender: message'. WhatsApp system/group events without a sender
    are labelled Group Notification. Sender parsing is intentionally cautious.
    """
    first_line = body.split("\n", 1)[0]
    if ": " in first_line:
        possible_sender, first_message_part = first_line.split(": ", 1)
        sender = possible_sender.strip()

        # Sender labels are usually short names or phone numbers.
        looks_like_sender = (
            0 < len(sender) <= 70
            and "\n" not in sender
            and not sender.lower().startswith(("http", "www."))
            and not any(sender.lower().startswith(p) for p in SYSTEM_PREFIXES)
        )
        if looks_like_sender:
            remainder = first_message_part
            if "\n" in body:
                remainder += "\n" + body.split("\n", 1)[1]
            return sender, remainder

    return "Group Notification", body


def remove_forward_label(message: str):
    pattern = r"^\s*\[(?:Forwarded|Forward)\]\s*"
    if re.match(pattern, message, flags=re.IGNORECASE):
        return "Forwarded", re.sub(
            pattern, "", message, count=1, flags=re.IGNORECASE
        )
    # Some export formats may use a plain text prefix.
    plain = r"^\s*Forwarded(?:\s+many\s+times)?\s*:\s*"
    if re.match(plain, message, flags=re.IGNORECASE):
        return "Forwarded", re.sub(
            plain, "", message, count=1, flags=re.IGNORECASE
        )
    return "Normal", message


def count_words(text: str) -> int:
    return len(WORD_PATTERN.findall(text or ""))


# ============================================================
# ANALYTICS HELPERS
# ============================================================
def extract_emojis(text: str):
    return [item["emoji"] for item in emoji.emoji_list(text or "")]


def prepare_analysis(df: pd.DataFrame):
    msg = df["message"].fillna("")
    words = []
    for value in msg:
        words.extend(w.lower() for w in WORD_PATTERN.findall(value))

    stop_words = set(STOPWORDS) | {
        "https", "http", "www", "com", "omitted", "media",
        "okay", "ok", "yeah", "yes", "no", "bro", "hmm",
    }
    useful_words = [w for w in words if w not in stop_words and len(w) > 1]

    emoji_counter = Counter()
    for value in msg:
        emoji_counter.update(extract_emojis(value))

    return useful_words, emoji_counter


def chart_layout(fig, theme_name):
    template = "plotly_dark" if theme_name == "Dark" else "plotly_white"
    fig.update_layout(
        template=template,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=45, b=10),
        font=dict(family="Inter, sans-serif"),
        hovermode="x unified",
        legend_title_text="",
    )
    return fig


def render_calendar_heatmap(df, theme_name):
    daily = df.groupby(df["date"].dt.date).size().rename("messages").reset_index()
    daily.columns = ["date", "messages"]
    if daily.empty:
        st.info("No activity to display.")
        return

    daily["date"] = pd.to_datetime(daily["date"])
    daily["weekday"] = daily["date"].dt.dayofweek
    daily["week"] = ((daily["date"] - daily["date"].min()).dt.days // 7)
    pivot = daily.pivot_table(
        index="weekday", columns="week", values="messages", aggfunc="sum", fill_value=0
    )
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=[f"Week {int(x)+1}" for x in pivot.columns],
            y=[labels[int(y)] for y in pivot.index],
            colorscale="Teal",
            hovertemplate="%{y}, %{x}<br>Messages: %{z}<extra></extra>",
        )
    )
    fig.update_layout(title="Weekly activity heatmap", height=300)
    st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)


def render_wordcloud(words, theme_name):
    if not words:
        st.info("Not enough text to create a word cloud.")
        return
    background = "#101827" if theme_name == "Dark" else "#FFFFFF"
    wc = WordCloud(
        width=1200,
        height=500,
        background_color=background,
        colormap="viridis",
        stopwords=set(STOPWORDS),
        collocations=False,
        max_words=100,
    ).generate(" ".join(words))
    st.image(wc.to_array(), use_container_width=True)


# ============================================================
# HEADER + UPLOAD
# ============================================================
with st.container():
    head_left, head_right = st.columns([5, 1.3], vertical_alignment="center")
    with head_left:
        st.markdown(
            """
            <div class="hero">
              <div class="hero-kicker">CONVERSATION INTELLIGENCE</div>
              <div class="hero-title">💬 WhatsApp Analytics Pro</div>
              <p class="hero-sub">Turn your exported conversations into clear, interactive insights.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with head_right:
        theme_name = st.selectbox("Appearance", ["Dark", "Light"], index=0)

apply_theme(theme_name)

with st.expander("📁 Upload WhatsApp chat", expanded="chat_df" not in st.session_state):
    uploaded = st.file_uploader(
        "Choose your WhatsApp export",
        type=["txt", "zip"],
        help="Export your chat from WhatsApp without media, or upload the ZIP export.",
    )
    dayfirst = st.checkbox(
        "My export uses day/month/year dates (for example 04/10/2026 = 4 October)",
        value=False,
    )
    if uploaded is not None:
        if st.button("🚀 Analyze chat", type="primary", use_container_width=True):
            try:
                with st.spinner("Reading and analyzing your conversation..."):
                    chat_text = read_uploaded_chat(uploaded)
                    chat_df = parse_chat(chat_text, dayfirst=dayfirst)
                    st.session_state["chat_df"] = chat_df
                    st.session_state["chat_name"] = uploaded.name
                st.success("Your chat is ready!")
            except Exception as exc:
                st.error(str(exc))

if "chat_df" not in st.session_state:
    st.info("Upload a WhatsApp TXT or ZIP export and press **Analyze chat** to open the dashboard.")
    st.markdown(
        """
        **What you can explore**
        - Messages, words, media and links
        - Monthly and daily message trends
        - Calendar and weekday/hour activity heatmaps
        - Most active users, common words and emojis
        - Overall group or an individual participant
        """
    )
    st.stop()

full_df = st.session_state["chat_df"].copy()

# ============================================================
# FILTER BAR
# ============================================================
st.markdown("### 🎛️ Explore your conversation")
f1, f2, f3, f4 = st.columns([1.5, 1.2, 1.2, 1.2])

users = sorted(full_df.loc[full_df["user"] != "Group Notification", "user"].dropna().unique())
with f1:
    selected_user = st.selectbox("Conversation view", ["Overall Group"] + users)
with f2:
    message_type_filter = st.selectbox("Message type", ["All", "Normal", "Forwarded"])
with f3:
    min_date = full_df["date"].min().date()
    max_date = full_df["date"].max().date()
    start_date = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
with f4:
    end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)

if start_date > end_date:
    st.error("The start date must be on or before the end date.")
    st.stop()

filtered = full_df[
    (full_df["date"].dt.date >= start_date)
    & (full_df["date"].dt.date <= end_date)
].copy()

if selected_user != "Overall Group":
    filtered = filtered[filtered["user"] == selected_user]

if message_type_filter != "All":
    filtered = filtered[filtered["message_type"] == message_type_filter]

if filtered.empty:
    st.warning("No messages match these filters. Change the person or date range.")
    st.stop()

# ============================================================
# TOP NAVIGATION
# ============================================================
overview_tab, timeline_tab, people_tab, words_tab, messages_tab = st.tabs(
    ["📊 Overview", "📈 Timeline & Activity", "👥 People", "🔤 Words & Emojis", "💬 Messages"]
)

# Shared metrics
total_messages = len(filtered)
total_words = int(filtered["word_count"].sum())
media_shared = int(filtered["media_count"].sum())
links_shared = int(filtered["link_count"].sum())
participants = filtered.loc[
    filtered["user"] != "Group Notification", "user"
].nunique()

with overview_tab:
    st.markdown("## Top statistics")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total messages", f"{total_messages:,}")
    k2.metric("Total words", f"{total_words:,}")
    k3.metric("Media shared", f"{media_shared:,}")
    k4.metric("Links shared", f"{links_shared:,}")
    k5.metric("Participants", f"{participants:,}")

    c1, c2 = st.columns(2)
    with c1:
        monthly = (
            filtered.set_index("date")
            .resample("MS")
            .size()
            .rename("Messages")
            .reset_index()
        )
        monthly["Month"] = monthly["date"].dt.strftime("%b %Y")
        fig = px.bar(monthly, x="Month", y="Messages", title="Monthly message volume")
        st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)

    with c2:
        type_counts = filtered["message_type"].value_counts().rename_axis("Type").reset_index(name="Messages")
        fig = px.pie(
            type_counts, names="Type", values="Messages",
            title="Forwarded vs normal messages", hole=0.58
        )
        st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)

    st.markdown("### Highlights")
    daily_counts = filtered.groupby(filtered["date"].dt.date).size()
    monthly_counts = filtered.groupby(filtered["date"].dt.to_period("M")).size()
    weekday_counts = filtered["weekday"].value_counts()
    h1, h2, h3 = st.columns(3)
    if not daily_counts.empty:
        h1.metric("Busiest day", str(daily_counts.idxmax()), f"{daily_counts.max():,} messages")
    if not monthly_counts.empty:
        h2.metric("Busiest month", monthly_counts.idxmax().strftime("%B %Y"), f"{monthly_counts.max():,} messages")
    if not weekday_counts.empty:
        h3.metric("Most active weekday", weekday_counts.idxmax(), f"{weekday_counts.max():,} messages")

    st.markdown("### Daily activity")
    daily = filtered.groupby(filtered["date"].dt.date).size().rename("Messages").reset_index()
    daily.columns = ["Date", "Messages"]
    fig = px.line(daily, x="Date", y="Messages", markers=True, title="Messages per day")
    fig.update_traces(line=dict(width=2))
    st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)

with timeline_tab:
    st.markdown("## Timeline & activity map")
    daily = filtered.groupby(filtered["date"].dt.date).size().rename("Messages").reset_index()
    daily.columns = ["Date", "Messages"]
    fig = px.area(daily, x="Date", y="Messages", title="Daily message timeline")
    st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)

    a, b = st.columns(2)
    with a:
        hourly = filtered.groupby("hour").size().reindex(range(24), fill_value=0).rename("Messages").reset_index()
        hourly.columns = ["Hour", "Messages"]
        fig = px.bar(hourly, x="Hour", y="Messages", title="Activity by hour")
        fig.update_xaxes(dtick=1)
        st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)
    with b:
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday = filtered["weekday"].value_counts().reindex(weekday_order, fill_value=0).rename("Messages").reset_index()
        weekday.columns = ["Weekday", "Messages"]
        fig = px.bar(weekday, x="Weekday", y="Messages", title="Activity by weekday")
        st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)

    render_calendar_heatmap(filtered, theme_name)

    # Weekday x hour heatmap
    pivot = filtered.pivot_table(
        index="weekday", columns="hour", values="message",
        aggfunc="count", fill_value=0
    ).reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
    fig = px.imshow(
        pivot, aspect="auto", color_continuous_scale="Teal",
        labels=dict(x="Hour", y="Weekday", color="Messages"),
        title="Weekly activity map — weekday × hour"
    )
    st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)

with people_tab:
    st.markdown("## Most busy users")
    user_df = filtered[filtered["user"] != "Group Notification"]
    if user_df.empty:
        st.info("No participant messages in this selection.")
    else:
        counts = user_df["user"].value_counts().head(20).sort_values().reset_index()
        counts.columns = ["User", "Messages"]
        fig = px.bar(
            counts, x="Messages", y="User", orientation="h",
            title="Top 20 participants by messages",
        )
        st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)

        word_user = user_df.groupby("user")["word_count"].sum().sort_values(ascending=False).head(10).reset_index()
        word_user.columns = ["User", "Words"]
        fig = px.bar(word_user, x="User", y="Words", title="Top participants by words")
        st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)

        st.markdown("### Participant summary")
        summary = user_df.groupby("user").agg(
            Messages=("message", "size"),
            Words=("word_count", "sum"),
            Media=("media_count", "sum"),
            Links=("link_count", "sum"),
        ).sort_values("Messages", ascending=False).reset_index()
        st.dataframe(summary, use_container_width=True, hide_index=True)

with words_tab:
    st.markdown("## Word cloud & emoji analysis")
    useful_words, emoji_counter = prepare_analysis(filtered)

    st.markdown("### Word cloud")
    render_wordcloud(useful_words, theme_name)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Most common words")
        common = Counter(useful_words).most_common(20)
        if common:
            common_df = pd.DataFrame(common, columns=["Word", "Count"])
            fig = px.bar(common_df.sort_values("Count"), x="Count", y="Word", orientation="h", title="Top 20 words")
            st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)
        else:
            st.info("No words available.")

    with c2:
        st.markdown("### Emoji analysis")
        if emoji_counter:
            emoji_df = pd.DataFrame(
                emoji_counter.most_common(20), columns=["Emoji", "Count"]
            )
            fig = px.bar(
                emoji_df.sort_values("Count"),
                x="Count", y="Emoji", orientation="h",
                title="Top 20 emojis",
            )
            st.plotly_chart(chart_layout(fig, theme_name), use_container_width=True)
            st.dataframe(emoji_df, use_container_width=True, hide_index=True)
        else:
            st.info("No emojis found in the selected messages.")

with messages_tab:
    st.markdown("## Search and inspect messages")
    query = st.text_input("Search message text", placeholder="Type a word, phrase, or URL...")
    view_df = filtered.copy()
    if query:
        view_df = view_df[
            view_df["message"].str.contains(query, case=False, na=False, regex=False)
        ]

    display_cols = [
        "date", "user", "message", "message_type",
        "word_count", "media_count", "link_count"
    ]
    st.caption(f"{len(view_df):,} matching messages")
    st.dataframe(
        view_df[display_cols].sort_values("date", ascending=False),
        use_container_width=True,
        hide_index=True,
        height=560,
    )

# ============================================================
# DOWNLOADS
# ============================================================
st.divider()
d1, d2, d3 = st.columns([2, 2, 3])
with d1:
    csv_bytes = full_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Download all chat data (CSV)",
        data=csv_bytes,
        file_name="whatsapp_analytics_all_messages.csv",
        mime="text/csv",
        use_container_width=True,
    )
with d2:
    filtered_bytes = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Download filtered data (CSV)",
        data=filtered_bytes,
        file_name="whatsapp_analytics_filtered.csv",
        mime="text/csv",
        use_container_width=True,
    )
with d3:
    st.markdown(
        '<p class="small-note">Your uploaded chat is processed in this Streamlit session. '
        'Avoid uploading conversations containing information you do not want to process.</p>',
        unsafe_allow_html=True,
    )
