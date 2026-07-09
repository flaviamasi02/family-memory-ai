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
            workspace_id=PHOTO_BROWSER_WORKSPACE,
            title="Photo Browser",
            sections=(
                _purpose_section(
                    why_this_workspace_exists="Photo Browser gives you the fastest way to inspect everything that was imported before deeper review work begins.",
                    problem_it_solves="Large folders are difficult to assess quickly without visual browsing, relevance filters, and metadata context.",
                    ai_automation="The AI-assisted classification engine tags each file with relevance categories and confidence signals during import.",
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
                            body="Previously rendered folders can show cached thumbnails first while missing thumbnails continue loading in the background.",
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
                    user_interaction="Correct Media Category values in small batches; every correction is captured for deterministic category and preference learning.",
                    expected_outcome="A cleaner, higher-confidence reviewed set that teaches future classification and recommendation behavior without mixing in album-decision editing.",
                ),
                _workflow_section(
                    [
                        "Review AI Suggested Priority",
                        "Confirm or Correct Category",
                        "Validate Explanations and Confidence",
                        "Feed Learning Signals from Corrections",
                        "Open Learning Summary to Review Timestamped Learning History",
                        "Improve Future Ranking Quality",
                    ]
                ),
                _best_practices_section(
                    [
                        "Review visually similar photos together to keep decisions consistent.",
                        "Use multi-selection for repeated patterns instead of editing one by one.",
                        "Correct category mistakes immediately when confidence is low.",
                        "Use Learning Summary to see when rules and preference signals were learned, including visual/content evidence when available.",
                        "Do focused sessions of 15 to 30 minutes to reduce fatigue.",
                        "Aim for consistent category corrections, not album-decision editing, in each session.",
                    ]
                ),
                _tips_section(
                    [
                        WorkspaceHelpTip(
                            title="Tip of the Day",
                            body="Reviewing only 20 photos with corrections can materially improve future AI categorization.",
                        ),
                        WorkspaceHelpTip(
                            title="Learning Tip",
                            body="Learning Summary shows stored event dates, times, and visual/content evidence when available so you can understand each learned pattern.",
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
                    ai_automation="The classifier proposes categories, confidence, and safe actions; exact duplicate candidates are grouped deterministically.",
                    user_interaction="Confirm keep or move decisions and correct categories when the recommendation does not match your intent.",
                    expected_outcome="A safer, cleaner working set with non-memory media moved to cleanup review instead of permanent deletion.",
                ),
                _workflow_section(
                    [
                        "Inspect Cleanup Candidates",
                        "Check AI Reasons and Confidence",
                        "Apply Keep or Move Decisions",
                        "Correct Category Where Needed",
                        "Run Face Analysis for Ambiguous Items",
                        "Complete Safe Cleanup Separation",
                    ]
                ),
                _best_practices_section(
                    [
                        "Use category grouping to process one media type at a time.",
                        "Prioritize low-confidence items first; they need your judgment most.",
                        "Move files to cleanup review rather than deleting anything immediately.",
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
                            body="Cleanup moves are reversible when reviewed in the dedicated cleanup folder.",
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
                            body="Month-by-month scanning helps identify overrepresented and missing moments quickly.",
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
                    ai_automation="The system applies configured defaults and will later surface adaptive recommendations based on project usage.",
                    user_interaction="Adjust application preferences deliberately, then validate effects in the workspace where decisions are made.",
                    expected_outcome="Predictable behavior, clearer control, and safer long-term scaling of memory workflows.",
                ),
                _workflow_section(
                    [
                        "Review Current Defaults",
                        "Adjust Workflow Preferences",
                        "Save and Validate Changes",
                        "Run a Small Test Import",
                        "Keep Stable Baselines for Team Use",
                    ]
                ),
                _best_practices_section(
                    [
                        "Change one setting group at a time and validate quickly.",
                        "Document preference changes for shared family workflows.",
                        "Keep conservative defaults for cleanup and irreversible actions.",
                        "Revisit settings after major model or workflow updates.",
                    ]
                ),
                _tips_section(
                    [
                        WorkspaceHelpTip(
                            title="Tip of the Day",
                            body="Stable defaults make AI behavior easier to understand and improve over time.",
                        ),
                        WorkspaceHelpTip(
                            title="Team Tip",
                            body="If multiple people review photos, align settings first to reduce inconsistent outcomes.",
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
