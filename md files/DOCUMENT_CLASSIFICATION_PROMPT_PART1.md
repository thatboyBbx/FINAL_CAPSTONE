# Claude Code Prompt: Document Classification for Insurance Documents

## PROJECT CONTEXT

You are working on an **Insurance Document Intelligence Platform** for Zimbabwe. This is a final-year BSc AI/ML dissertation project. The platform automates analysis of insurance documents (policy wordings, reinsurance treaties, claims documentation) using NLP, ML, and OCR.

**Current Status:**
- Backend architecture: ~92% complete (FastAPI + SQLAlchemy + Pydantic v2)
- NER extraction: Implemented or in progress
- OCR: Implemented or in progress
- Compliance checking: Implemented or in progress
- **CRITICAL GAP:** Document model has `document_category` field but NO classifier to populate it
- Project location: `C:\Users\lenovo\Desktop\EXPERIMENT\` (your actual project path)

**Tech Stack:**
- Backend: Python 3.11, FastAPI, SQLAlchemy (mapped_column syntax), Pydantic v2
- ML: scikit-learn, XGBoost, sentence-transformers
- NLP: TF-IDF, fastText, or BERT-based classification
- Database: SQLite (production: PostgreSQL)

---

## PROBLEM STATEMENT

**Current Issue:**
```python
# app/modules/documents/model.py
class Document(Base):
    document_category = Column(String(100), nullable=True, index=True)
    # ☝️ This field is ALWAYS NULL - no classifier populates it
```

**Impact:**
1. Cannot route documents to specialized processing pipelines
2. Cannot apply category-specific compliance rules (motor vs life vs property)
3. Cannot provide category-specific insights
4. Dashboard statistics are incomplete

**Solution:** Build a lightweight, fast document classifier that automatically categorizes uploaded documents into 4 main types:
1. **Policy Wording** - Standard insurance policy documents
2. **Reinsurance Treaty** - Reinsurance agreements
3. **Claims Documentation** - Claim forms, assessments, settlements
4. **Broker Agreement** - Brokerage contracts and commission agreements

---

## TASK: IMPLEMENT DOCUMENT CLASSIFIER

### Objective
Build a production-ready document classifier that automatically categorizes insurance documents with >85% accuracy using a lightweight ML model (TF-IDF + Logistic Regression or fastText).

---

## PART 1: TRAINING DATA PREPARATION

### 1.1 Create Synthetic Training Dataset

**File:** `scripts/generate_classification_training_data.py`

```python
"""
Generate synthetic training data for document classification.

Creates labeled examples for 4 document categories:
1. Policy Wording
2. Reinsurance Treaty
3. Claims Documentation
4. Broker Agreement

Uses Claude API to generate realistic insurance document excerpts.
Fallback: Rule-based generation if API unavailable.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Output directory
TRAINING_DATA_DIR = Path("storage/training_data")
TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)


# Document category templates for rule-based generation
POLICY_WORDING_TEMPLATES = [
    """
    MOTOR VEHICLE INSURANCE POLICY
    
    Policy Number: {policy_num}
    
    SECTION A - COVERAGE
    This policy provides coverage for loss or damage to the insured vehicle arising from:
    (a) Collision or overturning
    (b) Fire, explosion, or lightning
    (c) Theft or attempted theft
    (d) Malicious damage
    
    SECTION B - EXCLUSIONS
    The Insurer shall not be liable for:
    1. Wear and tear
    2. Mechanical or electrical breakdown
    3. Driving under the influence of alcohol or drugs
    
    SECTION C - CONDITIONS
    Sum Insured: ${sum_insured}
    Premium: ${premium} per annum
    Excess: ${excess} per claim
    
    The Insured must notify any claim within 30 days of the incident.
    """,
    """
    PROPERTY ALL RISKS INSURANCE POLICY
    
    INSURED: {insured_name}
    POLICY PERIOD: {start_date} to {end_date}
    
    COVERAGE:
    This policy covers all risks of physical loss or damage to the property described below,
    except as provided in the Exclusions section.
    
    PROPERTY INSURED:
    Building situated at {address}
    Sum Insured: ${sum_insured}
    
    PREMIUM: ${premium} annually
    DEDUCTIBLE: ${deductible} per occurrence
    
    CLAIMS PROCEDURE:
    All claims must be reported within 48 hours with supporting documentation.
    """,
    """
    LIFE ASSURANCE POLICY
    
    Life Assured: {life_assured}
    Policy Number: {policy_num}
    
    BENEFITS:
    Death Benefit: ${death_benefit}
    Maturity Benefit: ${maturity_benefit}
    
    PREMIUMS:
    Monthly Premium: ${premium}
    Premium Payment Term: {term} years
    
    EXCLUSIONS:
    Death by suicide within 12 months of policy commencement
    Death due to engaging in hazardous activities not disclosed
    
    BENEFICIARY DESIGNATION:
    The Life Assured may nominate beneficiaries who shall receive the death benefit.
    """
]

REINSURANCE_TREATY_TEMPLATES = [
    """
    REINSURANCE TREATY
    
    Between: {reinsured} (the Reinsured)
    And: {reinsurer} (the Reinsurer)
    
    Treaty Type: Quota Share Treaty
    Treaty Period: {start_date} to {end_date}
    
    ARTICLE 1 - SCOPE
    The Reinsurer agrees to accept {quota_share}% of all policies written by the Reinsured
    under the following classes of business:
    - Motor Insurance
    - Property Insurance
    - Liability Insurance
    
    ARTICLE 2 - RETENTION AND CESSION
    The Reinsured shall retain {retention}% of each risk and cede {cession}% to the Reinsurer.
    
    ARTICLE 3 - PREMIUM
    Reinsurance Premium: {premium_rate}% of gross written premium
    Commission: {commission_rate}%
    
    ARTICLE 4 - CLAIMS
    The Reinsurer shall pay its share of all claims within 30 days of settlement by the Reinsured.
    """,
    """
    EXCESS OF LOSS REINSURANCE AGREEMENT
    
    Reinsured: {reinsured}
    Reinsurer: {reinsurer}
    
    Treaty Year: {year}
    
    SECTION 1 - LIMIT AND RETENTION
    Layer: ${layer_limit} xs ${retention}
    The Reinsurer shall indemnify the Reinsured for the amount of each loss
    in excess of ${retention} up to ${layer_limit}.
    
    SECTION 2 - PREMIUM
    Provisional Premium: ${provisional_premium}
    Minimum Premium: ${minimum_premium}
    Deposit Premium due: {due_date}
    
    SECTION 3 - CLAIMS COOPERATION
    The Reinsured shall notify the Reinsurer of all claims exceeding ${notification_threshold}
    within 72 hours.
    
    SECTION 4 - ARBITRATION
    Any disputes shall be resolved by arbitration in accordance with ARIAS rules.
    """
]

CLAIMS_DOC_TEMPLATES = [
    """
    MOTOR VEHICLE CLAIM FORM
    
    Claim Number: {claim_num}
    Policy Number: {policy_num}
    Date of Loss: {loss_date}
    
    CLAIMANT DETAILS:
    Name: {claimant_name}
    Contact: {contact}
    
    INCIDENT DETAILS:
    Date and Time: {incident_datetime}
    Location: {location}
    Description: {description}
    
    VEHICLE DAMAGE:
    Make/Model: {vehicle}
    Registration: {registration}
    Estimated Repair Cost: ${repair_cost}
    
    POLICE REPORT:
    Report Number: {police_report_num}
    Attending Officer: {officer_name}
    
    DECLARATION:
    I declare that the information provided is true and accurate to the best of my knowledge.
    
    Signature: _______________
    Date: {declaration_date}
    """,
    """
    CLAIM ASSESSMENT REPORT
    
    Claim Reference: {claim_ref}
    Insured: {insured_name}
    
    ASSESSMENT SUMMARY:
    Loss Adjustor: {adjustor_name}
    Inspection Date: {inspection_date}
    
    FINDINGS:
    Nature of Loss: {nature_of_loss}
    Cause: {cause}
    
    VALUATION:
    Sum Insured: ${sum_insured}
    Assessed Loss: ${assessed_loss}
    Less Depreciation: ${depreciation}
    Less Excess: ${excess}
    
    NET CLAIM AMOUNT: ${net_claim}
    
    RECOMMENDATION:
    {recommendation}
    
    This claim {approval_status}.
    
    Signed: {adjustor_signature}
    Date: {signature_date}
    """,
    """
    CLAIM SETTLEMENT ADVICE
    
    Settlement Number: {settlement_num}
    Claim Number: {claim_num}
    
    CLAIMANT: {claimant_name}
    
    SETTLEMENT BREAKDOWN:
    Assessed Claim Value: ${claim_value}
    Less Policy Excess: ${excess}
    Less Salvage Recovery: ${salvage}
    
    TOTAL PAYABLE: ${total_payable}
    
    PAYMENT DETAILS:
    Method: {payment_method}
    Bank: {bank_name}
    Account Number: {account_num}
    
    Payment Date: {payment_date}
    
    This settlement is in full and final discharge of all liability under Policy {policy_num}.
    """
]

BROKER_AGREEMENT_TEMPLATES = [
    """
    INSURANCE BROKERAGE AGREEMENT
    
    Between: {insurer_name} (the Insurer)
    And: {broker_name} (the Broker)
    
    Effective Date: {effective_date}
    
    ARTICLE 1 - APPOINTMENT
    The Insurer appoints the Broker as its authorized insurance broker for the territory of Zimbabwe.
    
    ARTICLE 2 - BROKER RESPONSIBILITIES
    The Broker shall:
    (a) Solicit and procure insurance business
    (b) Issue cover notes and policy documents
    (c) Collect premiums from policyholders
    (d) Remit premiums to the Insurer within {remittance_days} days
    
    ARTICLE 3 - COMMISSION
    Commission Rate:
    - Motor Insurance: {motor_commission}%
    - Property Insurance: {property_commission}%
    - Life Insurance: {life_commission}%
    
    Commission shall be paid monthly within {commission_payment_days} days of premium receipt.
    
    ARTICLE 4 - AUTHORITY LIMITS
    Maximum Sum Insured per Risk: ${max_sum_insured}
    Binding Authority: ${binding_authority_limit}
    
    ARTICLE 5 - TERMINATION
    Either party may terminate this agreement with {notice_period} days written notice.
    """,
    """
    BROKER COMMISSION STATEMENT
    
    Broker: {broker_name}
    Statement Period: {period_start} to {period_end}
    
    PREMIUM SUMMARY:
    Gross Written Premium: ${gwp}
    Less Returns/Cancellations: ${returns}
    Net Written Premium: ${nwp}
    
    COMMISSION CALCULATION:
    Motor ({motor_rate}%): ${motor_commission}
    Property ({property_rate}%): ${property_commission}
    Life ({life_rate}%): ${life_commission}
    
    TOTAL COMMISSION DUE: ${total_commission}
    
    Less Previous Advances: ${advances}
    
    NET PAYABLE: ${net_payable}
    
    Payment will be made via bank transfer within 7 working days.
    """
]


def generate_rule_based_training_data(samples_per_category: int = 50) -> List[Dict[str, str]]:
    """
    Generate training data using rule-based templates.
    
    Args:
        samples_per_category: Number of samples to generate per category
        
    Returns:
        List of {"text": str, "category": str} dictionaries
    """
    import random
    from datetime import datetime, timedelta
    
    training_data = []
    
    # Category configs
    categories = {
        "policy_wording": {
            "templates": POLICY_WORDING_TEMPLATES,
            "label": "policy_wording"
        },
        "reinsurance_treaty": {
            "templates": REINSURANCE_TREATY_TEMPLATES,
            "label": "reinsurance_treaty"
        },
        "claims_documentation": {
            "templates": CLAIMS_DOC_TEMPLATES,
            "label": "claims_documentation"
        },
        "broker_agreement": {
            "templates": BROKER_AGREEMENT_TEMPLATES,
            "label": "broker_agreement"
        }
    }
    
    # Generate samples
    for category_name, config in categories.items():
        logger.info("Generating %d samples for: %s", samples_per_category, category_name)
        
        for i in range(samples_per_category):
            template = random.choice(config["templates"])
            
            # Fill template with random values
            filled_text = template.format(
                policy_num=f"POL-{random.randint(1000, 9999)}",
                claim_num=f"CLM-{random.randint(1000, 9999)}",
                settlement_num=f"SET-{random.randint(1000, 9999)}",
                claim_ref=f"REF-{random.randint(10000, 99999)}",
                insured_name=random.choice(["John Doe", "ABC Limited", "Jane Smith", "XYZ Corporation"]),
                life_assured=random.choice(["John Doe", "Jane Smith", "Robert Brown"]),
                claimant_name=random.choice(["John Doe", "Jane Smith", "Robert Brown"]),
                reinsured=random.choice(["First Mutual Zimbabwe", "Old Mutual", "Zimre Holdings"]),
                reinsurer=random.choice(["Munich Re", "Swiss Re", "Hannover Re"]),
                insurer_name=random.choice(["First Mutual Zimbabwe", "Old Mutual", "Zimre Holdings"]),
                broker_name=random.choice(["ABC Insurance Brokers", "XYZ Risk Solutions", "Prime Brokers Limited"]),
                adjustor_name=random.choice(["Peter Loss Adjustor", "Sarah Assessment Ltd"]),
                sum_insured=f"{random.randint(10, 500)},000",
                death_benefit=f"{random.randint(50, 500)},000",
                maturity_benefit=f"{random.randint(30, 300)},000",
                premium=f"{random.randint(500, 5000)}",
                excess=f"{random.randint(100, 1000)}",
                deductible=f"{random.randint(100, 1000)}",
                repair_cost=f"{random.randint(500, 10000)}",
                claim_value=f"{random.randint(1000, 50000)}",
                assessed_loss=f"{random.randint(1000, 50000)}",
                depreciation=f"{random.randint(100, 5000)}",
                salvage=f"{random.randint(0, 2000)}",
                net_claim=f"{random.randint(1000, 40000)}",
                total_payable=f"{random.randint(1000, 40000)}",
                quota_share=random.randint(20, 50),
                retention=random.randint(50, 80),
                cession=random.randint(20, 50),
                premium_rate=random.randint(5, 15),
                commission_rate=random.randint(10, 25),
                motor_commission=random.randint(10, 20),
                property_commission=random.randint(12, 22),
                life_commission=random.randint(15, 30),
                motor_rate=random.randint(10, 20),
                property_rate=random.randint(12, 22),
                life_rate=random.randint(15, 30),
                layer_limit=f"{random.randint(500, 2000)},000",
                retention=f"{random.randint(50, 200)},000",
                provisional_premium=f"{random.randint(50, 200)},000",
                minimum_premium=f"{random.randint(25, 100)},000",
                notification_threshold=f"{random.randint(50, 200)},000",
                gwp=f"{random.randint(500, 5000)},000",
                returns=f"{random.randint(10, 100)},000",
                nwp=f"{random.randint(450, 4900)},000",
                total_commission=f"{random.randint(50, 500)},000",
                advances=f"{random.randint(0, 100)},000",
                net_payable=f"{random.randint(40, 450)},000",
                max_sum_insured=f"{random.randint(100, 500)},000",
                binding_authority_limit=f"{random.randint(50, 200)},000",
                remittance_days=random.choice([7, 14, 30]),
                commission_payment_days=random.choice([7, 14, 30]),
                notice_period=random.choice([30, 60, 90]),
                term=random.choice([10, 15, 20, 25]),
                start_date=(datetime.now() - timedelta(days=random.randint(0, 365))).strftime("%d/%m/%Y"),
                end_date=(datetime.now() + timedelta(days=random.randint(0, 365))).strftime("%d/%m/%Y"),
                loss_date=(datetime.now() - timedelta(days=random.randint(1, 90))).strftime("%d/%m/%Y"),
                incident_datetime=(datetime.now() - timedelta(days=random.randint(1, 90))).strftime("%d/%m/%Y %H:%M"),
                inspection_date=datetime.now().strftime("%d/%m/%Y"),
                declaration_date=datetime.now().strftime("%d/%m/%Y"),
                signature_date=datetime.now().strftime("%d/%m/%Y"),
                payment_date=datetime.now().strftime("%d/%m/%Y"),
                effective_date=datetime.now().strftime("%d/%m/%Y"),
                due_date=datetime.now().strftime("%d/%m/%Y"),
                period_start=datetime.now().strftime("%B %Y"),
                period_end=(datetime.now() + timedelta(days=30)).strftime("%B %Y"),
                year=datetime.now().year,
                address=f"{random.randint(1, 999)} Main Street, Harare",
                location=random.choice(["Harare CBD", "Borrowdale", "Eastlea", "Belvedere"]),
                description=random.choice([
                    "Collision with another vehicle",
                    "Fire damage to building",
                    "Theft of vehicle",
                    "Water damage from burst pipe"
                ]),
                vehicle=random.choice(["Toyota Corolla", "Honda Fit", "Nissan March", "Mazda Demio"]),
                registration=f"A{random.randint(100, 999)}-{random.randint(100, 999)}",
                police_report_num=f"PR{random.randint(10000, 99999)}",
                officer_name=random.choice(["Sgt. Moyo", "Const. Ncube", "Insp. Dube"]),
                nature_of_loss=random.choice(["Accidental damage", "Fire", "Theft", "Natural disaster"]),
                cause=random.choice(["Driver error", "Third party negligence", "Electrical fault", "Weather"]),
                recommendation=random.choice([
                    "Claim approved for settlement",
                    "Further investigation required",
                    "Partial settlement recommended"
                ]),
                approval_status=random.choice(["is approved", "requires further review", "is partially approved"]),
                adjustor_signature="_____________",
                contact=f"+263 {random.randint(700, 799)} {random.randint(100, 999)} {random.randint(100, 999)}",
                payment_method=random.choice(["EFT", "Cheque", "Mobile Money"]),
                bank_name=random.choice(["CBZ Bank", "FBC Bank", "Stanbic Bank", "NMB Bank"]),
                account_num=f"{random.randint(10000, 99999)}-{random.randint(1000, 9999)}",
            )
            
            training_data.append({
                "text": filled_text.strip(),
                "category": config["label"]
            })
    
    # Shuffle
    random.shuffle(training_data)
    
    logger.info("Generated %d total training samples", len(training_data))
    return training_data


def save_training_data(training_data: List[Dict[str, str]]) -> str:
    """Save training data to JSON file."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = TRAINING_DATA_DIR / f"document_classification_training_{timestamp}.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "data": training_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_samples": len(training_data),
            "categories": list(set(item["category"] for item in training_data)),
            "samples_per_category": {
                cat: sum(1 for item in training_data if item["category"] == cat)
                for cat in set(item["category"] for item in training_data)
            }
        }, f, indent=2)
    
    logger.info("Training data saved to: %s", output_path)
    return str(output_path)


def main():
    """Generate document classification training data."""
    print("\n" + "="*60)
    print("DOCUMENT CLASSIFICATION TRAINING DATA GENERATION")
    print("="*60)
    
    # Generate 50 samples per category (200 total)
    training_data = generate_rule_based_training_data(samples_per_category=50)
    
    # Save to file
    output_path = save_training_data(training_data)
    
    print(f"\n✅ Generated {len(training_data)} training samples")
    print(f"📁 Saved to: {output_path}")
    print("\nNext step: python scripts/train_document_classifier.py")


if __name__ == "__main__":
    main()
```

---

### 1.2 Create Model Training Script

**File:** `scripts/train_document_classifier.py`

```python
"""
Train document classification model.

Uses TF-IDF + Logistic Regression for fast, lightweight classification.

Performance targets:
- Accuracy: >85%
- Training time: <1 minute
- Inference time: <100ms per document
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
TRAINING_DATA_DIR = Path("storage/training_data")
MODEL_DIR = Path("storage/models/app")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class DocumentClassifierTrainer:
    """Trains document classification model."""
    
    def __init__(self) -> None:
        self.vectorizer = None
        self.classifier = None
        self.label_mapping = {
            "policy_wording": 0,
            "reinsurance_treaty": 1,
            "claims_documentation": 2,
            "broker_agreement": 3
        }
        self.reverse_mapping = {v: k for k, v in self.label_mapping.items()}
    
    def load_training_data(self, data_path: str) -> Tuple[List[str], List[int]]:
        """
        Load training data from JSON file.
        
        Returns:
            (texts, labels) tuple
        """
        logger.info("Loading training data from: %s", data_path)
        
        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)
        
        training_samples = data["data"]
        
        texts = [item["text"] for item in training_samples]
        labels = [self.label_mapping[item["category"]] for item in training_samples]
        
        logger.info("Loaded %d samples across %d categories", len(texts), len(set(labels)))
        
        return texts, labels
    
    def train(self, texts: List[str], labels: List[int]) -> Dict[str, Any]:
        """
        Train TF-IDF + Logistic Regression classifier.
        
        Returns:
            Training metrics
        """
        logger.info("Training document classifier...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=0.2, random_state=42, stratify=labels
        )
        
        logger.info("Train set: %d samples | Test set: %d samples", len(X_train), len(X_test))
        
        # Create TF-IDF vectorizer
        logger.info("Creating TF-IDF features...")
        self.vectorizer = TfidfVectorizer(
            max_features=2000,
            ngram_range=(1, 3),  # Unigrams, bigrams, trigrams
            min_df=2,
            max_df=0.95,
            strip_accents='unicode',
            lowercase=True,
            stop_words='english'
        )
        
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_test_vec = self.vectorizer.transform(X_test)
        
        logger.info("Feature matrix shape: %s", X_train_vec.shape)
        
        # Train classifier
        logger.info("Training Logistic Regression...")
        self.classifier = LogisticRegression(
            C=1.0,
            solver='lbfgs',
            max_iter=500,
            multi_class='multinomial',
            random_state=42,
            n_jobs=-1
        )
        
        self.classifier.fit(X_train_vec, y_train)
        
        # Evaluate
        logger.info("Evaluating model...")
        
        y_train_pred = self.classifier.predict(X_train_vec)
        y_test_pred = self.classifier.predict(X_test_vec)
        
        train_accuracy = (y_train_pred == y_train).mean()
        test_accuracy = (y_test_pred == y_test).mean()
        
        # Cross-validation
        cv_scores = cross_val_score(
            self.classifier, X_train_vec, y_train, cv=5, scoring='accuracy'
        )
        
        # Classification report
        report = classification_report(
            y_test, y_test_pred,
            target_names=list(self.label_mapping.keys()),
            output_dict=True
        )
        
        # Confusion matrix
        cm = confusion_matrix(y_test, y_test_pred)
        
        metrics = {
            "train_accuracy": round(train_accuracy, 4),
            "test_accuracy": round(test_accuracy, 4),
            "cv_accuracy_mean": round(cv_scores.mean(), 4),
            "cv_accuracy_std": round(cv_scores.std(), 4),
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
            "feature_count": X_train_vec.shape[1],
            "training_samples": len(X_train),
            "test_samples": len(X_test),
        }
        
        logger.info("Training complete!")
        logger.info("  Train Accuracy: %.2f%%", train_accuracy * 100)
        logger.info("  Test Accuracy: %.2f%%", test_accuracy * 100)
        logger.info("  CV Accuracy: %.2f%% (±%.2f%%)", 
                   cv_scores.mean() * 100, cv_scores.std() * 100)
        
        return metrics
    
    def save_model(self, metrics: Dict[str, Any]) -> None:
        """Save trained model and metadata."""
        # Save vectorizer
        vectorizer_path = MODEL_DIR / "document_classifier_vectorizer.joblib"
        joblib.dump(self.vectorizer, vectorizer_path)
        logger.info("Saved vectorizer to: %s", vectorizer_path)
        
        # Save classifier
        classifier_path = MODEL_DIR / "document_classifier_model.joblib"
        joblib.dump(self.classifier, classifier_path)
        logger.info("Saved classifier to: %s", classifier_path)
        
        # Save metadata
        metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "model_type": "TF-IDF + Logistic Regression",
            "categories": list(self.label_mapping.keys()),
            "label_mapping": self.label_mapping,
            "metrics": metrics,
            "vectorizer_path": str(vectorizer_path),
            "classifier_path": str(classifier_path),
        }
        
        metadata_path = MODEL_DIR / "document_classifier_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info("Saved metadata to: %s", metadata_path)


def main():
    """Train document classification model."""
    print("\n" + "="*60)
    print("DOCUMENT CLASSIFIER TRAINING")
    print("="*60)
    
    # Find latest training data
    training_files = list(TRAINING_DATA_DIR.glob("document_classification_training_*.json"))
    if not training_files:
        print("\n❌ No training data found!")
        print("Run: python scripts/generate_classification_training_data.py")
        return 1
    
    latest_file = max(training_files, key=lambda p: p.stat().st_mtime)
    print(f"\nUsing training data: {latest_file.name}")
    
    # Train
    trainer = DocumentClassifierTrainer()
    texts, labels = trainer.load_training_data(str(latest_file))
    metrics = trainer.train(texts, labels)
    
    # Save
    trainer.save_model(metrics)
    
    # Print summary
    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    print(f"Train Accuracy: {metrics['train_accuracy'] * 100:.2f}%")
    print(f"Test Accuracy: {metrics['test_accuracy'] * 100:.2f}%")
    print(f"CV Accuracy: {metrics['cv_accuracy_mean'] * 100:.2f}% (±{metrics['cv_accuracy_std'] * 100:.2f}%)")
    
    print("\nPer-Category Performance:")
    report = metrics['classification_report']
    for category in trainer.label_mapping.keys():
        if category in report:
            print(f"  {category:25s} - Precision: {report[category]['precision']:.3f}, "
                  f"Recall: {report[category]['recall']:.3f}, "
                  f"F1: {report[category]['f1-score']:.3f}")
    
    print("\n✅ Model saved to: storage/models/app/")
    print("\nNext step: Test the classifier on real documents")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

---

## PART 2: CLASSIFIER SERVICE

### 2.1 Create Document Classifier Service

**File:** `app/services/document_classifier_service.py`

```python
"""
Document Classification Service.

Automatically classifies insurance documents into categories:
1. Policy Wording
2. Reinsurance Treaty
3. Claims Documentation
4. Broker Agreement

Uses pre-trained TF-IDF + Logistic Regression model.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, Literal

import joblib

logger = logging.getLogger(__name__)

# Model paths
MODEL_DIR = Path("storage/models/app")
VECTORIZER_PATH = MODEL_DIR / "document_classifier_vectorizer.joblib"
CLASSIFIER_PATH = MODEL_DIR / "document_classifier_model.joblib"
METADATA_PATH = MODEL_DIR / "document_classifier_metadata.json"

# Type hint for document categories
DocumentCategory = Literal[
    "policy_wording",
    "reinsurance_treaty",
    "claims_documentation",
    "broker_agreement",
    "unknown"
]


class DocumentClassifierService:
    """
    Service for classifying insurance documents.
    
    Features:
    - Fast classification (<100ms)
    - Confidence scoring
    - Graceful fallback if model not found
    """
    
    def __init__(self) -> None:
        """Load pre-trained model or set to None if unavailable."""
        self.vectorizer = None
        self.classifier = None
        self.label_mapping = None
        self.reverse_mapping = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load vectorizer, classifier, and metadata."""
        try:
            if not VECTORIZER_PATH.exists() or not CLASSIFIER_PATH.exists():
                logger.warning(
                    "Document classifier not found. Run: python scripts/train_document_classifier.py"
                )
                return
            
            # Load vectorizer
            self.vectorizer = joblib.load(VECTORIZER_PATH)
            
            # Load classifier
            self.classifier = joblib.load(CLASSIFIER_PATH)
            
            # Load metadata
            if METADATA_PATH.exists():
                with open(METADATA_PATH, encoding="utf-8") as f:
                    metadata = json.load(f)
                    self.label_mapping = metadata.get("label_mapping", {})
                    self.reverse_mapping = {v: k for k, v in self.label_mapping.items()}
            
            logger.info("Document classifier loaded successfully")
            
        except Exception as exc:
            logger.error("Failed to load document classifier: %s", exc)
            self.vectorizer = None
            self.classifier = None
    
    def classify(self, document_text: str) -> Dict[str, Any]:
        """
        Classify document into one of 4 categories.
        
        Args:
            document_text: Full text of document
            
        Returns:
            {
                "category": str,  # policy_wording | reinsurance_treaty | claims_documentation | broker_agreement | unknown
                "confidence": float,  # 0-1
                "probabilities": {
                    "policy_wording": 0.75,
                    "reinsurance_treaty": 0.15,
                    "claims_documentation": 0.08,
                    "broker_agreement": 0.02
                },
                "method": "ml_model" | "fallback"
            }
        """
        # Check if model is loaded
        if self.vectorizer is None or self.classifier is None:
            logger.warning("Classifier not loaded - using keyword fallback")
            return self._fallback_classification(document_text)
        
        try:
            # Vectorize text
            X = self.vectorizer.transform([document_text])
            
            # Predict
            prediction = self.classifier.predict(X)[0]
            probabilities = self.classifier.predict_proba(X)[0]
            
            # Map to category name
            category = self.reverse_mapping.get(prediction, "unknown")
            confidence = float(probabilities[prediction])
            
            # Build probability dictionary
            prob_dict = {}
            for label_name, label_id in self.label_mapping.items():
                prob_dict[label_name] = round(float(probabilities[label_id]), 4)
            
            return {
                "category": category,
                "confidence": round(confidence, 4),
                "probabilities": prob_dict,
                "method": "ml_model",
            }
        
        except Exception as exc:
            logger.error("Classification failed: %s", exc)
            return self._fallback_classification(document_text)
    
    def _fallback_classification(self, document_text: str) -> Dict[str, Any]:
        """
        Simple keyword-based fallback if ML model unavailable.
        
        Uses keyword frequency to guess category.
        """
        text_lower = document_text.lower()
        
        # Keyword scores
        scores = {
            "policy_wording": 0.0,
            "reinsurance_treaty": 0.0,
            "claims_documentation": 0.0,
            "broker_agreement": 0.0,
        }
        
        # Policy wording keywords
        policy_keywords = [
            "policy", "coverage", "sum insured", "premium", "exclusions",
            "deductible", "excess", "insured", "insurer", "conditions",
            "section a", "section b", "policy period"
        ]
        scores["policy_wording"] = sum(1 for kw in policy_keywords if kw in text_lower)
        
        # Reinsurance treaty keywords
        treaty_keywords = [
            "reinsurance", "treaty", "reinsured", "reinsurer", "cession",
            "retention", "quota share", "excess of loss", "article",
            "layer", "reinstatement", "arbitration"
        ]
        scores["reinsurance_treaty"] = sum(1 for kw in treaty_keywords if kw in text_lower)
        
        # Claims documentation keywords
        claims_keywords = [
            "claim", "claimant", "loss", "incident", "damage",
            "assessment", "adjustor", "settlement", "police report",
            "repair", "declaration", "claim number"
        ]
        scores["claims_documentation"] = sum(1 for kw in claims_keywords if kw in text_lower)
        
        # Broker agreement keywords
        broker_keywords = [
            "broker", "brokerage", "commission", "appointment",
            "binding authority", "remit", "solicit", "procure",
            "premium remittance", "broker responsibilities"
        ]
        scores["broker_agreement"] = sum(1 for kw in broker_keywords if kw in text_lower)
        
        # Find highest score
        total_score = sum(scores.values())
        if total_score == 0:
            # No keywords found
            return {
                "category": "unknown",
                "confidence": 0.0,
                "probabilities": {k: 0.25 for k in scores.keys()},  # Uniform distribution
                "method": "fallback",
            }
        
        # Normalize to probabilities
        probabilities = {k: round(v / total_score, 4) for k, v in scores.items()}
        category = max(probabilities, key=probabilities.get)
        confidence = probabilities[category]
        
        return {
            "category": category,
            "confidence": confidence,
            "probabilities": probabilities,
            "method": "fallback",
        }
```

---

**CONTINUED IN NEXT MESSAGE** (prompt is getting long - shall I continue with Part 3: Integration, Part 4: API & UI, and Part 5: Testing?)

