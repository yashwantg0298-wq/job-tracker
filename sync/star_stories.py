"""Generate per-row STAR stories from Yashwant's resume.

Run after `sync.py decrypt`. Picks the best Technical + Non-Technical story
per row based on company/role archetype, then writes them to two new
fields: `STAR (Technical)` and `STAR (Non-Technical)`.

Uses 7 technical + 7 non-technical master stories — every detail traces
to the resume at C:\\Users\\yashw\\OneDrive\\Desktop\\Resume\\Genpact\\
Yashwant_Gupta_Resume_A_FPA_Corporate.pdf.

Run again to regenerate (overwrites existing STAR fields).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROWS_FILE = ROOT / "state" / "rows.json"


# ============================================================
# MASTER STORY BANK — every fact verifiable from the resume
# ============================================================

T1_RECONCILIATION = """\
QUESTION: "Tell me about a process improvement you drove in finance."

SITUATION: At Stemmons India we had high-volume supplier invoice and vendor reconciliation work, and breaks were piling up at month-end — slowing down close and creating noise in the FP&A pack.

TASK: Identify root causes, clear the backlog, and prevent recurrence — without disrupting the close calendar.

ACTION: Analysed the high-volume supplier and vendor data line-by-line, traced recurring breaks back to inconsistent vendor master data and timing differences in cross-charge journals, and restructured the reconciliation workflow so matching happened *before* sub-ledger close — not after. Documented the new SOP and trained the AP team on it.

RESULT: 30% reduction in reconciliation cycle time, recurring breaks dropped to near zero, and the month-end close became predictable enough that finance could commit to firmer reporting deadlines for senior leadership."""

T2_ZERO_AUDIT = """\
QUESTION: "Tell me about a complex month-end / year-end close you owned."

SITUATION: At Stemmons India I owned the monthly and year-end close cycle across multiple inter-company entities, with statutory deadlines and zero room for restatement.

TASK: Deliver a clean close every month — journals, reconciliations, intercompany trading, cross-charge accounting, and FS finalisation — feeding consolidated reporting to senior leadership.

ACTION: Built a structured close calendar with hard deadlines for each sub-process; ran intercompany reconciliations before entity-level close so cross-charge mismatches surfaced early; pre-prepared the schedules our internal and statutory auditors typically asked for, instead of reacting during the close window.

RESULT: Zero audit observations across two consecutive reporting cycles, faster month-end, and a stronger control documentation file that auditors began reusing as a template across our entities."""

T3_INTERCOMPANY = """\
QUESTION: "Walk me through an intercompany / cross-charge issue you handled."

SITUATION: Stemmons had inter-company trading and cross-charge accounting running across multiple entities at high volume — feeding consolidated reporting that leadership relied on.

TASK: Ensure cost allocation was accurate, eliminate mismatches between entities, and keep the consolidation tie-out clean every month.

ACTION: Mapped the end-to-end intercompany flow, instituted a pre-close matching step where both sides of every cross-charge were reconciled before either entity closed its sub-ledger, and built a standing schedule that flagged variances above a materiality threshold for finance review.

RESULT: Cross-charge mismatches at consolidation went to near zero, and monthly intercompany reconciliation no longer extended the close window. The schedule itself became part of the audit working-paper bundle."""

T4_DASHBOARDS = """\
QUESTION: "Tell me about a dashboard or MIS deliverable you built end-to-end."

SITUATION: Senior leadership at Stemmons needed real-time visibility into revenue, cost, and expense trends across departments — but existing reporting was static monthly PDFs lagging 5–7 days.

TASK: Build a dashboarding layer over our R2R outputs that leadership could act on, without forcing the team to learn a new tool overnight.

ACTION: Designed Excel-based dashboards using Pivots, INDEX-MATCH, SUMIFS, and dynamic ranges over Business Central data extracts; defined KPIs *with* the leadership team rather than guessing; embedded variance commentary directly into each view; built a one-click refresh macro so analyst effort was minutes not hours.

RESULT: Variance discussions moved from "what happened" to "what do we do next." The dashboards became the default artefact in the monthly leadership review. I'm currently extending this work into Power BI and SQL."""

T5_BUDGETING = """\
QUESTION: "Walk me through an annual budget / forecast you owned."

SITUATION: Stemmons ran a structured annual budgeting cycle across multiple departments — operations, procurement, business — with leadership expecting actuals-vs-plan tracking and clean variance commentary every month.

TASK: Drive the cycle end-to-end: consolidate departmental submissions, challenge weak assumptions, build the actuals-vs-plan tracker, and own the monthly variance commentary going to leadership.

ACTION: Sat one-on-one with each department head to walk through their submission and stress-test the underlying assumptions; rebuilt the budgeting template so cost drivers were explicit (not buried); set up the actuals-vs-plan tracker with automated variance commentary tied to drivers, not just GL accounts.

RESULT: The budget held up at leadership review, monthly variance discussions became driver-led rather than line-item-led, and dept heads started coming to finance pre-emptively when their numbers were trending off — instead of finance chasing them after."""

T6_GST_COMPLIANCE = """\
QUESTION: "Tell me about a compliance / regulatory deliverable you owned."

SITUATION: At Dhyey Consulting Services I owned end-to-end GST compliance for multiple client entities — CGST, SGST, IGST, and RCM — with quarterly and annual filing deadlines that couldn't slip.

TASK: Deliver 100% on-time, accurate filings; reconcile each client's purchase register against their GST returns; minimise tax exposure from input tax credit gaps.

ACTION: Built a recurring reconciliation between purchase register and GSTR data, flagged ITC mismatches before filing, processed salary journals / TDS entries / statutory adjustments alongside; coordinated client-side discrepancies through structured email trails so audit defence was clean.

RESULT: 100% on-time filing record across quarterly and annual cycles, minimised tax exposure for clients, and clean outcomes when statutory auditors picked up the GST workings."""

T7_AUTOMATION = """\
QUESTION: "Tell me about something you automated in your finance stack."

SITUATION: Stemmons had a small finance team handling MIS, R2R close, audit prep, and AP workflows in parallel — and recurring AP processing + report generation in Business Central was eating 1+ analyst-day per week.

TASK: Free up team bandwidth for higher-value FP&A work without compromising accuracy or audit-readiness.

ACTION: Identified the two highest-volume AP workflows, built automated routines inside Business Central / Navision (using the platform's native job queue and report scheduler), and set up the recurring financial reports to refresh and distribute on a fixed cadence — eliminating manual re-runs.

RESULT: Reclaimed roughly a day per week per analyst; the freed bandwidth went into the leadership dashboards and budgeting cycle work; and the new routines became the standard way that AP + reporting ran going forward."""


B1_INFLUENCING = """\
QUESTION: "Tell me about a time you challenged a senior stakeholder."

SITUATION: During Stemmons' annual budgeting cycle, the Operations head submitted a 22% headcount increase that didn't reconcile with the forecast revenue trajectory or our cost-per-unit benchmark.

TASK: Either accept the number (and risk a budget that wouldn't survive board review) or challenge a stakeholder twice my level of seniority — without alienating him.

ACTION: Built a one-page variance walk that broke his ask into volume-driven cost vs. structural cost; framed the conversation as "here's what your number assumes" rather than "your number is wrong"; proposed a phased headcount plan tied to a revenue trigger so he wasn't losing the ask, just sequencing it.

RESULT: He revised down to ~12% with a phased gate; the leadership review went through cleanly; and that one-page walk became my standard framing for every budget-challenging conversation since."""

B2_TRANSLATING_FINANCE = """\
QUESTION: "How do you translate financial data for non-finance audiences?"

SITUATION: Department heads at Stemmons (operations, procurement, business) needed to understand cost-centre performance, but they wouldn't read a traditional finance pack.

TASK: Make variance commentary something they would actually use — not just file.

ACTION: Rewrote variance narratives in plain business language ("we spent ₹X more on freight because volumes shifted to longer lanes" instead of "freight cost variance unfavourable ₹X"); tied each variance to one decision the dept head could make; walked through the first version one-on-one with each head until they could read it standalone.

RESULT: Department heads started flagging issues before month-end based on the dashboards; cost-optimisation initiatives surfaced from operations themselves rather than from finance; the plain-language pack format spread to other functions on leadership ask."""

B3_TIGHT_DEADLINES = """\
QUESTION: "How do you manage tight deadlines and parallel workstreams?"

SITUATION: Stemmons was scaling fast — monthly MIS, R2R close, audit prep, and AP workflows all ran in parallel with overlapping deadlines, on a small team.

TASK: Hit every deadline without slipping quality or burning out the team.

ACTION: Built a shared close calendar mapping every deliverable to a day and an owner; identified the two biggest AP time-sinks and automated them in Business Central — that alone freed about one analyst-day per week. Flagged audit asks proactively to the auditors so we weren't firefighting last-minute requests.

RESULT: Hit every monthly close across 20 months at Stemmons; audit was clean both years; and the freed bandwidth was redirected into the leadership dashboards and budgeting work."""

B4_CROSS_FUNCTIONAL = """\
QUESTION: "Tell me about a cross-functional collaboration that produced business value."

SITUATION: Cost-optimisation initiatives at Stemmons couldn't be driven from finance alone — operations and procurement had context on actual cost drivers that didn't show up cleanly in the GL.

TASK: Partner across functions to identify and execute cost-optimisation wins backed by data, not assumptions.

ACTION: Set up a recurring monthly walkthrough with operations and procurement using the dashboards I'd built, framed each variance as a question rather than a verdict, and asked each function to nominate one driver they could move. Followed up on commitments in the next monthly review.

RESULT: Cost-optimisation initiatives stopped being a finance push and became cross-functional ownership; multiple recurring savings landed with operations/procurement as the named owners; and finance's role shifted from policing variances to enabling decisions."""

B5_AUDIT_PARTNERSHIP = """\
QUESTION: "How do you handle internal / statutory auditors?"

SITUATION: Stemmons faced annual statutory audits and recurring internal audits, and historically the audit window meant the finance team was firefighting auditor asks on top of normal close work.

TASK: Make audits non-disruptive and outcomes clean — without losing close-cycle quality.

ACTION: Pre-prepared the schedules and reconciliations auditors typically asked for as part of the regular close — instead of reacting during the audit window. Maintained a structured working-paper folder with cross-references to GL, sub-ledger, and policy. Treated auditors as a partner: walked them through control documentation up front rather than waiting for them to dig.

RESULT: Zero audit observations across two consecutive reporting cycles; the audit window stopped being a fire drill; and the structured working-paper bundle became a reusable template across our entities."""

B6_GROWTH = """\
QUESTION: "Tell me about your career progression."

SITUATION: I started as a Junior Accounts Executive at Ravi Sachdeva & Co. (Aug 2021) handling bookkeeping and audit support, with no exposure yet to the FP&A or controllership side of finance.

TASK: Grow into a role where I owned end-to-end financial deliverables — close, reporting, planning — not just transactional accounting.

ACTION: At Dhyey Consulting Services took on broader scope: P&L / BS / cash flow for multiple client entities, end-to-end GST compliance, audit support across engagements. Then at Stemmons stepped fully into FP&A: month-end close, dashboards, budgeting, process improvement, business partnering. Picked up Business Central and Navision on the job; currently learning Power BI and SQL.

RESULT: Moved from transactional bookkeeping to end-to-end ownership of MIS, R2R, and budgeting in 3+ years — with quantified wins (zero audit observations, 30% reconciliation cycle reduction, automated AP workflows) at each step."""

B7_FAST_PACED = """\
QUESTION: "Tell me about working in a fast-paced or build-from-scratch environment."

SITUATION: Stemmons was scaling its India operation — many of the finance processes I owned (close calendar, variance commentary, dashboards, automated AP workflows) didn't exist before I built them.

TASK: Stand up reporting and control infrastructure in parallel with the day-job of running close and audit — without buying expensive tools or adding headcount.

ACTION: Prioritised the highest-leverage gaps (close calendar, dashboards, automation) and built them iteratively rather than waiting for a perfect spec; treated v1 as good-enough-to-ship; partnered with department heads early so the artefacts solved their actual problems, not theoretical ones.

RESULT: In 20 months: zero audit observations, 30% faster reconciliations, leadership dashboards as the default monthly artefact, and a small finance team running a much larger operation than its headcount suggested."""


TECH = {
    "T1": T1_RECONCILIATION,
    "T2": T2_ZERO_AUDIT,
    "T3": T3_INTERCOMPANY,
    "T4": T4_DASHBOARDS,
    "T5": T5_BUDGETING,
    "T6": T6_GST_COMPLIANCE,
    "T7": T7_AUTOMATION,
}
BEHAVIORAL = {
    "B1": B1_INFLUENCING,
    "B2": B2_TRANSLATING_FINANCE,
    "B3": B3_TIGHT_DEADLINES,
    "B4": B4_CROSS_FUNCTIONAL,
    "B5": B5_AUDIT_PARTNERSHIP,
    "B6": B6_GROWTH,
    "B7": B7_FAST_PACED,
}


# ============================================================
# Per-row archetype classification → story pair
# Each archetype has a primary + secondary pair; we alternate
# to avoid identical stories on consecutive rows of the same
# company/archetype.
# ============================================================

ARCHETYPES = {
    # (T_primary, B_primary, T_alt, B_alt)
    "bank_controllership":  ("T2", "B5", "T3", "B1"),  # JPMC, Citi controllership
    "bank_fpa":             ("T5", "B1", "T4", "B2"),  # Citi FP&A officer roles
    "bank_other":           ("T2", "B3", "T1", "B5"),  # Citi misc / Barclays
    "big4_advisory":        ("T4", "B2", "T2", "B5"),  # KPMG, EY, PwC, Deloitte, GT
    "big4_ap":              ("T1", "B3", "T7", "B5"),  # KPMG AP / fixed-assets execution
    "bpo_r2r":              ("T1", "B3", "T3", "B4"),  # WNS, Genpact, EXL, Accenture R2R
    "bpo_intercompany":     ("T3", "B5", "T1", "B3"),  # WNS Intercompany etc.
    "bpo_fpa":              ("T5", "B2", "T4", "B1"),  # WNS FP&A, Capgemini Insurance BA
    "kpo_research":         ("T4", "B2", "T5", "B6"),  # Evalueserve, CRISIL, E2M
    "kpo_ap":               ("T1", "B5", "T6", "B3"),  # Acuity AP
    "industry_fpa":         ("T5", "B4", "T2", "B1"),  # Kraft Heinz, Hilti
    "industry_controls":    ("T2", "B5", "T3", "B7"),  # Kraft Heinz internal controls
    "finops_ap":            ("T1", "B3", "T7", "B5"),  # Amazon FinOps AP
    "erp_consultant":       ("T7", "B4", "T4", "B2"),  # Zetwerk ERP consultant
    "specialist_other":     ("T4", "B7", "T7", "B6"),  # NielsenIQ Data Ops, Apexon, Exxat
    "generic_fpa":          ("T5", "B2", "T4", "B3"),  # fallback for unknown roles
}


def classify(row: dict) -> str:
    company = (row.get("Company") or "").lower()
    role    = (row.get("Role / Position") or "").lower()
    tier    = (row.get("Tier") or "").lower()

    # Bank GCC controllership
    if company in {"jpmorgan chase", "citi", "barclays"}:
        if any(k in role for k in ["controller", "external reporting", "valuation control",
                                    "fund accounting", "bank controllers", "entity controller",
                                    "financial reporting", "asset servicing"]):
            return "bank_controllership"
        if "fp&a" in role or "fpa" in role or "planning and analysis" in role or "expense management" in role:
            return "bank_fpa"
        return "bank_other"

    # Big 4 / Tier 1 consulting
    if any(k in company for k in ["kpmg", "deloitte", "ey india", "pwc", "grant thornton"]):
        if "accounts payable" in role or "fixed assets" in role:
            return "big4_ap"
        return "big4_advisory"

    # BPO/SSC R2R
    if any(k in company for k in ["wns", "genpact", "exl", "accenture", "capgemini"]):
        if "intercompany" in role or "inter-company" in role:
            return "bpo_intercompany"
        if "fp&a" in role or "fpa" in role or "general insurance" in role:
            return "bpo_fpa"
        return "bpo_r2r"

    # KPO
    if any(k in company for k in ["evalueserve", "crisil", "acuity", "e2m"]):
        if "accounts payable" in role or "payables" in role:
            return "kpo_ap"
        return "kpo_research"

    # Industry / corporate
    if "kraft heinz" in company:
        return "industry_controls" if "control" in role else "industry_fpa"
    if "hilti" in company:
        return "industry_fpa"

    # Tech / FinOps
    if "amazon" in company:
        return "finops_ap"
    if "zetwerk" in company:
        return "erp_consultant"
    if any(k in company for k in ["nielseniq", "apexon", "exxat"]):
        return "specialist_other"

    # Unknown / via-careers — choose by role keywords
    if "fp&a" in role or "fpa" in role or "financial planning" in role:
        return "generic_fpa"
    if "r2r" in role or "record to report" in role or "general accounting" in role:
        return "bpo_r2r"
    return "generic_fpa"


def main() -> None:
    payload = json.loads(ROWS_FILE.read_text("utf-8"))
    rows = payload.get("rows", [])

    # Track usage per (company, archetype) to alternate primary/alt pairs
    used_count: dict[tuple[str, str], int] = {}

    for r in rows:
        arch = classify(r)
        key = (r.get("Company", ""), arch)
        n = used_count.get(key, 0)
        used_count[key] = n + 1

        Tp, Bp, Ta, Ba = ARCHETYPES[arch]
        # Alternate so consecutive same-archetype rows of the same company differ.
        if n % 2 == 0:
            t_code, b_code = Tp, Bp
        else:
            t_code, b_code = Ta, Ba

        r["STAR (Technical)"]      = TECH[t_code]
        r["STAR (Non-Technical)"]  = BEHAVIORAL[b_code]
        # Drop the legacy combined field; we render the two new ones in the detail view.
        r.pop("STAR Story", None)

    ROWS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")
    print(f"updated {len(rows)} rows with STAR (Technical) + STAR (Non-Technical)")
    # Distribution print
    from collections import Counter
    arch_counts = Counter(classify(r) for r in rows)
    for a, c in arch_counts.most_common():
        Tp, Bp, _, _ = ARCHETYPES[a]
        print(f"  {a:<22} {c:>3} rows  primary=({Tp}, {Bp})")


if __name__ == "__main__":
    main()
