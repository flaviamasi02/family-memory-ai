# Family Memory AI Product Vision

## Vision

Family Memory AI is an intelligent Family Memory Management System.

It is not primarily an album creator and it is not a generic photo manager.

Its purpose is to help families preserve, organize, understand, and rediscover the memories that matter most while continuously learning what is important for each family.

The product should feel thoughtful, personal, useful, adaptive, and trustworthy rather than purely technical.

---

# Mission

The mission of Family Memory AI is:

"Help families preserve, organize, understand and rediscover the memories that matter most while continuously learning what is important for each family."

Albums are only one possible output.

The real product is a Family Memory Intelligence platform that organizes memory knowledge and uses that knowledge to generate meaningful outputs.

---

# Target Users

## Primary Users

- Flavia
- Miguel
- Luis

## Future Users

- other families
- extended family groups
- users who want a more meaningful way to manage personal memory collections

---

# Product Philosophy

The product should be guided by human values first.

## Core beliefs

- Emotion before technology
- Meaning before aesthetics
- Rare memories matter
- Explainability is important
- User control is essential
- Privacy matters
- Offline-first whenever possible

The product should help users preserve what matters emotionally, not just what is technically easy to classify.

## Five major objectives

1. Organize memories.
2. Identify meaningful memories.
3. Remove clutter.
4. Learn user preferences.
5. Generate meaningful outputs (albums, stories, timelines, search, and similar experiences).

Albums are no longer the primary objective. They are one way of presenting knowledge produced by the broader memory intelligence system.

Development is now organized around capabilities and domains rather than chronological implementation numbering.

MASTER_DEVELOPMENT_PLAN.md is the highest-level planning document for future development decisions.

---

# Core Features

The initial product should focus on a set of high-value capabilities.

- Photo Import
- Memory Organization
- Memory Review
- Cleanup Review
- Cleanup and Clutter Removal
- Duplicate Detection
- Preference Learning
- Memory Intelligence
- Meaningful Collections
- Automatic Albums
- Storytelling
- Family Timeline
- Search

These features should work together to make memories easier to understand, preserve, rediscover, and curate.

## Current Product Direction

Current implemented direction emphasizes human-in-the-loop deterministic curation:

- Memory Review is the central decision interface.
- Cleanup Review shares the same UX philosophy (top toolbar, compact thumbnail grid, right details panel).
- Initial media classification is deterministic and explainable.
- Classification confidence and classification explanations are first-class review concepts.
- User corrections (Automatic Category -> User Corrected Category -> Effective Category) create the foundation for future Preference Learning.
- Categories are taxonomy-driven: system categories remain read-only while users can define unlimited custom categories directly in-app.
- Category records now include optional AI Description fields so future AI classifiers can learn from user-defined taxonomy intent.
- Album and cleanup behaviors are category-driven through category flags, not hardcoded category-name checks.

---

# Memory Review and Cleanup Review Philosophy

Memory Review and Cleanup Review are two distinct workspaces with different responsibilities. They operate on the same underlying knowledge base but serve different goals.

## Memory Review

**Purpose: Teach the AI.**

Memory Review is the workspace where the user reviews memories, corrects AI decisions, confirms important photos, assigns categories, improves people recognition, validates events, and increases the AI knowledge base.

The objective of Memory Review is improving the knowledge base.

User actions in Memory Review:

- Review AI-assigned media categories and correct them when wrong.
- Confirm which photos are family memories and which are not.
- Assign or adjust media categories to improve future AI classification.
- Mark important photos so the system learns what matters.
- Validate people recognition and event context.
- Approve or reject photos from album candidates.

Every decision in Memory Review is a learning signal. The AI uses these corrections to improve future classification and recommendations.

## Cleanup Review

**Purpose: Reduce noise.**

Cleanup Review is the workspace where the user reviews duplicate candidates, screenshots, low-quality images, and unnecessary files.

The objective of Cleanup Review is cleaning the collection without affecting valuable memories.

User actions in Cleanup Review:

- Review photos flagged as potential duplicates.
- Review screenshots and memes that may not belong in the memory collection.
- Review low-quality or blurry images.
- Review files that appear to have no family memory value.
- Decide what to move to the cleanup review folder and what to keep.

Cleanup Review does not teach the AI what matters — that is Memory Review's role. Cleanup Review reduces clutter so the rest of the system works with higher-quality input.

## Shared Knowledge

Both workspaces operate on the same underlying Knowledge Database. A category correction made in Memory Review is reflected in Cleanup Review. A cleanup decision does not remove a memory from Memory Review unless the user explicitly moves it.

They are different views of the same collection, with different goals and different user tasks.

## Summary

| Aspect | Memory Review | Cleanup Review |
| --- | --- | --- |
| Primary goal | Teach the AI | Reduce noise |
| User task | Review, correct, confirm, validate | Review, triage, move to cleanup |
| What improves | Knowledge base quality | Collection quality |
| Effect on AI | Creates learning signals | Removes low-value inputs |
| Shared knowledge | Yes | Yes |

---

# Future Features

Over time, the product may expand into a richer family memory platform.

- Google Photos integration
- Android support
- Cloud Sync
- Shared Family Profiles
- Voice Search
- Interactive Storytelling
- Memory Recommendations
- Timeline Viewer
- Photo Books
- Slideshows

These features should be introduced only when they clearly improve the family experience.

---

# Product Principles

The product should remain:

- Fast
- Simple
- Trustworthy
- Explainable
- Respectful of user choices
- Never force AI

Users should always feel that they are in control of the experience.

## Explainable Intelligence

Family Memory AI is designed to be an Explainable AI application.

Artificial Intelligence is encouraged.

Black-box user experience is not.

Every important automatic decision should be understandable by the user.

The user should always remain in control.

## Permanent Product Decisions

### FM-012
Title:
Explainability over Black Box

Decision:
Family Memory AI is free to use AI.

However every user-visible decision must remain:

- explainable
- transparent
- reviewable
- user-correctable

User trust has higher priority than AI automation.

### FM-013
Title:
AI Assists. Users Decide.

Decision:
Artificial Intelligence proposes.

The Decision Engine explains.

The User decides.

Every correction becomes a learning signal.

---

# Success Metrics

Success should be measured by the quality of the experience, not only by feature count.

## Key indicators

- Fast imports
- Responsive UI
- High quality recommendations
- Better clutter reduction
- Better preference alignment
- Low user effort
- High trust

A successful product should feel effortless, dependable, and increasingly personalized.

---

# Long Term Vision

Five years from now, Family Memory AI should be a thoughtful family memory intelligence platform that helps people relive meaningful moments with ease.

It should understand photos, people, events, emotions, stories, clutter, and family-specific patterns in a way that feels useful and natural.

The product should become a trusted companion for preserving family history and rediscovering treasured memories over time.

Every feature should help families preserve memories, not simply manage files.

The long-term objective is: "The application learns what matters to each family."

This means Memory Review evolves into the main decision-teaching interface, not only an approval screen. Over time, family-specific decisions should improve ranking, cleanup suggestions, memory collections, and meaningful outputs while preserving explainability and user control.
