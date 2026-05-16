# Architecture Refactor – Domain Alignment

## Problem
Current structure mixes AI, business logic, and infrastructure.

## Target Domains

app/
 ├── core/
 ├── api/
 ├── domains/
 │   ├── insurance/
 │   ├── clients/
 │   ├── compliance/
 │   ├── analytics/
 │
 ├── ai/
 │   ├── models/
 │   ├── training/
 │   ├── inference/
 │   ├── rag/
 │   ├── multilingual/
 │
 ├── infrastructure/
 │   ├── scrapers/
 │   ├── storage/
 │   ├── db/
 │
 ├── ui/

## Key Change
- Move ml/, rag/, multilingual → ai/
- Move services into domain-based grouping