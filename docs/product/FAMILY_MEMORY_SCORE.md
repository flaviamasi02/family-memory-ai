# Family Memory Score

Family Memory AI does not aim to select the technically best photos in isolation.
Its primary objective is to select the most meaningful memories.

The Family Memory Score is the official, explainable, multi-factor ranking design for annual album curation.
Every score decision must remain transparent and explainable to the user.

---

# Product Mission

Every feature should answer one question:

"Does this help the application better understand what matters to this family?"

If the answer is no, the feature should probably not be prioritized.

Family Memory AI is not primarily an album creator.

It is a Family Memory Intelligence system whose features should improve memory understanding, cleanup quality, preference modeling, and meaningful outputs over time.

The application does not optimize for beautiful photographs.

It optimizes for meaningful memories.

Current strategic priority order:

1. Reliable AI-assisted media classification
2. Learning from user corrections
3. Cleanup quality and safety
4. People Intelligence
5. Output generation (albums as one downstream consumer)

---

# Explainable Intelligence

Family Memory AI may use:

- deterministic rules
- statistical models
- machine learning
- local AI models
- cloud AI services

However every important decision must expose:

- why the decision was made
- evidence used
- confidence
- decision source

Decision source examples:

- Deterministic Rules
- Learned User Preferences
- AI Inference
- Hybrid Decision

Explainability requirement for classification:

- Visual-content-based decisions must expose human-readable evidence (for example white page-like background, text-like regions, tall screenshot layout, banner layout, or graphic-like low-resolution square structure).
- Face-based decisions must expose detector source, face count, and confidence as explicit evidence.
- Metadata-less images should use local visual evidence before falling back to Unknown.
- Unknown remains valid when evidence is weak or conflicting.

People-001 classification rule:

- Local face detection is allowed as Family Photo evidence.
- Strong face evidence may elevate Unknown to Family Photo.
- User-corrected category remains authoritative and must not be overridden automatically.
- No person identity recognition and no cloud AI are allowed in People-001.

People roadmap direction:

- PEOPLE-002 and later milestones may introduce relationship-level intelligence, but only with explicit explainability and user-control safeguards.
- Identity-level recognition is out of scope for PEOPLE-001 and remains gated by future product decisions.

---

## Scoring Philosophy

- Memories are more important than perfect photography.
- Rare moments are more important than technically perfect duplicates.
- Albums must tell a story.
- AI assists the user but never replaces them.
- Every score should be explainable.

---

## Scoring Components

### 1. Technical Quality Score

Purpose:
Measure the technical quality of a photo as a quality baseline.

Possible criteria:

- focus
- sharpness
- exposure
- colors
- noise
- composition
- resolution
- printable size

Important rule:
If duplicate photos exist, the technically best one should be preferred.

### 2. Expression Score

Purpose:
Evaluate the human expressiveness and natural emotional quality of the moment.

Examples:

- smiles
- open eyes
- natural expressions
- spontaneous emotions

Important rule:
Different expressions mean the photos are not duplicates.

### 3. Memory Value Score

Purpose:
Capture the emotional and personal importance of a memory.

This is expected to become one of the most important score components.

Examples:

- one of the few photos of a person
- one of the last photos together
- emotionally important memories

Important rule:
Memory value may outweigh technical quality.

### 4. People Importance Score

Purpose:
Prioritize photos containing people considered important in the user profile.

Example important-people list:

- Luis
- Miguel
- Patrizia
- Cleto
- Fiorenza
- Daniele
- Chon
- Joaquin
- Dani

### 5. Event Score

Purpose:
Recognize important life events and boost representative photos.

Examples:

- Birthday
- Christmas
- Vacation
- Wedding
- School
- Trips
- Celebrations

### 6. Rarity Score

Purpose:
Reward unique moments that are underrepresented in the library.

The fewer similar photos exist, the higher the rarity score.

Examples:

- only family selfie
- only photo of grandparents
- only childhood picture

### 7. Duplicate Score

Purpose:
Reduce near-identical repetition while preserving meaningful variation.

Official duplicate rules:

Duplicates:

- same moment
- same expression
- same interaction

Not duplicates:

- different expression
- different emotion
- different interaction

### 8. User Preference Score

Purpose:
Personalize ranking based on evolving user choices over time.

The AI should learn user preferences continuously, while keeping ranking explainable.

Examples:

Flavia prefers:

- family
- Luis
- landscapes
- spontaneous photos

Important note:
Different users may have completely different preferences.

### 9. Storytelling Score

Purpose:
Promote photos that help tell the story of a person's life across the year.

### 10. Album Balance Score

Purpose:
Keep the final album representative and well-distributed.

Albums should avoid imbalance.

Examples of imbalance:

- too many photos from one day
- missing months
- missing people
- missing events
- missing locations

Important rule:
The final album should represent the entire year.

---

## Future Architecture

The intended architecture is modular and explainable.
Each component should be implemented as an independent scorer.

Planned scorer modules:

- TechnicalQualityScorer
- ExpressionScorer
- MemoryValueScorer
- PeopleImportanceScorer
- EventScorer
- RarityScorer
- DuplicateScorer
- UserPreferenceScorer
- StorytellingScorer
- AlbumBalanceScorer

A final FamilyMemoryScoreEngine combines these scorers into the final ranking.

New scoring features should be developed inside their respective domains.

Examples:

- LEARN
- MEMORY
- PEOPLE
- EVENT

MASTER_DEVELOPMENT_PLAN.md defines the high-level product-planning rule set that determines whether new scoring capabilities should be prioritized.

---

# Memory Review

Memory Review is the main interaction point between the user and the application.

It is where users teach the application what matters.

Current Memory Review behavior is deterministic, explainable, and correction-oriented:

- multi-selection and bulk editing
- Media Category review with Automatic Category, User Corrected Category, and Effective Category
- confidence and reasoning visibility as first-class decision context

MEM-008 taxonomy update:

- Users can define custom media categories directly in-app and apply them in Memory Review and Cleanup Review.
- Custom categories are metadata-only organizational controls (no AI learning/scoring changes in this milestone).
- Category definitions persist in `.familymemory/categories.json`; per-photo category overrides continue to persist via sidecar metadata.

LEARN-001 deterministic category-learning update:

- Repeated manual category corrections now produce deterministic, explainable learning rules.
- Learned rules are local-only and transparent (no cloud AI, no black-box ML).
- Learned rules can boost future import-time category decisions when matching signals are observed.
- Learning profile persists locally in `.familymemory/category_learning_profile.json`.

LEARN-001 persistence foundation:

- Manual category corrections and user decisions are now stored in sidecar JSON files beside each image.
- Sidecar loading on import restores user-corrected category and user decision when file identity matches.
- If file identity changes, loading remains cautious and marks an identity-mismatch warning while preserving user correction/decision when filename still matches.
- Original image binary metadata is not modified yet; sidecar storage is the current safe persistence path.

Cleanup Review now follows the same UX philosophy as Memory Review:

- top filters and grouping controls
- compact thumbnail-first grid
- right-side details panel with explainability and actions

Grouping rule:

- Grouping is a visualization mechanism for review speed only.
- Grouping must not be treated as media classification.

## Terminology Alignment

Use the following terms consistently in review and learning documentation:

- Media Category
- Automatic Category
- User Corrected Category
- Effective Category
- Decision Engine
- Cleanup Engine

---

# User Decision Engine

Memory Review is no longer only an approval screen.

It becomes the central decision interface where every user action teaches Family Memory AI what matters.

Every decision can contribute to:

- album selection
- cleanup classification
- preference learning

Long-term workflow:

Import

↓

Metadata Extraction

↓

Media Classification

↓

Memory Review

↓

Cleanup Review

↓

Decision Engine

↓

Preference Learning

↓

Duplicate Management

↓

Memory Intelligence

↓

Album Builder

Every user decision contributes to future scoring, recommendations, cleanup suggestions, and ranking explainability.

## User Decisions

Future user-decision model:

Future PhotoDecision states:

### Pending

Purpose:
Default undecided state before the user provides a meaningful signal.

### ApprovedForAlbum

Purpose:
Strong positive signal that the photo should remain a high-priority album candidate.

### Keep

Purpose:
Signal that the photo should remain in the library even if it is not selected for the current album.

### IrrelevantMedia

Purpose:
Signal that the file is not a meaningful family memory candidate and should be treated as cleanup-oriented media.

### Duplicate

Purpose:
Signal that the file is a duplicate or redundant variant that should reduce future duplicate confidence for similar items.

### Document

Purpose:
Signal that the file is document-oriented media and should influence cleanup and relevance recommendations.

### Screenshot

Purpose:
Signal that the file is screenshot media and should influence cleanup and relevance recommendations.

### Advertisement

Purpose:
Signal that the file is advertisement or promotional content and should influence cleanup and relevance recommendations.

### MemeGraphic

Purpose:
Signal that the file is meme/graphic-style media and should influence cleanup and relevance recommendations.

### Rejected

Purpose:
Strong negative album-selection signal for the current curation context.

### Unknown

Purpose:
Fallback state for cases where the system cannot yet map the user action into a stable long-term decision category.

Every decision contributes to learning.

## Preference Learning

Every user decision becomes an example for future learning-oriented architecture.

Examples:

- approving many Luis photos
- approving outdoor photos
- rejecting blurry photos
- marking documents as irrelevant
- marking screenshots as irrelevant

Over time these decisions should influence:

- User Preference Score
- Memory Value
- album recommendations
- cleanup suggestions

Preference Learning must remain explainable. Future scoring should be able to trace how repeated user decisions changed scoring behavior.

## Continuous Learning

Every user interaction teaches the application.

Examples:

- approve photo
- keep photo
- remove irrelevant media
- mark irrelevant
- mark duplicate
- mark advertisement
- mark document
- mark screenshot
- choose between duplicates
- replace album photo

These actions become long-term learning signals.

Over time these decisions should improve:

- User Preference Score
- Memory Value Score
- cleanup recommendations
- future album suggestions
- duplicate handling

The application should eventually learn:

- important people
- favorite events
- favorite locations
- favorite compositions
- favorite expressions
- favorite memories
- cleanup preferences
- duplicate tolerance
- storytelling preferences
- album size preferences

---

## Implementation Status

| Component | Status |
| --- | --- |
| Technical Quality | Partial |
| Expression | Planned |
| Memory Value | Planned |
| People Importance | Planned |
| Event | Planned |
| Rarity | Planned |
| Duplicate | Planned |
| User Preference | Planned |
| Storytelling | Planned |
| Album Balance | Planned |

---

## Scope Note

This document is a product-design specification.
It defines ranking behavior and long-term scoring direction.

It is not implementation documentation.

# Product Decisions Log

This section records permanent product decisions that affect future implementations.

## Decision FM-001

Title:
Family Memory AI ranks memories, not photographs.

Decision:
The primary objective is preserving meaningful memories rather than selecting technically perfect images.

## Decision FM-002

Title:
Different facial expressions mean photos are not duplicates.

Decision:
Different facial expressions mean photos are not duplicates.

## Decision FM-003

Title:
Memory Value may outweigh Technical Quality.

Decision:
A technically poor photo can still become one of the highest ranked memories if it is unique or emotionally important.

## Decision FM-004

Title:
Technical quality preference applies only within true duplicates.

Decision:
The highest technical-quality version should be preferred only among true duplicates.

## Decision FM-005

Title:
Albums should represent the whole year.

Decision:
Avoid excessive concentration of:

- one day
- one event
- one location
- one person

## Decision FM-006

Title:
Every Family Memory Score must be explainable.

Decision:
The user must always be able to understand why a photo received its score.

## Decision FM-007

Title:
The scoring architecture must remain modular.

Decision:
Each score component should be implemented independently and combined by the FamilyMemoryScoreEngine.

## Decision FM-008

Title:
Memory Review and Cleanup Review are the central decision interfaces.

Decision:
Memory Review and Cleanup Review are no longer limited to generic approve/reject-style actions.

They are the primary interfaces where the user teaches Family Memory AI what is important.

Future scoring should continuously learn from these decisions.

## Decision FM-009

Title:
Family Memory AI is a Memory Intelligence platform.

Decision:
Every significant user interaction should improve future recommendations.

The application should continuously adapt to each family.

## Decision FM-010

Title:
Memory Review is the primary interaction point.

Decision:
Memory Review is the main interface where the user teaches the application what matters. Review behavior should eventually shape scoring, cleanup, duplicate handling, and meaningful outputs.

## Decision FM-011

Title:
Albums are generated from Memory Intelligence.

Decision:
Albums are not the purpose of the system.

They are generated from Memory Intelligence and are one of several possible outputs.

Future product decisions should be appended to this section rather than modifying previous decisions, unless a decision is explicitly superseded.
