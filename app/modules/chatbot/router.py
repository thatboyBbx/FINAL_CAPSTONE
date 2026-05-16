"""
app/modules/chatbot/router.py
==============================
Offline rule-based insurance chatbot — POST /api/chatbot/message

Architecture:
  Intent matching: regex pattern matching against a curated knowledge base
  Document Q&A:    keyword search over extracted document text
  Fallback:        helpful "I don't know" with suggested resources

Zero external API calls. Works with no internet connection.

Academic justification:
  Rule-based NLP systems are a recognised baseline methodology in information
  retrieval (Manning et al., 2008). For a domain-specific corpus with
  controlled vocabulary (insurance law), pattern matching outperforms
  general-purpose LLMs in precision for known query types while
  eliminating dependency on external infrastructure.

References:
  Manning, C.D., Raghavan, P., Schütze, H. (2008). Introduction to
  Information Retrieval. Cambridge University Press.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/chatbot",
    tags=["chatbot"],
    dependencies=[Depends(get_current_user)],
)


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    document_id: int | None = None
    page_context: str = ""
    conversation_history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    response: str
    sources: list[str] = []


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge base
# Each entry: intent name, list of regex patterns, response string
# ─────────────────────────────────────────────────────────────────────────────

_KB: list[dict[str, Any]] = [
    {
        "intent": "greeting",
        "patterns": [
            r"\bhello\b", r"\bhi\b", r"\bhey\b",
            r"\bgreetings?\b", r"\bgood\s+(morning|afternoon|evening)\b",
        ],
        "response": (
            "Hello! I am InsureIntel AI, your offline insurance intelligence assistant. "
            "I can help you with Zimbabwe insurance regulations, IPEC requirements, "
            "platform features, and document analysis questions.\n\n"
            "Type **help** to see everything I can assist with."
        ),
    },
    {
        "intent": "help",
        "patterns": [
            r"\bhelp\b", r"what can you (do|help|assist)",
            r"your capabilities", r"what do you know",
        ],
        "response": (
            "I can assist with the following topics:\n\n"
            "📋 **Zimbabwe Insurance Law** — Insurance Act [Chapter 24:07], IPEC regulations\n"
            "🏦 **Solvency & Capital** — Minimum capital requirements, solvency margins\n"
            "⚖️ **Claims Settlement** — Settlement timelines, ratios, IPEC requirements\n"
            "📄 **Policy Exclusions** — Standard exclusions, war/civil commotion clauses\n"
            "🔄 **Reinsurance** — Treaty types, ZimRe requirements, offshore placement\n"
            "📊 **CSP Module** — Weighted Composite Score, financial strength assessment\n"
            "🔍 **NER Extraction** — What entities are extracted from documents\n"
            "✅ **Compliance Center** — How compliance checking works\n"
            "📁 **Document Upload** — Supported formats, upload process\n"
            "🌍 **Multilingual** — Shona translation support\n\n"
            "If you have a document open, ask me a specific question about its content."
        ),
    },
    {
        "intent": "insurance_act",
        "patterns": [
            r"insurance act",
            r"chapter\s*24",
            r"24:07",
            r"zimbabwe\s+insurance\s+law",
            r"insurance\s+legislation",
        ],
        "response": (
            "**Zimbabwe Insurance Act [Chapter 24:07]** is the primary legislation "
            "governing insurance in Zimbabwe.\n\n"
            "Key provisions:\n"
            "• **Section 7** — Registration requirements for insurers and reinsurers\n"
            "• **Section 14** — Minimum capital requirements for registration\n"
            "• **Section 27** — Solvency margin obligations\n"
            "• **Section 31** — Claims settlement timelines (acknowledgement within 14 days, "
            "settlement within 90 days)\n"
            "• **Section 45** — IPEC reporting obligations (quarterly FSR-1 returns)\n"
            "• **Section 52** — Mandatory policy wording disclosure requirements\n"
            "• **Section 67** — Broker registration and conduct obligations\n\n"
            "The Act is administered by the Insurance and Pensions Commission (IPEC). "
            "Full text: parlzim.gov.zw"
        ),
    },
    {
        "intent": "ipec",
        "patterns": [
            r"\bipec\b",
            r"insurance and pensions commission",
            r"pensions commission",
            r"insurance regulator",
        ],
        "response": (
            "**IPEC (Insurance and Pensions Commission)** is Zimbabwe's regulatory "
            "authority for insurance and pension industries, established under the "
            "Insurance Act [Chapter 24:07].\n\n"
            "IPEC's core functions:\n"
            "• Licensing insurers, reinsurers, brokers, and agents\n"
            "• Supervising solvency and financial soundness\n"
            "• Protecting policyholders' interests\n"
            "• Receiving and analysing quarterly FSR-1 financial returns\n"
            "• Investigating complaints, disputes, and market conduct\n"
            "• Publishing actuarial and market statistics\n\n"
            "Contact: ipec.co.zw | Harare, Zimbabwe"
        ),
    },
    {
        "intent": "solvency",
        "patterns": [
            r"\bsolvency\b",
            r"solvency\s+margin",
            r"capital\s+requirement",
            r"minimum\s+capital",
            r"statutory\s+fund",
        ],
        "response": (
            "**Solvency Requirements** under the Zimbabwe Insurance Act:\n\n"
            "**Short-term insurers:**\n"
            "• Minimum solvency margin: 20% of net written premiums\n"
            "• Minimum: USD 500,000 (or ZWL equivalent at prevailing rate)\n\n"
            "**Long-term insurers:**\n"
            "• Actuarially determined policy liabilities + statutory margin\n"
            "• Must maintain a statutory fund equal to long-term liabilities\n\n"
            "**Reinsurers:** Enhanced requirements apply — consult current IPEC circulars.\n\n"
            "**InsureIntel CSP Module** weights solvency at 35% of the Weighted Composite "
            "Score: WCS = 0.35×solvency + 0.30×claims + 0.20×reserves + 0.15×liquidity."
        ),
    },
    {
        "intent": "claims_settlement",
        "patterns": [
            r"claim.{0,10}settl",
            r"settl.{0,10}claim",
            r"claims?\s+process(ing)?",
            r"claims?\s+payment",
            r"claims?\s+ratio",
            r"claims?\s+handling",
        ],
        "response": (
            "**Claims Settlement** under Zimbabwe insurance law:\n\n"
            "**Timelines (Insurance Act Section 31):**\n"
            "• Acknowledge claim: within 14 days of notification\n"
            "• Settle or repudiate: within 90 days of notification\n"
            "• Disputed claims: refer to IPEC arbitration process\n\n"
            "**IPEC Reporting:**\n"
            "• Claims settlement ratios reported in quarterly FSR-1 returns\n"
            "• Healthy benchmark: claims settlement ratio above 80%\n"
            "• Formula: Claims Paid ÷ Claims Incurred\n\n"
            "**InsureIntel CSP Module** weights claims settlement capacity at 30%: "
            "WCS = 0.35×solvency + **0.30×claims** + 0.20×reserves + 0.15×liquidity."
        ),
    },
    {
        "intent": "exclusions",
        "patterns": [
            r"exclusion",
            r"excluded\s+(risk|peril|cover)",
            r"not\s+covered",
            r"policy\s+exclusion",
            r"carve.?out",
        ],
        "response": (
            "**Common Policy Exclusions** in Zimbabwean insurance:\n\n"
            "**Standard exclusions across most policies:**\n"
            "• War, civil commotion, political violence (ZEPARU endorsement available)\n"
            "• Nuclear and radioactive contamination\n"
            "• Wilful misconduct, fraud, or illegal acts by the insured\n"
            "• Gradual deterioration, wear-and-tear, and inherent vice\n"
            "• Consequential loss (unless specifically endorsed)\n\n"
            "**Motor-specific exclusions:**\n"
            "• Unlicensed driver operating the vehicle\n"
            "• Vehicle used outside permitted purpose\n\n"
            "**Life/health-specific:**\n"
            "• Pre-existing conditions (disclosure obligations apply)\n"
            "• Suicide within the contestability period\n\n"
            "The **InsureIntel Clause Deviation** module flags exclusions that "
            "deviate from standard market wording and assigns a severity score."
        ),
    },
    {
        "intent": "reinsurance",
        "patterns": [
            r"reinsurance",
            r"\breinsur",
            r"\btreaty\b",
            r"facultative",
            r"retrocession",
            r"zimre",
            r"zb\s*reinsurance",
        ],
        "response": (
            "**Reinsurance in Zimbabwe:**\n\n"
            "**Mandatory local retention (IPEC requirement):**\n"
            "• All insurers must cede a minimum 20% of premium income to ZB Reinsurance "
            "(ZimRe) under the local retention policy\n"
            "• Offshore placements above specified thresholds require IPEC pre-approval\n\n"
            "**Types of reinsurance:**\n"
            "• **Treaty** — Ongoing agreement covering an entire portfolio of risks; "
            "automatic acceptance within defined parameters\n"
            "• **Facultative** — Individual risk placement for large, unusual, or "
            "high-value risks not fitting treaty terms\n"
            "• **Proportional** — Share premium and claims in agreed ratio\n"
            "• **Non-proportional (XL)** — Reinsurer pays above a retention threshold\n\n"
            "InsureIntel classifies uploaded documents as Policy Wordings, "
            "**Reinsurance Treaties**, Claims Documents, or Broker Agreements."
        ),
    },
    {
        "intent": "csp_module",
        "patterns": [
            r"\bcsp\b",
            r"claims\s+settlement\s+power",
            r"weighted\s+composite",
            r"\bwcs\b",
            r"insurer\s+(strength|assessment|rating|score)",
            r"financial\s+strength",
        ],
        "response": (
            "**Claims Settlement Power (CSP) Module:**\n\n"
            "The CSP module assesses insurer financial strength using the "
            "Weighted Composite Score (WCS):\n\n"
            "**WCS = 0.35×Solvency + 0.30×Claims Settlement + 0.20×Reserves + 0.15×Liquidity**\n\n"
            "Weight justification (derived from IPEC FSR-1 distressed insurer register):\n"
            "• 35% Solvency — primary regulatory obligation under Insurance Act\n"
            "• 30% Claims Settlement — direct policyholder impact metric\n"
            "• 20% Reserves — indicator of long-term obligation management\n"
            "• 15% Liquidity — short-term payment capacity\n\n"
            "**Score interpretation:**\n"
            "• 80–100: Strong Financial Position\n"
            "• 60–79: Adequate — Monitor key ratios\n"
            "• 40–59: Enhanced Due Diligence Required\n"
            "• 0–39: Significant Concerns — Escalate to compliance\n\n"
            "An XGBoost anomaly detection layer identifies distress signals, "
            "with SHAP values explaining each contributing factor."
        ),
    },
    {
        "intent": "ner_entities",
        "patterns": [
            r"named\s+entity",
            r"\bner\b",
            r"entity\s+extract",
            r"what\s+entities",
            r"extract\s+information",
            r"information\s+extract",
        ],
        "response": (
            "**InsureIntel extracts 8 entity types** from insurance documents:\n\n"
            "• **MONEY** — Premium amounts, coverage limits, deductibles, sum insured\n"
            "• **DATE** — Policy inception date, expiry date, renewal date\n"
            "• **ORG** — Insurer name, broker name, reinsurer, co-insurer\n"
            "• **PERSON** — Named insured, beneficiary, signatory, contact persons\n"
            "• **CLAUSE** — Referenced clause numbers (e.g. Clause 3.1, Section 7)\n"
            "• **RISK** — Perils covered, risk categories, hazard descriptions\n"
            "• **LOCATION** — Geographic coverage territories, premises addresses\n"
            "• **PERCENT** — Percentage rates, margins, deductible rates\n\n"
            "Extraction uses a spaCy NER model fine-tuned on Zimbabwean insurance "
            "documents. Navigate to **Analysis → NER Extraction** to view results."
        ),
    },
    {
        "intent": "compliance",
        "patterns": [
            r"\bcompliance\b",
            r"\bcomply\b",
            r"regulatory\s+(check|review|requirement)",
            r"non.?compliant",
            r"mandatory\s+clause",
            r"required\s+disclosure",
        ],
        "response": (
            "**InsureIntel Compliance Center** checks documents against:\n\n"
            "**Mandatory requirements validated:**\n"
            "• Zimbabwe Insurance Act [Chapter 24:07] mandatory clauses\n"
            "• IPEC disclosure requirements and prohibited language\n"
            "• Mandatory coverage inclusions (e.g. statutory third-party liability)\n"
            "• Standard wording benchmarks for the Zimbabwean market\n\n"
            "**How to run a compliance check:**\n"
            "1. Upload your document (Documents → Upload)\n"
            "2. Navigate to Analysis → Compliance Center\n"
            "3. Select the document and click 'Run Compliance Check'\n"
            "4. Review the pass/fail results with severity weightings\n"
            "5. Export the compliance report as PDF\n\n"
            "Results show pass/fail per rule, severity level "
            "(Critical / Major / Minor), and recommended corrective action."
        ),
    },
    {
        "intent": "document_upload",
        "patterns": [
            r"upload\s+(a\s+)?document",
            r"how\s+to\s+upload",
            r"upload\s+file",
            r"submit\s+document",
            r"add\s+(a\s+)?document",
            r"supported\s+(file\s+)?format",
        ],
        "response": (
            "**Uploading documents to InsureIntel:**\n\n"
            "**Supported formats:** PDF, DOCX, PNG, JPG (max 50MB per file)\n\n"
            "**Upload process:**\n"
            "1. Go to **Documents → Upload** in the sidebar\n"
            "2. Drag and drop your file, or click 'Choose File'\n"
            "3. Select document type (or let the classifier detect it automatically):\n"
            "   - Policy Wording\n"
            "   - Reinsurance Treaty\n"
            "   - Claims Document\n"
            "   - Broker Agreement\n"
            "4. Click **Upload & Analyse**\n\n"
            "**What happens next:**\n"
            "• Text is extracted (PDF text or OCR for scanned documents)\n"
            "• Document type is classified (TF-IDF + Logistic Regression)\n"
            "• NER entities are extracted (8 entity types)\n"
            "• Risk score and compliance check are generated\n"
            "• Results appear in the Analysis section within seconds"
        ),
    },
    {
        "intent": "multilingual",
        "patterns": [
            r"\bshona\b",
            r"\bndebele\b",
            r"multilingual",
            r"language\s+(support|detect)",
            r"translate",
            r"translation",
        ],
        "response": (
            "**Multilingual Support in InsureIntel:**\n\n"
            "The platform supports documents and queries in:\n"
            "• **English** — Full native support\n"
            "• **Shona** — Machine translation via MarianMT (Helsinki-NLP model)\n\n"
            "**Shona translation pipeline:**\n"
            "1. Language detection using XLM-RoBERTa\n"
            "2. Shona → English translation via MarianMT\n"
            "3. NLP analysis performed on translated English text\n"
            "4. Results displayed in original language\n\n"
            "Navigate to **Analysis → Multilingual** to run language detection "
            "and translation on any uploaded document.\n\n"
            "Note: Translation accuracy improves with formal insurance language. "
            "Legal terms may require manual review."
        ),
    },
]

# Compile patterns once at module load for performance
_COMPILED_KB: list[dict[str, Any]] = [
    {
        **entry,
        "compiled": [re.compile(p, re.IGNORECASE) for p in entry["patterns"]],
    }
    for entry in _KB
]

# Stop words for document keyword search
_STOP_WORDS: frozenset[str] = frozenset({
    "what", "is", "are", "the", "a", "an", "in", "of", "to", "for",
    "and", "or", "how", "does", "do", "this", "that", "it", "its",
    "with", "on", "at", "by", "from", "was", "be", "been", "has",
    "have", "had", "will", "would", "could", "should", "may", "might",
    "which", "who", "when", "where", "why", "about", "clause", "me",
    "tell", "explain", "show", "find", "give", "please",
})


# ─────────────────────────────────────────────────────────────────────────────
# Matching logic
# ─────────────────────────────────────────────────────────────────────────────

def _match_intent(message: str) -> str | None:
    """
    Score all knowledge base entries against the message.
    Returns the response of the highest-scoring entry, or None.
    """
    best_score = 0
    best_response: str | None = None

    for entry in _COMPILED_KB:
        score = sum(1 for pat in entry["compiled"] if pat.search(message))
        if score > best_score:
            best_score = score
            best_response = entry["response"]

    return best_response if best_score > 0 else None


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a query string."""
    tokens = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return [t for t in tokens if t not in _STOP_WORDS]


def _search_document_text(text: str, question: str, max_sentences: int = 3) -> str | None:
    """
    Keyword search over extracted document text.
    Returns the most relevant sentences joined, or None if nothing found.
    """
    if not text or not question:
        return None

    keywords = _extract_keywords(question)
    if not keywords:
        return None

    sentences = re.split(r'(?<=[.!?])\s+', text)
    scored: list[tuple[float, str]] = []

    for sentence in sentences:
        stripped = sentence.strip()
        if len(stripped) < 15:
            continue
        sentence_lower = stripped.lower()
        score = sum(1.0 for kw in keywords if kw in sentence_lower)
        if score > 0:
            # Slight length bonus to prefer more informative sentences
            score += len(stripped) / 2000.0
            scored.append((score, stripped))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    return " ".join(s for _, s in scored[:max_sentences])


def _get_document_text(db: Session, document_id: int) -> tuple[str, str]:
    """Fetch extracted text and filename for a document by primary key."""
    try:
        from app.modules.documents.model import Document
        doc = db.get(Document, document_id)
        if doc is None:
            return "", ""
        title = (
            getattr(doc, "title", None)
            or getattr(doc, "filename", "")
            or f"Document #{document_id}"
        )
        text = (
            getattr(doc, "extracted_text", None)
            or getattr(doc, "raw_text", None)
            or getattr(doc, "content", None)
            or ""
        )
        # Cap at 20k chars — enough for a full policy document
        return text[:20000], str(title)
    except Exception as exc:
        logger.warning("Could not fetch document %s: %s", document_id, exc)
        return "", ""


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/message", response_model=ChatResponse)
async def chat_message(
    req: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Offline chatbot endpoint.

    Decision cascade:
      1. Document context  → search extracted text if document_id is set
      2. Intent matching   → knowledge base lookup
      3. Fallback          → informative "I don't know" with resource links
    """
    sources: list[str] = []
    response_text: str = ""

    # 1. Document-grounded answer
    if req.document_id:
        doc_text, doc_title = _get_document_text(db, req.document_id)
        if doc_text:
            doc_answer = _search_document_text(doc_text, req.message)
            if doc_answer:
                response_text = (
                    f"**From {doc_title}:**\n\n{doc_answer}\n\n"
                    "_(Extracted from document text — verify against the original.)_"
                )
                sources.append(doc_title)

    # 2. Knowledge base intent matching
    if not response_text:
        kb_answer = _match_intent(req.message)
        if kb_answer:
            response_text = kb_answer

    # 3. Fallback
    if not response_text:
        response_text = (
            "I don't have specific information on that in my offline knowledge base.\n\n"
            "**Suggested resources:**\n"
            "• IPEC website: ipec.co.zw\n"
            "• Zimbabwe Insurance Act: parlzim.gov.zw\n"
            "• Your compliance officer for case-specific advice\n\n"
            "Try asking about: **IPEC**, **Insurance Act**, **solvency**, "
            "**claims settlement**, **exclusions**, **reinsurance**, **CSP module**, "
            "**NER extraction**, **compliance**, or **document upload**."
        )

    return ChatResponse(response=response_text, sources=sources)
