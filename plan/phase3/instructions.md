```
# Phase 3 Context Instructions for AI

## Objective

The goal of **Phase 3** is to enable configurable Region of Interest (ROI) and entry/exit direction mapping for person detection in the footfall tracking system. This phase enhances the flexibility of detection and analytics by allowing users to define specific zones (e.g., doorways) and classify movement through them as either entries or exits, based on custom direction preferences.

## Structure

Phase 3 implementation must be broken down and documented across three dedicated Markdown files:

1. **roi_setup.md**  
   Describes how ROI integration affects the detection pipeline.  
   Focus: DetectionManager logic, ROI filtering, direction tracking, and event classification.

2. **roi_html_interface.md**  
   Describes how the user configures the ROI and direction mapping visually via the HTML dashboard.  
   Focus: Canvas overlay, UI controls, and communication with backend APIs.

3. **roi_persistence.md**  
   Describes how ROI and direction settings are saved and reloaded automatically.  
   Focus: Database schema, persistence via DatabaseManager, and auto-loading during startup.

Each file should maintain a clean separation of concern:  
- No HTML/UI logic should appear in `roi_setup.md`.  
- No DB persistence logic should appear in `roi_html_interface.md`.  
- No detection-specific logic should appear in `roi_persistence.md`.  

## Style & Format

- Use code blocks where needed but prioritize clean Markdown formatting for clarity.
- Clearly separate sections with horizontal rules (`---`).
- Maintain consistent variable naming and terms across all files.
- Always wrap implementation guides in triple backtick blocks under appropriate language tags (e.g., `python`, `js`, `html`).
- Each file must conclude with a **`\sequentialthinking Subtasks Outline:`** section, listing the logical breakdown of steps for that specific part of Phase 3.

## Sequential Thinking

At the **`\sequentialthinking Subtasks Outline:`** section in each file, invoke the **Sequential Thinking MCP tool** to break down the work into discrete, logical, actionable development steps that follow the file's scope and ensure implementation readiness.

Do not include any code or logic here — it must be strictly for outlining the thought process and sequencing of development tasks.

\endinstructions
```
