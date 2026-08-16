"""
Humanization skill — ensures AI-generated text reads as naturally human-written.

Rules enforced:
- No em-dashes (—) or en-dashes used as separators
- No AI cliché openers: "I am excited/thrilled/passionate about..."
- No filler transitions: "Furthermore", "Moreover", "In conclusion"
- No corporate jargon: "leverage", "synergize", "cutting-edge", "dynamic"
- Varied sentence lengths (mix short punchy + longer explanatory)
- Starts sentences with different words (not always "I")
- Uses contractions naturally (I've, I'm, I'd, I'll)
- Concrete and specific — numbers, tech names, real achievements
"""

import re

from .client import complete

# Words and phrases that flag AI-generated text
AI_PATTERNS = [
    (r'\s*—\s*', ' - '),                          # em-dash → hyphen
    (r'\s*–\s*', ' - '),                           # en-dash → hyphen
    (r'\bI am excited to\b', "I want to"),
    (r'\bI am thrilled to\b', "I want to"),
    (r'\bI am passionate about\b', "I care about"),
    (r'\bI am eager to\b', "I want to"),
    (r'\bI am delighted to\b', "I want to"),
    (r'\bI am pleased to\b', "I want to"),
    (r'\bpassionate about\b', "focused on"),
    (r'\bleverage\b', "use"),
    (r'\butilize\b', "use"),
    (r'\bsynerg\w+\b', "collaboration"),
    (r'\bcutting-edge\b', "modern"),
    (r'\bstate-of-the-art\b', "modern"),
    (r'\bfast-paced environment\b', "fast-moving team"),
    (r'\bFurthermore,\b', "Also,"),
    (r'\bMoreover,\b', "On top of that,"),
    (r'\bIn conclusion,\b', "Overall,"),
    (r'\bIn summary,\b', "To summarize,"),
    (r'\bIn addition,\b', "Also,"),
    (r'\bIt is worth noting that\b', "Worth mentioning:"),
    (r'\bI hope to hear from you soon\b', "Looking forward to connecting"),
    (r'\bThank you for considering my application\b', "Thanks for reading"),
    (r'\bI look forward to the opportunity to\b', "I'd love to"),
    (r'\bplethora\b', "range"),
    (r'\bencompass\b', "cover"),
    (r'\bdemonstrated\b', "shown"),
    (r'\bexhibited\b', "shown"),
    (r'\bproficient in\b', "experienced with"),
    (r'\bpossess\b', "have"),
    (r'\bI am confident that\b', "I think"),
    (r'\bI believe I am\b', "I'm"),
    (r'\bwould make me an ideal candidate\b', "fits what you need"),
    (r'\bstrongly aligned with\b', "matches"),
    (r'\bI am writing to express\b', "I want to apply for"),
    (r'\bfoster\b', "build"),
    (r'\bfacilitate\b', "help"),
    (r'\bimpactful\b', "meaningful"),
    (r'\btransformative\b', "significant"),
]

HUMANIZE_SYSTEM_PROMPT = """You are a writing assistant that makes text sound naturally human-written
without being informal or unprofessional.

Rules you MUST follow:
1. Never use em-dashes (—) or en-dashes (–) as punctuation. Use a comma, period, or rewrite the sentence.
2. Never start with "I am excited/thrilled/passionate/delighted/pleased to..."
3. Never use: leverage, utilize, synergy, synergize, cutting-edge, state-of-the-art, plethora, encompass, foster, facilitate, impactful, transformative
4. Never use: Furthermore, Moreover, In conclusion, In summary, It is worth noting that
5. Vary sentence length — mix short punchy sentences with longer ones.
6. Don't start every sentence with "I". Vary sentence structure.
7. Use contractions naturally: I've, I'm, I'd, I'll, it's, that's, they've.
8. Be specific — reference actual technologies, numbers, and concrete outcomes.
9. Sound like a confident professional, not a cover letter template.
10. Keep it concise — every sentence should earn its place.

Do not explain what you changed. Return only the rewritten text."""


def post_process(text: str) -> str:
    """Apply regex replacements to catch obvious AI patterns."""
    for pattern, replacement in AI_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    # Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)
    return text.strip()


async def humanize(text: str, client, model: str) -> str:
    """Run text through AI to humanize it, then apply post-processing."""
    humanized = await complete(
        client=client,
        model=model,
        system=HUMANIZE_SYSTEM_PROMPT,
        user=f"Rewrite this to sound naturally human-written:\n\n{text}",
        max_tokens=1024,
    )
    return post_process(humanized)
