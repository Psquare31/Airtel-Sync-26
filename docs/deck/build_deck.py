"""Builds the business-case deck on the hackathon submission template.

usage: python docs/deck/build_deck.py "<Submission Template_Sync.pptx>" docs/deck/screens docs/deck/Udyam_Digital_Business_Case.pptx
Numbers come from analysis/funnel.py and the rules engine (see speaker notes).
"""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE, SCREENS, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])

RED = RGBColor(0xD7, 0x26, 0x1E)
INK = RGBColor(0x1D, 0x1B, 0x1A)
MUTED = RGBColor(0x5F, 0x58, 0x55)
TINT = RGBColor(0xFD, 0xEC, 0xEA)
LINE = RGBColor(0xEC, 0xE6, 0xE2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
OK = RGBColor(0x15, 0x80, 0x3D)
BAR = RGBColor(0x3B, 0x6E, 0xA8)
FONT = "Calibri"

prs = Presentation(TEMPLATE)
cover, first_content = prs.slides[0], prs.slides[1]
content_layout = first_content.slide_layout
bg_image = None
for shp in first_content.shapes:
    if shp.shape_type == 13:  # picture: the content background
        bg_image = shp.image.blob
bg_path = OUT.parent / "_bg.jpg"
bg_path.write_bytes(bg_image)


def new_slide():
    s = prs.slides.add_slide(content_layout)
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    s.shapes.add_picture(str(bg_path), 0, 0, prs.slide_width, prs.slide_height)
    return s


def text(slide, x, y, w, h, runs, size=14, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         name=None, space_after=4):
    """runs: str | list of paragraphs; a paragraph is str or list of (text, {bold,color,size}) tuples."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        parts = para if isinstance(para, list) else [(para, {})]
        for t, opt in parts:
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = FONT
            f.size = Pt(opt.get("size", size))
            f.bold = opt.get("bold", bold)
            f.italic = opt.get("italic", False)
            f.color.rgb = opt.get("color", color)
    return tb


def title(slide, t, kicker=None):
    if kicker:
        text(slide, 0.5, 0.78, 9, 0.25, kicker.upper(), size=11, color=RED, bold=True, name="Kicker")
    text(slide, 0.5, 1.0, 9, 0.5, t, size=24, bold=True, name="Title")


def card(slide, x, y, w, h, fill=WHITE, line=LINE, name=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.adjustments[0] = 0.08
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    shp.shadow.inherit = False
    if name:
        shp.name = name
    return shp


def circle_num(slide, x, y, n, d=0.36):
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    c.fill.solid()
    c.fill.fore_color.rgb = RED
    c.line.fill.background()
    c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(n)
    r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(12), True, WHITE, FONT
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return c


def stat(slide, x, y, w, value, label, color=RED):
    text(slide, x, y, w, 0.5, value, size=24, bold=True, color=color)
    text(slide, x, y + 0.5, w, 0.45, label, size=11, color=MUTED)


def bar_chart(slide, x, y, w, h, cats, vals, fmt='#,##0', horizontal=True, color=BAR, title_text=None):
    data = CategoryChartData()
    data.categories = cats
    data.add_series("v", vals)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), data)
    ch = gf.chart
    ch.has_legend = False
    ch.font.size = Pt(11)
    ch.font.name = FONT
    ch.font.color.rgb = MUTED
    if title_text:
        ch.has_title = True
        ch.chart_title.text_frame.text = title_text
        tp = ch.chart_title.text_frame.paragraphs[0]
        tp.runs[0].font.size, tp.runs[0].font.bold, tp.runs[0].font.color.rgb = Pt(12), True, INK
    else:
        ch.has_title = False
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = fmt, False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.color.rgb = Pt(11), INK
    ser = plot.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = color
    va = ch.value_axis
    va.visible = False
    va.has_major_gridlines = False
    ca = ch.category_axis
    ca.format.line.color.rgb = LINE
    ca.tick_labels.font.size = Pt(11)
    if horizontal:
        ca.reverse_order = True
    return gf


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


# ---------------------------------------------------------------- 1 cover
text(cover, 0.55, 3.05, 4.3, 0.55, "Udyam Digital", size=30, bold=True, color=WHITE, name="Cover title")
text(cover, 0.55, 3.62, 4.0, 0.7, "Small businesses discover, buy and activate Accel Business in one sitting, on their phone, in their language",
     size=13, color=WHITE, name="Cover subtitle")
text(cover, 0.55, 4.5, 4.0, 0.3, "YTL Hackathon 2026 · Enterprise Track A · Business case", size=11,
     color=RGBColor(0xF3, 0xB7, 0xB3), name="Cover meta")
notes(cover, "Udyam Digital: a digital-first acquisition and onboarding journey for Accel Business. "
             "All figures are from the synthetic dataset provided (smb_leads.csv, Apr-Jun 2026).")

# ---------------------------------------------------------------- 2 problem
s = first_content
for ph in list(s.placeholders):
    ph._element.getparent().remove(ph._element)
title(s, "Only 7.4% of leads activate; the quote is the biggest leak", "The problem")
bar_chart(s, 0.4, 1.6, 5.4, 3.45, ["Leads", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"],
          [5000, 3406, 1974, 861, 588, 368])
text(s, 0.5, 4.98, 5.3, 0.25, "Leads reaching each stage, Apr–Jun 2026. Needs assessed → quote accepted converts at just 44%.",
     size=10, color=MUTED)
stat(s, 6.15, 1.65, 1.6, "17.6 days", "lead to activation")
stat(s, 7.9, 1.65, 1.6, "3 calls", "customer chases status")
stat(s, 6.15, 2.75, 1.6, "₹15,053", "acquisition cost per activated SMB")
stat(s, 7.9, 2.75, 1.6, "9.6% / 2%", "activation with / without GSTIN")
card(s, 6.15, 3.9, 3.35, 1.1, fill=TINT, line=None)
text(s, 6.3, 3.98, 3.1, 0.95, [[("32% of all drops", {"bold": True, "color": RED}),
                                (" are caused by visits, slow or confusing quotes and paperwork, which a self-serve journey removes.", {})]],
     size=12)
notes(s, "Funnel from smb_leads.csv. Drop reasons removed by a digital journey: owner had no time for a visit (531), "
         "visit not scheduled (296), quote too complex (206), quote too slow (179), paperwork too long (79), "
         "missing GST/Udyam doc (94), signatory not available (53), document mismatch (47) = 1,485 of 4,632 drops.")

# ---------------------------------------------------------------- 3 segments
s = new_slide()
title(s, "Lead with offices; win micro retail on low-cost channels", "Who first")
text(s, 0.5, 1.6, 4.3, 0.3, "Months of revenue to repay acquisition cost", size=12, bold=True)
bar_chart(s, 0.4, 1.9, 4.4, 2.25, ["Professional offices", "Micro retail & services", "Small multi-site", "Small manufacturers"],
          [1.6, 8.1, 0.6, 1.0], fmt='0.0" mo"')
rows = [
    ("Segment", "Share", "Activ.", "₹/mo", "GSTIN", "Churn", "Wave"),
    ("Professional offices", "25%", "11.1%", "6,575", "86%", "13.8%", "1 · digital"),
    ("Micro retail & services", "55%", "4.1%", "2,470", "53%", "22.7%", "1 · digital + partner"),
    ("Small multi-site", "15%", "11.0%", "28,080", "98%", "10.8%", "2 · hybrid"),
    ("Small manufacturers", "5%", "12.8%", "15,910", "99%", "8.1%", "2 · field-led"),
]
tbl = s.shapes.add_table(len(rows), len(rows[0]), Inches(4.95), Inches(1.6), Inches(4.6), Inches(2.4)).table
widths = [1.25, 0.45, 0.5, 0.55, 0.5, 0.5, 0.85]
for i, wd in enumerate(widths):
    tbl.columns[i].width = Inches(wd * 4.6 / sum(widths))
for r, row in enumerate(rows):
    for c, val in enumerate(row):
        cell = tbl.cell(r, c)
        cell.text = val
        cell.margin_left = cell.margin_right = Inches(0.04)
        cell.margin_top = cell.margin_bottom = Inches(0.03)
        cell.fill.solid()
        cell.fill.fore_color.rgb = RED if r == 0 else (WHITE if r % 2 else RGBColor(0xFB, 0xF7, 0xF5))
        for p in cell.text_frame.paragraphs:
            for run in p.runs:
                run.font.size = Pt(10)
                run.font.name = FONT
                run.font.bold = r == 0 or c == 0
                run.font.color.rgb = WHITE if r == 0 else INK
text(s, 0.5, 4.3, 9.0, 0.75, [
    [("Why: ", {"bold": True}), ("offices pay back acquisition cost in 1.6 months and 86% already have a GSTIN, so instant KYC works on day one. "
                                 "Micro retail is the volume (55%) but pays back in 8 months at today's ₹20k cost per activation, so it must come through "
                                 "WhatsApp, referral and partner-assisted journeys (₹4–6k).", {})],
], size=12)
notes(s, "Per segment from analysis/funnel.py: activation rate, median monthly bundle value of activated leads, "
         "cost per activation (sum of acquisition_cost_inr / activations), GSTIN share and 6-month churn. "
         "Payback = cost per activation / median monthly bundle value.")

# ---------------------------------------------------------------- 4 bundles
s = new_slide()
title(s, "Four bundles, one transparent monthly price each", "Bundles & pricing")
bundles = [
    ("Dukaan Digital", "Kirana, salon, pharmacy", "₹1,448", "Biz Fibre 100 + 1 business SIM\nAdd: POS & UPI billing ₹749, CCTV, guest Wi-Fi, WhatsApp*",
     "12 mo · no GSTIN needed"),
    ("Office Pro", "Clinic, CA firm, coaching", "₹5,254", "Fibre 300 + 2 postpaid lines + email, backup & security for 6 users",
     "12 mo · ₹4,564 on 24 mo"),
    ("Multi-site Connect", "3–10 outlets", "₹36,710", "Fibre + 4G failover + SD-WAN per site, POS, CCTV, 10 lines (5 sites)",
     "Setup ₹63k or 6 EMIs"),
    ("Factory Line", "Units with 10+ staff", "₹26,375", "Leased line 20 Mbps, managed firewall, machine IoT, email & security",
     "GSTIN required"),
]
for i, (name, who, price, what, terms) in enumerate(bundles):
    x = 0.5 + i * 2.27
    card(s, x, 1.6, 2.1, 3.0, name=f"Bundle {name}")
    text(s, x + 0.15, 1.72, 1.8, 0.3, name, size=15, bold=True)
    text(s, x + 0.15, 2.02, 1.8, 0.25, who, size=10, color=MUTED)
    text(s, x + 0.15, 2.32, 1.8, 0.45, [[(price, {"size": 24, "bold": True, "color": RED}), ("/mo", {"size": 11, "color": MUTED})]])
    text(s, x + 0.15, 2.85, 1.8, 1.15, what.split("\n"), size=11)
    text(s, x + 0.15, 4.05, 1.8, 0.45, terms, size=10, color=MUTED)
text(s, 0.5, 4.72, 9.0, 0.4, [
    [("Pricing rule: ", {"bold": True}),
     ("price falls inside each catalogue range with commitment (12 mo = mid, 24 mo = floor). GST is always shown, setup can be paid in 6 EMIs, "
      "and the advisor trims optional add-ons to fit a stated budget. *WhatsApp, SMS and leased lines unlock once a GSTIN is added.", {})]], size=11)
notes(s, "Prices are generated by the prototype's rules engine and pricing module from product_catalogue.csv "
         "(examples: kirana 2 staff tier-2 no GST; clinic 6 staff tier-1; restaurant chain 5 sites 40 staff; auto-parts unit 30 staff). "
         "Activation: 5 days for fibre bundles, 14 days multi-site, 21 days leased line.")

# ---------------------------------------------------------------- 5 journey
s = new_slide()
title(s, "One sitting: advise, quote, verify, sign, track", "The journey")
steps = [
    ("Advisor", "Chat or voice in 10+ languages; 6 questions; deterministic bundle with plain-language reasons"),
    ("Quote", "One monthly price; toggle add-ons, quantities, 12/24 months; dependencies auto-added"),
    ("Smart KYC", "DPDP consent, photo upload with extraction, live GSTIN/Udyam lookup, 15+ automatic checks"),
    ("e-Sign & track", "OTP e-sign, install slot, live tracker and WhatsApp updates instead of calls"),
]
for i, (h, b) in enumerate(steps):
    y = 1.62 + i * 0.86
    circle_num(s, 0.5, y, i + 1)
    text(s, 1.0, y - 0.02, 3.2, 0.3, h, size=14, bold=True)
    text(s, 1.0, y + 0.27, 3.25, 0.55, b, size=11, color=MUTED)
shots = [("a_chat_hi.png", "Hindi advisor"), ("b_quote.png", "Live quote"), ("c_kyc.png", "KYC issues explained")]
for i, (f, cap) in enumerate(shots):
    x = 4.55 + i * 1.68
    pic = s.shapes.add_picture(str(SCREENS / f), Inches(x), Inches(1.55), height=Inches(3.15))
    pic.line.color.rgb = LINE
    pic.line.width = Pt(0.75)
    text(s, x, 4.75, 1.5, 0.25, cap, size=10, color=MUTED, align=PP_ALIGN.CENTER)
notes(s, "Screens are from the working prototype (React PWA). Demo shows: Hindi voice advisor, add-on toggle, "
         "consent, K07/K11/K02 specimen KYC, e-sign, tracker, back-office.")

# ---------------------------------------------------------------- 6 architecture
s = new_slide()
title(s, "The LLM talks; deterministic code decides prices", "Architecture")
cols = [
    (0.5, 1.75, "Phone · PWA", ["Advisor chat + voice", "Quote & checkout", "Consent & KYC upload", "e-Sign & tracker", "Back-office"], WHITE),
    (2.6, 2.55, "FastAPI + LangGraph", ["Journey graph · interrupts", "Advisor: parser + LLM slots", "Rules engine & pricing", "Smart KYC checks", "Tracker · propensity"], TINT),
    (5.5, 2.05, "AI & OCR services", ["Groq: Prompt Guard 2 on input", "Groq chat: gpt-oss-120b → qwen3.8-27b", "Groq: Whisper speech", "KYC docs: Groq vision now; own OCR ready"], WHITE),
    (7.9, 1.6, "Data", ["Neon Postgres: checkpoints, consent, orders, audit", "CSV: catalogue, GSTIN & Udyam registries, leads"], WHITE),
]
for i, (x, w, head, items, fill) in enumerate(cols):
    card(s, x, 1.6, w, 2.6, fill=fill, name=f"Arch {head}")
    text(s, x + 0.12, 1.68, w - 0.24, 0.3, head, size=12, bold=True, color=RED)
    ih = (2.6 - 0.5) / len(items)
    for j, it in enumerate(items):
        y = 2.02 + j * ih
        box = card(s, x + 0.1, y, w - 0.2, ih - 0.08, fill=WHITE if fill == TINT else RGBColor(0xFB, 0xF7, 0xF5), line=LINE)
        text(s, x + 0.18, y, w - 0.36, ih - 0.08, it, size=10, anchor=MSO_ANCHOR.MIDDLE)
    if i < len(cols) - 1:
        nx = cols[i + 1][0]
        arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + w + 0.03), Inches(2.75), Inches(nx - x - w - 0.06), Inches(0.3))
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = MUTED
        arrow.line.fill.background()
        arrow.shadow.inherit = False
points = [
    ("LLM talks, code decides", "the LLM fills slots and explains; products and prices come from the catalogue rules"),
    ("Model rotation", "a rate-limited model is parked until its reset; the next model answers"),
    ("Always works", "regex parser, scripted advisor and local OCR run with no API key"),
    ("Guarded", "Prompt Guard screens input; PII is redacted before any LLM call"),
]
for i, (h, b) in enumerate(points):
    x = 0.5 + i * 2.27
    text(s, x, 4.35, 2.1, 0.75, [[(h, {"bold": True, "size": 12})], [(b, {"color": MUTED, "size": 10})]], space_after=2)
notes(s, "Stack: React + Vite PWA on Vercel; FastAPI + LangGraph on Render (Docker); Neon Postgres; Groq for chat, "
         "prompt guard and Whisper. KYC documents are read by Groq vision in the prototype; our own OCR (ocr_service/) is built and switches on by config. "
         "100+ automated tests including advisor scenarios and model-rotation tests.")

# ---------------------------------------------------------------- 7 KYC & privacy
s = new_slide()
title(s, "Smart KYC catches the planted problems and keeps no images", "Smart KYC & privacy")
kyc_rows = [
    ("K01", "Blocked", "GSTIN cancelled in registry; Udyam number blank"),
    ("K04", "Retake", "GST certificate photo too blurry to read"),
    ("K06", "Fix", "GSTIN check digit wrong: altered number"),
    ("K07", "Blocked", "Legal name differs from GST registry"),
    ("K11", "Fix", "Bill 257 days old; 'Owner' can't sign for a Pvt Ltd"),
    ("K05", "Fix", "Udyam-registered but no certificate; 'Owner' can't sign for an LLP"),
    ("K10", "Fix", "'Owner' isn't a signing role for an LLP"),
    ("K02, K03, K08, K09, K12", "Verified", "incl. skewed scan and O/0 OCR auto-repair"),
]
tbl = s.shapes.add_table(len(kyc_rows), 3, Inches(0.5), Inches(1.6), Inches(5.2), Inches(3.0)).table
for i, wd in enumerate([1.25, 0.75, 3.2]):
    tbl.columns[i].width = Inches(wd)
for r, row in enumerate(kyc_rows):
    for c, val in enumerate(row):
        cell = tbl.cell(r, c)
        cell.text = val
        cell.margin_left = cell.margin_right = Inches(0.05)
        cell.fill.solid()
        cell.fill.fore_color.rgb = WHITE if r % 2 == 0 else RGBColor(0xFB, 0xF7, 0xF5)
        for p in cell.text_frame.paragraphs:
            for run in p.runs:
                run.font.size, run.font.name = Pt(10.5), FONT
                run.font.bold = c < 2
                run.font.color.rgb = (OK if val == "Verified" else RED) if c == 1 else INK
text(s, 0.5, 4.93, 5.2, 0.25, "Offline result on all 12 specimen applicants (scripts/kyc_batch.py), no LLM needed.", size=10, color=MUTED)
priv = [
    ("Consent by purpose", "verify · activate · marketing (opt-in), versioned ledger, withdraw anytime"),
    ("Minimise", "images never stored, only fields + SHA-256; own OCR (ready) keeps them off AI providers"),
    ("Mask & redact", "GSTIN/ID masked in UI and logs; PII stripped before LLM calls"),
    ("Retain & purge", "pending KYC 30 days, abandoned journeys 90 days, audit log of every action"),
]
for i, (h, b) in enumerate(priv):
    y = 1.6 + i * 0.84
    text(s, 6.0, y, 3.5, 0.8, [[(h, {"bold": True, "size": 13})], [(b, {"color": MUTED})]], size=11, space_after=2)
notes(s, "Checks: GSTIN mod-36 checksum and PAN structure, registry status, name and address fuzzy match against "
         "registry, Udyam vs GST trade name, signatory role by constitution, ID expiry, bill age (90 days from 2026-07-15), "
         "blur score, document type. DPDP Act 2023: notice + purpose-wise consent, purpose limitation, data minimisation, retention.")

# ---------------------------------------------------------------- 8 channels
s = new_slide()
title(s, "Digital adds to field sales and partners instead of competing", "Field force & partners")
text(s, 0.5, 1.6, 4.2, 0.3, "Cost per activation by lead source", size=12, bold=True)
bar_chart(s, 0.4, 1.9, 4.3, 2.45, ["Referral", "WhatsApp", "Inbound call", "Website", "Channel partner", "Field sales"],
          [4099, 4026, 5113, 6351, 20851, 24335], fmt='"₹"#,##0')
roles = [
    ("Owner, self-serve", "Micro & offices with GSTIN: WhatsApp, QR and web links open the advisor directly"),
    ("Partner-assisted", "Partner runs the same journey on the owner's phone with a partner code: earns commission, helps with GST, documents and install"),
    ("Field sales", "Multi-site and manufacturers, plus back-office leads ranked by propensity (AUC 0.72) with a next best action"),
]
for i, (h, b) in enumerate(roles):
    y = 1.6 + i * 1.02
    card(s, 4.95, y, 4.55, 0.92, fill=TINT if i == 1 else WHITE)
    text(s, 5.1, y + 0.08, 4.3, 0.8, [[(h, {"bold": True, "size": 13})], [(b, {"color": MUTED})]], size=11, space_after=2)
text(s, 0.5, 4.45, 4.2, 0.6, "Every lead keeps its source and partner code for 90 days, so the partner who brought it is paid even if the owner finishes alone.",
     size=11)
notes(s, "Cost per activation by source from smb_leads.csv. Hand-offs from the advisor (callback, tier-3 city, "
         "blocked KYC, consent declined) appear live at the top of the back-office list.")

# ---------------------------------------------------------------- 9 metrics
s = new_slide()
title(s, "Five metrics, with targets for the first digital cohort", "Measuring success")
metrics = [
    ("Lead → activation", "7.4%", "15%", "instant, plain quote fixes 385 'too slow / too complex' drops"),
    ("Days to activate", "17.6", "≤ 6", "KYC in minutes; fibre installs in 5 days"),
    ("Cost per activation", "₹15,053", "≤ ₹6,000", "digital sources cost ₹4–6k vs ₹24k field"),
    ("Status calls / customer", "3.0", "≤ 0.5", "tracker + WhatsApp updates"),
    ("6-month churn", "15.2%", "≤ 10%", "churn is 6% at 1 follow-up vs 28% at 5"),
]
text(s, 0.5, 1.55, 2.4, 0.25, "Metric", size=10, color=MUTED, bold=True)
text(s, 2.95, 1.55, 1.0, 0.25, "Today", size=10, color=MUTED, bold=True)
text(s, 3.95, 1.55, 1.1, 0.25, "Target", size=10, color=MUTED, bold=True)
text(s, 5.15, 1.55, 3.0, 0.25, "Why it moves", size=10, color=MUTED, bold=True)
for i, (m, now, tgt, why) in enumerate(metrics):
    y = 1.85 + i * 0.5
    text(s, 0.5, y, 2.4, 0.4, m, size=13, bold=True)
    text(s, 2.95, y, 1.0, 0.4, now, size=13, color=MUTED)
    text(s, 3.95, y, 1.1, 0.4, tgt, size=13, bold=True, color=RED)
    text(s, 5.15, y, 2.4, 0.45, why, size=10, color=MUTED)
card(s, 7.75, 1.55, 1.75, 2.75, fill=TINT, line=None)
text(s, 7.88, 1.68, 1.5, 2.55, [
    [("Per quarter of 5,000 leads", {"size": 10, "color": MUTED})],
    [("+382", {"size": 26, "bold": True, "color": RED})],
    [("activations (368 → 750)", {"size": 10})],
    [("≈ ₹3.2 cr", {"size": 22, "bold": True, "color": RED})],
    [("added annual revenue at ₹6,900 median/mo", {"size": 10})],
    [("₹10 L", {"size": 20, "bold": True, "color": RED})],
    [("less acquisition spend", {"size": 10})],
], space_after=1)
text(s, 0.5, 4.5, 7.0, 0.5, "Targets are set for 6 months after launch in pilot cities, measured on leads that start in the digital journey vs the field-led baseline.",
     size=11, color=MUTED)
notes(s, "Value estimate: 750 activations x Rs 6,000 = Rs 45 lakh vs today's 368 x Rs 15,053 = Rs 55.4 lakh; "
         "382 extra activations x Rs 6,900 median monthly bundle x 12 = Rs 3.16 crore annualised. Indicative, synthetic data.")

# ---------------------------------------------------------------- 10 rollout & risks
s = new_slide()
title(s, "Pilot in four cities, scale in nine months", "Rollout & risks")
phases = [
    ("Months 0–2 · Pilot", "Pune, Bengaluru, Jaipur, Lucknow. Offices + GST micro retail. Web and WhatsApp links, 50 partners"),
    ("Months 3–5 · Expand", "10 languages with voice, all channel partners onboarded, live DigiLocker and e-sign"),
    ("Months 6–9 · Scale", "All tier-1/2 cities; hybrid flow for multi-site and manufacturers; fine-tune a small Indic model on consented chats"),
]
for i, (h, b) in enumerate(phases):
    y = 1.6 + i * 1.08
    circle_num(s, 0.5, y, i + 1)
    text(s, 1.0, y - 0.02, 3.4, 1.0, [[(h, {"bold": True, "size": 13})], [(b, {"color": MUTED})]], size=11, space_after=2)
risks = [
    ("Wrong advice", "rules engine decides; 18 scenario tests; human hand-off"),
    ("Forged documents", "registry, checksum, cross-document and blur checks on every upload"),
    ("Channel conflict", "partner attribution and commission on assisted journeys"),
    ("Install capacity", "slot booking; 5G AirFiber in 2 days where fibre is late"),
    ("Price-sensitive micro", "24-month price, starter bundle, setup in EMIs"),
]
text(s, 4.75, 1.55, 4.7, 0.3, "Risk → mitigation", size=12, bold=True)
for i, (r, m) in enumerate(risks):
    y = 1.92 + i * 0.6
    card(s, 4.75, y, 4.75, 0.52)
    text(s, 4.9, y + 0.06, 4.5, 0.42, [[(r + ": ", {"bold": True}), (m, {"color": MUTED})]], size=11, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Pilot cities are in the dataset's tier-1 and tier-2 lists. 'Installation delayed beyond 21 days' caused 98 drops "
         "after KYC; 'price too high' 414 and 'competitor cheaper' 207 at the quote stage.")

prs.save(OUT)
bg_path.unlink()
print("saved", OUT, len(prs.slides), "slides")
