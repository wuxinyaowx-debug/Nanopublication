# Assertion and evidence rules

## 1. Atomicity is semantic, not punctuation-based

An assertion has one principal relation and one condition set. Split these patterns:

- **Different outcomes:** “A improved survival and reduced toxicity” becomes one survival comparison and one toxicity comparison.
- **Different populations or time points:** separate claims unless a single explicitly joint contrast is the object of study.
- **Separate mechanisms:** a chain “A activates B, which inhibits C” normally becomes `A activates B` and `B inhibits C`, with the chain context retained in conditions where needed.
- **Observation versus explanation:** keep a measured association separate from a proposed causal interpretation.
- **Distinct statistical statements:** an effect estimate and an independent secondary outcome are separate; the estimate and its own confidence interval/unit are not split apart.

Do not mechanically split every conjunction. “At 12 weeks, dose D reduced outcome O versus placebo in population P” contains necessary qualifiers of one comparison. Likewise, a list can be one set-valued characterization when the set itself is the object.

## 2. Preserve qualifiers and direction

Transfer only qualifiers supported by evidence. Check intervention versus comparator, treatment versus control, exposure versus outcome, numerator versus denominator, pre versus post, and relative versus absolute change. Preserve negation and modality (`may`, `suggests`, `did not detect`) in the assertion or its structured relation.

An effect written “20% lower” must not become “20% of” or “80% lower.” Keep percentage versus percentage-point differences distinct. Never convert statistical non-significance into no biological effect, or statistical significance into clinical importance. Preserve the time horizon and experimental system.

## 3. Distinguish five evidence situations

1. **Directly reported:** the quoted passage states the complete proposition. Use `epistemic_status=reported`, `support_type=direct`.
2. **Derived:** all inputs are quoted and a deterministic calculation is documented. Use `derived`; do not attribute the computed number to the paper as a reported result.
3. **Inferred:** your interpretation goes beyond a direct statement. Label it `inferred`; give the premises and reasoning. Do not use it as a factual answer when the task requires direct source support.
4. **Unsupported:** requested proposition has no sufficient material support. Return the gap rather than filling it.
5. **Contradicted/conflicting:** source evidence conflicts with the candidate statement or with another passage. Preserve the conflict and exact locations.

## 4. Minimal sufficient evidence test

For each assertion, underline mentally the words that establish each semantic slot: subject, relation/direction, object, effect magnitude/unit, and decisive conditions. Every slot must occur in the joined evidence set. Remove unrelated sentences if all slots remain supported. Keep multiple noncontiguous snippets as separate items.

Examples of insufficiency:

- Quote states “response increased” but omits which treatment and comparator.
- Quote gives a group mean but the assertion concerns between-group difference.
- Quote reports a p-value while the assertion gives an effect size not quoted or derived.
- Abstract quote omits a restriction stated in Results.
- Citation sentence describes prior work but is treated as the current study's experiment.

An evidence quote can be long when a methods qualifier is indispensable; minimal does not mean the shortest possible phrase. A direct quotation need not contain the assertion's exact surface wording, but the semantic mapping must be explicit and faithful.

## 5. Source hierarchy and conflicts

Prefer the primary results sentence/table for a measured result; use Methods to qualify it and Discussion/Abstract to capture interpretation only when appropriate. A later correction or explicitly supplied version takes precedence only when the material identifies that relationship. Record version identifiers rather than guessing which document is newest.

For internal disagreement (for example abstract versus table), do not average or silently choose. Represent both, identify the discrepancy, and, if a direct task answer must be selected, justify it from the task's criteria with `partial` status if unresolved.

## 6. Figures, tables, and equations

Text extracted from multi-column PDFs can interleave unrelated rows. Inspect the rendered region for decisive values, symbols, group order, axis scales, and figure panels. Evidence for a visual trend must identify the page, figure/panel, compared series, and approximate region. If image inspection is unavailable, mark the claim not determinable rather than converting a caption into proof of every visual detail.

For a table-derived assertion, quote table title/caption, relevant header, and row in separate evidence items when needed. Retain units and footnotes. A text-layer quote with malformed symbols requires visual confirmation before assigning exact values.

A formula is direct evidence for a symbolic relation only when the quoted/read equation and its surrounding definitions support the mapped variables. Do not infer variable meaning solely from notation.

## 7. Metadata and external retrieval

The supplied paper and case files are factual authority for the task. Use external retrieval only if permitted and needed to resolve identifiers or source versions; never use it to overwrite supplied scientific content. Record an actually retrieved URL and keep externally obtained metadata distinguishable. No retrieval result proves that an absent DOI, author, or year does not exist.

## 8. Deduping and stable identifiers

Semantically duplicate assertions with the same relation and condition set should be merged and their evidence combined. Do not merge different populations, comparators, follow-up times, doses, model systems, or statistical estimands. Do not merge a source-reported result with an agent-derived result merely because their numbers match. Deterministic IDs support repeatability but do not prove semantic uniqueness.

## 9. Final manual checklist

Before finalizing, read each assertion followed only by its bound evidence, without referring to your memory of the paper. Ask whether a skeptical reviewer could recover every part of the assertion from those spans. Then read each requested answer field and confirm that it responds to the actual question rather than merely surrounding it with citations. Record limitations specific to the encountered material, not generic disclaimers.
