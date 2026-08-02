from __future__ import annotations

from ui.help.workspace_help_models import (
    WorkspaceAIStatusMetric,
    WorkspaceHelpDefinition,
    WorkspaceHelpSection,
    WorkspaceHelpTip,
)

PHOTO_BROWSER_WORKSPACE = "photo_browser"
MEMORY_REVIEW_WORKSPACE = "memory_review"
CLEANUP_REVIEW_WORKSPACE = "cleanup_review"
ALBUM_DRAFT_WORKSPACE = "album_draft"
SETTINGS_WORKSPACE = "settings"
PEOPLE_REVIEW_WORKSPACE = "people_review"


def _purpose_section(
    why_this_workspace_exists: str,
    problem_it_solves: str,
    ai_automation: str,
    user_interaction: str,
    expected_outcome: str,
) -> WorkspaceHelpSection:
    return WorkspaceHelpSection(
        key="purpose",
        title="Purpose",
        kind="purpose",
        icon="info",
        payload={
            "why_this_workspace_exists": why_this_workspace_exists,
            "problem_it_solves": problem_it_solves,
            "ai_automation": ai_automation,
            "user_interaction": user_interaction,
            "expected_outcome": expected_outcome,
        },
    )


def _workflow_section(steps: list[str]) -> WorkspaceHelpSection:
    return WorkspaceHelpSection(
        key="workflow",
        title="Workflow",
        kind="workflow",
        icon="flow",
        payload=list(steps),
    )


def _best_practices_section(items: list[str]) -> WorkspaceHelpSection:
    return WorkspaceHelpSection(
        key="best_practices",
        title="Best Practices",
        kind="bullet_list",
        icon="check",
        payload=list(items),
    )


def _tips_section(tips: list[WorkspaceHelpTip]) -> WorkspaceHelpSection:
    return WorkspaceHelpSection(
        key="tips",
        title="Tips",
        kind="tips",
        icon="tip",
        payload=list(tips),
    )


def _ai_status_section(items: list[WorkspaceAIStatusMetric]) -> WorkspaceHelpSection:
    return WorkspaceHelpSection(
        key="ai_status",
        title="AI Status",
        kind="ai_status",
        icon="ai",
        payload=list(items),
    )


def build_workspace_help_definitions() -> list[WorkspaceHelpDefinition]:
    return [
        WorkspaceHelpDefinition(
            workspace_id=PEOPLE_REVIEW_WORKSPACE,
            title="People Review",
            sections=(
                _purpose_section(
                    "People Review privately groups locally detected faces for your review.",
                    "It helps organize recurring people without making public or automatic identity claims.",
                    "Local models detect, describe, and conservatively cluster faces; photos are never uploaded.",
                    "Start a scan explicitly, inspect candidates, and confirm or reject every name.",
                    "Only Product Owner-confirmed names appear elsewhere in the application.",
                ),
                _workflow_section(["Start a local scan", "Review unnamed clusters", "Create or select a person", "Confirm an assignment", "Correct false detections"]),
                _best_practices_section(["Treat faces as sensitive data.", "Use several varied examples before trusting a suggestion.", "Exclude non-photo sources and delete analysis data from Settings when no longer wanted."]),
                _tips_section([WorkspaceHelpTip(title="Privacy tip", body="Face processing stays local and every identity requires your confirmation.")]),
                _ai_status_section([WorkspaceAIStatusMetric("People Recognition", 45, "Owner-confirmed local face review")]),
            ),
        ),
        WorkspaceHelpDefinition(
            workspace_id=PHOTO_BROWSER_WORKSPACE,
            title="Photo Browser",
            sections=(
                _purpose_section(
                    why_this_workspace_exists="Photo Browser gives you the fastest way to inspect everything that was imported before deeper review work begins.",
                    problem_it_solves="Large folders are difficult to assess quickly without visual browsing, relevance filters, and metadata context.",
                    ai_automation="Import applies reliable technical rules for screenshots, documents, graphics, and workflow states. Ordinary photographs remain Unknown until family content is confirmed manually or through an accepted AI Suggestion.",
                    user_interaction="Use relevance filters and open photo details to validate what the system detected before moving into Memory Review or Cleanup Review.",
                    expected_outcome="You get a clear understanding of library quality, relevance distribution, and where to focus manual review effort.",
                ),
                _workflow_section(
                    [
                        "Import Photos",
                        "AI Classification and Metadata Analysis",
                        "Browse with Relevance Filters",
                        "Inspect Individual Details",
                        "Move to Memory Review or Cleanup Review",
                    ]
                ),
                _best_practices_section(
                    [
                        "Use filters first to narrow the scope before opening full details.",
                        "Spot-check unknown or low-confidence items before making workflow decisions.",
                        "Treat this workspace as orientation, not as the primary correction surface.",
                        "Start with one family event range to build a consistent review rhythm.",
                    ]
                ),
                _tips_section(
                    [
                        WorkspaceHelpTip(
                            title="Tip of the Day",
                            body="Use category filters to quickly verify if classification quality is stable before opening Memory Review.",
                        ),
                        WorkspaceHelpTip(
                            title="Efficiency Tip",
                            body="Folder scanning and EXIF extraction run in the background — the application stays responsive while your library loads. Cached thumbnails appear first; newly generated ones follow automatically. The compact workspace introduction panel at the top can be collapsed when you need more vertical space.",
                        ),
                    ]
                ),
                _ai_status_section(
                    [
                        WorkspaceAIStatusMetric("Category Learning", 72, "Improving from your category corrections"),
                        WorkspaceAIStatusMetric("People Recognition", 45, "Early stage face-learning pipeline"),
                        WorkspaceAIStatusMetric("Duplicate Detection", 85, "Exact duplicate stage is stable"),
                    ]
                ),
            ),
        ),
        WorkspaceHelpDefinition(
            workspace_id=MEMORY_REVIEW_WORKSPACE,
            title="Memory Review",
            sections=(
                _purpose_section(
                    why_this_workspace_exists="Memory Review is the core workspace for teaching which moments should contribute to family memories and future album quality.",
                    problem_it_solves="Raw imported photos contain noise, ambiguity, and mixed quality that must be resolved through guided category correction.",
                    ai_automation="The system pre-scores candidates, predicts categories, keeps explainable reasoning visible, and can use locally stored visual/content signals when those profiles are available.",
                    user_interaction="Select one or more photos in the grid. Use Current Status for the confirmed category, source, and decision; AI Suggestion for advisory evidence; Classification Summary for a plain-language explanation; Photo Information for secondary metadata; and Actions to apply a category to the stated selection count.",
                    expected_outcome="A cleaner, higher-confidence reviewed set that teaches future classification and recommendation behavior without mixing in album-decision editing.",
                ),
                _workflow_section(
                    [
                        "Filter and Select Photos in the Grid",
                        "Read Current Status and Classification Summary",
                        "Apply or Reject an AI Suggestion",
                        "Confirm or Correct Category for the Current Selection",
                        "Open Learning Summary to Review Timestamped Learning History",
                        "Improve Future Ranking Quality",
                    ]
                ),
                _best_practices_section(
                    [
                        "Review visually similar photos together to keep decisions consistent.",
                        "Use Ctrl/Shift selection or Select all visible for repeated patterns, then verify the selection count in Actions before applying a category.",
                        "Correct category mistakes immediately when confidence is low.",
                        "Use Learning Summary to distinguish activity counts, visual category learning, and preference signals; filenames and metadata are only secondary evidence.",
                        "Do focused sessions of 15 to 30 minutes to reduce fatigue.",
                        "Aim for consistent category corrections, not album-decision editing, in each session.",
                    ]
                ),
                _tips_section(
                    [
                        WorkspaceHelpTip(
                            title="Tip of the Day",
                            body="Current Status shows what is active now. AI Suggestion is advisory; Classification Summary explains the current category, while Photo Information keeps scores and dates secondary.",
                        ),
                        WorkspaceHelpTip(
                            title="Learning Tip",
                            body="For bulk work, select photos in the grid and check the exact count beside the category action. Apply Category to Selected uses the same persisted learning workflow for one photo or many. Technical import details remain available in the collapsed Technical details section.",
                        ),
                    ]
                ),
                _ai_status_section(
                    [
                        WorkspaceAIStatusMetric("Category Learning", 72, "Consuming correction signals from this workspace"),
                        WorkspaceAIStatusMetric("Preference Learning", 63, "Aggregating repeated category and review signals"),
                        WorkspaceAIStatusMetric("Ranking Calibration", 58, "Adapting score weighting from user behavior"),
                    ]
                ),
            ),
        ),
        WorkspaceHelpDefinition(
            workspace_id=CLEANUP_REVIEW_WORKSPACE,
            title="Cleanup Review",
            sections=(
                _purpose_section(
                    why_this_workspace_exists="Cleanup Review protects memory quality by isolating files that are likely non-memory content before album building.",
                    problem_it_solves="Screenshots, ads, duplicates, documents, and low-value media can pollute review quality if mixed with family memories.",
                    ai_automation="The classifier conservatively proposes To Trash with confidence and an explanation; it never moves a proposal automatically.",
                    user_interaction="Review and explicitly confirm To Trash proposals before moving, reject incorrect proposals, or restore moved photos.",
                    expected_outcome="To review shows only active work. Moved files disappear from normal workflows, are never permanently deleted, and remain available in Trash History for restore.",
                ),
                _workflow_section(
                    [
                        "Inspect Cleanup Candidates",
                        "Check AI Reasons and Confidence",
                        "Confirm Selected To Trash Proposals",
                        "Correct Category Where Needed",
                        "Run Face Analysis for Ambiguous Items",
                        "Move Confirmed Photos to Family Memory Trash",
                        "Restore From Trash When Needed",
                        "Switch to Trash History for Move and Restore Audit",
                    ]
                ),
                _best_practices_section(
                    [
                        "Use category grouping to process one media type at a time.",
                        "Prioritize low-confidence items first; they need your judgment most.",
                        "Only explicitly confirmed files can move to Trash; proposals alone are never moved.",
                        "Check the shown destination before moving. Files are never permanently deleted.",
                        "Use face analysis on uncertain candidates before final decisions.",
                        "Reclassify unknown items after enough corrections are available.",
                    ]
                ),
                _tips_section(
                    [
                        WorkspaceHelpTip(
                            title="Tip of the Day",
                            body="Batching cleanup decisions by category usually produces faster and more consistent outcomes.",
                        ),
                        WorkspaceHelpTip(
                            title="Safety Tip",
                            body="Trash moves are reversible, history is retained, and moved photos are excluded from normal active review. The compact workspace introduction panel can be collapsed for more grid space.",
                        ),
                    ]
                ),
                _ai_status_section(
                    [
                        WorkspaceAIStatusMetric("Noise Filtering", 81, "Strong deterministic rules for non-memory classes"),
                        WorkspaceAIStatusMetric("Uncertainty Handling", 49, "Needs additional user corrections"),
                        WorkspaceAIStatusMetric("Face-Assisted Validation", 40, "Early support for ambiguous family photos"),
                    ]
                ),
            ),
        ),
        WorkspaceHelpDefinition(
            workspace_id=ALBUM_DRAFT_WORKSPACE,
            title="Album Draft",
            sections=(
                _purpose_section(
                    why_this_workspace_exists="Album Draft converts reviewed memory decisions into an organized annual draft structure.",
                    problem_it_solves="Without deterministic assembly, selected memories are hard to transform into coherent monthly pages.",
                    ai_automation="The draft builder prioritizes approved photos, applies deterministic limits, and groups output pages by month.",
                    user_interaction="Inspect page composition and explanation notes to validate that the generated story matches family context.",
                    expected_outcome="A structured draft with transparent inclusion logic, ready for refinement and future export workflows.",
                ),
                _workflow_section(
                    [
                        "Load Reviewed Photo Decisions",
                        "Build Deterministic Draft",
                        "Inspect Monthly Pages",
                        "Check Inclusion and Exclusion Signals",
                        "Validate Story Coverage",
                        "Prepare for Next Output Stage",
                    ]
                ),
                _best_practices_section(
                    [
                        "Review page explanations to understand why each page was generated.",
                        "Confirm that high-priority family events are represented.",
                        "Use Memory Review decisions to improve draft quality before expecting manual edits.",
                        "Treat this as a planning surface, not a final layout editor.",
                    ]
                ),
                _tips_section(
                    [
                        WorkspaceHelpTip(
                            title="Tip of the Day",
                            body="If the draft feels unbalanced, return to Memory Review and improve decision consistency first.",
                        ),
                        WorkspaceHelpTip(
                            title="Coverage Tip",
                            body="Month-by-month scanning helps identify overrepresented and missing moments quickly. The compact workspace introduction panel at the top can be collapsed for a denser draft view.",
                        ),
                    ]
                ),
                _ai_status_section(
                    [
                        WorkspaceAIStatusMetric("Draft Assembly", 76, "Stable deterministic page grouping"),
                        WorkspaceAIStatusMetric("Story Balance", 52, "Improves as review consistency improves"),
                        WorkspaceAIStatusMetric("Export Readiness", 35, "Foundational stage before output integrations"),
                    ]
                ),
            ),
        ),
        WorkspaceHelpDefinition(
            workspace_id=SETTINGS_WORKSPACE,
            title="Settings",
            sections=(
                _purpose_section(
                    why_this_workspace_exists="Settings centralizes product behavior preferences so your workflow remains consistent across imports and review sessions.",
                    problem_it_solves="Growing AI workflows require explicit defaults and visibility into system behavior to avoid accidental drift.",
                    ai_automation="The AI Models section uses the generic AI Runtime Manager to show local provider status, Python environment details, licenses, and explicit installation plans. MobileCLIP remains evaluation-only and no model or dependency downloads silently.",
                    user_interaction="Inspect or select a Python environment, generate and review an AI model installation plan, confirm before installing, use Verify or Test only when ready, remove manager-owned model files when needed, and separately choose whether MobileCLIP evaluates the current library, selected photos, or another folder.",
                    expected_outcome="Predictable behavior, clearer control, local-only model processing, and safer long-term scaling of memory workflows.",
                ),
                _workflow_section(
                    [
                        "Review Current Defaults",
                        "Open AI Models and Review Registered Runtime Status",
                        "Inspect the Python Environment or Generate an Installation Plan",
                        "Review the Installation Plan Before Installing",
                        "Explicitly Confirm Install/Verify/Test/Remove Actions",
                        "Monitor Progress or Cancel Long-Running Runtime Work",
                        "Choose a MobileCLIP Evaluation Source",
                        "Confirm Available and Sample Counts",
                        "Run Evaluation Only When Ready",
                        "Keep Stable Baselines for Team Use",
                    ]
                ),
                _best_practices_section(
                    [
                        "Use Current imported library to evaluate photos already loaded in Family Memory AI without importing again.",
                        "Use Selected photos after selecting one or more items in Photo Browser or Cleanup Review; the app will not silently fall back to the full library.",
                        "Use Another folder only for an explicit external folder test, and keep the maximum sample cap small for CPU-only validation.",
                        "Treat MobileCLIP output as local-only evaluation evidence; it does not automatically change categories, original images, or the production classifier.",
                        "An installation plan is only a preview; installation starts only after explicit confirmation and uses the selected dedicated Python environment.",
                        "Use Verify to check the runtime, Test Image to choose one image file for embedding validation, and Remove model files only for manager-owned model files outside Git.",
                        "Do not approve installation or removal unless the generated AI Models plan shows the expected interpreter, cache path, licenses, and warnings.",
                    ]
                ),
                _tips_section(
                    [
                        WorkspaceHelpTip(
                            title="Tip of the Day",
                            body="The maximum sample cap controls how many eligible images are evaluated before any MobileCLIP run starts.",
                        ),
                        WorkspaceHelpTip(
                            title="Team Tip",
                            body="AI Models installation plans are previews until explicitly confirmed; MODEL-002B is merged but Product Owner detailed manual validation is pending, and no startup action installs MobileCLIP silently.",
                        ),
                    ]
                ),
                _ai_status_section(
                    [
                        WorkspaceAIStatusMetric("Preference Learning", 33, "Foundation stage for adaptive defaults"),
                        WorkspaceAIStatusMetric("Safety Guardrails", 78, "Strong deterministic protections are active"),
                        WorkspaceAIStatusMetric("Configuration Coverage", 41, "More settings integrations planned"),
                    ]
                ),
            ),
        ),
    ]
