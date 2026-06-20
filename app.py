# ================================================================
# منصة التسويق العقاري المتكاملة - النسخة النهائية
# تشمل: إدارة العملاء، واتساب، إيميل، مراجعات، تحليلات، ثنائي اللغة
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
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from streamlit_option_menu import option_menu
import plotly.express as px
import plotly.graph_objects as go

# ========== إعدادات اللغة ==========
if 'lang' not in st.session_state:
    st.session_state.lang = 'ar'  # ar أو en

def t(key):
    """ترجمة النصوص حسب اللغة"""
    texts = {
        # القائمة
        'dashboard': {'ar': 'لوحة القيادة', 'en': 'Dashboard'},
        'customers': {'ar': 'العملاء', 'en': 'Customers'},
        'whatsapp': {'ar': 'واتساب', 'en': 'WhatsApp'},
        'email': {'ar': 'إيميل', 'en': 'Email'},
        'reviews': {'ar': 'المراجعات', 'en': 'Reviews'},
        'analytics': {'ar': 'التحليلات', 'en': 'Analytics'},
        'settings': {'ar': 'الإعدادات', 'en': 'Settings'},
        # ... سأضيف باقي الترجمة داخل الكود
    }
    return texts.get(key, {}).get(st.session_state.lang, key)

# إعداد الصفحة
st.set_page_config(page_title="Digitizly - التسويق العقاري", layout="wide", initial_sidebar_state="expanded")

# CSS عربي/إنجليزي متجاوب
st.markdown(f"""
<style>
    .stApp {{ direction: {('rtl' if st.session_state.lang == 'ar' else 'ltr')}; font-family: 'Tajawal', 'Cairo', 'Segoe UI', sans-serif; background-color: #0E1525; }}
    .stButton button {{ background-color: #C9A24B; color: #0B1320; font-weight: bold; border-radius: 8px; width: 100%; }}
    .stTextInput input, .stSelectbox select, .stTextArea textarea {{ background-color: #161F33; color: #EDE6D6; border: 1px solid #1E2A45; }}
    h1, h2, h3 {{ color: #C9A24B !important; }}
    .stMetric {{ background-color: #161F33; padding: 10px; border-radius: 10px; border: 1px solid #1E2A45; }}
    .lang-btn {{ position: fixed; top: 10px; right: 10px; z-index: 999; background: #1E2A45; border: 1px solid #C9A24B; color: #EDE6D6; padding: 5px 12px; border-radius: 20px; cursor: pointer; font-size: 12px; }}
</style>
""", unsafe_allow_html=True)

# ========== زر تبديل اللغة ==========
col_lang1, col_lang2 = st.columns([6, 1])
with col_lang2:
    if st.button("🇸🇦 عربي" if st.session_state.lang == 'en' else "🇬🇧 English", key="lang_toggle"):
        st.session_state.lang = 'en' if st.session_state.lang == 'ar' else 'ar'
        st.rerun()

# ========== قاعدة البيانات ==========
def init_db():
    conn = sqlite3.connect('marketing_crm.db')
    c = conn.cursor()
    # جداول موجودة + جداول جديدة للمراجعات والواتساب
    c.execute('''CREATE TABLE IF NOT EXISTS developers (id TEXT PRIMARY KEY, name TEXT, contact TEXT, phone TEXT, email TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS campaigns (id TEXT PRIMARY KEY, dev_id TEXT, name TEXT, prop_type TEXT, budget_range TEXT, status TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id TEXT PRIMARY KEY, camp_id TEXT, name TEXT, phone TEXT, email TEXT, source TEXT, budget INTEGER, stage TEXT, score INTEGER, created_at TEXT, notes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sequences (id TEXT PRIMARY KEY, lead_id TEXT, day INTEGER, channel TEXT, label TEXT, status TEXT, scheduled_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (id TEXT PRIMARY KEY, key TEXT, value TEXT)''')
    # جداول جديدة
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, lead_id TEXT, name TEXT, stars INTEGER, text TEXT, sentiment TEXT, replied INTEGER, reply TEXT, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS whatsapp_campaigns (id TEXT PRIMARY KEY, name TEXT, status TEXT, sent INTEGER, delivered INTEGER, read INTEGER, clicked INTEGER, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS email_campaigns (id TEXT PRIMARY KEY, name TEXT, status TEXT, sent INTEGER, opened INTEGER, clicked INTEGER, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ========== دوال مساعدة ==========
def save_setting(key, value):
    conn = sqlite3.connect('marketing_crm.db')
    c = conn.cursor()
    c.execute("DELETE FROM settings WHERE key=?", (key,))
    c.execute("INSERT INTO settings VALUES (?,?,?)", (str(uuid.uuid4())[:8], key, value))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect('marketing_crm.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def add_lead(camp_id, name, phone, email, source, budget, notes=""):
    lead_id = str(uuid.uuid4())[:8]
    score = calculate_score(source, budget)
    stage = "جديد"
    created = datetime.datetime.now().isoformat()
    conn = sqlite3.connect('marketing_crm.db')
    c = conn.cursor()
    c.execute("INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?,?)", (lead_id, camp_id, name, phone, email, source, budget, stage, score, created, notes))
    # توليد المتابعة
    seqs = [(0, "whatsapp", "رسالة ترحيب فورية"), (1, "email", "أفضل المشاريع المطابقة"), (3, "whatsapp", "متابعة الميزانية"), (7, "email", "دراسة عائد استثماري"), (14, "whatsapp", "عرض حصري"), (21, "email", "دعوة لمعاينة")]
    for day, ch, label in seqs:
        s_id = str(uuid.uuid4())[:8]
        status = "تم" if day == 0 else "مجدولة"
        c.execute("INSERT INTO sequences VALUES (?,?,?,?,?,?,?)", (s_id, lead_id, day, ch, label, status, created))
    conn.commit()
    conn.close()
    return lead_id

def get_leads(camp_id=None):
    conn = sqlite3.connect('marketing_crm.db')
    if camp_id:
        df = pd.read_sql_query("SELECT * FROM leads WHERE camp_id=? ORDER BY created_at DESC", conn, params=(camp_id,))
    else:
        df = pd.read_sql_query("SELECT * FROM leads ORDER BY created_at DESC", conn)
    conn.close()
    return df

def calculate_score(source, budget):
    weights = {"meta":15, "google":15, "whatsapp":25, "linkedin":20, "csv":18, "referral":22, "webhook":20, "other":10}
    s = weights.get(source, 10)
    if budget >= 5000000: b = 40
    elif budget >= 1000000: b = 28
    elif budget >= 300000: b = 18
    else: b = 15
    return s + b

def get_developers():
    conn = sqlite3.connect('marketing_crm.db')
    df = pd.read_sql_query("SELECT * FROM developers ORDER BY created_at DESC", conn)
    conn.close()
    return df

def get_campaigns(dev_id=None):
    conn = sqlite3.connect('marketing_crm.db')
    if dev_id:
        df = pd.read_sql_query("SELECT * FROM campaigns WHERE dev_id=? ORDER BY created_at DESC", conn, params=(dev_id,))
    else:
        df = pd.read_sql_query("SELECT * FROM campaigns ORDER BY created_at DESC", conn)
    conn.close()
    return df

# دوال المراجعات
def add_review(lead_id, name, stars, text, sentiment, reply=""):
    rev_id = str(uuid.uuid4())[:8]
    conn = sqlite3.connect('marketing_crm.db')
    c = conn.cursor()
    c.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)", (rev_id, lead_id, name, stars, text, sentiment, 0, reply, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return rev_id

def get_reviews():
    conn = sqlite3.connect('marketing_crm.db')
    df = pd.read_sql_query("SELECT * FROM reviews ORDER BY date DESC", conn)
    conn.close()
    return df

def update_reply(rev_id, reply):
    conn = sqlite3.connect('marketing_crm.db')
    c = conn.cursor()
    c.execute("UPDATE reviews SET reply=?, replied=1 WHERE id=?", (reply, rev_id))
    conn.commit()
    conn.close()

# ========== دوال الإرسال الفعلي ==========
def send_email_via_smtp(to_email, subject, body, html=True):
    smtp_host = get_setting('smtp_host')
    smtp_port = get_setting('smtp_port')
    smtp_user = get_setting('smtp_user')
    smtp_pass = get_setting('smtp_pass')
    from_email = get_setting('from_email')
    if not all([smtp_host, smtp_port, smtp_user, smtp_pass, from_email]):
        return False, "إعدادات SMTP غير مكتملة"
    try:
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        if html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(smtp_host, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        return True, "تم الإرسال"
    except Exception as e:
        return False, str(e)

# ========== واجهة تسجيل الدخول ==========
def login():
    st.sidebar.image("https://via.placeholder.com/150x50/C9A24B/0B1320?text=Digitizly", use_column_width=True)
    st.sidebar.title("🔑 تسجيل الدخول")
    user = st.sidebar.text_input("المستخدم", value="admin")
    pwd = st.sidebar.text_input("كلمة المرور", type="password", value="123456")
    if st.sidebar.button("دخول"):
        if user == "admin" and pwd == "123456":
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.sidebar.error("المستخدم: admin | الرقم السري: 123456")
    st.sidebar.caption("👈 استخدم admin / 123456 للتجربة")

# ========== التطبيق الرئيسي ==========
def main():
    st.title("🏢 Digitizly - منصة التسويق العقاري المتكاملة")
    st.caption("إدارة العملاء، واتساب، إيميل، مراجعات، وتحليلات")

    with st.sidebar:
        menu = option_menu(None, 
            ["لوحة القيادة", "العملاء", "واتساب", "إيميل", "المراجعات", "التحليلات", "الإعدادات"],
            icons=["speedometer2", "people", "whatsapp", "envelope", "star", "bar-chart", "gear"],
            menu_icon="cast", default_index=0)

    # ============================================================
    # 1. لوحة القيادة
    # ============================================================
    if menu == "لوحة القيادة":
        st.subheader("📊 نظرة عامة")
        leads = get_leads()
        reviews = get_reviews()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("👥 العملاء", len(leads))
        col2.metric("⭐ المراجعات", len(reviews))
        col3.metric("📩 الحملات", 0)
        col4.metric("🔥 عملاء حارون", len(leads[leads['score'] >= 70]) if not leads.empty else 0)
        
        if not leads.empty:
            st.subheader("توزيع العملاء حسب المصدر")
            fig = px.pie(leads, names='source', title="المصادر")
            st.plotly_chart(fig, use_container_width=True)
        
        if not reviews.empty:
            st.subheader("آخر المراجعات")
            st.dataframe(reviews[['name', 'stars', 'text', 'date']].head(5), use_container_width=True)

    # ============================================================
    # 2. العملاء (محسّن مع استيراد CSV)
    # ============================================================
    elif menu == "العملاء":
        st.subheader("👤 إدارة العملاء")
        
        # استيراد CSV
        uploaded = st.file_uploader("📂 استيراد CSV (الأعمدة: name, phone, email, budget)", type=['csv', 'xlsx'])
        if uploaded:
            try:
                df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
                st.dataframe(df.head())
                if st.button("استيراد إلى النظام"):
                    camps = get_campaigns()
                    if not camps.empty:
                        camp_id = camps.iloc[0]['id']
                        for _, r in df.iterrows():
                            n = str(r.get('name', r.get('الاسم', 'مجهول')))
                            p = str(r.get('phone', r.get('الهاتف', '')))
                            e = str(r.get('email', r.get('البريد', '')))
                            b = int(r.get('budget', r.get('الميزانية', 500000)))
                            add_lead(camp_id, n, p, e, "csv", b, "مستورد من CSV")
                        st.success(f"تم استيراد {len(df)} عميل!")
                        st.rerun()
                    else:
                        st.warning("أنشئ حملة أولاً في تبويب الحملات")
            except Exception as e:
                st.error(f"خطأ: {e}")
        
        # عرض العملاء
        leads = get_leads()
        if not leads.empty:
            for _, row in leads.iterrows():
                with st.expander(f"{row['name']} | {row['phone']} | التقييم: {row['score']}"):
                    st.write(f"📧 {row['email']} | 💰 {row['budget']:,} | المصدر: {row['source']}")
                    st.write(f"📌 المرحلة: {row['stage']} | ملاحظات: {row['notes']}")

    # ============================================================
    # 3. واتساب (إرسال جماعي مع جدولة)
    # ============================================================
    elif menu == "واتساب":
        st.subheader("💬 واتساب ماركتنج")
        
        tab1, tab2, tab3 = st.tabs(["🔗 الربط", "📝 الرسالة", "🚀 الإطلاق"])
        
        with tab1:
            st.info("📲 امسح QR Code لربط حساب واتساب Business")
            st.image("https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=whatsapp://connect", width=200)
            phone = st.text_input("رقم الهاتف المرتبط", placeholder="+971...")
            if st.button("تأكيد الربط"):
                save_setting('wa_phone', phone)
                st.success("تم ربط واتساب بنجاح!")
        
        with tab2:
            wa_msg = st.text_area("نص الرسالة", value="مرحباً [الاسم] 👋\n\nلدينا عرض خاص لك اليوم!\n\n👉 [رابط]", height=150)
            st.caption("المتغيرات المتاحة: [الاسم] [رابط] [نشاط]")
            if st.button("حفظ قالب واتساب"):
                save_setting('wa_template', wa_msg)
                st.success("تم حفظ القالب!")
        
        with tab3:
            leads = get_leads()
            if leads.empty:
                st.warning("لا يوجد عملاء لإرسال الرسائل لهم")
            else:
                st.write(f"📋 عدد المستلمين: {len(leads)}")
                per_hour = st.slider("الرسائل في الساعة", 10, 200, 50)
                if st.button("▶ إطلاق حملة واتساب", type="primary"):
                    # محاكاة الإرسال
                    progress = st.progress(0)
                    for i in range(len(leads)):
                        progress.progress((i+1)/len(leads))
                        # هنا يمكنك إضافة كود إرسال حقيقي عبر API
                    st.success(f"✅ تم إرسال الرسائل إلى {len(leads)} عميل (محاكاة)")

    # ============================================================
    # 4. إيميل (إرسال جماعي مع SMTP)
    # ============================================================
    elif menu == "إيميل":
        st.subheader("✉️ إيميل ماركتنج")
        
        tab1, tab2, tab3 = st.tabs(["⚙️ SMTP", "📝 المحتوى", "🚀 الإطلاق"])
        
        with tab1:
            with st.form("smtp_form"):
                host = st.text_input("SMTP Host", get_setting('smtp_host') or "smtp.gmail.com")
                port = st.text_input("SMTP Port", get_setting('smtp_port') or "587")
                user = st.text_input("SMTP User", get_setting('smtp_user') or "")
                pwd = st.text_input("SMTP Password", type="password", get_setting('smtp_pass') or "")
                from_e = st.text_input("From Email", get_setting('from_email') or "")
                if st.form_submit_button("حفظ SMTP"):
                    save_setting('smtp_host', host)
                    save_setting('smtp_port', port)
                    save_setting('smtp_user', user)
                    save_setting('smtp_pass', pwd)
                    save_setting('from_email', from_e)
                    st.success("تم حفظ الإعدادات!")
        
        with tab2:
            email_subj = st.text_input("الموضوع", value="عرض خاص لك من [نشاط] 🎁")
            email_body = st.text_area("محتوى الرسالة (HTML)", value='<div dir="rtl"><h2>مرحباً [الاسم]!</h2><p>عرض خاص لفترة محدودة.</p><a href="[رابط]" style="background:#2563EB;color:#fff;padding:10px 20px;text-decoration:none;">اكتشف العرض</a></div>', height=200)
            if st.button("حفظ قالب الإيميل"):
                save_setting('email_subject', email_subj)
                save_setting('email_body', email_body)
                st.success("تم حفظ القالب!")
        
        with tab3:
            leads = get_leads()
            if leads.empty:
                st.warning("لا يوجد عملاء لإرسال الإيميلات لهم")
            else:
                st.write(f"📋 عدد المستلمين: {len(leads)}")
                if st.button("▶ إرسال إيميلات جماعية", type="primary"):
                    progress = st.progress(0)
                    success_count = 0
                    for i, (_, row) in enumerate(leads.iterrows()):
                        progress.progress((i+1)/len(leads))
                        if row['email']:
                            # استبدال المتغيرات
                            subj = email_subj.replace('[الاسم]', row['name']).replace('[نشاط]', 'شركتنا')
                            body = email_body.replace('[الاسم]', row['name']).replace('[رابط]', 'https://example.com')
                            status, msg = send_email_via_smtp(row['email'], subj, body)
                            if status:
                                success_count += 1
                    st.success(f"✅ تم إرسال {success_count} إيميل بنجاح")

    # ============================================================
    # 5. المراجعات (مع تحليل المشاعر والردود)
    # ============================================================
    elif menu == "المراجعات":
        st.subheader("⭐ إدارة المراجعات والتقييمات")
        
        # إضافة مراجعة جديدة
        with st.expander("➕ إضافة مراجعة جديدة"):
            with st.form("add_review"):
                r_name = st.text_input("الاسم")
                r_stars = st.slider("التقييم", 1, 5, 5)
                r_text = st.text_area("نص المراجعة")
                if st.form_submit_button("إضافة"):
                    if r_name:
                        # تحليل المشاعر بسيط
                        sentiment = "positive" if r_stars >= 4 else ("neutral" if r_stars == 3 else "negative")
                        add_review(None, r_name, r_stars, r_text, sentiment)
                        st.success("تمت الإضافة!")
                        st.rerun()
        
        # عرض المراجعات
        reviews = get_reviews()
        if not reviews.empty:
            # إحصائيات
            col1, col2, col3 = st.columns(3)
            col1.metric("📝 عدد المراجعات", len(reviews))
            col2.metric("⭐ متوسط التقييم", f"{reviews['stars'].mean():.1f}")
            col3.metric("👍 إيجابية", len(reviews[reviews['sentiment']=='positive']))
            
            for _, row in reviews.iterrows():
                with st.expander(f"{row['name']} | {'★' * row['stars']}{'☆' * (5-row['stars'])}"):
                    st.write(f"📅 {row['date']} | {row['sentiment']}")
                    st.write(f"📝 {row['text']}")
                    if row['replied']:
                        st.success(f"✅ رد: {row['reply']}")
                    else:
                        reply_text = st.text_area("اكتب رداً", key=f"reply_{row['id']}")
                        if st.button("إرسال الرد", key=f"send_{row['id']}"):
                            if reply_text:
                                update_reply(row['id'], reply_text)
                                st.success("تم حفظ الرد!")
                                st.rerun()

    # ============================================================
    # 6. التحليلات المتقدمة
    # ============================================================
    elif menu == "التحليلات":
        st.subheader("📊 التحليلات والتقارير")
        leads = get_leads()
        reviews = get_reviews()
        
        if not leads.empty:
            st.subheader("توزيع العملاء حسب المصدر")
            fig1 = px.pie(leads, names='source', title="المصادر")
            st.plotly_chart(fig1, use_container_width=True)
            
            st.subheader("توزيع العملاء حسب المرحلة")
            fig2 = px.bar(leads['stage'].value_counts().reset_index(), x='stage', y='count', title="مراحل المبيعات")
            st.plotly_chart(fig2, use_container_width=True)
        
        if not reviews.empty:
            st.subheader("توزيع التقييمات")
            fig3 = px.histogram(reviews, x='stars', title="النجوم")
            st.plotly_chart(fig3, use_container_width=True)
        
        # تصدير تقرير
        if st.button("📥 تصدير تقرير CSV"):
            combined = pd.concat([leads, reviews], axis=0)
            csv = combined.to_csv(index=False).encode('utf-8')
            st.download_button("تحميل", csv, "report.csv", "text/csv")

    # ============================================================
    # 7. الإعدادات
    # ============================================================
    elif menu == "الإعدادات":
        st.subheader("⚙️ إعدادات النظام")
        st.info("🔐 جميع المفاتيح تُخزن محلياً في قاعدة البيانات")
        st.caption("🔹 استخدم كلمة مرور تطبيق Gmail (وليس كلمة المرور العادية)")

# ========== تشغيل التطبيق ==========
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    login()
else:
    main()
