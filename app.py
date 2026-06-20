# ================================================================
# منصة التسويق العقاري - لوحة التحكم (app.py)
# تعمل على Streamlit Cloud
# ================================================================

import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib
import uuid
import random
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from streamlit_option_menu import option_menu
import plotly.express as px

st.set_page_config(page_title="منصة التسويق العقاري", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
    .stApp { direction: rtl; font-family: 'Tajawal', sans-serif; background-color: #0E1525; }
    .stButton button { background-color: #C9A24B; color: #0B1320; font-weight: bold; border-radius: 8px; width: 100%; }
    .stTextInput input, .stSelectbox select, .stTextArea textarea { background-color: #161F33; color: #EDE6D6; border: 1px solid #1E2A45; }
    h1, h2, h3 { color: #C9A24B !important; }
    .stMetric { background-color: #161F33; padding: 10px; border-radius: 10px; border: 1px solid #1E2A45; }
</style>
""", unsafe_allow_html=True)

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('marketing_crm.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS developers (id TEXT PRIMARY KEY, name TEXT, contact TEXT, phone TEXT, email TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS campaigns (id TEXT PRIMARY KEY, dev_id TEXT, name TEXT, prop_type TEXT, budget_range TEXT, status TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id TEXT PRIMARY KEY, camp_id TEXT, name TEXT, phone TEXT, email TEXT, source TEXT, budget INTEGER, stage TEXT, score INTEGER, created_at TEXT, notes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sequences (id TEXT PRIMARY KEY, lead_id TEXT, day INTEGER, channel TEXT, label TEXT, status TEXT, scheduled_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (id TEXT PRIMARY KEY, key TEXT, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS webhook_logs (id TEXT PRIMARY KEY, payload TEXT, received_at TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- دوال مساعدة ---
def hash_pass(pwd): return hashlib.sha256(pwd.encode()).hexdigest()
def save_setting(key, value):
    conn = sqlite3.connect('marketing_crm.db'); c = conn.cursor()
    c.execute("DELETE FROM settings WHERE key=?", (key,)); c.execute("INSERT INTO settings VALUES (?,?,?)", (str(uuid.uuid4())[:8], key, value)); conn.commit(); conn.close()
def get_setting(key):
    conn = sqlite3.connect('marketing_crm.db'); c = conn.cursor(); c.execute("SELECT value FROM settings WHERE key=?", (key,)); row = c.fetchone(); conn.close(); return row[0] if row else None

def add_developer(id, name, contact, phone, email):
    conn = sqlite3.connect('marketing_crm.db'); c = conn.cursor()
    c.execute("INSERT INTO developers VALUES (?,?,?,?,?,?)", (id, name, contact, phone, email, datetime.datetime.now().isoformat())); conn.commit(); conn.close()
def get_developers():
    conn = sqlite3.connect('marketing_crm.db'); df = pd.read_sql_query("SELECT * FROM developers ORDER BY created_at DESC", conn); conn.close(); return df

def add_campaign(id, dev_id, name, prop_type, budget_range):
    conn = sqlite3.connect('marketing_crm.db'); c = conn.cursor()
    c.execute("INSERT INTO campaigns VALUES (?,?,?,?,?,?,?)", (id, dev_id, name, prop_type, budget_range, "نشطة", datetime.datetime.now().isoformat())); conn.commit(); conn.close()
def get_campaigns(dev_id=None):
    conn = sqlite3.connect('marketing_crm.db')
    if dev_id: df = pd.read_sql_query("SELECT * FROM campaigns WHERE dev_id=? ORDER BY created_at DESC", conn, params=(dev_id,))
    else: df = pd.read_sql_query("SELECT * FROM campaigns ORDER BY created_at DESC", conn)
    conn.close(); return df

def calculate_score(source, budget):
    weights = {"meta":15, "google":15, "whatsapp":25, "linkedin":20, "csv":18, "referral":22, "webhook":20, "other":10}
    s = weights.get(source, 10)
    if budget >= 5000000: b = 40
    elif budget >= 1000000: b = 28
    elif budget >= 300000: b = 18
    else: b = 15
    return s + b

def add_lead(camp_id, name, phone, email, source, budget, notes=""):
    lead_id = str(uuid.uuid4())[:8]; score = calculate_score(source, budget); stage = "جديد"; created = datetime.datetime.now().isoformat()
    conn = sqlite3.connect('marketing_crm.db'); c = conn.cursor()
    c.execute("INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?,?)", (lead_id, camp_id, name, phone, email, source, budget, stage, score, created, notes))
    seqs = [(0, "whatsapp", "رسالة ترحيب فورية"), (1, "email", "أفضل المشاريع المطابقة"), (3, "whatsapp", "متابعة الميزانية"), (7, "email", "دراسة عائد استثماري"), (14, "whatsapp", "عرض حصري"), (21, "email", "دعوة لمعاينة")]
    for day, ch, label in seqs:
        s_id = str(uuid.uuid4())[:8]; status = "تم" if day == 0 else "مجدولة"
        c.execute("INSERT INTO sequences VALUES (?,?,?,?,?,?,?)", (s_id, lead_id, day, ch, label, status, created))
    conn.commit(); conn.close()
    return lead_id

def get_leads(camp_id=None):
    conn = sqlite3.connect('marketing_crm.db')
    if camp_id: df = pd.read_sql_query("SELECT * FROM leads WHERE camp_id=? ORDER BY created_at DESC", conn, params=(camp_id,))
    else: df = pd.read_sql_query("SELECT * FROM leads ORDER BY created_at DESC", conn)
    conn.close(); return df

def update_lead_stage(lead_id, new_stage):
    conn = sqlite3.connect('marketing_crm.db'); c = conn.cursor(); c.execute("UPDATE leads SET stage=? WHERE id=?", (new_stage, lead_id)); conn.commit(); conn.close()
def delete_lead(lead_id):
    conn = sqlite3.connect('marketing_crm.db'); c = conn.cursor(); c.execute("DELETE FROM sequences WHERE lead_id=?", (lead_id,)); c.execute("DELETE FROM leads WHERE id=?", (lead_id,)); conn.commit(); conn.close()
def get_sequences(lead_id):
    conn = sqlite3.connect('marketing_crm.db'); df = pd.read_sql_query("SELECT * FROM sequences WHERE lead_id=? ORDER BY day", conn, params=(lead_id,)); conn.close(); return df
def log_webhook(payload):
    conn = sqlite3.connect('marketing_crm.db'); c = conn.cursor()
    c.execute("INSERT INTO webhook_logs VALUES (?,?,?)", (str(uuid.uuid4())[:8], payload, datetime.datetime.now().isoformat())); conn.commit(); conn.close()
def get_webhook_logs():
    conn = sqlite3.connect('marketing_crm.db'); df = pd.read_sql_query("SELECT * FROM webhook_logs ORDER BY received_at DESC LIMIT 50", conn); conn.close(); return df

# دالة إرسال الإيميل
def send_real_email(to_email, subject, body):
    smtp_host = get_setting('smtp_host'); smtp_port = get_setting('smtp_port'); smtp_user = get_setting('smtp_user'); smtp_pass = get_setting('smtp_pass'); from_email = get_setting('from_email')
    if not all([smtp_host, smtp_port, smtp_user, smtp_pass, from_email]): return False, "إعدادات SMTP غير مكتملة."
    try:
        msg = MIMEMultipart(); msg['From'] = from_email; msg['To'] = to_email; msg['Subject'] = subject; msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP(smtp_host, int(smtp_port)); server.starttls(); server.login(smtp_user, smtp_pass); server.sendmail(from_email, to_email, msg.as_string()); server.quit()
        return True, "تم الإرسال"
    except Exception as e: return False, str(e)

# --- تسجيل الدخول ---
def login():
    st.sidebar.image("https://via.placeholder.com/150x50/C9A24B/0B1320?text=LeadGen+Pro", use_column_width=True)
    st.sidebar.title("🔑 دخول")
    user = st.sidebar.text_input("المستخدم", value="admin")
    pwd = st.sidebar.text_input("كلمة المرور", type="password", value="123456")
    if st.sidebar.button("دخول"):
        if user == "admin" and pwd == "123456": st.session_state['logged_in'] = True; st.rerun()
        else: st.sidebar.error("المستخدم: admin | الرقم السري: 123456")

# --- التطبيق الرئيسي ---
def main():
    st.title("🏢 منصة التسويق العقاري - مع Webhook")
    st.caption("الأن يمكنك استقبال العملاء تلقائياً من إعلانات ميتا عبر الرابط المخصص")

    with st.sidebar:
        menu = option_menu(None, ["لوحة القيادة", "المطورون", "الحملات", "العملاء", "توليد واستيراد", "المتابعة الآلية", "📩 Webhook", "الإرسال والإعدادات"],
                           icons=["speedometer2", "building", "folder", "people", "upload", "clock", "cloud-download", "gear"],
                           menu_icon="cast", default_index=0)

    if menu == "لوحة القيادة":
        st.subheader("📊 مؤشرات الأداء")
        devs = get_developers(); camps = get_campaigns(); leads = get_leads()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("المطورون", len(devs)); c2.metric("الحملات", len(camps)); c3.metric("إجمالي العملاء", len(leads))
        hot = len(leads[leads['score'] >= 70]) if not leads.empty else 0; c4.metric("عملاء حارون 🔥", hot)
        if not leads.empty:
            fig = px.pie(leads, names='source', title="المصادر")
            st.plotly_chart(fig, use_container_width=True)
            st.subheader("خط المبيعات")
            st.bar_chart(leads['stage'].value_counts())

    elif menu == "المطورون":
        st.subheader("🏢 إدارة المطورين")
        with st.form("add_dev"):
            c1, c2 = st.columns(2)
            with c1: did = st.text_input("المعرف", "dev_001"); name = st.text_input("اسم الشركة")
            with c2: contact = st.text_input("جهة التواصل"); phone = st.text_input("الهاتف"); email = st.text_input("البريد")
            if st.form_submit_button("إضافة مطور"): add_developer(did, name, contact, phone, email); st.success("تم!"); st.rerun()
        st.dataframe(get_developers(), use_container_width=True)

    elif menu == "الحملات":
        st.subheader("📁 إدارة الحملات")
        devs = get_developers(); dev_options = {row['name']: row['id'] for _, row in devs.iterrows()} if not devs.empty else {}
        with st.form("add_camp"):
            cid = st.text_input("معرف الحملة", "camp_001")
            dev_sel = st.selectbox("المطور", list(dev_options.keys())) if dev_options else "لا يوجد"
            cname = st.text_input("اسم الحملة"); ptype = st.selectbox("نوع العقار", ["شقة", "فيلا", "أرض", "تجاري"]); brange = st.text_input("نطاق الميزانية", "500K - 2M")
            if st.form_submit_button("إنشاء حملة"):
                if dev_options and dev_sel in dev_options: add_campaign(cid, dev_options[dev_sel], cname, ptype, brange); st.success("تم!"); st.rerun()
                else: st.error("أضف مطوراً أولاً")
        st.dataframe(get_campaigns(), use_container_width=True)

    elif menu == "العملاء":
        st.subheader("👤 العملاء المحتملين")
        camps = get_campaigns(); camp_opts = {row['name']: row['id'] for _, row in camps.iterrows()} if not camps.empty else {}
        sel_camp = st.selectbox("فلتر الحملة", ["الكل"] + list(camp_opts.keys()))
        df = get_leads(camp_opts[sel_camp]) if sel_camp != "الكل" and sel_camp in camp_opts else get_leads()
        if not df.empty:
            for _, row in df.iterrows():
                with st.expander(f"{row['name']} | {row['phone']} | التقييم: {row['score']} | {row['stage']}"):
                    col1, col2 = st.columns([3, 1])
                    col1.write(f"📧 {row['email']} | 💰 {row['budget']:,} | المصدر: {row['source']}")
                    stages = ["جديد", "تواصل", "مؤهل", "تحويل", "ملغي"]
                    idx = stages.index(row['stage']) if row['stage'] in stages else 0
                    new_stage = col2.selectbox("المرحلة", stages, index=idx, key=f"st_{row['id']}")
                    if new_stage != row['stage']: update_lead_stage(row['id'], new_stage); st.rerun()
                    if col2.button("🗑️", key=f"del_{row['id']}"): delete_lead(row['id']); st.rerun()
                    with st.expander("📨 جدول المتابعة"):
                        seq = get_sequences(row['id'])
                        if not seq.empty: st.dataframe(seq[['day', 'channel', 'label', 'status']])
        else: st.info("لا يوجد عملاء")

    elif menu == "توليد واستيراد":
        st.subheader("📥 توليد واستيراد")
        camps = get_campaigns(); camp_opts = {row['name']: row['id'] for _, row in camps.iterrows()} if not camps.empty else {}
        if not camp_opts: st.warning("أنشئ حملة أولاً")
        else:
            target = st.selectbox("الحملة المستهدفة", list(camp_opts.keys()))
            tab1, tab2, tab3 = st.tabs(["📂 CSV", "🔗 LinkedIn", "➕ يدوي"])
            with tab1:
                uploaded = st.file_uploader("رفع CSV/Excel", type=['csv', 'xlsx'])
                if uploaded:
                    df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
                    st.dataframe(df.head())
                    if st.button("استيراد"):
                        for _, r in df.iterrows():
                            n = r.get('الاسم', r.get('name', 'مجهول')); p = r.get('الهاتف', r.get('phone', '')); e = r.get('البريد', r.get('email', '')); b = int(r.get('الميزانية', r.get('budget', 500000)))
                            add_lead(camp_opts[target], str(n), str(p), str(e), "csv", b, "مستورد")
                        st.success("تم!"); st.rerun()
            with tab2:
                urls = st.text_area("روابط LinkedIn (كل سطر رابط)")
                if st.button("إضافة"):
                    for url in urls.split('\n'):
                        if url.strip():
                            name = url.split('/')[-1].replace('-', ' ').title()
                            add_lead(camp_opts[target], name, "+97150000000", "linkedin@lead.com", "linkedin", 1000000, f"رابط: {url}")
                    st.success("تم!"); st.rerun()
            with tab3:
                with st.form("manual"):
                    c1, c2 = st.columns(2)
                    with c1: n = st.text_input("الاسم"); ph = st.text_input("الهاتف")
                    with c2: em = st.text_input("البريد"); bd = st.number_input("الميزانية", min_value=10000, step=10000)
                    src = st.selectbox("المصدر", ["whatsapp", "meta", "google", "referral"])
                    if st.form_submit_button("إضافة"):
                        if n: add_lead(camp_opts[target], n, ph, em, src, bd, "يدوي"); st.success("تم!"); st.rerun()

    elif menu == "المتابعة الآلية":
        st.subheader("⏳ المتابعة الآلية")
        leads = get_leads()
        if leads.empty: st.info("لا يوجد عملاء")
        else:
            for _, row in leads.iterrows():
                with st.expander(f"{row['name']} - {row['stage']}"):
                    seq = get_sequences(row['id'])
                    if not seq.empty: st.dataframe(seq[['day', 'channel', 'label', 'status']])

    # ============================================================
    # 🔥 تبويب Webhook الجديد (لرؤية الطلبات الواردة من ميتا)
    # ============================================================
    elif menu == "📩 Webhook":
        st.subheader("📩 سجل الطلبات الواردة من إعلانات ميتا")
        st.info("🔗 هذا هو الرابط الذي سترسله إلى ميتا في إعدادات Lead Form: (سيعطيك إياه ملف webhook_api.py بعد تشغيله)")
        st.code("https://your-api-name.onrender.com/webhook/meta", language="text")
        st.caption("💡 يجب أن يكون معرف الحملة (campaign_id) موجوداً في الطلب، أو سيتم إضافته إلى حملة افتراضية.")
        
        logs = get_webhook_logs()
        if not logs.empty:
            st.dataframe(logs[['received_at', 'payload']], use_container_width=True)
        else:
            st.info("لم يتم استقبال أي طلب حتى الآن. انتظر حتى يرسل ميتا أول عميل.")

    elif menu == "الإرسال والإعدادات":
        st.subheader("⚙️ الإعدادات والإرسال الفعلي")
        with st.form("smtp_form"):
            host = st.text_input("SMTP Host", get_setting('smtp_host') or "smtp.gmail.com")
            port = st.text_input("SMTP Port", get_setting('smtp_port') or "587")
            user = st.text_input("SMTP User", get_setting('smtp_user') or "")
            pwd = st.text_input("SMTP Password", type="password", value=get_setting('smtp_pass') or "")
            from_e = st.text_input("From Email", get_setting('from_email') or "")
            if st.form_submit_button("حفظ SMTP"):
                save_setting('smtp_host', host); save_setting('smtp_port', port); save_setting('smtp_user', user); save_setting('smtp_pass', pwd); save_setting('from_email', from_e)
                st.success("تم حفظ الإعدادات!")
        st.divider()
        test_email = st.text_input("بريد تجريبي", "your_email@gmail.com")
        if st.button("إرسال إيميل تجريبي"):
            status, msg = send_real_email(test_email, "اختبار", "<h1>مرحباً</h1><p>النظام يعمل!</p>")
            st.success(msg) if status else st.error(msg)

if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    login()
else:
    main()
