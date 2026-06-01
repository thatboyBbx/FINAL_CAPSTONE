"""
gen_standard_clauses_real.py
==============================
Generates a REAL standard clauses library derived directly from actual
Zimbabwean insurance policy documents uploaded by the user:

  Sources (all Zimnat Lion Insurance Company Limited):
  - Domestic All In One Policy Wording
  - Auto Fleet Policy (July 2025)
  - Private Motor Policy (July 2025, Foreign Currency)
  - Group Personal Accident Policy
  - Directors & Officers Liability Policy (2019)
  - Commercial All In One Policy Wording
  - Assets Policy (Sanlam branding)
  - TRADEGUARD Policy
  - DOL Policy Wording

These clauses are verbatim or lightly adapted from the source documents.
They represent the ACTUAL standard clause language used in the Zimbabwean
insurance market and provide a high-quality reference for the Clause
Deviation Detector.

Output: storage/datasets/production/standard_clauses_real.json

Run: python scripts/gen_standard_clauses_real.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

OUT_DIR = Path("storage/datasets/production")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Real standard clauses extracted from Zimbabwean insurance policy documents
# ---------------------------------------------------------------------------

CLAUSES: list[dict] = [

    # -----------------------------------------------------------------------
    # OPERATIVE / PREAMBLE CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "operative_clause",
        "product_category": ["motor", "property", "personal_accident", "liability"],
        "title": "Standard Operative Clause (Premium Condition)",
        "text": (
            "Notwithstanding anything to the contrary set out in the Policy or any Section "
            "thereof the Company's agreement to insure and indemnify the Policyholder is "
            "conditional upon the payment of the premium by or on behalf of the Insured and "
            "the receipt thereof by or on behalf of the Company. Premium is payable on or "
            "before the inception date or renewal date as the case may be and the Company "
            "shall not be liable for any claims arising under this Policy prior to receipt "
            "of the premium. The Company shall not be obliged to accept premium tendered to "
            "it or to any intermediary after such date, but may do so upon such terms as it "
            "in its sole discretion may determine."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion Insurance Company Limited — Multiple Policies",
        "risk_level": "low",
    },
    {
        "clause_type": "operative_clause",
        "product_category": ["property", "domestic"],
        "title": "Domestic All In One — Indemnity Operative Clause",
        "text": (
            "Upon receipt of the premium the company will in accordance with the terms and "
            "conditions of this policy indemnify or pay compensation as defined herein to "
            "the insured in respect of accident, loss or damage if it occurs during the "
            "period of insurance or any subsequent period for which the Insured pays and "
            "the Company agrees to accept the renewal premium. The proposal and declarations "
            "made by the Insured form the basis of this contract and are deemed incorporated "
            "herein."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Domestic All In One Policy Wording",
        "risk_level": "low",
    },

    # -----------------------------------------------------------------------
    # CLAIMS NOTIFICATION CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "claims_notification",
        "product_category": ["motor", "property", "personal_accident"],
        "title": "Motor Claims Notification — 7-Day Rule",
        "text": (
            "On the happening of any loss, damage, destruction, injury or liability which "
            "may result in a claim under this Policy the Insured shall at his own expense: "
            "(i) forthwith notify the Company of any claim within seven days; "
            "(ii) immediately inform the police of any claim involving theft, dishonesty, "
            "fraud or loss of property and take all practicable steps to discover the guilty "
            "party and to recover the stolen or lost property; "
            "(iii) within 30 days after the occurrence submit to the Company full details in "
            "writing of any claim together with particulars of any other insurances covering "
            "such occurrence; "
            "(iv) give to the Company such proofs, information and sworn declarations as the "
            "Company may require and forward immediately any notice of claim or legal process "
            "issued or commenced against the Insured."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy (July 2025)",
        "risk_level": "moderate",
    },
    {
        "clause_type": "claims_notification",
        "product_category": ["personal_accident"],
        "title": "Personal Accident — Claims Notification (90 Days)",
        "text": (
            "Notice must be given to The Company in writing within 30 days of any occurrence "
            "which may give rise to a claim under this Policy. In no case whatever shall The "
            "Company be liable under this Policy after the expiration of 12 months from any "
            "occurrence which may give rise to a claim under this Policy unless the claim is "
            "the subject of pending action or arbitration. All certificates, information and "
            "evidence required by The Company shall be furnished in the form prescribed and "
            "without expense to The Company and must be submitted to The Company within 90 "
            "days following notification."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Group Personal Accident Policy",
        "risk_level": "moderate",
    },
    {
        "clause_type": "claims_notification",
        "product_category": ["liability", "directors_officers"],
        "title": "D&O Claims-Made Reporting Condition",
        "text": (
            "The Company or the Insured shall, as a condition precedent to the obligations "
            "of the Insurer under this policy, give written notice to the Insurer during the "
            "Policy Period, or during the Discovery Period (if applicable), of any Claim made "
            "against the Insured. If written notice of a Claim has been given to the Insurer "
            "pursuant to this clause, then any Claim subsequently made alleging, arising out "
            "of, based upon or attributable to the facts alleged in the original Claim shall "
            "be considered made against the Insured and reported to the Insurer at the time "
            "such original notice was given."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat General Insurance — Directors & Officers Liability Policy (2019)",
        "risk_level": "high",
    },

    # -----------------------------------------------------------------------
    # FRAUD / WILFUL ACT CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "fraud_exclusion",
        "product_category": ["motor", "property", "personal_accident", "liability"],
        "title": "Standard Fraud and Wilful Act Forfeiture Clause",
        "text": (
            "If any claim under this Policy: (i) be in any respect fraudulent or if any "
            "fraudulent means or devices be used by the Insured or anyone acting on his "
            "behalf to obtain any benefit under this Policy; (ii) be in respect of any loss, "
            "damage, destruction, injury or liability by the wilful act of or with the "
            "connivance of the Insured; all benefit under this Policy shall be forfeited and "
            "the policy voided."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy",
        "risk_level": "high",
    },
    {
        "clause_type": "fraud_exclusion",
        "product_category": ["personal_accident"],
        "title": "Personal Accident — Fraudulent Claim Forfeiture",
        "text": (
            "If any claim under this Policy be in any respect fraudulent or intentionally "
            "exaggerated or if any fraudulent means or devices are used by the Insured "
            "Person or anyone acting on his behalf to obtain any benefit which would have "
            "been payable (even if already due) hereunder shall be forfeited from the date "
            "of such fraud."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Group Personal Accident Policy",
        "risk_level": "high",
    },

    # -----------------------------------------------------------------------
    # ARBITRATION CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "arbitration",
        "product_category": ["motor", "property"],
        "title": "Motor Policy — Arbitration Clause (Zimbabwe)",
        "text": (
            "If any difference arises as to the amount of any loss or damage to be paid "
            "under this Policy such difference shall independently of all other questions "
            "be referred to the decision of an Arbitrator to be appointed in writing by the "
            "parties in difference or if they cannot agree upon a single Arbitrator to the "
            "decision of two disinterested persons as Arbitrators of whom one shall be "
            "appointed in writing by each of the parties within two calendar months after "
            "having been required so to do in writing by the other party. The cost of the "
            "reference and of the award shall be in the discretion of the Arbitrator. It "
            "shall be a condition precedent to any rights of action or suit upon this Policy "
            "that the award by such Arbitrator of the amount of the loss or damage if "
            "disputed shall be first obtained."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy (July 2025)",
        "risk_level": "moderate",
    },
    {
        "clause_type": "arbitration",
        "product_category": ["personal_accident", "property", "domestic"],
        "title": "Standard Arbitration Clause — Zimbabwe Statutory Provisions",
        "text": (
            "If any difference shall arise as to the amount to be paid under this Policy "
            "(liability being otherwise admitted) such difference shall be referred to "
            "arbitration in accordance with the statutory provisions in that behalf for the "
            "time being in force in Zimbabwe and the making of an award shall be a condition "
            "precedent to any liability for The Company to make any payment under this Policy."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Group Personal Accident Policy / Domestic All In One",
        "risk_level": "moderate",
    },

    # -----------------------------------------------------------------------
    # FORFEITURE / TIME-BAR CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "time_bar",
        "product_category": ["motor"],
        "title": "Forfeiture of Claim — 3-Month Disclaimer Bar",
        "text": (
            "In the event of the Company disclaiming liability in respect of any claim and "
            "an action or suit be not commenced within three months after such disclaimer or "
            "(in case of an arbitration taking place in pursuance of the Arbitration "
            "Condition of this Policy) within three months after the Arbitrator or "
            "Arbitrators or Umpire shall have made their award, all benefit under this "
            "Policy in respect of such claim shall be forfeited."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy",
        "risk_level": "high",
    },
    {
        "clause_type": "time_bar",
        "product_category": ["personal_accident"],
        "title": "Personal Accident — 12-Month Forfeiture Bar",
        "text": (
            "In the event of The Company disclaiming liability in respect of any claim and "
            "an action or suit not being commenced within twelve months after such disclaimer "
            "or, in the case of an arbitration taking place within twelve months after the "
            "arbitrator shall have made his award, all benefit under this Policy in respect "
            "of such claim shall be forfeited."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Group Personal Accident Policy",
        "risk_level": "high",
    },

    # -----------------------------------------------------------------------
    # CANCELLATION CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "cancellation",
        "product_category": ["motor", "property", "personal_accident"],
        "title": "Standard 30-Day Notice Cancellation Clause",
        "text": (
            "The Company may cancel this Policy by giving 30 days written notice to the "
            "Insured at his last known address and in such event will return to the Insured "
            "the premium less the pro rata portion thereof for the period the Policy has "
            "been in force, or the Policy may be cancelled at any time by the Insured on "
            "written notice and (provided no claim has arisen during the then current period "
            "of insurance) the Insured shall be entitled to a return of the premium less "
            "premium at the Company's short period rates for the time the Policy has been "
            "in force."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy (July 2025)",
        "risk_level": "moderate",
    },
    {
        "clause_type": "cancellation",
        "product_category": ["personal_accident"],
        "title": "Group Personal Accident — 30-Day Cancellation",
        "text": (
            "The Company or the Policyholder may cancel this Policy by giving 30 days "
            "notice in writing to the other party. In such event the Policyholder shall "
            "be entitled to a pro rata refund of premium subject to any minimum premium "
            "or adjustable premium provisions."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Group Personal Accident Policy",
        "risk_level": "moderate",
    },

    # -----------------------------------------------------------------------
    # SUBROGATION CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "subrogation",
        "product_category": ["motor", "property", "personal_accident"],
        "title": "Standard Rights Against Third Parties (Subrogation)",
        "text": (
            "The Insured shall at the expense of the Company do and concur in doing and "
            "permit to be done all such acts and things as may be necessary or reasonably "
            "required by the Company for the purpose of enforcing any rights and remedies "
            "or of obtaining relief or indemnity from other parties to which the Company "
            "shall be or would become entitled or subrogated upon its paying for or making "
            "good any loss or damage under this Policy, whether such acts and things shall "
            "be or become necessary or required before or after his indemnification by "
            "the Company."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy",
        "risk_level": "moderate",
    },

    # -----------------------------------------------------------------------
    # OTHER INSURANCE CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "other_insurance",
        "product_category": ["motor", "property", "personal_accident"],
        "title": "Rateable Proportion — Other Insurances Clause",
        "text": (
            "If at the time any claim arises under this Policy there is any other existing "
            "insurance covering the same loss, damage or liability the Company shall not be "
            "liable to pay or contribute more than its rateable proportion of any loss, "
            "damage, compensation, costs or expenses."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy",
        "risk_level": "low",
    },

    # -----------------------------------------------------------------------
    # EXCLUSION CLAUSES — WAR, RIOT, NUCLEAR
    # -----------------------------------------------------------------------
    {
        "clause_type": "war_exclusion",
        "product_category": ["motor", "property", "personal_accident", "liability"],
        "title": "War, Invasion and Terrorism Exclusion",
        "text": (
            "This Policy does not cover loss or damage directly or indirectly occasioned by "
            "or through or in consequence of: (a) War, invasion, act of foreign enemy, "
            "hostilities or warlike operations (whether war be declared or not), civil war; "
            "mutiny, riot, strike, civil commotion, military or popular uprising, "
            "insurrection, rebellion, revolution, military or usurped power, martial law or "
            "state of siege; (b) Any act calculated or directed to overthrow or influence "
            "any Government de jure or de facto or any provincial or local authority with "
            "force, or by means of fear, terrorism or violence; (c) Any act which is "
            "calculated or directed to further any political aim, objective or cause or in "
            "protest against any Government de jure or de facto; (d) Any armed conflict "
            "between regions or political, religious, ethnic or tribal factions within "
            "Zimbabwe; (e) Any acts of terrorism committed by any body or person or any "
            "group of persons or by any Government de jure or de facto. In any action suit "
            "or other proceedings where the Company alleges that by reason of the provisions "
            "of this exception any event, loss, destruction or damage is not covered by this "
            "policy the burden of proving that such event, loss, destruction or damage is "
            "covered shall be upon the Insured."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy (July 2025)",
        "risk_level": "high",
    },
    {
        "clause_type": "nuclear_exclusion",
        "product_category": ["motor", "property", "personal_accident", "liability"],
        "title": "Nuclear and Radioactive Contamination Exclusion",
        "text": (
            "This Policy does not cover loss, destruction or damage or any consequential "
            "loss or any legal liability of whatever nature directly or indirectly caused by "
            "or arising from or in consequence of or contributed to by nuclear weapons "
            "material or by ionizing radiations or contamination by radioactivity from any "
            "nuclear fuel or from any nuclear waste or from the combustion of nuclear fuel. "
            "For the purpose of this exception only, combustion shall include any "
            "self-sustaining process of nuclear fission."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy (July 2025)",
        "risk_level": "high",
    },
    {
        "clause_type": "riot_strike",
        "product_category": ["motor", "property"],
        "title": "Non-Political Riot and Strike Extension",
        "text": (
            "Subject to the terms, conditions and clauses contained herein the Insurers "
            "agree to indemnify the Insured against physical loss of or damage to the "
            "property insured directly related to or caused by or arising from: (a)(i) The "
            "act of any person taking part together with others in any disturbance of the "
            "public peace (whether in connection with a labour disturbance, strike or "
            "lock-out or not) not being an occurrence mentioned in the General War Exception; "
            "(ii) the wilful act of any striker or locked-out worker done in furtherance of "
            "a strike or in resistance to a lock-out; (iii) the act of any lawfully "
            "established authority in controlling, preventing, suppressing or in any other "
            "way dealing with any occurrence referred to in clauses (i) or (ii) above."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy (July 2025)",
        "risk_level": "moderate",
    },

    # -----------------------------------------------------------------------
    # MOTOR-SPECIFIC CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "total_loss",
        "product_category": ["motor"],
        "title": "Motor Total Loss — 70% Threshold Rule",
        "text": (
            "In the event of the estimated repair costs exceeding 70% (seventy percent) of "
            "the market value or insured's estimated value as stated in the schedule, "
            "whichever is lesser, at the time of loss or damage, the vehicle shall be "
            "considered to be beyond economical repair and shall be considered a Total Loss. "
            "In the event of any claim on any vehicle described in the Schedule being settled "
            "on a total loss basis all insurance in respect of such vehicle shall cease from "
            "the date of settlement. However, the insured may be given the option of "
            "retaining the damaged vehicle on payment to the Company of 30% of insured value "
            "or the actual value of the salvage as determined by the Company, whichever is "
            "higher."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Private Motor Policy (July 2025)",
        "risk_level": "moderate",
    },
    {
        "clause_type": "condition_of_average",
        "product_category": ["motor"],
        "title": "Motor Condition of Average — 20% Market Value Rule",
        "text": (
            "The onus shall be upon the Insured to keep the insured value of every vehicle "
            "level with market value at all times and shall give due regard to any features "
            "that would increase the value above that of a standard model. If the market "
            "value of any vehicle shall at the time of any loss or damage be more than "
            "twenty percent greater than the insured value the Insured shall be considered "
            "as being his own insurer for the difference between the market value and the "
            "insured value and shall bear a rateable proportion of the loss accordingly. "
            "Market value means the current market value of the insured vehicle taking into "
            "account its mileage, general condition and what a willing buyer would pay a "
            "willing seller of a similar vehicle of the same kind and condition."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy",
        "risk_level": "moderate",
    },
    {
        "clause_type": "glass_clause",
        "product_category": ["motor"],
        "title": "Glass / Windscreen Clause — 33.33% Contribution",
        "text": (
            "Any claim for the cost of reinstating any glass forming a portion of any motor "
            "car described in the Schedule or of any accessory permanently attached thereto "
            "as a result of contact with flying stones or any other flying object will be "
            "met without deduction of that portion of the First Amount Payable for which no "
            "discount of premium has been allowed, but the Insured shall be required to make "
            "a contribution of 33.33% of the cost of reinstatement or as specified in the "
            "Schedule. The Company will however pay repair costs in full should the Insured "
            "opt to have the glass repaired rather than replaced. Provided however that this "
            "extension does not apply to the breakage of glass arising from an accident in "
            "which other damage is sustained to the vehicle."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Private Motor Policy (July 2025)",
        "risk_level": "low",
    },
    {
        "clause_type": "territorial_extension",
        "product_category": ["motor"],
        "title": "SADC Territorial Extension Clause",
        "text": (
            "It is hereby declared and agreed that notwithstanding anything contained herein "
            "to the contrary this policy shall be extended to indemnify the Insured whilst "
            "the vehicle/s is/are temporarily in any of the countries that are part of the "
            "Southern African Development Community (SADC) in the African continent but "
            "excluding the Democratic Republic of Congo (DRC). Temporary shall mean for the "
            "purpose of this clause, not more than 45 (Forty-five) Days outside Zimbabwe "
            "during any one trip or not more than 90 (Ninety) Days in aggregate outside "
            "Zimbabwe during any one period of insurance, including cover whilst the vehicle "
            "is in transit by sea between any ports in the aforementioned territories. "
            "Provided always that this policy shall not be deemed to be a policy of "
            "insurance in compliance with the provisions of any compulsory insurance "
            "legislation in the territories."
        ),
        "jurisdiction": "Zimbabwe / SADC",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy",
        "risk_level": "low",
    },
    {
        "clause_type": "road_traffic_act",
        "product_category": ["motor"],
        "title": "Road Traffic Act [Chapter 13:11] Compliance Clause",
        "text": (
            "It is hereby declared and agreed that in respect of the use of the motor "
            "vehicle on any road in Zimbabwe this policy shall, subject to the following "
            "conditions, be a policy for all purposes of the Road Traffic Act [Chapter "
            "13:11] as amended: (1) In the event of the Company being required to make any "
            "payment under this policy in respect of the liability of any person which, but "
            "for the provisions of the legislation or any amendment thereof, it would not "
            "have been required to make, any sum so paid shall be recoverable by the Company "
            "from that person. (2) Nothing contained in this extension shall extend the "
            "liability of the Company beyond the minimum requirements of the legislation or "
            "any amendments thereof. (3) Any limitation of liability stated in this Policy "
            "as to the amount or amounts which may become payable in respect of the death or "
            "injury to any person or persons shall not apply to the indemnity which is by "
            "law required to be provided in terms of the legislation."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy (July 2025)",
        "risk_level": "moderate",
    },
    {
        "clause_type": "drunk_driving_exclusion",
        "product_category": ["motor"],
        "title": "Drunk Driving Exclusion — 80mg/100ml Threshold",
        "text": (
            "This Policy does not cover any accident, injury, loss, damage and/or liability "
            "caused, sustained or incurred while any Vehicle is being driven by the Insured "
            "or by any person with the general knowledge and consent of the Insured while "
            "under the influence of intoxicating liquor or drugs, or while the percentage of "
            "alcohol in the driver's blood is in excess of 80 milligrams of alcohol per 100 "
            "millilitres of blood."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy",
        "risk_level": "high",
    },
    {
        "clause_type": "fleet_declaration",
        "product_category": ["motor"],
        "title": "Fleet Declaration Adjustment Clause",
        "text": (
            "The Insured shall submit to the Company at the end of each six months during "
            "the period of Insurance a declaration of the total number of Vehicles insured "
            "under this Policy, owned, hired or leased at such expiry. Further the Insured "
            "shall provide valuations of such vehicles based on reasonable market value. "
            "The Company shall upon receipt of this declaration make a premium adjustment "
            "of 50% of the annual rate per vehicle applied to the difference in the number "
            "of vehicles at inception or renewal and the number declared. It is further "
            "declared that the Company shall be notified immediately during the period of "
            "Insurance where any vehicle is hired by the Insured for a period exceeding "
            "30 (Thirty) days or where there are more than 2 (Two) vehicles hired at any "
            "one time."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy (July 2025)",
        "risk_level": "moderate",
    },

    # -----------------------------------------------------------------------
    # PERSONAL ACCIDENT SPECIFIC CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "permanent_disablement",
        "product_category": ["personal_accident"],
        "title": "Permanent Total Disablement — 24-Month Assessment Period",
        "text": (
            "\"Permanent Total Disablement\" shall mean total and absolute disablement "
            "which entirely prevents an Insured Person from engaging in or giving attention "
            "to an Insured Person's usual occupation and any occupation for which the "
            "Insured Person is qualified or has received specialised training and which will "
            "in all probability be lasting and continuous for the lifetime of the Insured "
            "Person. The diagnosis and determination of the Permanent Total Disablement must "
            "be made by a Physician and must be continuous and permanent for at least 24 "
            "consecutive months from the onset of the disablement. The degree of Permanent "
            "Disablement will be determined immediately it is established or as soon as it "
            "can reasonably be assumed that there will be no further improvement or worsening "
            "of the Insured Person's condition in consequence of the Accident, but not later "
            "than 24 months from the Date of Loss."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Group Personal Accident Policy",
        "risk_level": "moderate",
    },
    {
        "clause_type": "age_limit",
        "product_category": ["personal_accident"],
        "title": "Personal Accident — Age 70 Cover Cessation",
        "text": (
            "All cover in respect of an Insured Person shall cease on the renewal date "
            "following such Insured Person's 70th birthday."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Group Personal Accident Policy",
        "risk_level": "low",
    },
    {
        "clause_type": "wage_declaration",
        "product_category": ["personal_accident"],
        "title": "Wage Declaration and Claim Settlement Basis",
        "text": (
            "It is a condition of this policy that the Insured shall declare to the Insurers "
            "each and every increase in the salaries and wages of its employees and pay the "
            "additional premium due for such increase. Such declaration to be made within "
            "30 days from the end of the month of such salary and wage increase being "
            "implemented. For any accident or injury for which compensation is payable in "
            "terms of this policy the basis of any claim settlement will be as follows: "
            "(1) If the accident or injury takes place in a period in which a declaration "
            "has been made by the Insured then this declaration will be used to calculate "
            "any compensation payable. (2) If the accident or injury takes place in a period "
            "in which no declaration has been made then the last declaration on record will "
            "be used to calculate any compensation payable."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Group Personal Accident Policy",
        "risk_level": "moderate",
    },

    # -----------------------------------------------------------------------
    # D&O SPECIFIC CLAUSES
    # -----------------------------------------------------------------------
    {
        "clause_type": "insuring_agreement",
        "product_category": ["directors_officers"],
        "title": "D&O Section 1 — Directors and Officers Insurance Agreement",
        "text": (
            "The Insurer shall pay the Loss of each and every Insured arising from any "
            "Claim or Claims first made against the Insured during the Policy Period or the "
            "Discovery Period (if applicable) and notified to the Insurer during the Policy "
            "Period or the Discovery Period (if applicable) for any Wrongful Act in their "
            "respective capacities as Directors or Officers of the Company, except if and to "
            "the extent that the Company has indemnified the Insured. The Insurer shall, in "
            "accordance with and subject to the Defence Costs provision, advance in respect "
            "of each and every Insured the Defence Costs of such Claim or Claims prior to "
            "the final resolution."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat General Insurance — Directors & Officers Liability Policy (2019)",
        "risk_level": "high",
    },
    {
        "clause_type": "wrongful_act_definition",
        "product_category": ["directors_officers"],
        "title": "D&O Wrongful Act Definition",
        "text": (
            "\"Wrongful Act\" means any actual or alleged breach of duty, breach of trust, "
            "neglect, error, misstatement, misrepresentation, misleading statement, "
            "omission, breach of warranty of authority or other act by the Directors and "
            "Officers of the Company solely in their respective capacities as such, but not "
            "in their capacity as Director or Officer of an entity other than the Company "
            "or any act or omission claimed against them solely by reason of their status "
            "as Directors and Officers of the Company. Same, related, continuous or repeated "
            "Wrongful Acts shall constitute a single Wrongful Act."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat General Insurance — Directors & Officers Liability Policy (2019)",
        "risk_level": "high",
    },
    {
        "clause_type": "discovery_period",
        "product_category": ["directors_officers"],
        "title": "D&O Discovery Period (Run-Off) Clause",
        "text": (
            "At the option of the Company and subject to payment of an additional premium "
            "of 100% of the Full Annual Premium of the current year the Insurer agrees to "
            "extend the period during which the Insured may report a Claim for a Period of "
            "12 months (herein referred to as the Discovery Period) provided that: (a) this "
            "option may only be exercised in the event that the Insurer cancels or refuses "
            "to renew this policy; (b) this option must be exercised by the Company in "
            "writing and the premium must be paid within ten (10) days of the effective date "
            "of cancellation or non-renewal; (c) once exercised the option cannot be "
            "cancelled by either the Company or Insurer. The Named Company shall be entitled "
            "to a ninety (90) day Discovery Period at no additional premium in the event "
            "that the Insurer cancels or refuses to renew the policy."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat General Insurance — Directors & Officers Liability Policy (2019)",
        "risk_level": "high",
    },
    {
        "clause_type": "defence_costs",
        "product_category": ["directors_officers"],
        "title": "D&O Defence Costs — Prior Consent and Advancement",
        "text": (
            "The Insurer does not, however, under this policy, assume any duty to defend. "
            "The Insureds shall defend and contest any Claim made against them. The Insured "
            "shall not admit or assume any liability, enter into any settlement agreement, "
            "consent to any judgement or incur any Defence Costs without the prior written "
            "consent of the Insurer. Only those settlements, consent to judgements and "
            "Defence Costs which have been consented to by the Insurer shall be recoverable "
            "as Loss under the terms of this policy. The Insurer shall advance, at the "
            "written request of the Insured, Defence Costs prior to the final resolution of "
            "a Claim, but such advance payments shall be repaid to the Insurer in the event "
            "and to the extent that the Insureds or the Company shall not be entitled under "
            "the terms and conditions of this policy to payment of such Loss."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat General Insurance — Directors & Officers Liability Policy (2019)",
        "risk_level": "high",
    },
    {
        "clause_type": "zimbabwe_law_jurisdiction",
        "product_category": ["directors_officers"],
        "title": "D&O — Zimbabwe Jurisdiction Clause",
        "text": (
            "No action shall lie against the Insurer unless as a condition precedent thereto, "
            "such action is brought in a court of competent jurisdiction in the Republic of "
            "Zimbabwe, which shall have exclusive jurisdiction (High Court). It is further "
            "a condition precedent to any action against the Insurer that there shall have "
            "been full compliance with all of the terms of this policy, and the amount of "
            "the Insured's obligation to pay shall have been finally determined either by "
            "judgement against the Insured after actual trial or by written agreement of "
            "the Insured, the Claimant and the Insurer."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat General Insurance — Directors & Officers Liability Policy (2019)",
        "risk_level": "high",
    },
    {
        "clause_type": "false_accounting_exclusion",
        "product_category": ["directors_officers"],
        "title": "D&O False Accounting Exclusion",
        "text": (
            "It is hereby understood and agreed that the Insurer shall not be liable to make "
            "any payment for Loss in connection with any claim or claims made against the "
            "Insured, alleging, arising out of, based upon or attributable to False "
            "Accounting. For the purposes of this policy \"False Accounting\" shall mean the "
            "creation, recording or concealment of financial results or transactions with "
            "the intention of giving, or which results in, a misleading or deceptive "
            "statement of the financial condition of the Insured. Off balance sheet "
            "transactions shall not constitute False Accounting provided that: (a) There "
            "shall have been full disclosure of such transactions to the Insurer; (b) The "
            "Insurer shall have acknowledged such transactions in writing; and (c) The "
            "Insured shall agree to abide by any terms, conditions, exclusions or additional "
            "premiums required by the Insurer."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat General Insurance — Directors & Officers Liability Policy (2019)",
        "risk_level": "high",
    },

    # -----------------------------------------------------------------------
    # MISDESCRIPTION / CONDITIONS PRECEDENT
    # -----------------------------------------------------------------------
    {
        "clause_type": "conditions_precedent",
        "product_category": ["motor", "property", "personal_accident"],
        "title": "Conditions Precedent to Liability",
        "text": (
            "The due observance and fulfillment of the terms, conditions and endorsements "
            "of this Policy by the Insured in so far as they relate to anything to be done "
            "or complied with by the Insured shall be conditions precedent to any liability "
            "of the Company to make any payment under this Policy. No waiver of any of the "
            "terms, conditions and endorsements of this Policy shall be valid unless made "
            "in writing and signed by a duly authorised officer of the Company."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy",
        "risk_level": "moderate",
    },
    {
        "clause_type": "misdescription",
        "product_category": ["motor", "property", "personal_accident"],
        "title": "Misdescription, Misrepresentation and Non-Disclosure",
        "text": (
            "This Policy or any particular Section shall be voidable in the event of: "
            "(a) any material misdescription of any property insured or of any building or "
            "place in which such property is contained; (b) any misrepresentation of "
            "material fact; (c) any omission to disclose material fact such as would affect "
            "the Company's assessment of the risk."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy / Private Motor Policy",
        "risk_level": "moderate",
    },

    # -----------------------------------------------------------------------
    # PREVENTION OF LOSS
    # -----------------------------------------------------------------------
    {
        "clause_type": "prevention_of_loss",
        "product_category": ["motor"],
        "title": "Motor — Prevention of Loss / Reasonable Precautions",
        "text": (
            "The Insured shall take all reasonable steps to safeguard any vehicle described "
            "in the schedule hereto from loss or damage and to maintain it in efficient "
            "condition and the Company shall have at all times free and full access to "
            "examine such vehicle or any part thereof or any driver or employee of the "
            "Insured. In the event of any accident or breakdown such vehicle shall not be "
            "left unattended without proper precautions being taken to prevent further "
            "damage or loss and if such vehicle be driven before the necessary repairs are "
            "effected any extension of the damage or further damage to such vehicle shall "
            "be entirely at the Insured's own risk."
        ),
        "jurisdiction": "Zimbabwe",
        "source": "Zimnat Lion — Auto Fleet Policy (July 2025)",
        "risk_level": "low",
    },
]


def _add_hashes(clauses: list[dict]) -> list[dict]:
    """Add SHA-256 text hash for deduplication."""
    for clause in clauses:
        clause["text_hash"] = hashlib.sha256(clause["text"].encode()).hexdigest()
    return clauses


def main() -> None:
    print("=== Real Clauses Library Generator ===")
    print(f"  Source: 8 Zimnat Lion Insurance Company Limited policy documents")

    clauses = _add_hashes(CLAUSES)

    # Count by type
    by_type: dict[str, int] = {}
    by_product: dict[str, int] = {}
    for c in clauses:
        by_type[c["clause_type"]] = by_type.get(c["clause_type"], 0) + 1
        for p in c["product_category"]:
            by_product[p] = by_product.get(p, 0) + 1

    out_path = OUT_DIR / "standard_clauses_real.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"clauses": clauses, "total": len(clauses)}, f, indent=2)

    print(f"\n  Total clauses: {len(clauses)}")
    print("\n  By clause type:")
    for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"    {t:<35} {n}")
    print("\n  By product category:")
    for p, n in sorted(by_product.items(), key=lambda x: -x[1]):
        print(f"    {p:<35} {n}")
    print(f"\n  Saved to: {out_path.resolve()}")
    print("\n  These are REAL clauses extracted from actual Zimnat Lion policy documents.")
    print("  Use them as the primary reference set for the Clause Deviation Detector.")


if __name__ == "__main__":
    main()
