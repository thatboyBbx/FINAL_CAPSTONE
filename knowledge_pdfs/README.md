# InsureIntel Zimbabwe — Knowledge Base Source Documents

Place PDF files here before running the knowledge base seeder.

## Required Documents

| Document | Source | Priority |
|----------|--------|----------|
| Insurance Act Chapter 24:07 | Government of Zimbabwe website / Zimbabwe Laws Online | P0 — Critical |
| IPEC Guidance Notes | ipec.co.zw/download-centre | P0 — Critical |
| IPEC Circulars (2020–present) | ipec.co.zw/download-centre | P1 |
| Standard Motor Policy Wording | Any licensed Zimbabwean insurer | P1 |
| Standard Fire Policy Wording | Any licensed Zimbabwean insurer | P1 |
| Reinsurance Treaty Template | Broker association / ICZ | P2 |

## Running the Seeder

After placing PDFs here, run:

```bash
python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/
```

For a dry run (no writes, just verify):

```bash
python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/ --dry-run
```

## File Naming Convention

Name files descriptively — the filename becomes part of the ChromaDB metadata:

```
insurance_act_chapter_24_07.pdf
ipec_guidance_note_life_2023.pdf
standard_motor_policy_wording.pdf
```

## Notes

This directory is in `.gitignore` — PDF files are NOT committed to the repository.
Only this README is tracked.
