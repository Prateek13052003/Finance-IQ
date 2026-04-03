

import streamlit as st
import os, json, threading, queue, time, sys
from datetime import datetime
from pathlib import Path
import textwrap
import re
from dotenv import load_dotenv


env_path = Path(__file__).parent / ".env"
print("ENV PATH:", env_path)  # debug
print("ENV EXISTS:", env_path.exists())  # debug

load_dotenv(dotenv_path=env_path)

print("SERPER FROM ENV:", os.getenv("SERPER_API_KEY"))  # debug

# ── Add src/ to Python path so 'from finance.crew import ...' works ────────────
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="FinanceIQ",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS  — refined dark-accent theme
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>

/* Global */
body, .stApp {
    background: #0b0f19;
    color: #e6edf3;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0f172a;
    border-right: 1px solid #1e293b;
}

/* Hero */
.hero {
    background: linear-gradient(135deg, #111827, #1e293b);
    padding: 2rem;
    border-radius: 14px;
    margin-bottom: 1.5rem;
}
.hero h1 {
    font-size: 2rem;
    font-weight: 700;
}
.hero p {
    color: #9ca3af;
}

/* Cards */
.metric-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
}

/* Report */
.report-wrap {
    background: #0f172a;
    border-radius: 14px;
    padding: 2rem;
    line-height: 1.8;
    font-size: 0.95rem;
}

/* Headings */
.report-wrap h1, .report-wrap h2 {
    color: #60a5fa;
    margin-top: 1.2rem;
}

/* Buttons */
.stButton button {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    border-radius: 8px;
    border: none;
    color: white;
    font-weight: 600;
}

/* Logs */
.log-box {
    background: #020617;
    border-radius: 10px;
    padding: 1rem;
    font-size: 0.8rem;
}

</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS & DIRECTORIES
# ══════════════════════════════════════════════════════════════════════════════
HISTORY_DIR = Path("history")
OUTPUT_DIR  = Path("output")
HISTORY_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
DEFAULTS = {
    "report":            None,
    "logs":              [],
    "running":           False,
    "company":           "",
    "duration":          0.0,
    "sentiment":         "Neutral",
    "compare_a":         None,
    "compare_b":         None,
    "compare_company_a": "",
    "compare_company_b": "",
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def load_history(limit: int = 25) -> list[dict]:
    records = []
    for f in sorted(HISTORY_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            with open(f) as fp:
                records.append(json.load(fp))
        except Exception:
            pass
    return records


def save_to_history(company, report, duration):
    ts = datetime.now()
    rec = {
        "company": company,
        "report": report,
        "timestamp": ts.isoformat(),
        "display_time": ts.strftime("%d %b %Y, %H:%M"),
        "duration_sec": round(duration),
    }

    slug = f"{company.lower().replace(' ', '_')}_{ts.strftime('%Y%m%d_%H%M%S')}"
    with open(HISTORY_DIR / f"{slug}.json", "w") as f:
        json.dump(rec, f, indent=2)
    return rec

def analyze_sentiment(text: str) -> str:
    t = text.lower()
    pos = sum(t.count(w) for w in [
        "growth","profit","strong","revenue","opportunity","bullish",
        "gain","record","increase","expand","positive","outperform",
    ])
    neg = sum(t.count(w) for w in [
        "loss","decline","weak","risk","decrease","bearish",
        "debt","drop","concern","layoff","lawsuit","negative",
    ])
    if pos > neg + 3:  return "Positive"
    if neg > pos + 3:  return "Negative"
    return "Neutral"

def sentiment_badge(s: str) -> str:
    cls = {"Positive": "badge-pos", "Negative": "badge-neg"}.get(s, "badge-neu")
    icon = {"Positive": "▲", "Negative": "▼", "Neutral": "◆"}.get(s, "◆")
    return f'<span class="badge {cls}">{icon} {s}</span>'

def check_api_keys() -> tuple[bool, bool]:
    return bool(os.getenv("GROQ_API_KEY")), bool(os.getenv("SERPER_API_KEY"))

def export_pdf(report_text: str, company: str) -> bytes | None:
    """Convert markdown report → PDF bytes using fpdf2."""
    try:
        from fpdf import FPDF
        import textwrap
        import re

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(13, 40, 71)
        pdf.multi_cell(0, 10, f"Research Report: {company}")
        pdf.ln(4)

        # Metadata
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}  |  FinanceIQ", ln=True)
        pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
        pdf.ln(6)

        # Clean markdown
        clean = (report_text
                 .replace("**", "").replace("__", "")
                 .replace("##", "").replace("#", "")
                 .replace("*", "").replace("`", ""))

        # Main content
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(0, 0, 0)

        usable_width = pdf.w - pdf.l_margin - pdf.r_margin

        for line in clean.split("\n"):
            line = line.strip()

            if not line:
                pdf.ln(3)
                continue

            safe = line.encode("latin-1", "replace").decode("latin-1")

            chunks = [safe[i:i+80] for i in range(0, len(safe), 80)]

            for chunk in chunks:
                chunk = chunk.strip()
                if not chunk:
                    continue

                while pdf.get_string_width(chunk) > usable_width:
                    chunk = chunk[:-1]

                if not chunk:
                    continue

                try:
                    pdf.multi_cell(0, 6, chunk)
                except Exception:
                    continue

        return bytes(pdf.output())

    except ImportError:
        return None

# ══════════════════════════════════════════════════════════════════════════════
# CREW CALLBACK  — thread-safe log collection
# ══════════════════════════════════════════════════════════════════════════════
class LiveCallback:
    def __init__(self, log_queue: queue.Queue):
        self.q = log_queue
        self.task_num = 0

    def step(self, output) -> None:
        """Fires after each agent reasoning step."""
        try:
            for attr in ("log", "thought", "text", "output"):
                val = getattr(output, attr, None)
                if val and isinstance(val, str) and val.strip():
                    self.q.put(("step", val[:400]))
                    return
            self.q.put(("step", str(output)[:300]))
        except Exception:
            pass

    def task_done(self, output) -> None:
        """Fires when a task completes."""
        self.task_num += 1
        try:
            desc = getattr(output, "description", "") or ""
            label = desc[:60] + "…" if len(desc) > 60 else desc
        except Exception:
            label = f"Task {self.task_num}"
        self.q.put(("task", f"✅ Task {self.task_num} complete — {label}"))


# ══════════════════════════════════════════════════════════════════════════════
# CREW RUNNER  — executed in a background thread
# ══════════════════════════════════════════════════════════════════════════════
def _run_crew(company: str, log_q: queue.Queue, result_q: queue.Queue) -> None:
    try:
        from finance.crew import ResearchCrew          # type: ignore

        log_q.put(("info", f"🚀 Initialising agents for: {company}"))
        cb           = LiveCallback(log_q)
        crew_inst    = ResearchCrew()

        # Patch callbacks onto the Crew object AFTER creation
        crew_obj               = crew_inst.crew()
        crew_obj.step_callback = cb.step
        crew_obj.task_callback = cb.task_done

        result = crew_obj.kickoff(inputs={"company": company})
        result_q.put(("success", result.raw or ""))

    except Exception as exc:
        result_q.put(("error", str(exc)))


def launch_crew(company: str) -> tuple[queue.Queue, queue.Queue, threading.Thread, float]:
    log_q, result_q = queue.Queue(), queue.Queue()
    t = threading.Thread(target=_run_crew, args=(company, log_q, result_q), daemon=True)
    t.start()
    return log_q, result_q, t, time.time()


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📈 FinanceIQ")
    st.caption("AI-Powered Financial Research")
    st.divider()

    st.markdown("### 🔑 API Status")
    groq_ok, serper_ok = check_api_keys()

    def key_badge(ok): return f'<span class="badge {"badge-ok" if ok else "badge-err"}">{"✓ Connected" if ok else "✗ Missing"}</span>'
    st.markdown(f"Groq &nbsp;&nbsp;&nbsp; {key_badge(groq_ok)}", unsafe_allow_html=True)
    st.markdown(f"Serper {key_badge(serper_ok)}", unsafe_allow_html=True)

    if not groq_ok or not serper_ok:
        st.warning("Add missing keys to your `.env` file.")

    st.divider()
    st.markdown("### ⚙️ Settings")
    enable_logs = st.toggle("Show Live Agent Logs", value=True)
    enable_pdf  = st.toggle("Enable PDF Export",    value=True)

    st.divider()
    st.markdown("### 📊 Stats")
    history_records = load_history()
    st.metric("Total Reports", len(history_records))
    if history_records:
        sentiments   = [r.get("sentiment", "Neutral") for r in history_records]
        pos_pct      = round(sentiments.count("Positive") / len(sentiments) * 100)
        st.metric("Positive Outlook", f"{pos_pct}%")
        recent       = history_records[0]
        st.caption(f"Last: **{recent['company']}** — {recent['display_time']}")

    st.divider()
    st.caption("Powered by CrewAI · Groq LLaMA 3.3 · Serper")

# ══════════════════════════════════════════════════════════════════════════════
# HERO HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
    <h1>📈 FinanceIQ — AI Research Agent</h1>
    <p>Two-agent pipeline · Real-time web search · Verified facts only · Instant PDF export</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_research, tab_history, tab_compare = st.tabs(["🔍 Research", "📁 History", "⚖️ Compare"])


# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  TAB 1 — RESEARCH                                                           │
# └─────────────────────────────────────────────────────────────────────────────┘
with tab_research:

    col_inp, col_btn = st.columns([5, 1])
    with col_inp:
        company_input = st.text_input(
            "company",
            placeholder="Enter company name (e.g. Apple, Reliance, Tesla…)",
            label_visibility="collapsed",
            disabled=st.session_state.running,
        )
    with col_btn:
        run_clicked = st.button(
            "🚀 Research",
            use_container_width=True,
            type="primary",
            disabled=st.session_state.running,
        )

    # ── Trigger research ───────────────────────────────────────────────────────
    if run_clicked:
        if not company_input.strip():
            st.warning("Please enter a company name.")
        elif not groq_ok:
            st.error("GROQ_API_KEY is missing from your .env file.")
        else:
            company = company_input.strip()
            st.session_state.update(
                running=True, report=None, logs=[], company=company
            )

            log_q, result_q, thread, t0 = launch_crew(company)
            all_logs   = []
            task_count = 0

            # ── Live UI during run ─────────────────────────────────────────────
            st.markdown(f"#### Researching **{company}**…")
            progress_bar  = st.progress(0, text="Agents initialising…")
            status_slot   = st.empty()
            log_slot      = st.empty() if enable_logs else None

            while thread.is_alive() or not result_q.empty():
                # Drain the log queue
                drained = False
                while not log_q.empty():
                    drained     = True
                    kind, msg   = log_q.get_nowait()
                    ts          = datetime.now().strftime("%H:%M:%S")
                    cls         = {"task": "log-task", "step": "log-step",
                                   "info": "log-info", "error": "log-error"}.get(kind, "log-step")
                    all_logs.append(f'<span class="{cls}">[{ts}] {msg}</span>')

                    if kind == "task":
                        task_count += 1
                        progress_bar.progress(
                            min(task_count / 2, 0.97),
                            text=f"Task {task_count} / 2 complete…",
                        )
                    elif kind == "error":
                        status_slot.error(msg)

                if log_slot and drained:
                    shown    = all_logs[-30:]
                    log_html = "<br>".join(shown)
                    log_slot.markdown(
                        f'<div class="log-box">{log_html}</div>',
                        unsafe_allow_html=True,
                    )

                if not result_q.empty():
                    break
                time.sleep(0.25)

            thread.join(timeout=5)

            # ── Process result ─────────────────────────────────────────────────
            progress_bar.progress(1.0, text="✅ Research complete!")
            status_slot.empty()

            if not result_q.empty():
                status, payload = result_q.get_nowait()
                duration = time.time() - t0
                if status == "success":
                    st.session_state.report    = payload
                    st.session_state.logs      = all_logs
                    st.session_state.duration  = duration
                    st.session_state.sentiment = analyze_sentiment(payload)
                    save_to_history(company, payload, duration)
                    st.success(f"✅ Completed in {duration:.0f}s — report ready below.")
                else:
                    st.error(f"❌ Crew error: {payload}")
            else:
                st.warning("Crew finished but returned no output.")

            st.session_state.running = False
            st.rerun()

    # ── Display report ─────────────────────────────────────────────────────────
    if st.session_state.report:
        report    = st.session_state.report
        company   = st.session_state.company
        sentiment = st.session_state.sentiment
        duration  = st.session_state.duration

        # Metrics row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Company",       company)
        m2.metric("Research Time", f"{duration:.0f}s")
        m3.metric("Word Count",    f"{len(report.split()):,}")
        with m4:
            st.metric("Sentiment", "")
            st.markdown(sentiment_badge(sentiment), unsafe_allow_html=True)

        st.divider()

        # Download row
        dc1, dc2, _ = st.columns([1.3, 1.3, 4])
        with dc1:
            st.download_button(
                "⬇️ Markdown",
                data=report,
                file_name=f"{company.replace(' ', '_')}_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dc2:
            if enable_pdf:
                pdf_bytes = export_pdf(report, company)
                if pdf_bytes:
                    st.download_button(
                        "⬇️ PDF",
                        data=pdf_bytes,
                        file_name=f"{company.replace(' ', '_')}_report.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                else:
                    st.caption("Run `pip install fpdf2` for PDF export.")

        # Report body
        st.markdown(f'<div class="report-wrap">{report}</div>', unsafe_allow_html=True)

        # Agent logs (collapsed)
        if st.session_state.logs:
            with st.expander("🤖 Raw Agent Logs", expanded=False):
                log_html = "<br>".join(st.session_state.logs)
                st.markdown(
                    f'<div class="log-box" style="height:400px">{log_html}</div>',
                    unsafe_allow_html=True,
                )

    elif not st.session_state.running:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">🔍</div>
            <h3>Start a Research</h3>
            <p>Type a company name above and click <strong>🚀 Research</strong>.<br>
               The AI crew will search the web and generate a verified financial report.</p>
        </div>
        """, unsafe_allow_html=True)


# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  TAB 2 — HISTORY                                                            │
# └─────────────────────────────────────────────────────────────────────────────┘
with tab_history:
    st.markdown("### 📁 Research History")

    records = load_history()

    if not records:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">📂</div>
            <h3>No history yet</h3>
            <p>Run your first research report to see it appear here.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        hc1, hc2 = st.columns([5, 1])
        with hc1:
            st.caption(f"{len(records)} report(s) saved locally in `history/`")
        with hc2:
            if st.button("🗑️ Clear All", type="secondary"):
                for f in HISTORY_DIR.glob("*.json"):
                    f.unlink()
                st.success("History cleared.")
                st.rerun()

        st.divider()

        for i, rec in enumerate(records):
            sent  = rec.get("sentiment", "Neutral")
            emoji = {"Positive": "🟢", "Negative": "🔴", "Neutral": "🟡"}.get(sent, "🟡")

            with st.expander(
                f"{emoji} **{rec['company']}** — {rec.get('display_time', 'No time')} · {rec.get('duration_sec', 0)}s",
                expanded=False,
):
                col_report, col_actions = st.columns([4, 1])

                with col_report:
                        st.markdown('<div class="report-wrap">', unsafe_allow_html=True)
                        st.markdown(rec["report"])
                        st.markdown('</div>', unsafe_allow_html=True)   # use rec["report"], NOT report




                    

                with col_actions:
                    st.markdown(f"**Sentiment:**<br>{sentiment_badge(sent)}", unsafe_allow_html=True)
                    st.markdown(f"**Duration:** {rec.get('duration_sec', 0)}s")
                    st.divider()
                    st.download_button(
                        "⬇️ MD",
                        data=rec["report"],
                        file_name=f"{rec['company'].replace(' ', '_')}_report.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key=f"hist_md_{i}",
                    )
                    if enable_pdf:
                        pdf_b = export_pdf(rec["report"], rec["company"])
                        if pdf_b:
                            st.download_button(
                                "⬇️ PDF",
                                data=pdf_b,
                                file_name=f"{rec['company'].replace(' ', '_')}_report.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"hist_pdf_{i}",
                            )


# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  TAB 3 — COMPARE                                                            │
# └─────────────────────────────────────────────────────────────────────────────┘
with tab_compare:
    st.markdown("### ⚖️ Side-by-Side Company Comparison")
    st.caption("Runs two independent research crews sequentially and displays reports side-by-side.")

    cc1, cc2 = st.columns(2)
    with cc1:
        cmp_a = st.text_input("Company A", placeholder="e.g. Apple",     key="inp_cmp_a",
                              disabled=st.session_state.running)
    with cc2:
        cmp_b = st.text_input("Company B", placeholder="e.g. Microsoft", key="inp_cmp_b",
                              disabled=st.session_state.running)

    cmp_btn = st.button(
        "⚖️ Compare Both",
        type="primary",
        disabled=st.session_state.running or not (cmp_a.strip() and cmp_b.strip()),
    )

    if cmp_btn and cmp_a.strip() and cmp_b.strip():
        st.session_state.update(
            running=True,
            compare_a=None, compare_b=None,
            compare_company_a=cmp_a.strip(),
            compare_company_b=cmp_b.strip(),
        )

        # ── Run A ───────────────────────────────────────────────────────────
        with st.status(f"🔍 Researching **{cmp_a}**…", expanded=True) as status_a:
            lq, rq, t, t0 = launch_crew(cmp_a.strip())
            log_slot_a = st.empty()
            logs_a = []
            while t.is_alive() or not rq.empty():
                while not lq.empty():
                    kind, msg = lq.get_nowait()
                    ts = datetime.now().strftime("%H:%M:%S")
                    cls = {"task":"log-task","step":"log-step","info":"log-info"}.get(kind,"log-step")
                    logs_a.append(f'<span class="{cls}">[{ts}] {msg}</span>')
                if enable_logs:
                    log_slot_a.markdown(
                        f'<div class="log-box">{"<br>".join(logs_a[-15:])}</div>',
                        unsafe_allow_html=True,
                    )
                if not rq.empty(): break
                time.sleep(0.25)
            t.join(timeout=5)
            if not rq.empty():
                s, p = rq.get_nowait()
                st.session_state.compare_a = p if s == "success" else None
            status_a.update(label=f"✅ {cmp_a} complete!", state="complete")

        # ── Run B ───────────────────────────────────────────────────────────
        with st.status(f"🔍 Researching **{cmp_b}**…", expanded=True) as status_b:
            lq, rq, t, t0 = launch_crew(cmp_b.strip())
            log_slot_b = st.empty()
            logs_b = []
            while t.is_alive() or not rq.empty():
                while not lq.empty():
                    kind, msg = lq.get_nowait()
                    ts = datetime.now().strftime("%H:%M:%S")
                    cls = {"task":"log-task","step":"log-step","info":"log-info"}.get(kind,"log-step")
                    logs_b.append(f'<span class="{cls}">[{ts}] {msg}</span>')
                if enable_logs:
                    log_slot_b.markdown(
                        f'<div class="log-box">{"<br>".join(logs_b[-15:])}</div>',
                        unsafe_allow_html=True,
                    )
                if not rq.empty(): break
                time.sleep(0.25)
            t.join(timeout=5)
            if not rq.empty():
                s, p = rq.get_nowait()
                st.session_state.compare_b = p if s == "success" else None
            status_b.update(label=f"✅ {cmp_b} complete!", state="complete")

        # Save both to history
        if st.session_state.compare_a:
            save_to_history(cmp_a.strip(), st.session_state.compare_a, 0)
        if st.session_state.compare_b:
            save_to_history(cmp_b.strip(), st.session_state.compare_b, 0)

        st.session_state.running = False
        st.rerun()

    # ── Display comparison ────────────────────────────────────────────────────
    if st.session_state.compare_a or st.session_state.compare_b:
        ra, rb = st.columns(2)

        def render_compare_col(col, report, company):
            with col:
                if report:
                    sent  = analyze_sentiment(report)
                    st.markdown(f'<div class="compare-header">🏢 {company}</div>', unsafe_allow_html=True)
                    st.markdown(sentiment_badge(sent), unsafe_allow_html=True)
                    st.download_button(
                        "⬇️ MD",
                        data=report,
                        file_name=f"{company.replace(' ', '_')}_report.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key=f"cmp_dl_{company}",
                    )
                    st.markdown(
                        f'<div class="report-wrap" style="max-height:700px;overflow-y:auto">'
                        f'{report}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.info(f"No report for {company}.")

        render_compare_col(ra, st.session_state.compare_a, st.session_state.compare_company_a or cmp_a)
        render_compare_col(rb, st.session_state.compare_b, st.session_state.compare_company_b or cmp_b)

    elif not (st.session_state.compare_a or cmp_btn):
        st.markdown("""
        <div class="empty-state">
            <div class="icon">⚖️</div>
            <h3>No comparison yet</h3>
            <p>Enter two companies above and click <strong>⚖️ Compare Both</strong>.</p>
        </div>
        """, unsafe_allow_html=True)




st.write("SERPER KEY:", os.getenv("SERPER_API_KEY"))