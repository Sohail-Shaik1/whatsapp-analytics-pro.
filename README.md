# WhatsApp Analytics Pro

A Streamlit dashboard for analyzing WhatsApp exported chat TXT or ZIP files.

## Features
- Upload WhatsApp `.txt` or `.zip` exports
- Overall group or individual participant filters
- Date range and message type filters
- Message, word, media and link statistics
- Monthly, daily, hourly and weekday charts
- Weekly activity heatmap and weekday/hour map
- Busy users and participant summary
- Word cloud, common words and emoji analysis
- Search messages and download CSV files
- Dark/light appearance and wide layout

## Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Create and activate a virtual environment (recommended).
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Start the app:

   ```bash
   streamlit run app.py
   ```

## Exporting a WhatsApp chat

In WhatsApp, open the chat or group, choose **Export chat**, and save the `.txt` file or ZIP export. Upload it in the app.

## Date format note
The app includes a checkbox for day-first dates. If your export shows dates like `04/10/2026` and means 4 October, enable it before analyzing.

## Important limitations
- WhatsApp exports vary by phone, language, operating system and export settings. This parser supports common Android bracketed timestamps and common iOS dash-separated timestamps. If your export uses a different format, its timestamp pattern may need to be added.
- Group notification detection is heuristic. A system notification that resembles `Sender: message` can be ambiguous.
- Media counts are based on omitted-media placeholders in the text export. A text-only export cannot reveal every attachment's actual type or file size.
- Word cloud and common-word analysis are language-dependent; this starter version uses basic tokenization and English stop words.
- All analytics are descriptive and based on the exported text; they do not recover deleted messages or data not included in the export.
