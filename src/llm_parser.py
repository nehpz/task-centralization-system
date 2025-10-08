"""
LLM Parser for Meeting Notes

Extracts structured data from meeting notes using Claude API:
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
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class LLMParser:
    """Parse meeting notes using Claude API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM parser

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("Anthropic API key required (set ANTHROPIC_API_KEY env var)")

        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-3-5-sonnet-20241022"

        logger.info("LLMParser initialized")

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

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract JSON from response
            response_text = response.content[0].text
            logger.debug(f"Response length: {len(response_text)} chars")

            # Parse JSON
            parsed_data = json.loads(response_text)

            logger.info(f"Successfully parsed meeting: {len(parsed_data.get('action_items', []))} actions, "
                       f"{len(parsed_data.get('decisions', []))} decisions")

            return parsed_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            raise
        except Exception as e:
            logger.error(f"Error parsing meeting: {e}")
            raise

    def _build_extraction_prompt(self, markdown_content: str, metadata: Dict[str, Any]) -> str:
        """
        Build the extraction prompt for Claude

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

        prompt = f"""You are analyzing meeting notes to extract actionable information. Extract the following from this meeting:

# Meeting Context
- **Title**: {meeting_title}
- **Date**: {meeting_date}
- **Attendees**: {attendees_str}

# Meeting Notes
{markdown_content}

---

# Your Task
Extract structured data from these meeting notes and return ONLY valid JSON (no markdown, no code blocks, just raw JSON).

## JSON Schema
{{
  "action_items": [
    {{
      "task": "Clear description of the action item",
      "assignee": "Person's name or 'unassigned'",
      "context": "Why this needs to be done, any dependencies",
      "mentioned_by": "Who suggested or assigned this",
      "due_date": "YYYY-MM-DD or null if not mentioned",
      "priority": "high|medium|low",
      "related_entities": ["Project names", "Issue IDs like ISA-234", "Other people mentioned"]
    }}
  ],
  "decisions": [
    {{
      "decision": "What was decided",
      "rationale": "Why this decision was made",
      "alternatives_considered": ["Other options discussed"],
      "impact": "Expected impact or consequences",
      "owner": "Person responsible for the decision"
    }}
  ],
  "topics": [
    {{
      "topic": "Topic name",
      "summary": "Brief summary of discussion",
      "key_points": ["Important point 1", "Important point 2"]
    }}
  ],
  "entities": {{
    "people": ["Names of people mentioned (beyond attendees)"],
    "projects": ["Project names or abbreviations like 'SAR', 'Self-service Towing'"],
    "issues": ["Issue IDs like ISA-234, JIRA-123"],
    "companies": ["External companies mentioned"],
    "technologies": ["Technologies, tools, or systems discussed"]
  }},
  "follow_ups": [
    {{
      "item": "What needs follow-up",
      "owner": "Who should follow up",
      "timing": "When (e.g., 'next meeting', 'before Friday')"
    }}
  ],
  "open_questions": [
    "Questions that were raised but not answered"
  ]
}}

## Extraction Guidelines

1. **Action Items**:
   - Only extract EXPLICIT action items, not implied tasks
   - Look for phrases like "needs to", "should", "will", "assigned to", "action item"
   - Include context and dependencies
   - Assignee should be a specific person's name, or "unassigned"
   - If someone says "I'll do X", that person is the assignee

2. **Decisions**:
   - Extract concrete decisions made during the meeting
   - Capture the reasoning/rationale
   - Note alternatives if discussed
   - Identify who made or owns the decision

3. **Topics**:
   - Major discussion themes or subject areas
   - Provide brief summaries
   - Extract 3-5 key points per topic

4. **Entities**:
   - Extract people mentioned (not just attendees)
   - Project names and abbreviations
   - Issue/ticket IDs (patterns like ABC-123)
   - External companies or partners
   - Technologies, tools, systems mentioned

5. **Follow-ups & Questions**:
   - Items that need future action or discussion
   - Unanswered questions raised in the meeting

## Important
- Return ONLY the JSON object, no markdown formatting, no code blocks
- Use null for missing/unknown values
- Empty arrays [] for no items
- Be conservative: don't invent information not in the notes
- Preserve exact names and terminology from the notes

Return the JSON now:"""

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

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description='Parse meeting notes with LLM')
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

    # Extract metadata from frontmatter (simple parser)
    import re
    frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)

    if frontmatter_match:
        import yaml
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
        print(f"Parsed data written to: {args.output}")
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

        print(f"Enriched note written to: {enriched_path}")


if __name__ == "__main__":
    main()
