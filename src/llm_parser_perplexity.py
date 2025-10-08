"""
LLM Parser for Meeting Notes - Perplexity API Version

Extracts structured data from meeting notes using Perplexity API with JSON Schema:
- Action items with assignees and context
- Decisions with rationale
- Key topics and entities
- People, projects, issues mentioned
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from openai import OpenAI  # Perplexity uses OpenAI-compatible SDK

logger = logging.getLogger(__name__)


class LLMParser:
    """Parse meeting notes using Perplexity API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM parser with Perplexity API

        Args:
            api_key: Perplexity API key (defaults to PERPLEXITY_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("Perplexity API key required (set PERPLEXITY_API_KEY env var)")

        # Perplexity uses OpenAI-compatible API
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.perplexity.ai"
        )
        self.model = "sonar-pro"  # Best model for structured outputs

        logger.info("LLMParser initialized (Perplexity sonar-pro)")

    def get_json_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for meeting extraction

        Returns:
            JSON schema dictionary
        """
        return {
            "type": "object",
            "properties": {
                "action_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string"},
                            "assignee": {"type": "string"},
                            "context": {"type": "string"},
                            "mentioned_by": {"type": ["string", "null"]},
                            "due_date": {"type": ["string", "null"]},
                            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                            "related_entities": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["task", "assignee", "context", "priority"]
                    }
                },
                "decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "decision": {"type": "string"},
                            "rationale": {"type": "string"},
                            "alternatives_considered": {"type": "array", "items": {"type": "string"}},
                            "impact": {"type": ["string", "null"]},
                            "owner": {"type": ["string", "null"]}
                        },
                        "required": ["decision", "rationale"]
                    }
                },
                "topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string"},
                            "summary": {"type": "string"},
                            "key_points": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["topic", "summary"]
                    }
                },
                "entities": {
                    "type": "object",
                    "properties": {
                        "people": {"type": "array", "items": {"type": "string"}},
                        "projects": {"type": "array", "items": {"type": "string"}},
                        "issues": {"type": "array", "items": {"type": "string"}},
                        "companies": {"type": "array", "items": {"type": "string"}},
                        "technologies": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "follow_ups": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item": {"type": "string"},
                            "owner": {"type": "string"},
                            "timing": {"type": ["string", "null"]}
                        },
                        "required": ["item", "owner"]
                    }
                },
                "open_questions": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["action_items", "decisions", "topics", "entities"]
        }

    def parse_meeting(self, markdown_content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse meeting notes to extract structured data

        Args:
            markdown_content: The meeting notes in markdown format
            metadata: Meeting metadata (title, date, attendees, etc.)

        Returns:
            Dictionary with extracted action items, decisions, topics, entities
        """
        try:
            prompt = self._build_extraction_prompt(markdown_content, metadata)

            logger.info(f"Parsing meeting: {metadata.get('title', 'Untitled')}")
            logger.debug(f"Prompt length: {len(prompt)} chars")

            # Call Perplexity API with JSON schema
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "meeting_extraction",
                        "schema": self.get_json_schema()
                    }
                },
                temperature=0
            )

            # Extract and parse JSON
            response_text = response.choices[0].message.content
            logger.debug(f"Response length: {len(response_text)} chars")

            parsed_data = json.loads(response_text)

            logger.info(f"Successfully parsed meeting: {len(parsed_data.get('action_items', []))} actions, "
                       f"{len(parsed_data.get('decisions', []))} decisions")

            # Stage 2: Consolidate and refine (optional)
            if len(parsed_data.get('action_items', [])) > 15:
                logger.info(f"Stage 2: Consolidating {len(parsed_data['action_items'])} action items...")
                parsed_data = self._consolidate_action_items(parsed_data, markdown_content, metadata)
                logger.info(f"After consolidation: {len(parsed_data['action_items'])} action items")

            return parsed_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            raise
        except Exception as e:
            logger.error(f"Error parsing meeting: {e}")
            raise

    def _consolidate_action_items(
        self,
        initial_parse: Dict[str, Any],
        markdown_content: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stage 2: Consolidate action items with fresh context

        Uses LLM to review extracted actions and consolidate duplicates,
        remove decision details that shouldn't be actions, and merge related items.

        Args:
            initial_parse: Initial parsed data with action items
            markdown_content: Original meeting notes
            metadata: Meeting metadata

        Returns:
            Refined parsed data with consolidated action items
        """
        meeting_title = metadata.get('title', metadata.get('meeting', 'Untitled'))

        # Build consolidation prompt
        actions_json = json.dumps(initial_parse['action_items'], indent=2)
        decisions_json = json.dumps(initial_parse['decisions'], indent=2)

        consolidation_prompt = f"""You are reviewing extracted action items from a meeting to consolidate and refine them.

# Meeting: {meeting_title}

# Extracted Action Items (Initial Pass)
{actions_json}

# Extracted Decisions (for context)
{decisions_json}

# Task
Review the action items and consolidate them. Return a refined list that:

1. **Removes duplicates** - If multiple items describe the same work, merge them
2. **Removes decision details** - If an item is just implementing a decision (like "Change button label X"), either:
   - Remove it if it's covered by a broader implementation task
   - Keep it if it's a standalone work item
3. **Groups related items** - Combine small related tasks into logical work items
4. **Preserves critical items** - Keep distinct work items that are truly separate

**Examples of consolidation**:

Before:
- "Replace 'car' with 'vehicle' in designs"
- "Change 'Shop appointment' to 'Shop details'"
- "Update button label to 'Accept shop referral'"

After:
- "Update UI copy and terminology based on design decisions" (combines all copy changes)

Before:
- "Implement MSO shop logic"
- "Prevent appointment booking for vehicles at shop"

After:
- "Implement MSO shop logic to prevent appointment booking for vehicles already at shop" (merged related)

**Guidelines**:
- Target: 8-15 high-quality action items
- Each action should be a distinct work item requiring effort
- Preserve assignees, priorities, and context
- Don't lose important details - just consolidate redundant ones

Return the consolidated action items as a JSON array matching this schema:
{self.get_json_schema()['properties']['action_items']}

Return ONLY the JSON array, no other text."""

        try:
            # Call LLM for consolidation
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": consolidation_prompt
                }],
                temperature=0
            )

            consolidated_text = response.choices[0].message.content
            consolidated_actions = json.loads(consolidated_text)

            # Replace action items in parsed data
            initial_parse['action_items'] = consolidated_actions

            return initial_parse

        except Exception as e:
            logger.warning(f"Consolidation failed: {e}. Using original action items.")
            return initial_parse

    def _build_extraction_prompt(self, markdown_content: str, metadata: Dict[str, Any]) -> str:
        """
        Build the extraction prompt for Perplexity

        Args:
            markdown_content: Meeting notes content
            metadata: Meeting metadata

        Returns:
            Formatted prompt string
        """
        meeting_title = metadata.get('title', metadata.get('meeting', 'Untitled'))
        meeting_date = metadata.get('date', 'Unknown date')
        attendees = metadata.get('attendees', [])
        attendees_str = ', '.join(attendees) if attendees else 'Unknown'

        prompt = f"""You are an expert at analyzing meeting notes and extracting actionable information with exceptional attention to detail.

# Meeting Context
- **Title**: {meeting_title}
- **Date**: {meeting_date}
- **Attendees**: {attendees_str}

# Meeting Notes
{markdown_content}

---

# Task
Extract ALL actionable information from these notes. Be THOROUGH - this is production data that people rely on.

## 1. Action Items - BE SELECTIVE (Quality over Quantity)

**What counts as an action item** (IMPORTANT - Don't confuse decisions with actions):

✅ **YES - Extract as action item**:
- Standalone work that needs to be done: "Update Sidekick to collect phone numbers"
- Investigation/exploration tasks: "Consider better product naming"
- Reviews and validations: "Complete QA review"
- Documentation work: "Create centralized terminology documentation"
- High-level implementation: "Implement logic for MSO integrated shops"
- Bug fixes and releases: "Compile must-have bug fixes"

❌ **NO - This is a DECISION, not an action item**:
- UI copy changes: "Replace 'car' with 'vehicle'" (this is a decision detail, not a task)
- Button labels: "Use 'Accept shop referral' button" (design decision)
- Field requirements: "Make drop-off date mandatory" (requirement decision)
- Visual changes: "Add car icon to map pin" (design decision)
- Removal of features: "Remove 'View other recommendations'" (design decision)

**The distinction**:
- **Decision** = What we decided to do (goes in Decisions section)
- **Action item** = Who needs to do work to implement decisions (could be one action for many decisions)

**Example**:
- Meeting discusses: "Use button X", "Change label Y", "Remove field Z"
- **Decisions**: 3 separate decisions (document what was decided)
- **Action items**: 1 action item = "Update UI based on design decisions" (the actual work)

**Assignee detection** (CRITICAL - don't mark everything "unassigned"):
- "I'll..." or "I will..." → speaker (check context for who's speaking)
- "Sam will review" → Sam
- "[Name] needs to..." → that person
- "We should..." + specific domain → assign to relevant attendee or "team"
- Only use "unassigned" if truly impossible to determine

**Priority assignment**:
- **high**: Has deadline, blocks work, "must-have", related to imminent release
- **medium**: Standard tasks, process improvements, no urgency stated
- **low**: "Consider", "nice to have", exploratory, long-term

**Context**: Include WHY the task matters, dependencies, blockers

## 2. Decisions - CAPTURE ALL (not just major ones)

Look for:
- "Use [X] button" (UI decision)
- "Make [X] mandatory" (requirement decision)
- "Replace [X] with [Y]" (terminology decision)
- "Remove [X]" (removal decision)
- ANY conclusive statement about how to proceed

**Rationale**: Explain WHY, not just "for consistency"
- "Use 'Accept shop referral' for consistency with existing button patterns in the app"
- Include constraints, requirements, user impact

**Alternatives**: Look for "instead of", "rather than", "not using", "remove X since Y"

## 3. Topics - Group logically
Extract 3-5 major themes and their key points

## 4. Entities - BE EXHAUSTIVE

**People**: ANYONE mentioned, even in passing (beyond attendees)

**Projects/Products** - Extract ALL:
- Abbreviations: SAR, NSF, VAS, GPC, MSO, ERAC, FNOL, PEG, etc.
- Full names: "Service Assignment", "Self-service", etc.
- Features: "Network shop flow", "Sidekick", "virtual estimate"

**Companies**: Progressive, Enterprise, Agero, etc.

**Technologies/Systems**:
- "Google API", "Granola API", "Notion"
- Internal systems: "MSO", "Sidekick"
- Features: "GPC", "virtual estimate"

**Issues**: ABC-123 patterns (ISA-234, etc.)

## 5. Follow-ups & Open Questions

**Follow-ups**: Items explicitly needing future discussion

**Open Questions**: Questions with "?" that weren't answered
- "When a vehicle is at a shop and customer accepts ERAC, how do they receive the rental?"
- "How does Enterprise coordination work?"

## Success Criteria (Target for this meeting)
- ✅ 8-15 action items (actual work items, not decision details!)
- ✅ 5-15 decisions (include small ones - this is where UI changes go!)
- ✅ 20-40 entities (be comprehensive!)
- ✅ Specific assignees where possible (not all "unassigned")
- ✅ 3-7 open questions

Remember: QUALITY over QUANTITY. Don't duplicate decisions as action items."""

        return prompt

    def enrich_meeting_note(
        self,
        original_markdown: str,
        metadata: Dict[str, Any],
        parsed_data: Dict[str, Any]
    ) -> str:
        """
        Create enriched meeting note with extracted data

        Args:
            original_markdown: Original meeting notes
            metadata: Meeting metadata
            parsed_data: Parsed data from LLM

        Returns:
            Enhanced markdown with action items, decisions, etc.
        """
        # Build enhanced note
        sections = []

        # Action Items section
        if parsed_data.get('action_items'):
            sections.append("## Action Items\n")
            for item in parsed_data['action_items']:
                assignee = item.get('assignee', 'unassigned')
                task = item['task']
                context = item.get('context', '')
                due_date = item.get('due_date')
                priority = item.get('priority', 'medium')

                # Format task with Obsidian Tasks plugin emoji format
                priority_emoji = {
                    'high': '⏫',
                    'medium': '🔽',
                    'low': '⏬'
                }.get(priority, '')

                due_emoji = f" 📅 {due_date}" if due_date else ""

                sections.append(f"### @{assignee}\n")
                sections.append(f"- [ ] {task} {priority_emoji}{due_emoji}\n")

                if context:
                    sections.append(f"  - **Context**: {context}\n")
                if item.get('mentioned_by'):
                    sections.append(f"  - **Mentioned by**: {item['mentioned_by']}\n")
                if item.get('related_entities'):
                    entities = ', '.join([f"[[{e}]]" for e in item['related_entities']])
                    sections.append(f"  - **Related**: {entities}\n")

                sections.append("\n")

        # Decisions section
        if parsed_data.get('decisions'):
            sections.append("## Decisions\n\n")
            for decision in parsed_data['decisions']:
                sections.append(f"### {decision['decision']}\n\n")
                sections.append(f"**Rationale**: {decision.get('rationale', 'Not specified')}\n\n")

                if decision.get('alternatives_considered'):
                    sections.append("**Alternatives considered**:\n")
                    for alt in decision['alternatives_considered']:
                        sections.append(f"- {alt}\n")
                    sections.append("\n")

                if decision.get('impact'):
                    sections.append(f"**Impact**: {decision['impact']}\n\n")
                if decision.get('owner'):
                    sections.append(f"**Owner**: [[{decision['owner']}]]\n\n")

        # Topics section (keep original for now, could enhance later)
        sections.append("## Notes\n\n")
        sections.append(original_markdown)

        # Follow-ups section
        if parsed_data.get('follow_ups'):
            sections.append("\n## Follow-ups\n\n")
            for item in parsed_data['follow_ups']:
                owner = item.get('owner', 'unassigned')
                timing = item.get('timing', '')
                timing_str = f" ({timing})" if timing else ""
                sections.append(f"- **@{owner}**: {item['item']}{timing_str}\n")

        # Open Questions section
        if parsed_data.get('open_questions'):
            sections.append("\n## Open Questions\n\n")
            for question in parsed_data['open_questions']:
                sections.append(f"- {question}\n")

        # Entities section (as metadata for linking)
        if parsed_data.get('entities'):
            sections.append("\n## Entities Referenced\n\n")
            entities = parsed_data['entities']

            if entities.get('people'):
                people_links = ', '.join([f"[[{p}]]" for p in entities['people']])
                sections.append(f"**People**: {people_links}\n\n")

            if entities.get('projects'):
                project_links = ', '.join([f"[[{p}]]" for p in entities['projects']])
                sections.append(f"**Projects**: {project_links}\n\n")

            if entities.get('issues'):
                issue_links = ', '.join([f"[[{i}]]" for i in entities['issues']])
                sections.append(f"**Issues**: {issue_links}\n\n")

        return ''.join(sections)


def main():
    """CLI for testing LLM parser"""
    import argparse
    from pathlib import Path
    import yaml
    import re

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description='Parse meeting notes with Perplexity LLM')
    parser.add_argument('--file', type=str, required=True, help='Path to meeting note markdown file')
    parser.add_argument('--output', type=str, help='Output file for parsed JSON')
    parser.add_argument('--enrich', action='store_true', help='Generate enriched markdown')

    args = parser.parse_args()

    # Read file
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract metadata from frontmatter
    frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)

    if frontmatter_match:
        metadata = yaml.safe_load(frontmatter_match.group(1))
        markdown_content = frontmatter_match.group(2)
    else:
        metadata = {'title': file_path.stem}
        markdown_content = content

    # Parse with LLM
    llm = LLMParser()
    parsed = llm.parse_meeting(markdown_content, metadata)

    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(parsed, f, indent=2)
        print(f"✓ Parsed data written to: {args.output}")
    else:
        print(json.dumps(parsed, indent=2))

    # Generate enriched note
    if args.enrich:
        enriched = llm.enrich_meeting_note(markdown_content, metadata, parsed)
        enriched_path = file_path.parent / f"{file_path.stem}_enriched.md"

        # Reconstruct with frontmatter
        if frontmatter_match:
            full_content = f"---\n{frontmatter_match.group(1)}\n---\n\n{enriched}"
        else:
            full_content = enriched

        with open(enriched_path, 'w', encoding='utf-8') as f:
            f.write(full_content)

        print(f"✓ Enriched note written to: {enriched_path}")


if __name__ == "__main__":
    main()
