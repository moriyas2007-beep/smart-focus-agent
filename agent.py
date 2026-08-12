import os
import datetime
import time
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

# Setup API key from env or Streamlit secrets
api_key = os.getenv("GEMINI_API_KEY")
if not api_key and "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="Smart Focus Agent", page_icon="⚡", layout="centered")

# --- Helper Function: Dynamic Model Discovery & Safe API Call ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_available_models(key):
    """Fetches the list of active models available for the given API key in real-time."""
    try:
        client = genai.Client(api_key=key)
        models_list = []
        for m in client.models.list():
            name = m.name
            if "gemini" in name.lower() and "embed" not in name.lower():
                models_list.append(name)
        # Ensure the verified working model is prioritized
        if "models/gemini-flash-lite-latest" in models_list:
            models_list.remove("models/gemini-flash-lite-latest")
            models_list.insert(0, "models/gemini-flash-lite-latest")
        return models_list if models_list else ["models/gemini-flash-lite-latest", "gemini-1.5-flash"]
    except Exception:
        return ["models/gemini-flash-lite-latest", "gemini-flash-lite-latest", "gemini-1.5-flash"]

def safe_generate_text(key, model_name, prompt):
    """Executes a safe API call with automatic fallbacks, prioritizing the verified Lite model."""
    client = genai.Client(api_key=key)
    
    # Priority order for model execution
    candidate_models = [
        model_name,
        "models/gemini-flash-lite-latest",
        "gemini-flash-lite-latest",
        "models/gemini-1.5-flash",
        "gemini-1.5-flash"
    ]
    
    for m in candidate_models:
        if not m:
            continue
        try:
            res = client.models.generate_content(model=m, contents=prompt)
            if res and res.text:
                return res.text
        except Exception:
            # Continue seamlessly to the next fallback model if 404 or other error occurs
            continue
            
    return "Could not receive a response from the AI at this time. Please check your API key."

# --- Session State Management ---
if "completed_pomodoros" not in st.session_state:
    st.session_state.completed_pomodoros = 0

if "daily_tasks" not in st.session_state:
    st.session_state.daily_tasks = []

if "weekly_tasks" not in st.session_state:
    st.session_state.weekly_tasks = []

if "weekly_streak" not in st.session_state:
    st.session_state.weekly_streak = {i: False for i in range(7)}

if "theme" not in st.session_state:
    st.session_state.theme = "Classic Purple"

# --- Sound Notification Function ---
def play_sound():
    audio_html = """
        <audio autoplay style="display:none;">
            <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
        </audio>
    """
    components.html(audio_html, height=0)

# --- Dynamic CSS Theme Styling (RTL support) ---
themes_css = {
    "Classic Purple": {
        "bg": "#f8f9fa",
        "card_bg": "linear-gradient(135deg, #6a11cb 0%, #2575fc 100%)",
        "card_text": "white",
        "btn_bg": "linear-gradient(90deg, #2575fc 0%, #6a11cb 100%)",
        "metric_val": "#2575fc",
        "text": "#212529"
    },
    "Dark Mode": {
        "bg": "#0e1117",
        "card_bg": "linear-gradient(135deg, #1f2937 0%, #111827 100%)",
        "card_text": "#f3f4f6",
        "btn_bg": "linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%)",
        "metric_val": "#60a5fa",
        "text": "#e5e7eb"
    },
    "Focus Green": {
        "bg": "#f4fbf7",
        "card_bg": "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)",
        "card_text": "white",
        "btn_bg": "linear-gradient(90deg, #11998e 0%, #38ef7d 100%)",
        "metric_val": "#11998e",
        "text": "#1a3a2a"
    },
    "Pomodoro Orange": {
        "bg": "#fff8f5",
        "card_bg": "linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%)",
        "card_text": "white",
        "btn_bg": "linear-gradient(90deg, #ff416c 0%, #ff4b2b 100%)",
        "metric_val": "#ff416c",
        "text": "#3d1e18"
    }
}

active_theme = themes_css[st.session_state.theme]

st.markdown(f"""
    <style>
    .stApp {{
        background-color: {active_theme["bg"]};
        color: {active_theme["text"]};
        direction: rtl;
        text-align: right;
    }}
    .stMarkdown, .stCheckbox, .stTextInput, .stSelectbox {{
        direction: rtl;
        text-align: right;
    }}
    .info-card {{
        background: {active_theme["card_bg"]};
        color: {active_theme["card_text"]};
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.15);
        margin-bottom: 20px;
    }}
    .metric-card {{
        background: white;
        padding: 18px;
        border-radius: 14px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
        text-align: center;
    }}
    .metric-value {{
        font-size: 26px;
        font-weight: 700;
        color: {active_theme["metric_val"]};
    }}
    .metric-label {{
        font-size: 13px;
        color: #6c757d;
    }}
    .stButton>button {{
        width: 100%;
        border-radius: 12px;
        height: 48px;
        font-weight: 600;
        background: {active_theme["btn_bg"]};
        color: white;
        border: none;
        transition: all 0.3s ease;
    }}
    .stButton>button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(0,0,0,0.2);
    }}
    </style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ הגדרות ומידע")
    
    if not api_key:
        api_key = st.text_input("הכנס GEMINI_API_KEY:", type="password")
    
    # Dynamic model selection based on active key
    if api_key:
        available_models = fetch_available_models(api_key)
        selected_model = st.selectbox("🤖 בחר דגם AI פעיל:", available_models)
    else:
        selected_model = "gemini-1.5-flash"

    st.subheader("🎨 ערכת נושא (Theme)")
    theme_choice = st.selectbox(
        "בחר עיצוב:",
        ["Classic Purple", "Dark Mode", "Focus Green", "Pomodoro Orange"],
        index=["Classic Purple", "Dark Mode", "Focus Green", "Pomodoro Orange"].index(st.session_state.theme)
    )
    if theme_choice != st.session_state.theme:
        st.session_state.theme = theme_choice
        st.rerun()

    st.markdown("---")

    st.subheader("🎧 מוזיקת רקע לריכוז")
    audio_tracks = {
        "ללא צלילי רקע": None,
        "🌧️ קולות גשם ורעמים": "https://cdn.pixabay.com/download/audio/2022/05/16/audio_db6591201e.mp3",
        "☕ אווירת בית קפה (Cafe)": "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",
        "🌊 גלי ים מרגיעים": "https://cdn.pixabay.com/download/audio/2022/03/15/audio_1a1e053f3f.mp3",
        "🌲 צלילי יער וציפורים": "https://cdn.pixabay.com/download/audio/2021/09/06/audio_74c10c14b3.mp3"
    }

    selected_music = st.selectbox("בחר צלילי רקע:", list(audio_tracks.keys()))

    if selected_music != "ללא צלילי רקע" and audio_tracks[selected_music]:
        st.audio(audio_tracks[selected_music], loop=True)
        st.caption("💡 הנגן מופעל במצב בלופ (Loop) רציף.")

    st.markdown("---")

    with st.expander("🍅 מהי טכניקת פומודורו?"):
        st.markdown("""
        **טכניקת פומודורו** היא שיטה לניהול זמן שמטרתה להגביר את הריכוז ולמנוע עייפות.
        
        **איך זה עובד?**
        1. **בוחרים משימה** להתמקד בה.
        2. **מכוונים טיימר ל-25 דקות** ועובדים ללא הסחות דעת.
        3. **לוקחים הפסקה קצרה** של 5 דקות.
        4. **לאחר 4 סבבים**, נהנים מהפסקה ארוכה של 15–30 דקות.
        """)

# --- Main Header ---
st.title("⚡ Smart Focus Agent")

st.markdown("""
<div class="info-card">
    <h3 style="margin-top:0; color:white;">🎯 סוכן העבודה הממוקדת שלך</h3>
    <p style="margin-bottom:0; opacity: 0.9;">
        ניהול משימות חכם, פירוק יעדים אוטומטי, מעקב רצף ודו"חות AI.
    </p>
</div>
""", unsafe_allow_html=True)

# --- 1. Weekly Streak & Daily Status Tracker ---
st.subheader("🔥 הרצף השבועי שלי (Weekly Streak)")

days_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
today_idx = datetime.datetime.now().weekday()

if st.session_state.daily_tasks and all(t["done"] for t in st.session_state.daily_tasks):
    st.session_state.weekly_streak[today_idx] = True

cols_days = st.columns(7)
for i, col in enumerate(cols_days):
    day_name = days_names[i]
    is_done = st.session_state.weekly_streak[i]
    is_today = (i == today_idx)
    
    with col:
        status_icon = "✅" if is_done else ("📌" if is_today else "⚪")
        border_style = "border: 2px solid #2575fc;" if is_today else "border: 1px solid #ddd;"
        
        st.markdown(f"""
        <div style="text-align: center; background: white; padding: 10px 5px; border-radius: 10px; {border_style}">
            <div style="font-size: 12px; color: #6c757d;">{day_name}</div>
            <div style="font-size: 20px; margin-top: 4px;">{status_icon}</div>
        </div>
        """, unsafe_allow_html=True)

completed_days_count = sum(1 for v in st.session_state.weekly_streak.values() if v)
st.caption(f"🏆 השלמת **{completed_days_count} מתוך 7** ימי עבודה השבוע!")

st.markdown("---")

# --- 2. Tasks Management (Daily & Weekly) ---
st.subheader("📋 משימות יומיות ושבועיות")

tab_daily, tab_weekly = st.tabs(["☀️ משימות יומיות", "📅 משימות שבועיות"])

with tab_daily:
    col_input, col_add = st.columns([3, 1])
    with col_input:
        new_daily = st.text_input("משימה יומית חדשה:", key="new_daily_input", label_visibility="collapsed", placeholder="הוסף משימה להיום...")
    with col_add:
        if st.button("➕ הוסף", key="add_daily_btn"):
            if new_daily.strip():
                st.session_state.daily_tasks.append({"task": new_daily.strip(), "done": False})
                st.rerun()

    if st.session_state.daily_tasks:
        for idx, task_obj in enumerate(st.session_state.daily_tasks):
            is_done = st.checkbox(task_obj["task"], value=task_obj["done"], key=f"daily_task_{idx}")
            st.session_state.daily_tasks[idx]["done"] = is_done

        col_del, col_mark = st.columns(2)
        with col_del:
            if st.button("🗑️ נקה הושלמו", key="clean_daily"):
                st.session_state.daily_tasks = [t for t in st.session_state.daily_tasks if not t["done"]]
                st.rerun()
        with col_mark:
            if st.button("✨ סיים את משימות היום", key="mark_today_done"):
                st.session_state.weekly_streak[today_idx] = True
                st.balloons()
                st.success("כל הכבוד! היום סומן בהצלחה ברצף השבועי שלך!")
                st.rerun()
    else:
        st.info("אין כרגע משימות יומיות ברשימה.")

with tab_weekly:
    col_w_input, col_w_add = st.columns([3, 1])
    with col_w_input:
        new_weekly = st.text_input("משימה שבועית חדשה:", key="new_weekly_input", label_visibility="collapsed", placeholder="הוסף יעד שבועי רחב...")
    with col_w_add:
        if st.button("➕ הוסף", key="add_weekly_btn"):
            if new_weekly.strip():
                st.session_state.weekly_tasks.append({"task": new_weekly.strip(), "done": False})
                st.rerun()

    if st.session_state.weekly_tasks:
        for idx, task_obj in enumerate(st.session_state.weekly_tasks):
            col_check, col_breakdown = st.columns([4, 1])
            with col_check:
                is_done = st.checkbox(task_obj["task"], value=task_obj["done"], key=f"weekly_task_{idx}")
                st.session_state.weekly_tasks[idx]["done"] = is_done
            
            with col_breakdown:
                if st.button("🪄 פרק", key=f"break_w_{idx}"):
                    if api_key:
                        with st.spinner("מפרק למשימות יומיות..."):
                            prompt = f"פרק את המשימה השבועית '{task_obj['task']}' ל-3 משימות יומיות קטנות וברורות. החזר אך ורק את המשימות מופרדות בשורה חדשה ללא מספרים."
                            try:
                                text_res = safe_generate_text(api_key, selected_model, prompt)
                                subtasks = [line.strip("- ").strip() for line in text_res.split("\n") if line.strip()]
                                for sub in subtasks:
                                    st.session_state.daily_tasks.append({"task": sub, "done": False})
                                st.success("המשימה פורקה והתווספה למשימות היומיות!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"שגיאה: {e}")
                    else:
                        st.warning("נדרש API Key של Gemini")

        if st.button("🗑️ נקה משימות שבועיות שהושלמו", key="clean_weekly"):
            st.session_state.weekly_tasks = [t for t in st.session_state.weekly_tasks if not t["done"]]
            st.rerun()
    else:
        st.info("אין כרגע משימות שבועיות ברשימה.")

st.markdown("---")

# --- 3. Timers and Break Ideas Generator ---
st.subheader("⚙️ טיימר פוקוס והפסקות")

col1, col2, col3 = st.columns(3)
with col1:
    work_mins = st.number_input("עבודה (דקות):", min_value=1, max_value=60, value=25)
with col2:
    short_break_mins = st.number_input("הפסקה קצרה:", min_value=1, max_value=30, value=5)
with col3:
    long_break_mins = st.number_input("הפסקה ארוכה:", min_value=5, max_value=60, value=15)

# Select agent communication tone
ai_tone = st.selectbox("טון מסר הסוכן (לסיום העבודה):", ["אנרגטי ומדרבן", "מצחיק וקליל", "מרגיע ומאזן", "קצר וענייני"])

current_cycle = (st.session_state.completed_pomodoros % 4) + 1
total_completed = st.session_state.completed_pomodoros

col_m1, col_m2 = st.columns(2)
with col_m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">סבב נוכחי במחזור</div>
        <div class="metric-value">סבב {current_cycle} / 4</div>
    </div>
    """, unsafe_allow_html=True)

with col_m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">סבבים שנשלמו היום</div>
        <div class="metric-value">{total_completed} ✨</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Display the completion message generated by the AI agent
if "last_ai_message" in st.session_state:
    st.success(f"🤖 **פסקת תוכן מהסוכן האישי (בטון {ai_tone}):**\n\n{st.session_state['last_ai_message']}")
    st.markdown("---")

tab_work, tab_break = st.tabs(["🚀 טיימר עבודה", "☕ טיימר הפסקה"])

with tab_work:
    st.write(f"התחל סבב עבודה ממוקד של **{work_mins} דקות**.")
    if st.button("▶️ התחל סבב עבודה"):
        st.info(f"סבב עבודה מס' {current_cycle} יצא לדרך! בהצלחה.")
        
        total_sec = work_mins * 60
        timer_ph = st.empty()
        prog_bar = st.progress(1.0)
        
        for rem in range(total_sec, -1, -1):
            m, s = divmod(rem, 60)
            timer_ph.metric(label="זמן עבודה נותר", value=f"{m:02d}:{s:02d}")
            prog_bar.progress(rem / total_sec)
            time.sleep(1)
            
        st.session_state.completed_pomodoros += 1
        play_sound()
        
        if api_key:
            prompt = f"המשתמש סיים סבב עבודה ממוקד של {work_mins} דקות! כתוב פסקת תוכן מדרבנת, מעצימה ומעניינת בעברית בטון '{ai_tone}' שמזמינה אותו לקחת הפסקה מפרגנת."
            try:
                msg = safe_generate_text(api_key, selected_model, prompt)
                st.session_state["last_ai_message"] = msg
            except Exception as e:
                st.session_state["last_ai_message"] = f"🔔 הגיע הזמן להפסקה! קום/י מהכיסא, התרענן/י וטען/י מצברים. (שגיאה: {e})"
        else:
            st.session_state["last_ai_message"] = "🔔 הגיע הזמן להפסקה! קום/י מהכיסא, התרענן/י וטען/י מצברים."

        st.rerun()

with tab_break:
    is_long_next = (st.session_state.completed_pomodoros > 0 and st.session_state.completed_pomodoros % 4 == 0)
    current_break_mins = long_break_mins if is_long_next else short_break_mins
    
    st.write(f"הפסקה מיועדת: **{'ארוכה (' + str(long_break_mins) + ' דק\')' if is_long_next else 'קצרה (' + str(short_break_mins) + ' דק\')'}**")
    
    if st.button("💡 הצע לי רעיון להפסקה איכותית (AI)"):
        if api_key:
            with st.spinner("מחשב רעיון..."):
                prompt = f"תן רעיון קצר, מרענן ובריא לפעילות של {current_break_mins} דקות הפסקה מעבודה על מחשב. בעברית, במשפט או שניים."
                try:
                    idea = safe_generate_text(api_key, selected_model, prompt)
                    st.info(f"🌱 **הצעה להפסקה:** {idea}")
                except Exception as e:
                    st.error(f"שגיאה: {e}")
    
    if st.button("☕ התחל טיימר הפסקה"):
        st.info("ההפסקה החלה! התרענן/י וקום/י מהכיסא.")
        
        total_sec = current_break_mins * 60
        timer_ph = st.empty()
        prog_bar = st.progress(1.0)
        
        for rem in range(total_sec, -1, -1):
            m, s = divmod(rem, 60)
            timer_ph.metric(label="זמן הפסקה נותר", value=f"{m:02d}:{s:02d}")
            prog_bar.progress(rem / total_sec)
            time.sleep(1)
            
        st.success("🔔 ההפסקה הסתיימה! אפשר לחזור לעבודה.")
        play_sound()

# --- 4. Weekly Insights & Daily Summaries ---
st.markdown("---")
st.subheader("📊 ניתוחים וסיכומים מבוססי AI")

tab_summary_daily, tab_summary_weekly = st.tabs(["📝 סיכום יומי", '📈 דו"ח תפוקה שבועי'])

with tab_summary_daily:
    if st.button("✨ חולל סיכום יום"):
        if api_key:
            with st.spinner("מכין סיכום..."):
                summary_prompt = f"המשתמש סיים {st.session_state.completed_pomodoros} סבבי פוקוס. כתוב סיכום יום מדרבן ומעצים בעברית."
                try:
                    summary_text = safe_generate_text(api_key, selected_model, summary_prompt)
                    st.session_state["daily_ai_summary"] = summary_text
                except Exception as e:
                    st.error(f"שגיאה ביצירת הסיכום: {e}")

    if "daily_ai_summary" in st.session_state:
        st.info(f"🏆 **סיכום היום שלך:**\n\n{st.session_state['daily_ai_summary']}")

with tab_summary_weekly:
    if st.button("🚀 חולל דו\"ח תפוקה שבועי מקיף"):
        if api_key:
            with st.spinner("מנתח את ביצועי השבוע החולף..."):
                weekly_data = f"""
                נתוני השבוע:
                - ימים בהם הרצף הושלם: {completed_days_count} מתוך 7.
                - סה"כ סבבי פוקוס שהושלמו היום/השבוע: {st.session_state.completed_pomodoros}.
                - משימות שבועיות שהושלמו: {sum(1 for t in st.session_state.weekly_tasks if t['done'])} מתוך {len(st.session_state.weekly_tasks)}.
                """
                
                weekly_prompt = f"""
                אתה יועץ פרודוקטיביות אישי. נתח את הנתונים השבועיים הבאים:
                {weekly_data}
                
                ערוך דו"ח תפוקה שבועי מעצים בעברית המורכב מ:
                1. 🌟 **תקציר הישגים מרכזי**
                2. 📊 **ניתוח התמדה ורצף**
                3. 💡 **3 טיפים מותאמים אישית לשבוע הבא**
                """
                try:
                    report_text = safe_generate_text(api_key, selected_model, weekly_prompt)
                    st.session_state["weekly_ai_report"] = report_text
                except Exception as e:
                    st.error(f"שגיאה ביצירת הדו\"ח: {e}")
        else:
            st.warning("נא לוודא שמפתח GEMINI_API_KEY מוגדר בקובץ .env או בסרגל הצד")

    if "weekly_ai_report" in st.session_state:
        st.success(f"📊 **דו\"ח תפוקה שבועי מ-Gemini:**\n\n{st.session_state['weekly_ai_report']}")