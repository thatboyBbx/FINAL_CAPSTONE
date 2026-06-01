"""
gen_document_training.py
========================
Generates a production-quality document classifier training dataset for the
InsureIntel Zimbabwe platform.

Categories (9 total, 60 samples each = 540 samples):
  1. policy_wording          - Motor, fire, property, life, liability policies
  2. reinsurance_treaty      - XL, quota share, facultative reinsurance
  3. claims_documentation    - Claim forms, loss adjuster reports, assessments
  4. broker_agreement        - Brokerage agreements, commission schedules
  5. actuarial_report        - Actuarial valuations, reserve assessments
  6. compliance_letter       - IPEC compliance notices, regulatory correspondence
  7. annual_return           - IPEC FSR-1 annual returns, quarterly submissions
  8. licence_notice          - IPEC licensing documents, renewals, approvals
  9. court_order             - Court orders, legal judgments, garnishee orders

Output: storage/datasets/production/document_classifier_training.json
        storage/datasets/production/document_classifier_training.csv

Run:    python scripts/gen_document_training.py
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from datetime import date, timedelta

RNG = random.Random(42)

# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------
OUT_DIR = Path("storage/datasets/production")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
ZIMBABWEAN_INSURERS = [
    "CBZ Insurance Limited", "NicozDiamond Insurance", "Old Mutual Insurance",
    "FBC Insurance", "Econet Insurance", "Zimnat Lion Insurance",
    "First Mutual Life Assurance Company", "Fidelity Life Assurance Company",
    "Alliance Insurance", "Allied Insurance Ltd", "Zimre Holdings",
    "Cell Insurance Company Ltd", "Hamilton Insurance", "AFC Insurance",
    "Clarion Insurance", "Quality Insurance", "Sanctuary Insurance",
    "CBZ Life Limited", "Nyaradzo Life Assurance Company", "Doves Life Assurance",
    "Trans Africa Reinsurance Company", "Heritage Life Assurance Company",
    "Evolution Health & Life Assurance Company", "Nhaka Life Assurance",
]
BROKERS = [
    "Prime Brokers Limited", "XYZ Risk Solutions", "Afre Corporation",
    "Heritage Insurance Brokers", "Zim Insurance Brokers", "Reliance Brokers",
    "Pan Africa Brokers", "Sterling Insurance Brokers", "Eagle Brokers Ltd",
    "First Capital Brokers",
]
REINSURERS = ["Swiss Re", "Munich Re", "Africa Re", "ZEP-Re", "Zimre Holdings"]
INDIVIDUALS = [
    "John Moyo", "Mary Chikwanda", "Tendai Mhuriro", "Farai Ncube",
    "Priscilla Dube", "Samuel Mutasa", "Grace Chigumba", "Peter Nkomo",
    "Rutendo Macheka", "Blessing Sibanda", "Alice Mwale", "David Zvenyika",
]
COMPANIES = [
    "ZimBev Holdings Ltd", "Delta Corporation Ltd", "Innscor Africa Ltd",
    "Econet Wireless Zimbabwe Ltd", "OK Zimbabwe Ltd", "SeedCo Limited",
    "Bindura Nickel Corporation", "Zimbabwe Iron & Steel Company",
    "First Capital Bank Ltd", "CBZ Holdings Ltd",
]

def _rng_date(start_year: int = 2020, end_year: int = 2026) -> str:
    """Return a random date string between start_year and end_year."""
    start = date(start_year, 1, 1)
    end   = date(end_year, 5, 1)
    delta = (end - start).days
    return (start + timedelta(days=RNG.randint(0, delta))).strftime("%d/%m/%Y")

def _amount(lo: int, hi: int) -> str:
    return f"${RNG.randint(lo, hi):,}"

def _pct(lo: float, hi: float) -> str:
    return f"{RNG.uniform(lo, hi):.1f}%"

def _pol_num() -> str:
    return f"POL-{RNG.randint(1000, 9999)}"

def _claim_num() -> str:
    return f"CLM-{RNG.randint(10000, 99999)}"

def _circular_num() -> str:
    year = RNG.randint(2018, 2026)
    num  = RNG.randint(1, 15)
    return f"Circular {num} of {year}"

# ---------------------------------------------------------------------------
# 1. POLICY WORDING
# ---------------------------------------------------------------------------
def _policy_wording() -> str:
    """Generate a realistic insurance policy wording document."""
    templates = [
        # Motor comprehensive
        lambda: f"""MOTOR VEHICLE INSURANCE POLICY — COMPREHENSIVE COVER

Policy Number: {_pol_num()}
Insured: {RNG.choice(INDIVIDUALS + list(COMPANIES))}
Insurer: {RNG.choice(ZIMBABWEAN_INSURERS)}
Policy Period: {_rng_date(2022, 2025)} to {_rng_date(2025, 2026)}
Vehicle Registration: {RNG.choice('ABCDFGHJKLMNPQRSTUVWXYZ')}{RNG.randint(100,999)}{RNG.choice('ABCDFGHJ')}

SECTION A — ACCIDENTAL LOSS OR DAMAGE
The Insurer agrees to indemnify the Insured against loss of or damage to the insured vehicle
caused by accidental collision or overturning, fire, external explosion, self-ignition, lightning,
burglary, housebreaking or theft occurring during the period of insurance.
Sum Insured: {_amount(15000, 120000)}
Territorial Limits: Zimbabwe, Zambia, Mozambique, Botswana, South Africa (COMESA extension)

SECTION B — THIRD PARTY LIABILITY
The Insurer will indemnify the Insured against all sums which the Insured shall become legally
liable to pay in respect of: (a) death of or bodily injury to any person; (b) damage to property
Third Party Property Damage Limit: {_amount(50000, 500000)}

SECTION C — EXCLUSIONS
This policy does not cover: (1) wear, tear, depreciation or mechanical breakdown; (2) damage
whilst the vehicle is driven by a person without a valid driver's licence; (3) use for hire or reward
unless specially noted; (4) consequential loss or damage.

SECTION D — CONDITIONS
Excess payable by the Insured: {_amount(300, 2000)} per claim.
Premium: {_amount(800, 6000)} per annum.
The Insured must notify the Insurer of any claim within {RNG.randint(7, 30)} days of the incident.

IPEC-Regulated Policy | Zimbabwe Insurance Act [Chapter 24:07]""",

        # Fire and property
        lambda: f"""FIRE AND ALLIED PERILS INSURANCE POLICY

Policy Number: {_pol_num()}
Insured: {RNG.choice(list(COMPANIES) + INDIVIDUALS)}
Insurer: {RNG.choice(ZIMBABWEAN_INSURERS)}
Risk Address: {RNG.randint(1, 200)} {RNG.choice(['Samora Machel Avenue', 'Julius Nyerere Way', 'Josiah Tongogara Avenue', 'Borrowdale Road', 'Harare Street'])}, Harare

DESCRIPTION OF PROPERTY INSURED
Buildings including fixtures and fittings constructed of brick under iron roof.
Contents: Office furniture, equipment, stock-in-trade and merchandise.

Sum Insured — Buildings: {_amount(100000, 5000000)}
Sum Insured — Contents: {_amount(50000, 2000000)}
Annual Premium (Buildings): {_amount(500, 25000)}
Annual Premium (Contents): {_amount(300, 15000)}

PERILS INSURED AGAINST
Fire | Lightning | Explosion | Aircraft damage | Impact by vehicles | Riot and strike |
Malicious damage | Storm, tempest, flood | Burst pipes | Earthquake (if specified)

EXCLUSIONS
This policy excludes: electrical or mechanical breakdown; inherent vice or latent defect;
war, invasion or act of foreign enemies; nuclear contamination; gradual deterioration.

AVERAGE CLAUSE: If the property insured is of greater value than the sum insured, the Insured
shall be considered their own insurer for the difference and shall bear a proportionate share of loss.

BASIS OF SETTLEMENT: Reinstatement value unless stated as indemnity basis.
Policy Period: {_rng_date(2022, 2025)} to {_rng_date(2025, 2026)}""",

        # Life assurance
        lambda: f"""LIFE ASSURANCE POLICY — WHOLE OF LIFE / ENDOWMENT

Policy Number: {_pol_num()}
Life Assured: {RNG.choice(INDIVIDUALS)}
Policyholder: {RNG.choice(INDIVIDUALS)}
Insurer: {RNG.choice([i for i in ZIMBABWEAN_INSURERS if 'Life' in i or 'Mutual' in i or 'Fidelity' in i or 'Nyaradzo' in i])}
Policy Commencement Date: {_rng_date(2018, 2024)}

BENEFITS SCHEDULE
Death Benefit (any cause): {_amount(20000, 500000)}
Permanent Total Disability Benefit: {_amount(20000, 500000)}
Maturity Benefit (if applicable): {_amount(30000, 600000)}
Maturity Date: {_rng_date(2030, 2045)}

PREMIUM DETAILS
Monthly Premium: {_amount(50, 2000)}
Premium Payment Term: {RNG.randint(5, 30)} years
Premium Frequency: {RNG.choice(['Monthly', 'Quarterly', 'Annually'])}
Waiver of Premium: Included — premiums waived on total disability.

EXCLUSIONS
1. Death by suicide within {RNG.randint(12, 24)} months of policy commencement.
2. Death arising from engaging in hazardous activities not disclosed at inception.
3. Pre-existing conditions not declared on the proposal form.

BENEFICIARY DESIGNATION
Primary Beneficiary: {RNG.choice(INDIVIDUALS)} (Spouse)
Contingent Beneficiary: {RNG.choice(INDIVIDUALS)} (Child)
The Life Assured may amend beneficiary designations by written notice to the Insurer.

REINSTATEMENT: A lapsed policy may be reinstated within {RNG.randint(12, 36)} months of lapse upon
payment of all outstanding premiums with interest and satisfactory evidence of insurability.

Zimbabwe Life Offices Association (LOA) Member | IPEC Licenced""",

        # Liability
        lambda: f"""PUBLIC AND PRODUCTS LIABILITY INSURANCE POLICY

Policy Number: {_pol_num()}
Insured: {RNG.choice(list(COMPANIES))}
Business Description: {RNG.choice(['Retail trade', 'Manufacturing', 'Construction', 'Hospitality', 'Transportation'])}
Insurer: {RNG.choice(ZIMBABWEAN_INSURERS)}
Policy Period: {_rng_date(2022, 2025)} to {_rng_date(2025, 2026)}

LIMIT OF INDEMNITY
Any one occurrence: {_amount(100000, 5000000)}
Aggregate for the period of insurance: {_amount(500000, 10000000)}

COVERAGE
The Insurer will indemnify the Insured against all sums which the Insured shall become legally
liable to pay as damages (including claimants' costs and expenses) arising from:
(a) Accidental bodily injury to any third party
(b) Accidental damage to property belonging to third parties
(c) Products liability for goods manufactured, sold or supplied by the Insured

DEFENCE COSTS: The Insurer will pay costs and expenses incurred with its written consent.

EXCLUSIONS
1. Liability arising from deliberate or intentional acts.
2. Liability assumed under contract unless attaching at common law.
3. Liability arising from professional advice or services — see Professional Indemnity.
4. Employer's liability — see Workmen's Compensation policy.
5. Liability arising from pollution or contamination unless sudden and accidental.

ANNUAL PREMIUM: {_amount(2000, 50000)}
EXCESS: {_amount(500, 10000)} per occurrence.""",

        # Agricultural
        lambda: f"""AGRICULTURAL MULTI-PERIL INSURANCE POLICY

Policy Number: {_pol_num()}
Insured Farmer: {RNG.choice(INDIVIDUALS)}
Farm Name: {RNG.choice(['Sunrise Farm', 'Green Valley Farm', 'Hwange Farm', 'Ruwa Estates', 'Mazowe Farm'])}
Insurer: {RNG.choice(ZIMBABWEAN_INSURERS)}
Crop: {RNG.choice(['Tobacco', 'Maize', 'Wheat', 'Soya beans', 'Sunflower', 'Cotton'])}

INSURED AREA: {RNG.randint(10, 2000)} hectares
SUM INSURED PER HECTARE: {_amount(300, 2000)}
TOTAL SUM INSURED: {_amount(50000, 3000000)}

PERILS COVERED
1. Hailstorm | 2. Fire | 3. Drought (if drought index cover selected) |
4. Excessive rainfall | 5. Frost | 6. Wind damage | 7. Animal damage (specified)

EXCLUSIONS
1. Losses due to poor agronomic practices or failure to follow prescribed inputs.
2. Harvesting losses due to mechanical breakdown.
3. Losses occurring after the crop maturity date specified in the schedule.
4. Market price fluctuations.

BASIS OF INDEMNITY: Yield shortfall below guaranteed yield threshold of {RNG.randint(60, 80)}%
of historic average. Loss assessment by an independent agricultural loss adjuster.
Premium Rate: {_pct(3, 12)} of sum insured.""",
    ]
    return RNG.choice(templates)()


# ---------------------------------------------------------------------------
# 2. REINSURANCE TREATY
# ---------------------------------------------------------------------------
def _reinsurance_treaty() -> str:
    insurer = RNG.choice(ZIMBABWEAN_INSURERS)
    reinsurer = RNG.choice(REINSURERS)
    templates = [
        lambda: f"""EXCESS OF LOSS REINSURANCE AGREEMENT

Reinsured: {insurer}
Reinsurer: {reinsurer}
Treaty Reference: XOL/{RNG.randint(1, 99):02d}/{RNG.randint(2020, 2026)}
Treaty Year: {RNG.randint(2020, 2026)}
Class of Business: {RNG.choice(['Motor', 'Fire and Property', 'Engineering', 'Marine', 'Aviation', 'General Accident'])}

SECTION 1 — LIMIT AND RETENTION
Layer: {_amount(500000, 5000000)} xs {_amount(50000, 300000)}
The Reinsurer shall indemnify the Reinsured for the amount of each and every loss
in excess of the Reinsured's retention up to but not exceeding the limit per occurrence.
Annual Aggregate Deductible (AAD): {_amount(0, 200000)} (if applicable)
Reinstatement: {RNG.randint(1, 3)} automatic reinstatement(s) at {_pct(50, 100)} additional premium.

SECTION 2 — PREMIUM
Rate on Line: {_pct(5, 25)}
Provisional Premium: {_amount(50000, 800000)}
Minimum and Deposit Premium: {_amount(30000, 500000)}
Premium Due Date: {_rng_date(2022, 2026)}
Adjustment Basis: Flat rate, no adjustment.

SECTION 3 — CLAIMS COOPERATION
The Reinsured shall notify the Reinsurer of all claims likely to exceed {_amount(30000, 150000)}
within {RNG.randint(48, 120)} hours of notification to the Reinsured.
All claims shall be settled by the Reinsured following original policy conditions.
Cash Loss provision: Claims exceeding {_amount(100000, 500000)} payable within {RNG.randint(14, 30)} days of agreement.

SECTION 4 — ARBITRATION
Any disputes arising out of or relating to this Agreement shall be finally settled by arbitration
under ARIAS (Arbitration and Reinsurance Industry Specialists) rules. Place of arbitration: Harare, Zimbabwe.

SECTION 5 — GOVERNING LAW
This agreement shall be governed by and construed in accordance with the laws of Zimbabwe.""",

        lambda: f"""QUOTA SHARE REINSURANCE TREATY

Reinsured: {insurer}
Reinsurer(s): {reinsurer} ({RNG.randint(30, 70)}%) | Africa Re ({100 - RNG.randint(30, 70)}%)
Treaty Reference: QS/{RNG.randint(1, 99):02d}/{RNG.randint(2020, 2026)}
Effective Date: {_rng_date(2020, 2026)}
Class of Business: {RNG.choice(['Short-Term All Classes', 'Life Assurance', 'Fire and Property', 'Motor Fleet'])}

QUOTA SHARE PERCENTAGE
Cession Rate: {RNG.randint(20, 60)}% of each and every risk
The Reinsurer accepts {RNG.randint(20, 60)}% of each risk written by the Reinsured.
Reinsured retains {100 - RNG.randint(20, 60)}%.
Maximum Line per Risk: {_amount(200000, 5000000)}

COMMISSION STRUCTURE
Reinsurance Commission: {_pct(20, 35)} of gross ceded premium
Profit Commission: {_pct(10, 25)} of ceded profit after {RNG.randint(5, 15)}% loading
Sliding Scale Commission: Minimum {_pct(20, 28)} / Maximum {_pct(30, 40)} based on loss ratio.

CLAIMS SHARING
The Reinsurer participates in all claims proportionally to the cession.
Claims reporting threshold: All claims exceeding {_amount(5000, 50000)}.
Claims settlement authority: Reinsured has authority up to {_amount(20000, 200000)}.

PREMIUM ACCOUNTING
Accounts rendered: {RNG.choice(['Monthly', 'Quarterly'])}
Settlement terms: {RNG.randint(30, 60)} days from account date.
Funds Withheld: {_pct(20, 40)} of net ceded premium withheld by Reinsured.

EXCLUSIONS FROM TREATY
Facultative business separately placed | Business with sum insured exceeding {_amount(2000000, 20000000)} |
War risks | Nuclear risks | Cyber risks""",

        lambda: f"""FACULTATIVE REINSURANCE CERTIFICATE

Certificate Number: FAC/{RNG.randint(1000, 9999)}/{RNG.randint(2020, 2026)}
Reinsured: {insurer}
Reinsurer: {reinsurer}
Original Insured: {RNG.choice(list(COMPANIES))}
Risk Description: {RNG.choice(['Commercial property complex', 'Industrial plant and machinery', 'Construction all risks project', 'Marine cargo shipment', 'Engineering erection all risks'])}

RISK DETAILS
Original Sum Insured: {_amount(1000000, 50000000)}
Reinsurer's Line: {_pct(20, 80)} = {_amount(200000, 25000000)}
Original Rate: {_pct(0.5, 5)}
Ceded Premium: {_amount(10000, 500000)}
Reinsurance Commission: {_pct(10, 20)}

PERIOD OF COVER: {_rng_date(2022, 2025)} to {_rng_date(2025, 2026)}
CONDITIONS: As original policy including all endorsements. Subject to reinsurer's standard conditions.
BASIS OF ACCEPTANCE: Full conditions, including original policy exclusions.
CLAIMS COOPERATION: Claims to be notified immediately; joint survey rights reserved.
ARBITRATION: Zimbabwe Arbitration Centre, Harare.""",
    ]
    return RNG.choice(templates)()


# ---------------------------------------------------------------------------
# 3. CLAIMS DOCUMENTATION
# ---------------------------------------------------------------------------
def _claims_documentation() -> str:
    claimant = RNG.choice(INDIVIDUALS)
    insurer  = RNG.choice(ZIMBABWEAN_INSURERS)
    templates = [
        lambda: f"""INSURANCE CLAIM ASSESSMENT REPORT

Claim Reference: {_claim_num()}
Date of Loss: {_rng_date(2021, 2026)}
Date of Report: {_rng_date(2022, 2026)}
Insured: {claimant}
Policy Number: {_pol_num()}
Insurer: {insurer}
Class of Claim: {RNG.choice(['Motor Vehicle Damage', 'Fire and Property Loss', 'Theft', 'Personal Accident', 'Liability Claim'])}

LOSS ADJUSTER'S PRELIMINARY REPORT
Loss Adjuster: {RNG.choice(['Peter Mutasa & Associates', 'Harare Loss Adjusters (Pvt) Ltd', 'National Adjusters Zimbabwe', 'First Capital Loss Adjusters'])}
Inspection Date: {_rng_date(2022, 2026)}

CIRCUMSTANCES OF LOSS
Nature of Loss: {RNG.choice(['Collision with stationary object', 'Fire of unknown origin', 'Theft of vehicle', 'Storm damage to roof', 'Third-party collision', 'Flooding of premises'])}
Cause of Loss: {RNG.choice(['Negligence', 'Accidental damage', 'Act of God', 'Criminal act', 'Mechanical failure'])}
Witness: {RNG.choice(INDIVIDUALS)}

VALUATION
Sum Insured: {_amount(20000, 500000)}
Assessed Replacement/Repair Cost: {_amount(5000, 300000)}
Less Depreciation ({RNG.randint(5, 30)}%): ({_amount(500, 50000)})
Less Policy Excess: ({_amount(300, 5000)})
Less Salvage Value: ({_amount(0, 20000)})
NET CLAIM AMOUNT RECOMMENDED: {_amount(3000, 250000)}

FINDINGS AND RECOMMENDATION
Coverage: {RNG.choice(['Confirmed — claim falls within policy scope', 'Confirmed with endorsement review required'])}
Recommendation: {RNG.choice(['Approved for settlement', 'Approved subject to excess deduction', 'Approved — third-party recovery to be pursued'])}
Further Action Required: {RNG.choice(['Obtain police abstract', 'Await fire brigade report', 'Obtain repair quotations from approved repairers', 'None'])}

Signed: _______________ Date: {_rng_date(2022, 2026)}
Loss Adjuster Ref: LA-{RNG.randint(1000, 9999)}""",

        lambda: f"""MOTOR VEHICLE CLAIM FORM — IPEC STANDARD

SECTION A: POLICYHOLDER DETAILS
Policyholder: {claimant}
Policy Number: {_pol_num()}
Insurer: {insurer}
Contact: {RNG.randint(0770000000, 0779999999)}

SECTION B: ACCIDENT DETAILS
Date and Time of Accident: {_rng_date(2021, 2026)} at {RNG.randint(6, 22):02d}:{RNG.choice(['00','15','30','45'])}
Location of Accident: {RNG.choice(['Corner Borrowdale Road and Enterprise Road, Harare', 'Bulawayo Road near Kwekwe turnoff', 'Robert Mugabe Road, Mutare', 'Masvingo-Beit Bridge Highway km {}'.format(RNG.randint(50,300))])}
Description of Accident: {RNG.choice(['Insured vehicle struck from the rear by third-party vehicle. Third party accepted liability.', 'Insured vehicle collided with a stationary object whilst reversing in parking area. No third party involved.', 'Third-party vehicle encroached into insured vehicle lane causing sideswipe damage.'])}

SECTION C: VEHICLE DETAILS
Vehicle Make/Model: {RNG.choice(['Toyota Hilux', 'Toyota Land Cruiser', 'Isuzu KB', 'Ford Ranger', 'Mazda BT-50', 'Toyota Corolla', 'Honda Fit', 'Nissan Navara'])}
Registration Number: {RNG.choice('ABCDFGHJKLMNPQRSTUVWXYZ')}{RNG.randint(100,999)}{RNG.choice('ABCDFGHJ')}
Year of Manufacture: {RNG.randint(2010, 2023)}
Estimated Damage: {_amount(2000, 80000)}

SECTION D: THIRD PARTY DETAILS (if applicable)
Third Party Name: {RNG.choice(INDIVIDUALS)}
Third Party Insurer: {RNG.choice(ZIMBABWEAN_INSURERS)}
Police Case Number: {RNG.randint(100000, 999999)}/{RNG.randint(2020, 2026)}

SECTION E: DECLARATION
I declare that the above information is true and correct to the best of my knowledge.
Signature: _______________ Date: {_rng_date(2022, 2026)}""",

        lambda: f"""PROPERTY INSURANCE CLAIM — LOSS ASSESSMENT CERTIFICATE

Reference Number: {_claim_num()}
Insured: {RNG.choice(list(COMPANIES))}
Policy Insurer: {insurer}
Risk Address: {RNG.randint(1, 500)} {RNG.choice(['Samora Machel Avenue', 'Kwame Nkrumah', 'Nelson Mandela', 'Second Street Extension'])}, Harare
Date of Loss: {_rng_date(2020, 2026)}

DESCRIPTION OF LOSS
The insured premises sustained {RNG.choice(['extensive fire damage to the warehouse section', 'storm damage resulting in roof collapse', 'flooding damage to ground floor stock and equipment', 'burglary resulting in theft of electronic equipment'])} on the date stated above.

SCOPE OF ASSESSMENT
Building Structural Damage: {_amount(50000, 2000000)}
Stock and Merchandise Loss: {_amount(10000, 500000)}
Equipment and Machinery Damage: {_amount(5000, 300000)}
Business Interruption Loss (if applicable): {_amount(0, 200000)}

GROSS ASSESSED LOSS: {_amount(70000, 3000000)}
Less: Policy Excess: ({_amount(1000, 50000)})
Less: Recoverable Salvage: ({_amount(0, 100000)})
Less: Underinsurance Adjustment (Average Clause {_pct(0, 15)}): ({_amount(0, 200000)})

RECOMMENDED SETTLEMENT: {_amount(50000, 2500000)}

SETTLEMENT TERMS
Basis of Settlement: {RNG.choice(['Reinstatement value', 'Indemnity value', 'Agreed value'])}
Payment Method: {RNG.choice(['EFT to insured account', 'Payment to contractor on completion', 'Partial advance payment'])}
IPEC Excess Claim Report submitted: {RNG.choice(['Yes', 'No — below IPEC reporting threshold'])}""",
    ]
    return RNG.choice(templates)()


# ---------------------------------------------------------------------------
# 4. BROKER AGREEMENT
# ---------------------------------------------------------------------------
def _broker_agreement() -> str:
    insurer = RNG.choice(ZIMBABWEAN_INSURERS)
    broker  = RNG.choice(BROKERS)
    templates = [
        lambda: f"""INSURANCE BROKERAGE AGREEMENT

Parties to this Agreement:
  Insurer: {insurer} (hereinafter "the Insurer")
  Broker:  {broker} (hereinafter "the Broker")
  IPEC Broker Licence No: IB-{RNG.randint(1000, 9999)}

Effective Date: {_rng_date(2020, 2025)}

ARTICLE 1 — APPOINTMENT
The Insurer hereby appoints the Broker as its non-exclusive authorised insurance broker for the
territory of Zimbabwe for the classes of business specified in Schedule A attached hereto.

ARTICLE 2 — BROKER RESPONSIBILITIES
The Broker undertakes to:
(a) Solicit and procure insurance business in compliance with the Insurance Act [Chapter 24:07]
(b) Issue cover notes, certificates of insurance and policy documents as authorised
(c) Collect premiums from policyholders and remit to the Insurer within {RNG.randint(14, 30)} days
(d) Maintain adequate professional indemnity insurance of not less than {_amount(100000, 1000000)}
(e) Report all claims to the Insurer within {RNG.randint(24, 72)} hours of notification
(f) Maintain proper records of all transactions for a minimum of {RNG.randint(5, 10)} years

ARTICLE 3 — COMMISSION SCHEDULE
Motor Insurance: {_pct(12, 22)} of gross premium written
Property/Fire: {_pct(10, 20)} of gross premium written
Life Assurance (first year): {_pct(20, 40)} of first-year premium
Life Assurance (renewal): {_pct(5, 15)} of renewal premium
Engineering/Marine: {_pct(10, 18)} of gross premium written
All other classes: {_pct(10, 18)} of gross premium written
Commission shall be paid monthly within {RNG.randint(14, 30)} days of account settlement.

ARTICLE 4 — BINDING AUTHORITY
Maximum Sum Insured per risk (Motor): {_amount(50000, 500000)}
Maximum Sum Insured per risk (Property): {_amount(100000, 2000000)}
The Broker shall NOT bind risks exceeding these limits without prior written approval from the Insurer.

ARTICLE 5 — PREMIUM TRUST ACCOUNT
The Broker shall maintain a separate premium trust account at a registered bank.
Premiums collected are held on trust for the Insurer and may not be commingled with the Broker's own funds.

ARTICLE 6 — TERMINATION
Either party may terminate this agreement by giving {RNG.randint(30, 90)} days written notice.
Immediate termination is permissible in the event of: (a) insolvency; (b) licence revocation by IPEC;
(c) material breach of this agreement; (d) conviction of a criminal offence.

IN WITNESS WHEREOF the parties have executed this Agreement on the date first above written.
For and on behalf of {insurer}: _______________
For and on behalf of {broker}: _______________""",
    ]
    return RNG.choice(templates)()


# ---------------------------------------------------------------------------
# 5. ACTUARIAL REPORT
# ---------------------------------------------------------------------------
def _actuarial_report() -> str:
    insurer = RNG.choice(ZIMBABWEAN_INSURERS)
    actuary = RNG.choice(['FIA', 'FASSA', 'ASA'])
    templates = [
        lambda: f"""ACTUARIAL VALUATION REPORT — STATUTORY RETURN

Prepared for: {insurer}
Prepared by: {RNG.choice(['Actuarial Solutions Zimbabwe (Pvt) Ltd', 'First Actuaries Ltd', 'KPMG Actuarial Services', 'Deloitte Actuarial & Insurance Solutions'])}
Actuary: {RNG.choice(INDIVIDUALS)}, {actuary}
Valuation Date: {RNG.choice(['31 December', '30 June'])} {RNG.randint(2020, 2025)}
Submission to IPEC: Required under Section {RNG.randint(30, 60)} of the Insurance Act [Chapter 24:07]

EXECUTIVE SUMMARY
This report sets out the results of the actuarial valuation of {insurer} as at the valuation date.
The insurer operates as a {RNG.choice(['short-term insurer', 'life assurer', 'composite insurer', 'reinsurer'])}.

RESERVE ADEQUACY ASSESSMENT
Outstanding Claims Reserve (OCR): {_amount(2000000, 50000000)}
Incurred But Not Reported (IBNR): {_amount(500000, 20000000)}
Unearned Premium Reserve (UPR): {_amount(1000000, 30000000)}
Long-term Policy Reserve: {_amount(5000000, 200000000)}
Total Policyholder Reserves: {_amount(10000000, 280000000)}

CLAIMS DEVELOPMENT ANALYSIS
The claims development triangles for the period {RNG.randint(2015, 2020)}–{RNG.randint(2021, 2025)} indicate
{RNG.choice(['adequate development in most classes', 'potential adverse development in motor class', 'favourable development in fire and property'])} .
Weighted average chain-ladder development factor (all classes): {round(RNG.uniform(1.05, 1.35), 3)}
Selected IBNR provision covers {_pct(90, 100)} of estimated ultimate liability.

SOLVENCY ASSESSMENT
Minimum Capital Requirement (IPEC): {_amount(500000, 5000000)}
Available Capital: {_amount(600000, 80000000)}
Solvency Coverage Ratio: {round(RNG.uniform(1.05, 3.5), 2)}x ({round(RNG.uniform(105, 350), 0):.0f}% of minimum)
VERDICT: {RNG.choice(['SOLVENT — Capital adequacy maintained', 'SOLVENT — Monitor reserve trends', 'WARNING — Capital approaching minimum threshold'])}

ASSUMPTIONS
Inflation rate (USD): {_pct(3, 8)} per annum
Discount rate: {_pct(5, 12)} per annum
Claims development period: {RNG.randint(36, 84)} months
Reinsurance recoveries netted against gross reserves.

RECOMMENDATIONS
1. {RNG.choice(['Increase IBNR reserves for motor class by 10–15%', 'Maintain current reserve levels — adequate', 'Review pricing adequacy for property portfolio'])}
2. {RNG.choice(['Pursue reinsurance protection for catastrophe exposure', 'Consider rate increases in high-loss lines', 'Implement improved claims data collection'])}

This report is prepared for the exclusive use of {insurer} and IPEC. Not for public distribution.
Actuary's Signature: _______________ Date: {_rng_date(2020, 2026)}""",

        lambda: f"""ACTUARIAL RESERVE CERTIFICATE — IPEC FSR SUBMISSION

Company: {insurer}
Valuation Date: 31 December {RNG.randint(2020, 2025)}
Signing Actuary: {RNG.choice(INDIVIDUALS)}, {actuary}, {RNG.choice(['Actuarial Society of South Africa', 'Institute and Faculty of Actuaries'])}
IPEC Reference: FSR-{RNG.randint(100, 999)}/{RNG.randint(2020, 2026)}

CERTIFICATE OF ACTUARIAL OPINION
In my opinion as Appointed Actuary, the insurance liabilities of {insurer} as at the valuation date
are adequate to meet all policyholder obligations with a probability of not less than {RNG.randint(75, 95)}%.

SUMMARY OF RESERVES
Gross Outstanding Claims Reserves: USD {_amount(1000000, 40000000)}
Reinsurance Recoverable: USD ({_amount(200000, 20000000)})
Net Outstanding Claims Reserves: USD {_amount(800000, 25000000)}
UPR (Gross): USD {_amount(500000, 15000000)}
Total Net Insurance Liabilities: USD {_amount(2000000, 60000000)}

LOSS RATIO EXPERIENCE ({RNG.randint(2020, 2025)})
Motor: {_pct(55, 90)}   | Fire: {_pct(35, 70)}   | Personal Accident: {_pct(45, 80)}
Engineering: {_pct(30, 60)} | Marine: {_pct(40, 75)} | General Liability: {_pct(40, 70)}
Combined Loss Ratio (weighted): {_pct(55, 88)}

CAPITAL ADEQUACY RETURN
Net Premium Income (last 12 months): USD {_amount(5000000, 100000000)}
Required Minimum Solvency Margin: USD {_amount(500000, 10000000)}
Actual Capital & Reserves: USD {_amount(600000, 150000000)}
Excess over Minimum: USD {_amount(100000, 100000000)}

I certify that the reserves stated above are in my professional opinion adequate.
Date: {_rng_date(2020, 2026)}""",
    ]
    return RNG.choice(templates)()


# ---------------------------------------------------------------------------
# 6. COMPLIANCE LETTER
# ---------------------------------------------------------------------------
def _compliance_letter() -> str:
    insurer = RNG.choice(ZIMBABWEAN_INSURERS)
    ref_num = f"IPEC/{RNG.randint(100, 999)}/{RNG.randint(2018, 2026)}"
    templates = [
        lambda: f"""INSURANCE AND PENSIONS COMMISSION OF ZIMBABWE (IPEC)
3rd Floor, Finsure House, 84-86 Kwame Nkrumah Avenue, Harare
Tel: 0242-250613/250614 | Website: www.ipec.co.zw

Reference: {ref_num}
Date: {_rng_date(2018, 2026)}

The Chief Executive Officer
{insurer}
Harare

COMPLIANCE NOTICE — {RNG.choice(['MINIMUM CAPITAL REQUIREMENTS', 'OUTSTANDING RETURNS SUBMISSION', 'CONDUCT OF BUSINESS REVIEW', 'CLAIMS SETTLEMENT OBLIGATIONS', 'CONSUMER PROTECTION REQUIREMENTS'])}

Dear Sir/Madam,

It has come to the Commission's attention that {insurer} has {RNG.choice(['failed to submit the quarterly FSR-1 return for the period ended', 'not met the minimum capital requirements as prescribed under Section 28 of the Insurance Act for the quarter ended', 'received consumer complaints regarding delays in claims settlement for the period', 'not complied with the prescribed motor insurance tariff rates for'])} {RNG.randint(1,4)} quarter {RNG.randint(2020, 2025)}.

The Commission wishes to draw your attention to Section {RNG.randint(20, 60)} of the Insurance Act [Chapter 24:07] which requires all registered insurers to {RNG.choice(['submit statutory returns within 30 days of each quarter end', 'maintain minimum capital of USD 500,000 at all times', 'settle valid claims within 30 days of agreement on quantum', 'ensure all marketing materials comply with disclosure requirements'])}.

REQUIRED ACTIONS
1. {RNG.choice(['Submit the outstanding return immediately.', 'Provide a detailed capital restoration plan within 14 days.', 'Provide a breakdown of all claims outstanding for more than 60 days.', 'Confirm adherence to the prescribed tariff.'])}
2. {RNG.choice(['Confirm all future submissions will be made on time.', 'Submit audited accounts as supporting evidence.', 'Confirm date by which all outstanding claims will be settled.', 'Submit compliance certificate signed by appointed actuary.'])}
3. Failure to comply within {RNG.randint(7, 30)} days will result in regulatory action including {RNG.choice(['imposition of a penalty under Section 73', 'referral to the Commissioner for further action', 'suspension of new business writing authority', 'public censure'])}.

Please acknowledge receipt of this notice and confirm your proposed remedial action within {RNG.randint(5, 14)} days.

Yours faithfully,
Commissioner of Insurance and Pensions
Insurance and Pensions Commission of Zimbabwe""",

        lambda: f"""COMPLIANCE SELF-ASSESSMENT REPORT

Company: {insurer}
Reporting Period: {RNG.choice(['Q1', 'Q2', 'Q3', 'Q4'])} {RNG.randint(2020, 2026)}
Submitted to: Insurance and Pensions Commission of Zimbabwe (IPEC)
Reference: {ref_num}
Board Approval Date: {_rng_date(2020, 2026)}

SECTION 1 — CORPORATE GOVERNANCE
Board composition: {RNG.randint(5, 12)} directors ({RNG.randint(3, 8)} independent, {RNG.randint(2, 5)} executive)
Board meetings held this period: {RNG.randint(2, 6)}
Audit committee meetings held: {RNG.randint(2, 4)}
Risk management framework: {RNG.choice(['Fully documented and implemented', 'Under review and update', 'Implemented — minor gaps identified'])}

SECTION 2 — CONSUMER PROTECTION
Complaints received this period: {RNG.randint(0, 150)}
Complaints resolved within prescribed period: {RNG.randint(70, 100)}%
Outstanding complaints over 30 days: {RNG.randint(0, 20)}
Average claims settlement time: {RNG.randint(7, 45)} days
Disclosure compliance: {RNG.choice(['Full compliance', 'Partial — marketing material updates in progress'])}

SECTION 3 — FINANCIAL COMPLIANCE
Capital adequacy ratio: {round(RNG.uniform(1.1, 3.5), 2)}x IPEC minimum
FSR-1 returns submitted on time: {RNG.choice(['Yes — all returns current', 'No — Q3 return delayed by 15 days'])}
Actuarial valuation: {RNG.choice(['Completed and submitted', 'In progress', 'Completed — awaiting IPEC review'])}
External audit: {RNG.choice(['Completed — clean opinion', 'Completed — qualified on IBNR reserves', 'In progress'])}

SECTION 4 — AML/CFT COMPLIANCE
KYC procedures: Implemented for all new policyholders
Suspicious transaction reports filed this period: {RNG.randint(0, 5)}
AML training completed by staff: {RNG.randint(80, 100)}%
Board member responsible for compliance: {RNG.choice(INDIVIDUALS)}

I certify that the information contained in this report is accurate and complete.
Chief Executive Officer: _______________ Date: {_rng_date(2020, 2026)}
Compliance Officer: _______________ Date: {_rng_date(2020, 2026)}""",
    ]
    return RNG.choice(templates)()


# ---------------------------------------------------------------------------
# 7. ANNUAL RETURN (IPEC FSR-1)
# ---------------------------------------------------------------------------
def _annual_return() -> str:
    insurer = RNG.choice(ZIMBABWEAN_INSURERS)
    year    = RNG.randint(2019, 2025)
    templates = [
        lambda: f"""INSURANCE AND PENSIONS COMMISSION OF ZIMBABWE
FINANCIAL SOUNDNESS RETURN — FSR 1 (ANNUAL)

Company Name: {insurer}
IPEC Registration No: IRS-{RNG.randint(100, 999)}
Category: {RNG.choice(['Short-Term Insurer', 'Life Assurer', 'Composite Insurer', 'Reinsurer', 'Funeral Assurer'])}
Financial Year End: 31 December {year}
Submission Date: {RNG.randint(28, 31)} March {year + 1}

PART A — INCOME STATEMENT (USD)
Gross Written Premiums (GWP): {_amount(2000000, 150000000)}
Less Reinsurance Premiums Ceded: ({_amount(200000, 50000000)})
Net Written Premiums (NWP): {_amount(1500000, 110000000)}
Change in Unearned Premium Reserve: ({_amount(0, 15000000)})
Net Earned Premiums: {_amount(1400000, 100000000)}

Gross Claims Incurred: ({_amount(800000, 80000000)})
Reinsurance Recoveries: {_amount(100000, 30000000)}
Net Claims Incurred: ({_amount(500000, 60000000)})

Commission Paid (net of ceded): ({_amount(200000, 20000000)})
Management Expenses: ({_amount(500000, 30000000)})
Underwriting Result: {_amount(-5000000, 20000000)}
Investment Income: {_amount(200000, 10000000)}
Other Income: {_amount(0, 3000000)}
Profit/(Loss) Before Tax: {_amount(-3000000, 25000000)}

PART B — BALANCE SHEET (USD)
Total Assets: {_amount(5000000, 500000000)}
Total Insurance Liabilities: {_amount(2000000, 300000000)}
Shareholder Equity: {_amount(1000000, 200000000)}

PART C — RATIOS
Gross Loss Ratio: {_pct(40, 90)}
Net Loss Ratio: {_pct(35, 85)}
Expense Ratio: {_pct(15, 40)}
Combined Ratio: {_pct(60, 115)}
Solvency Margin: {_pct(100, 350)}
Liquidity Ratio: {round(RNG.uniform(0.9, 3.0), 2)}

PART D — CLAIMS ANALYSIS
Motor: GWP {_amount(500000, 40000000)} | Claims ratio {_pct(45, 90)}
Fire/Property: GWP {_amount(300000, 30000000)} | Claims ratio {_pct(30, 75)}
Life/Disability: GWP {_amount(1000000, 60000000)} | Claims ratio {_pct(30, 70)}
Funeral/PA: GWP {_amount(100000, 10000000)} | Claims ratio {_pct(40, 80)}

CERTIFICATION
I certify that the information in this return is accurate and complete.
Principal Officer: _______________ Date: {_rng_date(2020, 2026)}
External Auditor: _______________ Date: {_rng_date(2020, 2026)}""",

        lambda: f"""IPEC QUARTERLY STATISTICAL RETURN — Q{RNG.randint(1,4)} {RNG.randint(2020, 2025)}

Company: {insurer}
Return Period: {RNG.choice(['January-March', 'April-June', 'July-September', 'October-December'])} {RNG.randint(2020, 2025)}
Due Date: {RNG.randint(28, 31)} {RNG.choice(['April', 'July', 'October', 'January'])} {RNG.randint(2020, 2026)}

PREMIUM INCOME (USD '000)
                    Current Quarter    Year to Date    Prior Year YTD
Gross Written        {RNG.randint(500, 40000):>10,}    {RNG.randint(1000, 120000):>12,}    {RNG.randint(800, 110000):>15,}
Ceded                ({RNG.randint(50, 8000):>10,})   ({RNG.randint(100, 25000):>12,})   ({RNG.randint(80, 22000):>15,})
Net Written          {RNG.randint(400, 35000):>10,}    {RNG.randint(800, 100000):>12,}    {RNG.randint(700, 90000):>15,}

CLAIMS INCURRED (USD '000)
Gross Claims         {RNG.randint(300, 25000):>10,}    {RNG.randint(600, 70000):>12,}    {RNG.randint(500, 65000):>15,}
Reinsurance          {RNG.randint(30, 6000):>10,}     {RNG.randint(60, 18000):>12,}     {RNG.randint(50, 16000):>15,}
Net Claims           {RNG.randint(200, 20000):>10,}    {RNG.randint(400, 55000):>12,}    {RNG.randint(350, 50000):>15,}

SOLVENCY (USD '000)
Minimum Required Capital:  {RNG.randint(500, 5000):>10,}
Available Capital:         {RNG.randint(600, 80000):>10,}
Solvency Cover:            {round(RNG.uniform(1.05, 3.5), 2):>10.2f}x

OUTSTANDING CLAIMS REGISTER
Claims under 30 days: {RNG.randint(0, 200)}    |    Avg value: USD {RNG.randint(1000, 50000):,}
Claims 30-60 days:    {RNG.randint(0, 100)}    |    Avg value: USD {RNG.randint(2000, 80000):,}
Claims 60-90 days:    {RNG.randint(0, 50)}     |    Avg value: USD {RNG.randint(3000, 100000):,}
Claims over 90 days:  {RNG.randint(0, 30)}     |    Avg value: USD {RNG.randint(5000, 200000):,}

Authorised signatory: _______________ Date: {_rng_date(2020, 2026)}""",
    ]
    return RNG.choice(templates)()


# ---------------------------------------------------------------------------
# 8. LICENCE NOTICE
# ---------------------------------------------------------------------------
def _licence_notice() -> str:
    insurer = RNG.choice(ZIMBABWEAN_INSURERS)
    templates = [
        lambda: f"""INSURANCE AND PENSIONS COMMISSION OF ZIMBABWE
CERTIFICATE OF REGISTRATION

Reference: {f'IPEC/REG/{RNG.randint(2000, 9999)}/{RNG.randint(2010, 2026)}'}

THIS IS TO CERTIFY THAT:

{insurer}

having satisfied the requirements of the Insurance Act [Chapter 24:07] and regulations made
thereunder, is hereby registered and licensed to carry on the following class(es) of insurance
business in Zimbabwe:

Class of Business: {RNG.choice(['Short-Term Insurance (All Classes)', 'Life Assurance', 'Composite Insurance', 'Reinsurance (Short-Term)', 'Funeral Assurance', 'Microinsurance'])}

This certificate is valid from {_rng_date(2020, 2025)} and shall remain in force until
{_rng_date(2025, 2027)} unless earlier suspended, cancelled or surrendered.

CONDITIONS ATTACHED:
1. The registered insurer shall at all times maintain minimum capital as prescribed.
2. Annual statutory returns (FSR-1) must be submitted within 90 days of financial year end.
3. This certificate must be prominently displayed at the principal place of business.
4. Any change in control or ownership requires prior IPEC approval.

Minimum Capital Requirement: USD {RNG.choice(['500,000', '1,000,000', '2,000,000', '750,000'])}

Issued at Harare this {RNG.randint(1, 28)} day of {RNG.choice(['January','March','June','September'])} {RNG.randint(2020, 2026)}

Commissioner of Insurance and Pensions
Insurance and Pensions Commission of Zimbabwe
[IPEC OFFICIAL SEAL]""",

        lambda: f"""NOTICE OF LICENCE RENEWAL / ENDORSEMENT

IPEC Reference: {f'IPEC/ENR/{RNG.randint(1000, 9999)}/{RNG.randint(2020, 2026)}'}
Date: {_rng_date(2020, 2026)}

To: The Board of Directors
    {insurer}
    Harare

SUBJECT: RENEWAL OF INSURANCE REGISTRATION CERTIFICATE FOR {year_val := RNG.randint(2021, 2026)}

Following your application for renewal of registration dated {_rng_date(2020, 2025)}, and having
reviewed the documentation submitted including:
  (a) Audited Financial Statements for the year ended 31 December {year_val - 1}
  (b) Actuarial Valuation Certificate as at 31 December {year_val - 1}
  (c) Statutory declaration of capital adequacy
  (d) Board of directors' resolution authorising the application
  (e) Payment of licence fee of USD {RNG.randint(2000, 20000):,}

The Insurance and Pensions Commission is pleased to renew the registration of {insurer}
for the period {year_val} to {year_val + 1}, subject to the following conditions:

SPECIAL CONDITIONS ATTACHED TO THIS RENEWAL:
1. {RNG.choice(['Capital adequacy to be maintained above 125% at all times', 'Outstanding claims register to be submitted monthly until further notice', 'Board to present capital strengthening plan by 30 June', 'Appointed actuary must be a Fellow of a recognised actuarial body'])}
2. {RNG.choice(['Reinsurance programme must be approved by IPEC before inception', 'Consumer complaints register to be submitted quarterly', 'External audit firm to be rotated within 2 years'])}

Any breach of these conditions may result in suspension or cancellation of this licence.
Commissioner of Insurance and Pensions
Signed: _______________ Date: {_rng_date(2020, 2026)}""",
    ]
    return RNG.choice(templates)()


# ---------------------------------------------------------------------------
# 9. COURT ORDER
# ---------------------------------------------------------------------------
def _court_order() -> str:
    insurer = RNG.choice(ZIMBABWEAN_INSURERS)
    claimant = RNG.choice(INDIVIDUALS)
    templates = [
        lambda: f"""IN THE HIGH COURT OF ZIMBABWE
HARARE

Case Number: HC {RNG.randint(1000, 9999)}/{RNG.randint(2018, 2026)}

In the matter between:
  {claimant} — Plaintiff
  and
  {insurer} — Defendant

JUDGMENT — INSURANCE CLAIM DISPUTE

This matter came before me on {_rng_date(2019, 2026)}. Having heard argument from counsel for
both parties and having considered the evidence adduced, I make the following order:

FACTS OF THE MATTER
The Plaintiff instituted action against the Defendant insurer for payment of {_amount(10000, 500000)}
representing an unpaid insurance claim under Policy No. {_pol_num()} in respect of
{RNG.choice(['motor vehicle damage sustained on', 'fire damage to property at', 'theft of goods at', 'personal accident suffered on'])} {_rng_date(2019, 2025)}.
The Defendant denied liability on the basis that {RNG.choice(['the claim was fraudulent', 'the policy was void for non-disclosure of material facts', 'the loss fell within a policy exclusion', 'the claim was submitted outside the prescribed notification period'])}.

FINDINGS
Having considered the evidence, I find that:
1. {RNG.choice(['The Plaintiff has established a valid claim under the policy.', 'The Defendant has not established its defence of non-disclosure.', 'The alleged exclusion does not apply to the circumstances of this loss.', 'The Plaintiff complied with all policy conditions.'])}
2. {RNG.choice(['The Defendant failed to comply with its obligations under the Insurance Act [Chapter 24:07].', 'The denial of the claim was unreasonable and made without proper investigation.'])}
3. The quantum of the claim has been assessed at {_amount(8000, 450000)}.

ORDER
1. The Defendant shall pay to the Plaintiff the sum of {_amount(8000, 450000)} within {RNG.randint(7, 30)} days.
2. Interest on the above amount at the prescribed rate of {_pct(15, 25)} per annum from {_rng_date(2020, 2025)}.
3. The Defendant shall pay the Plaintiff's costs of suit on the {RNG.choice(['ordinary scale', 'attorney and client scale', 'party and party scale'])}.
4. The Registrar of this Court is directed to serve a copy of this judgment on the Insurance and Pensions Commission of Zimbabwe (IPEC).

JUDGE: _______________
DATE: {_rng_date(2020, 2026)}
REGISTRAR: _______________""",

        lambda: f"""IN THE MAGISTRATE'S COURT OF ZIMBABWE
{RNG.choice(['HARARE', 'BULAWAYO', 'MUTARE', 'GWERU'])} CIVIL DIVISION

Case No: MC {RNG.randint(100, 999)}/{RNG.randint(2019, 2026)}

Claimant: {claimant}
Respondent: {insurer}

CONSENT TO JUDGMENT / SETTLEMENT ORDER

The parties having reached an agreement in settlement of the above matter, and the court
having been so informed, the following order is made by consent:

1. The Respondent insurer shall pay the Claimant the sum of {_amount(2000, 100000)}
   in full and final settlement of all claims arising from the insurance dispute between the parties.
2. Payment shall be made by {_rng_date(2023, 2026)} by electronic funds transfer.
3. Each party shall bear its own costs.
4. The Respondent's reference number for this settlement is: {_claim_num()}
5. Upon payment, the Claimant undertakes to provide the Respondent with a full discharge receipt.

This order is made with the consent of both parties.

Presiding Magistrate: _______________
Date: {_rng_date(2020, 2026)}

For Claimant: _______________   For Respondent: _______________""",

        lambda: f"""GARNISHEE ORDER — ATTACHMENT OF DEBT

In the High Court of Zimbabwe, Harare
Case No: HC {RNG.randint(5000, 9999)}/{RNG.randint(2019, 2026)}

Judgment Creditor: {claimant}
Judgment Debtor: {insurer}
Garnishee: Reserve Bank of Zimbabwe / {RNG.choice(['CBZ Bank', 'FBC Bank', 'ZB Bank', 'BancABC'])}

UPON APPLICATION by the Judgment Creditor and upon reading the affidavit filed in
support hereof, it is ORDERED that:

1. The Garnishee ({RNG.choice(['CBZ Bank', 'FBC Bank', 'ZB Bank', 'BancABC'])}) is hereby
   ordered to hold the sum of {_amount(5000, 200000)} currently held in Account No. ****{RNG.randint(1000, 9999)}
   standing to the credit of the Judgment Debtor {insurer}.

2. The Garnishee shall pay the withheld sum to the Judgment Creditor within {RNG.randint(7, 21)} days
   of service of this order, such sum being in partial/full satisfaction of the judgment debt of
   {_amount(5000, 200000)} plus interest and costs awarded in Case No. HC {RNG.randint(1000, 4999)}/{RNG.randint(2018, 2025)}.

3. The Insurance and Pensions Commission is served as a matter of record.

This order operates as a warrant of execution against movable property.
Judge: _______________   Date: {_rng_date(2020, 2026)}""",
    ]
    return RNG.choice(templates)()


# ---------------------------------------------------------------------------
# GENERATOR DISPATCH
# ---------------------------------------------------------------------------
GENERATORS = {
    "policy_wording":       (_policy_wording,      60),
    "reinsurance_treaty":   (_reinsurance_treaty,  60),
    "claims_documentation": (_claims_documentation, 65),
    "broker_agreement":     (_broker_agreement,    55),
    "actuarial_report":     (_actuarial_report,    55),
    "compliance_letter":    (_compliance_letter,    60),
    "annual_return":        (_annual_return,        65),
    "licence_notice":       (_licence_notice,       55),
    "court_order":          (_court_order,          60),
}


def generate_all() -> list[dict]:
    """Generate all document training samples."""
    samples: list[dict] = []
    for category, (fn, n_samples) in GENERATORS.items():
        print(f"  Generating {n_samples} samples for '{category}'...")
        for _ in range(n_samples):
            text = fn()
            samples.append({"text": text.strip(), "category": category})
    RNG.shuffle(samples)
    return samples


def save_json(samples: list[dict]) -> Path:
    out = OUT_DIR / "document_classifier_training.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"data": samples, "total": len(samples),
                   "categories": list(GENERATORS.keys()),
                   "generated_by": "gen_document_training.py"}, f, indent=2, ensure_ascii=False)
    return out


def save_csv(samples: list[dict]) -> Path:
    out = OUT_DIR / "document_classifier_training.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text", "category"])
        for s in samples:
            w.writerow([s["text"], s["category"]])
    return out


if __name__ == "__main__":
    print("=== Document Classifier Training Data Generator ===")
    print(f"Output directory: {OUT_DIR.resolve()}\n")
    samples = generate_all()
    j_path = save_json(samples)
    c_path = save_csv(samples)
    print(f"\nGenerated {len(samples)} samples:")
    cats = {}
    for s in samples:
        cats[s["category"]] = cats.get(s["category"], 0) + 1
    for cat, cnt in sorted(cats.items()):
        print(f"  {cat:<30} {cnt:>4} samples")
    print(f"\nSaved:\n  JSON: {j_path}\n  CSV:  {c_path}")
