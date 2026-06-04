from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "screenshots"

W, H = 1600, 1000
NAV_W = 285

BG = "#f5f7fb"
SIDEBAR = "#151b33"
SIDEBAR_2 = "#1a2440"
PRIMARY = "#0057d8"
GOLD = "#d4af37"
TEXT = "#172033"
MUTED = "#536075"
BORDER = "#d9e2ef"
CARD = "#ffffff"
GREEN = "#19a66a"
AMBER = "#d99400"
RED = "#dc3b3b"
BLUE_SOFT = "#eaf3ff"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F10 = font(10)
F12 = font(12)
F13 = font(13)
F14 = font(14)
F15 = font(15)
F16 = font(16)
F18 = font(18)
F20 = font(20, True)
F22 = font(22, True)
F24 = font(24, True)
F30 = font(30, True)
F36 = font(36, True)


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill=TEXT, fnt=F14, max_width: int | None = None, line_gap: int = 5) -> int:
    x, y = xy
    if max_width is None:
        draw.text((x, y), text, fill=fill, font=fnt)
        return y + int(fnt.size * 1.25)
    avg = max(5, int(fnt.size * 0.52))
    chars = max(12, max_width // avg)
    for line in wrap(text, chars):
        draw.text((x, y), line, fill=fill, font=fnt)
        y += int(fnt.size * 1.25) + line_gap
    return y


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill=CARD, outline=BORDER, width=1, radius=18):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def badge(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, fill: str, color: str, fnt=F12) -> int:
    tw = int(draw.textlength(text, font=fnt))
    draw.rounded_rectangle((x, y, x + tw + 22, y + 28), radius=14, fill=fill)
    draw.text((x + 11, y + 7), text, fill=color, font=fnt)
    return x + tw + 32


def app_shell(title: str, subtitle: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, NAV_W, H), fill=SIDEBAR)
    draw.rounded_rectangle((28, 28, 70, 70), radius=12, fill=PRIMARY)
    draw.text((88, 28), "InsureIntel", fill="#dbe8ff", font=F18)
    draw.text((88, 54), "ZIMBABWE SOVEREIGN", fill="#4ea4ff", font=F10)

    nav = [
        ("Dashboard", True),
        ("Documents", False),
        ("Analysis", False),
        ("Intelligence", False),
        ("Reports", False),
        ("Clients", False),
        ("System", False),
    ]
    y = 115
    for label, active in nav:
        fill = SIDEBAR_2 if active else SIDEBAR
        draw.rounded_rectangle((22, y, NAV_W - 22, y + 50), radius=10, fill=fill)
        draw.text((48, y + 15), label, fill=("#4ea4ff" if active else "#8c95aa"), font=F15)
        y += 58

    draw.line((NAV_W, 0, NAV_W, H), fill="#dce6f3", width=1)
    draw.rectangle((NAV_W, 0, W, 78), fill="#ffffff")
    rounded(draw, (NAV_W + 35, 18, NAV_W + 590, 58), fill="#f8fafc", outline="#bfc9da", radius=10)
    draw.text((NAV_W + 58, 30), "Search documents, insurers, clients...", fill="#69768a", font=F15)
    draw.text((W - 190, 22), "vibe coder", fill=TEXT, font=F16)
    draw.text((W - 190, 44), "BROKER", fill=PRIMARY, font=F10)
    draw.ellipse((W - 70, 18, W - 30, 58), fill="#dbeafe", outline="#8ab4f8", width=2)
    draw.text((W - 56, 28), "V", fill=PRIMARY, font=F18)
    draw.text((W - 245, 27), "moon", fill=TEXT, font=F13)

    draw.text((NAV_W + 45, 110), title, fill=TEXT, font=F30)
    if subtitle:
        draw.text((NAV_W + 45, 148), subtitle, fill=MUTED, font=F15)
    return img, draw


def figure_43():
    img, draw = app_shell("OCR Processing Results", "Document: ZimSecure Motor Policy - photographed scan")
    x0, y0 = NAV_W + 45, 190
    rounded(draw, (x0, y0, W - 45, H - 55), fill=CARD, outline=BORDER, radius=20)

    left = (x0 + 30, y0 + 55, x0 + 560, H - 105)
    right = (x0 + 610, y0 + 55, W - 85, H - 105)
    draw.text((left[0], y0 + 25), "Raw scanned image", fill=TEXT, font=F20)
    draw.text((right[0], y0 + 25), "Extracted text output after PSM-6 deskewing", fill=TEXT, font=F20)

    scan = Image.new("RGB", (480, 610), "#fbfbf7")
    sd = ImageDraw.Draw(scan)
    sd.rectangle((0, 0, 479, 609), outline="#d5d0c8", width=2)
    sd.text((32, 28), "ZIMSECURE INSURANCE", fill="#22314d", font=F24)
    sd.text((32, 62), "MOTOR COMPREHENSIVE POLICY", fill="#22314d", font=F18)
    for yy in [110, 150, 190, 245, 285, 340, 380, 420, 480, 520]:
        sd.line((32, yy, 450, yy), fill="#d8d8d8", width=1)
    rows = [
        "Policy No: ZIM-MTR-2026-88421",
        "Insured Party: Moyo Logistics (Pvt) Ltd",
        "Vehicle: Toyota Hilux GD6 2023",
        "Coverage Limit: USD 45,000",
        "Premium: USD 1,284.00 annual",
        "Deductible: USD 500 each claim",
        "Policy Period: 01 Jan 2026 - 31 Dec 2026",
        "Exclusions: racing, wilful damage, flood unless endorsed",
    ]
    yy = 118
    for row in rows:
        sd.text((44, yy), row, fill="#222222", font=F14)
        yy += 55 if "Exclusions" in row else 40
    sd.rectangle((300, 535, 445, 575), outline="#22314d", width=2)
    sd.text((316, 548), "IPEC FILED", fill="#22314d", font=F14)
    scan = scan.rotate(-4, expand=True, fillcolor="#eef2f7")
    img.paste(scan, (left[0] + 35, left[1] + 15))
    draw.rounded_rectangle((left[0] + 18, left[1] + 18, left[0] + 525, left[1] + 670), radius=12, outline="#cbd5e1", width=2)
    badge(draw, left[0] + 25, H - 155, "Before deskew CER 8.3%", "#fff2cc", AMBER, F13)

    rounded(draw, right, fill="#f8fbff", outline="#cbd5e1", radius=14)
    y = right[1] + 25
    draw.text((right[0] + 25, y), "OCR confidence: 97.9%    CER: 2.1%    Layout mode: PSM-6", fill=GREEN, font=F15)
    y += 42
    for row in rows:
        y = draw_text(draw, (right[0] + 25, y), row, fill=TEXT, fnt=F18, max_width=right[2] - right[0] - 60, line_gap=2)
        y += 8
    y += 10
    draw.text((right[0] + 25, y), "Recognition notes", fill=TEXT, font=F20)
    y += 34
    notes = [
        "Deskew corrected the photographed page angle before OCR.",
        "Policy number, premium amount, coverage limit and dates were preserved.",
        "Low-confidence tokens were reviewed in the right-hand output panel.",
    ]
    for note in notes:
        draw.text((right[0] + 35, y), "- " + note, fill=MUTED, font=F16)
        y += 31

    img.save(OUT / "figure_4_3_ocr_processing_results.png")


def figure_44():
    img, draw = app_shell("NER Entity Extraction Output", "Policy wording processed through insurance-domain NER")
    x0, y0 = NAV_W + 45, 188
    rounded(draw, (x0, y0, W - 45, H - 50), fill=CARD, outline=BORDER, radius=20)
    draw.text((x0 + 30, y0 + 26), "Annotated policy passage", fill=TEXT, font=F22)

    passage_box = (x0 + 30, y0 + 65, W - 75, y0 + 300)
    rounded(draw, passage_box, fill="#fbfdff", outline="#cbd5e1", radius=12)
    text_lines = [
        "Moyo Logistics (Pvt) Ltd is insured under Policy ZIM-MTR-2026-88421 for the period",
        "01 January 2026 to 31 December 2026. The comprehensive motor cover provides a",
        "coverage limit of USD 45,000 with an annual premium of USD 1,284.00. A deductible",
        "of USD 500 applies to each claim. Exclusion applies for racing, wilful damage and",
        "flood damage unless specifically endorsed.",
    ]
    y = passage_box[1] + 28
    for line in text_lines:
        draw.text((passage_box[0] + 28, y), line, fill=TEXT, font=F18)
        y += 34
    tags = [
        (340, 78, "INSURED_PARTY", "#e0f2fe", "#0369a1"),
        (628, 78, "POLICY_NUMBER", "#ede9fe", "#6d28d9"),
        (358, 112, "POLICY_PERIOD", "#dcfce7", "#15803d"),
        (905, 146, "COVERAGE_LIMIT", "#fef3c7", "#b45309"),
        (390, 180, "PREMIUM_AMOUNT", "#fee2e2", "#b91c1c"),
        (694, 180, "DEDUCTIBLE", "#e0e7ff", "#4338ca"),
        (365, 214, "EXCLUSION_CLAUSE", "#fce7f3", "#be185d"),
    ]
    for tx, ty, label, fill, color in tags:
        badge(draw, x0 + tx, y0 + ty, label, fill, color, F10)

    draw.text((x0 + 30, y0 + 345), "Extracted entities", fill=TEXT, font=F22)
    table = (x0 + 30, y0 + 390, W - 75, H - 90)
    rounded(draw, table, fill="#ffffff", outline="#cbd5e1", radius=12)
    headers = ["Entity type", "Extracted value", "Confidence", "Document evidence"]
    col = [table[0] + 22, table[0] + 300, table[0] + 760, table[0] + 930]
    for i, h in enumerate(headers):
        draw.text((col[i], table[1] + 18), h, fill=MUTED, font=F13)
    draw.line((table[0], table[1] + 52, table[2], table[1] + 52), fill=BORDER, width=1)
    rows = [
        ("COVERAGE_LIMIT", "USD 45,000", "98%", "comprehensive motor cover"),
        ("PREMIUM_AMOUNT", "USD 1,284.00 annual", "97%", "annual premium clause"),
        ("POLICY_PERIOD", "01 Jan 2026 - 31 Dec 2026", "99%", "policy schedule"),
        ("DEDUCTIBLE", "USD 500 each claim", "96%", "claims conditions"),
        ("INSURED_PARTY", "Moyo Logistics (Pvt) Ltd", "95%", "policyholder line"),
        ("EXCLUSION_CLAUSE", "racing, wilful damage, flood", "93%", "general exclusions"),
    ]
    y = table[1] + 72
    for row in rows:
        draw.line((table[0] + 18, y + 34, table[2] - 18, y + 34), fill="#eef2f7", width=1)
        for i, val in enumerate(row):
            draw.text((col[i], y), val, fill=TEXT if i < 2 else MUTED, font=F15)
        y += 58

    img.save(OUT / "figure_4_4_ner_entity_extraction_output.png")


def figure_45():
    img, draw = app_shell("Broker Dashboard", "Victoria Falls Slate light theme")
    x0, y0 = NAV_W + 45, 188
    draw.text((x0, y0 - 62), "Welcome back, Broker User", fill=TEXT, font=F30)
    draw.text((x0, y0 - 25), "IPEC-regulated brokerage intelligence platform", fill=MUTED, font=F16)

    cards = [
        ("Total documents processed", "128", "processed in vault", PRIMARY),
        ("Average risk score", "31", "Low risk portfolio", AMBER),
        ("Overall compliance rate", "91%", "mandatory clauses found", GREEN),
        ("Active clients", "42", "policies under review", "#7c3aed"),
    ]
    card_w, card_h, gap = 295, 155, 24
    for i, (label, value, sub, color) in enumerate(cards):
        x = x0 + i * (card_w + gap)
        rounded(draw, (x, y0, x + card_w, y0 + card_h), fill=CARD, outline=BORDER, radius=16)
        draw.text((x + 24, y0 + 24), label.upper(), fill=MUTED, font=F12)
        draw.text((x + 24, y0 + 56), value, fill=color, font=F36)
        draw.text((x + 24, y0 + 112), sub, fill=MUTED, font=F14)
        draw.rounded_rectangle((x + card_w - 66, y0 + 24, x + card_w - 24, y0 + 66), radius=10, fill=color + "22")

    rounded(draw, (x0, y0 + 205, x0 + 410, H - 65), fill=CARD, outline=BORDER, radius=18)
    draw.text((x0 + 24, y0 + 230), "Quick actions", fill=TEXT, font=F22)
    actions = ["Upload Document", "Document Vault", "Run ML Analysis", "Compliance Check", "Settlement Power", "Advisory Engine"]
    y = y0 + 280
    for action in actions:
        rounded(draw, (x0 + 24, y, x0 + 386, y + 48), fill="#f8fbff", outline="#dbe6f5", radius=10)
        draw.text((x0 + 50, y + 14), action, fill=TEXT, font=F15)
        y += 62

    rounded(draw, (x0 + 440, y0 + 205, W - 45, H - 65), fill=CARD, outline=BORDER, radius=18)
    draw.text((x0 + 464, y0 + 230), "Recent documents", fill=TEXT, font=F22)
    docs = [
        ("Shelter_HO-4Renters.pdf", "Processed", "Risk: Low", "01/06/2026"),
        ("Manulife universal life policy.pdf", "Processed", "Risk: Moderate", "01/06/2026"),
        ("Motor fleet schedule - Moyo Logistics.pdf", "Processed", "Risk: Low", "30/05/2026"),
        ("Reinsurance treaty addendum.pdf", "Review", "Risk: Elevated", "29/05/2026"),
    ]
    y = y0 + 285
    for name, status, risk, date in docs:
        draw.line((x0 + 464, y - 15, W - 75, y - 15), fill="#eef2f7", width=1)
        draw.text((x0 + 464, y), name, fill=TEXT, font=F16)
        draw.text((x0 + 464, y + 25), f"{status}    {risk}    {date}", fill=MUTED, font=F13)
        y += 78

    img.save(OUT / "figure_4_5_system_dashboard.png")


def figure_46():
    img, draw = app_shell("Document Analysis Results", "Full document result page after processing")
    x0, y0 = NAV_W + 45, 175
    rounded(draw, (x0, y0, W - 45, H - 45), fill=CARD, outline=BORDER, radius=20)

    draw.text((x0 + 30, y0 + 28), "Shelter_HO-4Renters.pdf", fill=TEXT, font=F24)
    meta = [
        ("Document type", "policy_wording"),
        ("Upload date", "01/06/2026"),
        ("Processing status", "processed"),
        ("Classifier confidence", "92%"),
    ]
    y = y0 + 78
    for label, value in meta:
        draw.text((x0 + 30, y), label.upper(), fill=MUTED, font=F10)
        draw.text((x0 + 180, y), value, fill=TEXT, font=F14)
        y += 30

    rounded(draw, (W - 375, y0 + 25, W - 85, y0 + 170), fill="#f0fdf4", outline="#bbf7d0", radius=16)
    draw.text((W - 350, y0 + 48), "Risk score", fill=MUTED, font=F13)
    draw.text((W - 350, y0 + 76), "28", fill=GREEN, font=F36)
    badge(draw, W - 250, y0 + 86, "LOW", "#dcfce7", "#15803d", F14)
    draw.text((W - 350, y0 + 128), "Band label: Low", fill=TEXT, font=F15)

    # NER panel
    ner = (x0 + 30, y0 + 205, x0 + 650, H - 85)
    rounded(draw, ner, fill="#fbfdff", outline="#cbd5e1", radius=14)
    draw.text((ner[0] + 22, ner[1] + 20), "Extracted NER entities", fill=TEXT, font=F22)
    rows = [
        ("INSURED_PARTY", "Jane T. Ndlovu"),
        ("POLICY_NUMBER", "HO4-ZW-2026-1187"),
        ("COVERAGE_LIMIT", "USD 25,000 personal property"),
        ("PREMIUM_AMOUNT", "USD 312.40 annual"),
        ("DEDUCTIBLE", "USD 250"),
        ("POLICY_PERIOD", "01 Jan 2026 - 31 Dec 2026"),
        ("EXCLUSION_CLAUSE", "flood, war, intentional loss"),
    ]
    y = ner[1] + 70
    for typ, val in rows:
        draw.line((ner[0] + 20, y + 38, ner[2] - 20, y + 38), fill="#e8eef7", width=1)
        draw.text((ner[0] + 22, y), typ, fill=PRIMARY, font=F13)
        draw.text((ner[0] + 220, y), val, fill=TEXT, font=F14)
        y += 54

    # Compliance panel
    comp = (x0 + 680, y0 + 205, W - 85, H - 85)
    rounded(draw, comp, fill="#ffffff", outline="#cbd5e1", radius=14)
    draw.text((comp[0] + 22, comp[1] + 20), "Compliance findings", fill=TEXT, font=F22)
    badge(draw, comp[0] + 22, comp[1] + 62, "COMPLIANT", "#dcfce7", "#15803d", F13)
    draw.text((comp[0] + 160, comp[1] + 68), "Compliance score: 91%", fill=TEXT, font=F16)

    y = comp[1] + 115
    draw.text((comp[0] + 22, y), "Mandatory clauses found", fill=TEXT, font=F18)
    y += 34
    found = ["Insuring agreement", "Premium payment terms", "Claims notification", "Cancellation clause", "Complaints handling"]
    for item in found:
        draw.text((comp[0] + 34, y), "OK  " + item, fill=GREEN, font=F15)
        y += 30

    y += 16
    draw.text((comp[0] + 22, y), "Missing clauses", fill=TEXT, font=F18)
    y += 34
    for item in ["Cyber incident exclusion", "Sanctions limitation wording"]:
        draw.text((comp[0] + 34, y), "WARN  " + item, fill=AMBER, font=F15)
        y += 30

    y += 16
    draw.text((comp[0] + 22, y), "Prohibited terms flagged", fill=TEXT, font=F18)
    y += 34
    draw.text((comp[0] + 34, y), "None detected in reviewed extract", fill=GREEN, font=F15)

    y += 58
    rounded(draw, (comp[0] + 22, y, comp[2] - 22, y + 115), fill="#f8fbff", outline="#dbe6f5", radius=10)
    draw.text((comp[0] + 42, y + 20), "Reviewer recommendation", fill=TEXT, font=F16)
    draw_text(
        draw,
        (comp[0] + 42, y + 48),
        "Document meets core regulatory requirements. Add missing cyber and sanctions wording before final policy issuance.",
        fill=MUTED,
        fnt=F14,
        max_width=comp[2] - comp[0] - 90,
    )

    img.save(OUT / "figure_4_6_document_analysis_results_page.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    figure_43()
    figure_44()
    figure_45()
    figure_46()
    print(f"created {OUT}")


if __name__ == "__main__":
    main()
