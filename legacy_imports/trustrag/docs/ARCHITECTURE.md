# TrustRAG: Financial Evidence OS Architecture

## Core Principles

### P0: Default Distrust (Financial Extremism)
**All extracted numbers are UNTRUSTED by default.** 
No numeric value is valid until it passes multi-modal cross-validation (Table, Chart, Text), unit normalization, and period alignment.

### P1: Modality Trust Hierarchy (HARD RULE)
- **Table / Chart**: ONLY sources of numeric truth (trust_score: 0.9 - 1.0).
- **Text**: Explanation layer ONLY (trust_score: 0.0 - 0.5).
- **Conflict Rule**: If Text contradicts Table/Chart, Text ALWAYS loses.
- **Invalid Rule**: Text-only numbers that cannot be traced to a Table or Chart are INVALID.

---

## 2. Truth Graph & Canonical Truth

### Canonical Truth Graph (Entity–Metric–Period)
The system maintains a versioned graph of evidence.
- **Entity**: Company, Ticker, or Segment.
- **Metric**: Financial line item (Revenue, EPS, etc.).
- **Period**: Q4 2024, FY2023.
- **Version**: Documents enter a version graph (10-K > 10-Q > Deck).

---

## 3. Chart & Table: First-Class Units

### Chart Semantic Validation
Every chart must pass semantic integrity before emitting facts:
1. **Axis Validator**: Check unit/scale/metric consistency.
2. **Legend Validator**: Ensure every series maps to a unique semantic entity.
3. **Temporal Checker**: Align X-axis with claimed periods.
4. **Contradiction Detector**: Flags discrepancies between chart data and nearby text.

---

## 4. LLM Cognitive Isolation

The LLM is a **Language Renderer**, not a reasoner.
- **Input**: `AnswerPlan` JSON (Target bindings, Citations, Verdict).
- **Forbidden**: Raw document text, tables, or charts.
- **Refusal**: System-level decision based on evidence quality. LLM merely verbalizes the refusal reason.

---

## 5. Implementation Roadmap (Final 40%)

### Phase 1: Modality & Distrust Logic
- [ ] Update `Fact` models with `source_modality` and `trace_links`.
- [ ] Implement hierarchy-aware `EvidenceResolver`.

### Phase 2: Chart Engine
- [ ] Create `ChartIR` models and pluggable `ChartParser` interface.
- [ ] Implement the 4 base semantic validators.

### Phase 3: Canonical Truth Layer
- [ ] Implement `TruthStore` with versioned `EvidenceSet`.
- [ ] Add "Effective Truth" selection logic (Filing priority).

### Phase 4: Extreme Isolation
- [ ] Create `AnswerPlan` schema.
- [ ] Hard-code refusal templates to bypass LLM logic.

### Phase 5: UI & UX (Compliance-Grade)
- [ ] Implement 3-panel layout (Verdict, Answer, Evidence).
- [ ] Embed execution trace and defensibility indicators.
