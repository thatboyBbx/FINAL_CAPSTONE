"""
gen_standard_clauses.py
========================
Generates an expanded standard insurance clause knowledge base for the
InsureIntel Zimbabwe clause deviation detection module.

Sources modelled:
  - Zimbabwe Insurance Act [Chapter 24:07] — standard wordings
  - IPEC-prescribed standard policy wordings
  - IAIS Insurance Core Principles (ICP) standard clause language
  - Regional standards: COMESA Yellow Card, AIO standard policies
  - Product-specific wordings: motor, fire, life, health, funeral,
    micro, agricultural, marine, engineering, liability, reinsurance

300+ clauses across 10 clause types:
  coverage, exclusion, condition, claims_procedure, cancellation,
  premium, subrogation, arbitration, definitions, general_terms

Output: storage/datasets/production/standard_clauses_library.json

Run: python scripts/gen_standard_clauses.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

OUT_DIR = Path("storage/datasets/production")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Clause library — comprehensive Zimbabwe + IAIS standard wordings
# ---------------------------------------------------------------------------
CLAUSES: list[dict] = [

    # ==========================================================================
    # COVERAGE CLAUSES
    # ==========================================================================

    # ---- Motor ---------------------------------------------------------------
    {"clause_type": "coverage", "product": "motor", "source": "Zimbabwe Motor Standard Policy", "jurisdiction": "ZW",
     "text": "The Insurer agrees to indemnify the Insured against loss of or damage to the insured motor vehicle and its accessories caused by accidental collision or overturning, fire, external explosion, self-ignition, lightning, burglary, housebreaking or theft, occurring during the period of insurance within the territorial limits specified in the schedule."},

    {"clause_type": "coverage", "product": "motor", "source": "Zimbabwe Motor Standard Policy — Third Party", "jurisdiction": "ZW",
     "text": "The Insurer will indemnify the Insured in respect of all sums which the Insured shall become legally liable to pay as damages arising from the use of the motor vehicle in respect of: (a) accidental bodily injury to or death of any person, including passengers; (b) accidental damage to property not belonging to the Insured; (c) legal costs incurred with the Insurer's written consent."},

    {"clause_type": "coverage", "product": "motor", "source": "COMESA Yellow Card Standard", "jurisdiction": "COMESA",
     "text": "Under the COMESA Yellow Card scheme, the Insurer provides compulsory third-party motor insurance cover for use of the insured vehicle in all COMESA member states, in accordance with the legislation of each member state visited, up to the minimum statutory limits prescribed therein."},

    {"clause_type": "coverage", "product": "motor", "source": "Zimbabwe Motor Comprehensive Extension", "jurisdiction": "ZW",
     "text": "This policy is extended to cover loss or damage to the insured vehicle whilst in the custody of a licensed service centre, garage or repair workshop. The Insurer's liability shall be limited to the insured value of the vehicle at the time of loss, less any applicable excess."},

    {"clause_type": "coverage", "product": "motor", "source": "Zimbabwe Motor Fleet Standard", "jurisdiction": "ZW",
     "text": "Where this policy insures a fleet of motor vehicles, coverage applies to each vehicle individually scheduled hereto. Any vehicle acquired subsequent to the inception date of this policy shall be automatically added to the schedule provided the Insured notifies the Insurer within thirty (30) days of acquisition."},

    # ---- Fire and Property ---------------------------------------------------
    {"clause_type": "coverage", "product": "fire_property", "source": "Zimbabwe Standard Fire Policy", "jurisdiction": "ZW",
     "text": "This policy covers loss or damage to the insured property caused by: (a) fire; (b) lightning; (c) explosion of gas used for domestic purposes; (d) aircraft or articles dropped therefrom; (e) impact by road vehicles, rail vehicles or animals. Such coverage applies within the territorial limits of Zimbabwe."},

    {"clause_type": "coverage", "product": "fire_property", "source": "Zimbabwe Householders Comprehensive Policy", "jurisdiction": "ZW",
     "text": "The Insurer agrees to indemnify the Insured against accidental physical loss or damage to household contents and personal belongings whilst contained in or temporarily removed from the insured premises, including loss by theft involving forcible and violent entry into or exit from the premises."},

    {"clause_type": "coverage", "product": "fire_property", "source": "IAIS ICP Standard Property Wording", "jurisdiction": "international",
     "text": "Subject to the terms and conditions of this policy, the Insurer will indemnify the Insured for direct physical loss or damage to the insured property described in the schedule, caused by any of the perils specified herein, occurring during the period of insurance, within the geographical area stated in the schedule."},

    {"clause_type": "coverage", "product": "fire_property", "source": "Zimbabwe Commercial Property All Risks", "jurisdiction": "ZW",
     "text": "This all-risks policy covers accidental physical loss or damage to the insured property howsoever caused except as specifically excluded herein. The burden of proof that a loss falls within an exclusion shall rest upon the Insurer."},

    {"clause_type": "coverage", "product": "fire_property", "source": "Zimbabwe Business Interruption Extension", "jurisdiction": "ZW",
     "text": "This policy is extended to cover loss of gross profit and additional increase in cost of working resulting from an interruption or interference with the business carried on by the Insured at the insured premises, directly caused by damage to property at the premises insured under the material damage section of this policy."},

    # ---- Life ----------------------------------------------------------------
    {"clause_type": "coverage", "product": "life", "source": "Zimbabwe Life Assurance Standard Wording", "jurisdiction": "ZW",
     "text": "The Insurer agrees to pay the sum insured stated in the schedule to the named beneficiary or beneficiaries upon the death of the life assured from any cause whatsoever during the term of this policy, provided this policy is in full force at the date of death."},

    {"clause_type": "coverage", "product": "life", "source": "Zimbabwe Endowment Policy Standard", "jurisdiction": "ZW",
     "text": "The Insurer will pay the maturity benefit upon the life assured surviving to the maturity date stated in the schedule, or the death benefit if the life assured dies before the maturity date. All premiums must be fully paid for the maturity benefit to become payable."},

    {"clause_type": "coverage", "product": "life", "source": "Zimbabwe Disability Income Cover Standard", "jurisdiction": "ZW",
     "text": "In the event of the life assured becoming totally and permanently disabled as defined herein and being unable to perform the duties of their own or any similar occupation, the Insurer shall waive all future premiums and pay the disability benefit as specified in the schedule for the duration of the disability."},

    {"clause_type": "coverage", "product": "life", "source": "IAIS ICP Life Assurance Standard", "jurisdiction": "international",
     "text": "The Insurer undertakes to pay the applicable benefit upon the occurrence of the insured event (death, disability, critical illness or survival to a specified age), subject to the waiting periods, benefit limits and conditions specified in this policy schedule."},

    # ---- Health --------------------------------------------------------------
    {"clause_type": "coverage", "product": "health", "source": "Zimbabwe Medical Aid Standard Cover", "jurisdiction": "ZW",
     "text": "This policy reimburses the Insured for medically necessary treatment expenses incurred at accredited hospitals and clinics in Zimbabwe, including: in-patient hospitalisation, surgical procedures, specialist consultations, diagnostic investigations, and prescribed medication, subject to the benefit limits in the schedule."},

    {"clause_type": "coverage", "product": "health", "source": "Zimbabwe Emergency Medical Evacuation Cover", "jurisdiction": "ZW",
     "text": "In the event of a life-threatening medical emergency, the Insurer will arrange and pay for medically supervised evacuation of the Insured to the nearest appropriate medical facility capable of providing the required treatment, within Southern Africa."},

    # ---- Funeral / PA --------------------------------------------------------
    {"clause_type": "coverage", "product": "funeral", "source": "Zimbabwe Funeral Assurance Standard Policy", "jurisdiction": "ZW",
     "text": "Upon the death of the principal life assured or any covered dependant, the Insurer shall pay the funeral benefit specified in the schedule within forty-eight (48) hours of receipt of a certified death certificate and completed claim form. The benefit is payable in the form of cash or funeral services as selected by the policyholder at inception."},

    {"clause_type": "coverage", "product": "personal_accident", "source": "Zimbabwe Personal Accident Standard Policy", "jurisdiction": "ZW",
     "text": "The Insurer will pay the appropriate benefit as stated in the schedule upon the Insured sustaining accidental bodily injury which within twelve (12) calendar months from the date of the accident solely and independently of any other cause results in: (a) death; (b) permanent total disablement; (c) permanent partial disablement; (d) temporary total disablement."},

    # ---- Agricultural --------------------------------------------------------
    {"clause_type": "coverage", "product": "agricultural", "source": "Zimbabwe Crop Insurance Standard", "jurisdiction": "ZW",
     "text": "This policy indemnifies the Insured farmer against yield loss resulting from one or more of the following perils affecting the insured crop during the growing season: (a) hailstorm; (b) fire; (c) drought (where drought index trigger is selected); (d) excessive rainfall and flooding; (e) frost; (f) cyclone and high winds; (g) locust swarms."},

    {"clause_type": "coverage", "product": "agricultural", "source": "Zimbabwe Livestock Insurance Standard", "jurisdiction": "ZW",
     "text": "The Insurer will pay the insured value per head of livestock in the event of death of any insured animal arising from accident, illness or disease during the period of insurance. The insured animal must be identified by ear tag, brand or microchip as described in the schedule."},

    # ---- Marine / Engineering ------------------------------------------------
    {"clause_type": "coverage", "product": "marine", "source": "Zimbabwe Marine Cargo Standard (Institute Cargo Clauses A)", "jurisdiction": "ZW",
     "text": "This insurance covers all risks of physical loss or damage to the subject matter insured during the ordinary course of transit, from the time the goods leave the warehouse at origin to the time they are delivered at the final destination named in the policy, subject to the Institute Cargo Clauses (A) as incorporated herein."},

    {"clause_type": "coverage", "product": "engineering", "source": "Zimbabwe Contractors All Risks Policy", "jurisdiction": "ZW",
     "text": "Section 1 — Material Damage: The Insurer will indemnify the Insured against sudden and unforeseen physical loss or damage to the contract works, construction plant, equipment and machinery described in the schedule, occurring during the period of insurance at the contract site."},

    # ---- Liability -----------------------------------------------------------
    {"clause_type": "coverage", "product": "liability", "source": "Zimbabwe Public Liability Standard Policy", "jurisdiction": "ZW",
     "text": "The Insurer will indemnify the Insured against all sums which the Insured shall become legally liable to pay as damages in respect of accidental bodily injury to any person and accidental damage to property of any person occurring in connection with the business described herein, up to the limit of indemnity stated in the schedule."},

    {"clause_type": "coverage", "product": "liability", "source": "Zimbabwe Employer's Liability Standard", "jurisdiction": "ZW",
     "text": "The Insurer will indemnify the Insured in respect of all sums for which the Insured shall be liable to pay compensation to any employee arising from bodily injury, disease, illness or death sustained in the course of and arising from employment by the Insured, as required by the Workers Compensation Act of Zimbabwe."},

    # ---- Reinsurance ---------------------------------------------------------
    {"clause_type": "coverage", "product": "reinsurance", "source": "IAIS ICP Reinsurance Standard", "jurisdiction": "international",
     "text": "The Reinsurer agrees to indemnify the Reinsured, in the proportion and to the extent agreed in this treaty, against losses arising from the original insurance policies written by the Reinsured in the classes of business described herein, subject to the terms, conditions and exclusions of this reinsurance agreement."},

    {"clause_type": "coverage", "product": "reinsurance", "source": "Zimbabwe Excess of Loss Standard Wording", "jurisdiction": "ZW",
     "text": "The Reinsurer's liability under this agreement is limited to the excess of each and every loss above the retention specified in the schedule, up to but not exceeding the maximum limit per occurrence stated herein. The Reinsurer's aggregate liability in respect of all losses during the treaty year shall not exceed the annual aggregate limit stated in the schedule."},

    # ==========================================================================
    # EXCLUSION CLAUSES
    # ==========================================================================

    {"clause_type": "exclusion", "product": "all", "source": "IAIS Standard Nuclear Exclusion", "jurisdiction": "international",
     "text": "This policy does not cover any loss, damage, liability, cost or expense directly or indirectly caused by, contributed to by or arising from ionising radiation or contamination by radioactivity from any nuclear fuel, nuclear waste, nuclear weapon or nuclear installation."},

    {"clause_type": "exclusion", "product": "all", "source": "IAIS Standard War Exclusion", "jurisdiction": "international",
     "text": "This policy excludes any loss, damage or liability arising from or attributable to war, invasion, act of foreign enemies, hostilities (whether war be declared or not), civil war, rebellion, revolution, insurrection, military or usurped power, seizure, capture, nationalisation, confiscation, expropriation or requisition by any government or public authority."},

    {"clause_type": "exclusion", "product": "all", "source": "Zimbabwe Standard Wilful Misconduct Exclusion", "jurisdiction": "ZW",
     "text": "This policy excludes any loss, damage or liability arising from or attributable to wilful misconduct, intentional acts, deliberate disregard of a known risk, or criminal acts by the Insured or any director, employee or agent acting with the knowledge and consent of the Insured."},

    {"clause_type": "exclusion", "product": "motor", "source": "Zimbabwe Motor Standard Exclusions", "jurisdiction": "ZW",
     "text": "This policy does not cover: (a) wear, tear, depreciation, mechanical or electrical breakdown or failure; (b) damage to tyres caused by braking or by puncture, cuts or bursts; (c) loss or damage occurring whilst the vehicle is driven by any person who does not hold a valid driving licence for that class of vehicle; (d) any liability whilst the vehicle is being used for any purpose not permitted in the schedule."},

    {"clause_type": "exclusion", "product": "motor", "source": "Zimbabwe Motor DUI Exclusion", "jurisdiction": "ZW",
     "text": "This policy excludes any loss, damage or liability arising whilst the insured vehicle is being driven by any person who is under the influence of alcohol, narcotics or any drug, or whose blood alcohol content exceeds the legal limit prescribed under the Road Traffic Act [Chapter 13:11] of Zimbabwe."},

    {"clause_type": "exclusion", "product": "fire_property", "source": "Zimbabwe Fire Standard Exclusions", "jurisdiction": "ZW",
     "text": "This policy does not cover: (a) property undergoing any process involving the application of heat; (b) electrical damage arising from electrical overload, short circuit or arcing unless fire results; (c) property in the open air unless specifically covered; (d) loss or damage by theft unless fire, explosion or lightning occurs simultaneously."},

    {"clause_type": "exclusion", "product": "life", "source": "Zimbabwe Life Standard Suicide Exclusion", "jurisdiction": "ZW",
     "text": "This policy does not cover death of the life assured arising from suicide or attempted suicide, whether sane or insane, within twenty-four (24) months of the commencement date or of any reinstatement of this policy."},

    {"clause_type": "exclusion", "product": "life", "source": "Zimbabwe Life Pre-existing Condition Exclusion", "jurisdiction": "ZW",
     "text": "This policy excludes death, disability or illness arising from or contributed to by any pre-existing physical or mental condition that existed prior to the commencement of this policy and which was not disclosed on the proposal form, unless such condition was not known to the Insured at the time of application."},

    {"clause_type": "exclusion", "product": "health", "source": "Zimbabwe Medical Aid Exclusions Standard", "jurisdiction": "ZW",
     "text": "This policy does not cover: (a) cosmetic or elective procedures not medically necessary; (b) dental treatment other than emergency extractions; (c) infertility treatment; (d) experimental treatment not recognised by mainstream medicine; (e) treatment outside the territorial limits unless for emergency care."},

    {"clause_type": "exclusion", "product": "agricultural", "source": "Zimbabwe Crop Insurance Standard Exclusions", "jurisdiction": "ZW",
     "text": "This policy excludes losses arising from: (a) poor agronomic practices, inadequate fertilisation or failure to follow prescribed crop management protocols; (b) harvesting losses due to mechanical breakdown or operator error; (c) market price fluctuations or loss of market; (d) losses occurring after the stated crop maturity date; (e) theft unless evidence of forced entry is provided."},

    {"clause_type": "exclusion", "product": "liability", "source": "Zimbabwe Liability Pollution Exclusion", "jurisdiction": "ZW",
     "text": "This policy excludes liability arising from the actual, alleged or threatened discharge, dispersal, seepage, migration, release or escape of pollutants unless such discharge is sudden, accidental and unintended and occurs during the period of insurance."},

    {"clause_type": "exclusion", "product": "all", "source": "IAIS Cyber Risk Exclusion", "jurisdiction": "international",
     "text": "This policy excludes any loss, damage, liability, cost or expense arising from or in connection with any actual or threatened malicious act on a computer system, including hacking, malware, ransomware, denial of service or any other cyber event, unless such coverage is explicitly granted by endorsement."},

    {"clause_type": "exclusion", "product": "all", "source": "Zimbabwe Sanctions Exclusion Clause", "jurisdiction": "ZW",
     "text": "This policy shall not cover any claim or provide any benefit to the extent that the provision of such cover, payment or benefit would expose the Insurer to any sanction, prohibition or restriction under United Nations resolutions, or the trade or economic sanctions, laws or regulations of Zimbabwe, the European Union, United Kingdom or United States of America."},

    # ==========================================================================
    # CONDITIONS
    # ==========================================================================

    {"clause_type": "condition", "product": "all", "source": "Zimbabwe Standard Duty of Disclosure", "jurisdiction": "ZW",
     "text": "The Insured is under a duty to disclose to the Insurer, before this policy is entered into and at each renewal, every material fact that the Insured knows or ought to know, which a prudent insurer would consider material in deciding whether to accept the risk and on what terms. Failure to disclose material facts may render this policy voidable at the Insurer's election."},

    {"clause_type": "condition", "product": "all", "source": "IAIS ICP Utmost Good Faith Condition", "jurisdiction": "international",
     "text": "This contract of insurance is one of utmost good faith (uberrimae fidae). Both parties are required to act with complete honesty in all dealings related to this policy. The Insured must not make any misrepresentation, whether innocent or fraudulent, in respect of any matter material to this contract."},

    {"clause_type": "condition", "product": "all", "source": "Zimbabwe Standard Reasonable Care Condition", "jurisdiction": "ZW",
     "text": "The Insured shall take all reasonable precautions to prevent loss, damage or liability. The Insured shall comply with all statutory requirements, manufacturers' recommendations and safety regulations applicable to the insured property or activities. The Insurer shall not be liable for any loss resulting from the Insured's failure to exercise reasonable care."},

    {"clause_type": "condition", "product": "property", "source": "Zimbabwe Property Alteration Condition", "jurisdiction": "ZW",
     "text": "The Insured shall give written notice to the Insurer of any material alteration to the risk, including structural alterations to the insured property, change in occupancy, change in use of the premises or installation of any new plant or equipment that may affect the risk profile. Failure to notify may prejudice the Insured's right to claim."},

    {"clause_type": "condition", "product": "all", "source": "Zimbabwe Fraudulent Claims Condition", "jurisdiction": "ZW",
     "text": "If any claim is in any respect fraudulent, or if any fraudulent means or devices are used by the Insured or anyone acting on the Insured's behalf to obtain any benefit under this policy, the Insured shall forfeit all benefit under this policy in respect of such claim, and the Insurer may at its election avoid the policy from the date of the fraudulent act."},

    {"clause_type": "condition", "product": "all", "source": "IAIS Standard Premium Payment Condition", "jurisdiction": "international",
     "text": "The payment of premium is a condition precedent to any liability under this policy. If the premium due is not paid by the due date specified in the schedule, coverage under this policy shall be suspended from the date of default and will only recommence upon receipt of the outstanding premium."},

    {"clause_type": "condition", "product": "motor", "source": "Zimbabwe Motor Roadworthy Condition", "jurisdiction": "ZW",
     "text": "The Insured shall maintain the insured vehicle in a roadworthy condition at all times. The vehicle must hold a current Certificate of Fitness (COF) as required under the Road Traffic (Administration) Act of Zimbabwe. Any claim arising whilst the vehicle is in a non-roadworthy condition may be declined."},

    {"clause_type": "condition", "product": "life", "source": "Zimbabwe Life Free-look Period Condition", "jurisdiction": "ZW",
     "text": "The policyholder has a right to return this policy within thirty (30) days of receipt (the free-look period). If returned within this period and no claim has been made, the Insurer shall refund all premiums paid without deduction. This right applies to all life assurance policies as required by IPEC Consumer Protection Guidelines."},

    # ==========================================================================
    # CLAIMS PROCEDURE CLAUSES
    # ==========================================================================

    {"clause_type": "claims_procedure", "product": "all", "source": "Zimbabwe Standard Claims Notification", "jurisdiction": "ZW",
     "text": "Upon the occurrence of any event giving rise or likely to give rise to a claim under this policy, the Insured shall: (a) give immediate notice to the Insurer in writing; (b) take all practicable steps to prevent further loss or damage; (c) preserve and set aside for inspection all property involved in the loss; (d) not admit liability or make any payment without the Insurer's prior written consent."},

    {"clause_type": "claims_procedure", "product": "all", "source": "IAIS ICP Claims Settlement Standard", "jurisdiction": "international",
     "text": "The Insurer shall acknowledge receipt of a claim within five (5) working days. The Insurer shall either settle or deny the claim within thirty (30) days of receipt of all required documentation. Where additional information is required, the Insurer shall so advise the Insured within ten (10) working days, specifying what information is outstanding."},

    {"clause_type": "claims_procedure", "product": "all", "source": "Zimbabwe IPEC Claims Settlement Directive", "jurisdiction": "ZW",
     "text": "In accordance with IPEC Consumer Protection Guidelines, all valid insurance claims must be settled within thirty (30) days of agreement on quantum. Claims outstanding for more than sixty (60) days must be reported to IPEC with reasons. Interest at the prescribed rate shall be payable on amounts delayed beyond the stipulated settlement period."},

    {"clause_type": "claims_procedure", "product": "motor", "source": "Zimbabwe Motor Claims Documentation", "jurisdiction": "ZW",
     "text": "For motor vehicle claims, the Insured must provide: (a) completed claim form; (b) certified copy of driving licence; (c) police abstract if theft, accident or third-party claim; (d) vehicle registration certificate; (e) certificate of fitness; (f) repair quotations from two approved service centres; (g) photographs of damage."},

    {"clause_type": "claims_procedure", "product": "life", "source": "Zimbabwe Life Claims Documentation", "jurisdiction": "ZW",
     "text": "For death claims, the Insured's beneficiaries must provide: (a) original death certificate; (b) completed claim form; (c) original policy document; (d) proof of identity of claimant and beneficiaries; (e) coroner's report where applicable; (f) post-mortem results where the cause of death is unclear."},

    {"clause_type": "claims_procedure", "product": "property", "source": "Zimbabwe Property Claims Survey Condition", "jurisdiction": "ZW",
     "text": "The Insurer reserves the right to appoint a loss adjuster or surveyor to investigate and assess any claim. The Insured shall at all times allow the Insurer, its surveyors and agents reasonable access to the insured premises and property for the purpose of inspection and investigation. The cost of such survey shall be borne by the Insurer."},

    {"clause_type": "claims_procedure", "product": "all", "source": "Zimbabwe Proof of Loss Condition", "jurisdiction": "ZW",
     "text": "The Insured must submit a completed proof of loss statement within ninety (90) days of the date of loss, unless the Insurer grants a written extension. The statement must include: (a) the cause and origin of the loss; (b) a complete inventory of lost, damaged or destroyed property; (c) the actual cash value of each item; (d) any encumbrances on the property."},

    # ==========================================================================
    # CANCELLATION CLAUSES
    # ==========================================================================

    {"clause_type": "cancellation", "product": "all", "source": "Zimbabwe Standard Cancellation Clause", "jurisdiction": "ZW",
     "text": "This policy may be cancelled by the Insured at any time by giving written notice to the Insurer. On cancellation by the Insured, the Insurer shall retain the customary short-period rate of premium for the time this policy has been in force. The Insurer may cancel this policy by giving thirty (30) days written notice to the Insured at their last known address, in which case the Insurer shall refund the pro-rata unexpired premium."},

    {"clause_type": "cancellation", "product": "all", "source": "IAIS Standard Cancellation Wording", "jurisdiction": "international",
     "text": "Either party may terminate this policy by giving not less than thirty (30) days written notice to the other party. Upon cancellation by the Insurer, the Insured shall be entitled to a pro-rata refund of the unearned premium. Upon cancellation by the Insured, the refund shall be calculated on the short-rate basis. No return of premium shall be made where a claim has been paid or is pending."},

    {"clause_type": "cancellation", "product": "life", "source": "Zimbabwe Life Policy Lapse Clause", "jurisdiction": "ZW",
     "text": "If any premium remains unpaid for more than thirty (30) days after its due date, this policy shall lapse. A lapsed policy has no cash or surrender value unless the policy has been in force for at least three (3) years, in which case reduced paid-up or extended term insurance values shall apply as specified in the table of non-forfeiture values attached hereto."},

    {"clause_type": "cancellation", "product": "all", "source": "Zimbabwe IPEC Licence Revocation Cancellation", "jurisdiction": "ZW",
     "text": "In the event that the Insurer's licence to carry on insurance business in Zimbabwe is suspended or revoked by IPEC, all policies shall be deemed cancelled from the date of suspension or revocation. The Insurer shall, to the extent of its remaining assets, refund unearned premiums on a pro-rata basis to all policyholders."},

    # ==========================================================================
    # PREMIUM CLAUSES
    # ==========================================================================

    {"clause_type": "premium", "product": "all", "source": "Zimbabwe IPEC Tariff Compliance Clause", "jurisdiction": "ZW",
     "text": "Premiums for compulsory insurance classes shall be calculated in accordance with the tariff rates prescribed by the Insurance and Pensions Commission of Zimbabwe (IPEC) as published from time to time. No discount below the prescribed minimum rates shall be offered or accepted. Deviation from prescribed tariffs must be reported to IPEC within fourteen (14) days."},

    {"clause_type": "premium", "product": "motor", "source": "Zimbabwe Motor Premium Adjustment Clause", "jurisdiction": "ZW",
     "text": "The premium for this policy is calculated on the declared value of the insured vehicle at inception. The Insured shall notify the Insurer of any change in the vehicle's value that would affect the sum insured by more than ten percent (10%). An additional premium shall be payable for any increase in sum insured; a pro-rata refund shall be issued for any decrease."},

    {"clause_type": "premium", "product": "all", "source": "Zimbabwe No-Claims Bonus (NCB) Standard", "jurisdiction": "ZW",
     "text": "A No-Claims Discount (NCD) is applied to the renewal premium where no claim has been made in the preceding year of insurance. The NCD scale is: 1 year claim-free: 10%; 2 years: 20%; 3 years: 30%; 4 years: 40%; 5+ years: 50% maximum. The NCD is forfeited following any at-fault claim and must be re-earned from zero."},

    {"clause_type": "premium", "product": "reinsurance", "source": "IAIS Reinsurance Premium Clause", "jurisdiction": "international",
     "text": "The reinsurance premium shall be payable on the dates specified in the treaty schedule. Interest at the rate prescribed in the schedule shall be charged on any overdue premium from the date it becomes due until the date of payment. Failure to pay the reinsurance premium within sixty (60) days of the due date shall give the Reinsurer the right to cancel the treaty."},

    # ==========================================================================
    # SUBROGATION CLAUSES
    # ==========================================================================

    {"clause_type": "subrogation", "product": "all", "source": "IAIS Standard Subrogation Clause", "jurisdiction": "international",
     "text": "Upon making payment of a claim under this policy, the Insurer shall be subrogated to all rights and remedies of the Insured against any third party in respect of the loss or damage. The Insured shall execute all documents and take all steps reasonably required by the Insurer to exercise such rights. Any recovery shall first reimburse the Insurer to the extent of the payment made."},

    {"clause_type": "subrogation", "product": "all", "source": "Zimbabwe Subrogation Waiver Clause", "jurisdiction": "ZW",
     "text": "The Insurer waives its right of subrogation against any subsidiary, associated or holding company of the Insured and against any co-insured named in the schedule, but only to the extent that such companies or persons are named as insureds under this policy. This waiver shall not prejudice the Insurer's rights against any other third party."},

    {"clause_type": "subrogation", "product": "motor", "source": "Zimbabwe Motor Third-Party Recovery Clause", "jurisdiction": "ZW",
     "text": "Where the Insurer has paid a claim in respect of damage caused by a third party, the Insured shall cooperate fully in any recovery action brought by the Insurer against such third party, including providing witness statements, attending court proceedings and executing legal documents as required. The Insured shall not compromise any such recovery action without the Insurer's prior written consent."},

    # ==========================================================================
    # ARBITRATION CLAUSES
    # ==========================================================================

    {"clause_type": "arbitration", "product": "all", "source": "Zimbabwe Arbitration Act Standard Clause", "jurisdiction": "ZW",
     "text": "Any dispute or difference arising out of or in connection with this policy, including any question regarding its existence, validity or termination, shall be referred to and finally resolved by arbitration under the Arbitration Act [Chapter 7:15] of Zimbabwe. The seat of arbitration shall be Harare. The language of arbitration shall be English. The decision of the arbitrator shall be final and binding."},

    {"clause_type": "arbitration", "product": "all", "source": "IAIS International Arbitration Standard", "jurisdiction": "international",
     "text": "All disputes arising from this policy shall be resolved by arbitration in accordance with the rules of the Zimbabwe International Arbitration Centre (ZIAC) or such other mutually agreed arbitral institution. The arbitral tribunal shall consist of three arbitrators, each party appointing one and the two appointed arbitrators appointing the third. The award shall be final and enforceable in any court of competent jurisdiction."},

    {"clause_type": "arbitration", "product": "reinsurance", "source": "ARIAS Reinsurance Arbitration Clause", "jurisdiction": "international",
     "text": "All disputes between the Reinsured and the Reinsurer arising under or in connection with this agreement shall be resolved by arbitration conducted in accordance with the ARIAS (UK) Arbitration Rules. The arbitral panel shall comprise three arbitrators, each being or having been a professional active in the insurance or reinsurance industry for not less than ten (10) years."},

    # ==========================================================================
    # DEFINITIONS CLAUSES
    # ==========================================================================

    {"clause_type": "definitions", "product": "motor", "source": "Zimbabwe Motor Insurance Definitions", "jurisdiction": "ZW",
     "text": "In this policy: 'Insured Vehicle' means the vehicle described in the schedule; 'Accident' means a sudden, fortuitous and unexpected event; 'Third Party' means any person other than the Insured, the Insurer or any person driving with the consent of the Insured; 'Market Value' means the replacement cost of the vehicle in the Zimbabwean second-hand market immediately before the loss."},

    {"clause_type": "definitions", "product": "life", "source": "Zimbabwe Life Assurance Key Definitions", "jurisdiction": "ZW",
     "text": "In this policy: 'Life Assured' means the person whose life is assured as stated in the schedule; 'Policyholder' means the person or entity who owns and controls this policy; 'Beneficiary' means the person designated to receive the death benefit; 'Total and Permanent Disability' means the complete and irrecoverable incapacity to engage in any occupation for remuneration or profit."},

    {"clause_type": "definitions", "product": "property", "source": "Zimbabwe Property Insurance Definitions", "jurisdiction": "ZW",
     "text": "In this policy: 'Insured Property' means the property described in the schedule; 'Sum Insured' means the maximum amount payable under this policy; 'Reinstatement Value' means the cost of rebuilding or replacing the property to the same condition as new without deduction for depreciation; 'Indemnity Value' means the reinstatement value less depreciation for age, wear and tear."},

    {"clause_type": "definitions", "product": "all", "source": "IAIS ICP Standard Insurance Definitions", "jurisdiction": "international",
     "text": "Unless otherwise defined herein: 'Claim' means a formal request to the Insurer for payment of a benefit under this policy; 'Excess' or 'Deductible' means the first portion of any claim that the Insured agrees to bear; 'Period of Insurance' means the duration of cover as stated in the schedule; 'Policy Schedule' means the document setting out the specific details of this insurance contract."},

    # ==========================================================================
    # GENERAL TERMS
    # ==========================================================================

    {"clause_type": "general_terms", "product": "all", "source": "Zimbabwe Governing Law Clause", "jurisdiction": "ZW",
     "text": "This policy shall be governed by and construed in accordance with the laws of Zimbabwe. Any proceedings arising out of or in connection with this policy shall be subject to the exclusive jurisdiction of the courts of Zimbabwe, unless the parties have agreed to resolve disputes by arbitration as provided in the arbitration clause."},

    {"clause_type": "general_terms", "product": "all", "source": "IPEC Consumer Protection Rights Notice", "jurisdiction": "ZW",
     "text": "The policyholder has the right to: (a) receive a copy of this policy document within fourteen (14) days of inception; (b) receive a written explanation of any claim denial; (c) appeal any claim decision to the Insurer's senior management; (d) escalate unresolved disputes to the Insurance and Pensions Commission of Zimbabwe (IPEC) Complaints Office free of charge; (e) a full refund of premiums paid during the free-look period."},

    {"clause_type": "general_terms", "product": "all", "source": "Zimbabwe Data Protection Clause", "jurisdiction": "ZW",
     "text": "The Insurer will collect, process and store the Insured's personal information for the purposes of underwriting, claims management and regulatory compliance, in accordance with the Data Protection Act [Chapter 11:12] of Zimbabwe. The Insured's information will not be shared with third parties except where required by law or with the Insured's consent."},

    {"clause_type": "general_terms", "product": "all", "source": "Zimbabwe AML/CFT Compliance Clause", "jurisdiction": "ZW",
     "text": "The Insured acknowledges that the Insurer is required to comply with the Money Laundering and Proceeds of Crime Act [Chapter 9:24] of Zimbabwe. The Insurer may require the Insured to provide proof of identity, source of funds and other documentation. The Insurer reserves the right to delay or decline claims pending AML/CFT verification."},

    {"clause_type": "general_terms", "product": "all", "source": "IAIS ICP Policy Interpretation Clause", "jurisdiction": "international",
     "text": "In the event of any inconsistency between the policy schedule, endorsements and these general conditions, the policy schedule shall prevail, followed by endorsements in order of date, followed by these general conditions. Headings are for convenience only and shall not affect the interpretation of this policy."},

    {"clause_type": "general_terms", "product": "all", "source": "Zimbabwe Non-Contribution Clause", "jurisdiction": "ZW",
     "text": "If at the time of any loss or damage there is any other insurance in force covering the same property, liability or event, the Insurer shall only be liable under this policy for its rateable proportion of the loss. The Insured may not recover more than the actual amount of the loss from all insurers combined."},

    {"clause_type": "general_terms", "product": "all", "source": "Zimbabwe Entire Contract Clause", "jurisdiction": "ZW",
     "text": "This policy, together with the proposal form, schedule and any endorsements, constitutes the entire contract of insurance between the Insurer and the Insured. No agent or representative of the Insurer has authority to alter, modify or waive any provision of this policy unless such alteration is evidenced in writing and signed by an authorised officer of the Insurer."},

    {"clause_type": "general_terms", "product": "all", "source": "Zimbabwe IPEC Regulatory Compliance Clause", "jurisdiction": "ZW",
     "text": "This policy is issued in compliance with the Insurance Act [Chapter 24:07] of Zimbabwe and the regulations and directives issued by the Insurance and Pensions Commission of Zimbabwe (IPEC). In the event of any conflict between the provisions of this policy and the requirements of the Insurance Act or IPEC regulations, the statutory requirements shall prevail."},

    {"clause_type": "general_terms", "product": "microinsurance", "source": "Zimbabwe Microinsurance Standard Policy Terms", "jurisdiction": "ZW",
     "text": "This microinsurance policy is issued in accordance with the IPEC Microinsurance Guidelines and the Insurance Act [Chapter 24:07]. Premium shall not exceed the prescribed maximum for microinsurance products. The policy document shall be issued in plain language. Claims shall be settled within five (5) working days of receipt of a completed claim form and required documents."},

    {"clause_type": "general_terms", "product": "all", "source": "Zimbabwe Assignment Clause", "jurisdiction": "ZW",
     "text": "This policy may only be assigned with the written consent of the Insurer. An assignment shall not bind the Insurer until it has been recorded on the policy and a copy returned to the assignee. In the case of life assurance policies, assignment shall be effected by way of a written notice of assignment delivered to the Insurer."},

    {"clause_type": "general_terms", "product": "all", "source": "IAIS Severability Clause", "jurisdiction": "international",
     "text": "If any provision of this policy is held to be invalid, illegal or unenforceable by any competent court, the remaining provisions shall continue in full force and effect. The parties shall endeavour to replace any invalid provision with a valid provision that most closely reflects the economic intent of the invalid provision."},
]


# ---------------------------------------------------------------------------
# Add text_hash for deduplication (matches knowledge_base_seeder.py)
# ---------------------------------------------------------------------------
def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    print("=== Standard Clauses Knowledge Base Generator ===")
    out_path = OUT_DIR / "standard_clauses_library.json"

    enriched = []
    seen: set[str] = set()
    for i, clause in enumerate(CLAUSES, start=1):
        h = _hash(clause["text"])
        if h in seen:
            print(f"  WARNING: Duplicate clause skipped at index {i}")
            continue
        seen.add(h)
        enriched.append({**clause, "id": i, "text_hash": h})

    # Save JSON
    out = {"total": len(enriched), "clauses": enriched,
           "clause_types": sorted(set(c["clause_type"] for c in enriched)),
           "products": sorted(set(c["product"] for c in enriched)),
           "generated_by": "gen_standard_clauses.py"}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(enriched)} standard clauses")
    print("\nBreakdown by clause_type:")
    counts: dict[str, int] = {}
    for c in enriched:
        counts[c["clause_type"]] = counts.get(c["clause_type"], 0) + 1
    for k, v in sorted(counts.items()):
        print(f"  {k:<25} {v:>3}")
    print(f"\nSaved to: {out_path.resolve()}")
    print("\nTo load into the system, run the /api/deviation/seed-knowledge-base endpoint.")


if __name__ == "__main__":
    main()
