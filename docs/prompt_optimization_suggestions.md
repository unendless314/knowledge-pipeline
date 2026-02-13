# Prompt Framework & Taxonomy Optimization Report

**Date:** 2026-02-13
**Status:** Draft / Proposal
**Context:** Analysis of the current JSON extraction prompts used in the Knowledge Pipeline.

## 1. Executive Summary

The current prompt framework relies on a rigid schema (7 fields) to extract structured data from video transcripts. While highly effective for **Information Filtering** (High Signal-to-Noise Ratio), the `content_type` classification exhibits strictness limitations that may lead to ambiguity in edge cases.

This document outlines the strengths of the current approach, identifies specific gaps, and proposes three tiers of optimization strategies.

## 2. Current Framework Assessment

### Strengths
- **High Signal-to-Noise Ratio**: The combination of `content_density` (High/Medium/Low) and `temporal_relevance` (Evergreen/Time-sensitive/News) creates a powerful filter for Personal Knowledge Management (PKM). It effectively answers: *"Do I need to watch this now?"* and *"How much mental energy does it require?"*
- **Consistent Schema**: All prompts share identical JSON fields, ensuring robust parsing and type safety in the Python backend.

### Weaknesses
- **Dimensional Confusion**: The `content_type` field mixes **Format** (e.g., `interview`) with **Intent** (e.g., `educational`, `news`).
- **Mutual Exclusivity Conflicts**: A "technical deep-dive interview" confuses the model—it fits both `technical_analysis` and `interview`.

## 3. Gap Analysis: Unsupported Scenarios

The current 5 options (`technical_analysis`, `opinion_discussion`, `news`, `educational`, `interview`) fail to capture specific content styles adequately:

| Scenario | Issue | Current Workaround (Suboptimal) |
| :--- | :--- | :--- |
| **Documentaries / History** | Narrative-driven content (e.g., "The History of the Cold War") is neither news, opinion, nor strictly educational in a "how-to" sense. | Forced into `educational` or `opinion_discussion`. |
| **Storytelling / Case Studies** | Business case studies (e.g., "Why FTX Collapsed") focus on the *story arc* rather than technical data. | Forced into `opinion_discussion`. |
| **Q&A / AMAs / Livestreams** | Loose structure, mixed topics. | Forced into `interview` or `opinion_discussion`. |
| **Entertainment / Satire** | Content consumed for pleasure rather than information. | No clear category (currently out of scope). |

## 4. Optimization Recommendations

### Strategy A: Definition Refinement (Low Effort)
*Best for: Immediate improvements without code changes.*

Update the prompt instructions to prioritize **Intent** over **Format**.
- **Rule**: "Select `interview` ONLY if the dialogue dynamic is the primary focus. If an expert is teaching a concept during an interview, classify as `educational` or `technical_analysis`."
- **Effect**: Reduces ambiguity for high-value content hidden in interview formats.

### Strategy B: Taxonomy Expansion (Recommended)
*Best for: Better coverage of narrative content.*

Add a 6th option to `content_type`:
- **`storytelling`** (or `narrative_history`): For documentaries, historical recaps, true crime, or business case studies.
- **Reasoning**: The human brain processes narratives differently from analytical data. This distinction is valuable for retrieval.

### Strategy C: Dimension Splitting (High Effort)
*Best for: Long-term architectural robustness.*

Split `content_type` into two distinct fields in the database and schema:
1.  **`format`**: `['monologue', 'interview', 'panel', 'documentary', 'livestream']`
2.  **`intent`** (Primary Category): `['education', 'analysis', 'news', 'opinion', 'entertainment']`

**Pros**: Eliminates all ambiguity. A "Technical Interview" becomes `format: interview` + `intent: analysis`.
**Cons**: Requires database migration and frontend logic updates.

## 5. Conclusion

For the current phase of the Knowledge Pipeline, **Strategy A (Refinement)** combined with **Strategy B (Adding `storytelling`)** offers the best balance of effort vs. value. Strategy C should be reserved for a major version refactor (v2.0).
