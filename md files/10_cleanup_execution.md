# Cleanup Execution – Project Specific

## REMOVE COMPLETELY
- app/scrapers/zse_scraper.py (if unused)
- app/ui_backup_*/
- .pytest_cache/
- all __pycache__ folders

## REVIEW BEFORE REMOVAL
- app/scrapers/ipec_scraper.py (keep if used)
- storage/models/ (remove if empty)

## CLEAN
- Remove unused imports across all modules
- Remove commented-out code blocks
- Ensure no orphan services exist

## VALIDATION
- All tests in /tests must still pass
- All API routes must respond