import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
import asyncio
from urllib.parse import quote_plus

from .config import config

OPENCODE_PATH = "/Users/michaelshattuck/.opencode/bin/opencode"


class TopicResearcher:
    def __init__(self):
        self.ddg_url = "https://html.duckduckgo.com/html/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    async def research_topic(self, topic: str, depth: int = 3) -> dict:
        results = {
            "facts": [],
            "recent_events": [],
            "statistics": [],
            "expert_quotes": [],
            "controversies": [],
        }

        search_queries = self._generate_queries(topic, depth)

        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = [self._search_ddg_html(session, query) for query in search_queries]
            search_results = await asyncio.gather(*tasks, return_exceptions=True)

        for snippets in search_results:
            if isinstance(snippets, Exception):
                continue
            for snippet in snippets:
                self._categorize_snippet(snippet, results)

        results["facts"] = list(dict.fromkeys(results["facts"]))
        results["statistics"] = list(dict.fromkeys(results["statistics"]))

        return results

    def _generate_queries(self, topic: str, depth: int) -> list[str]:
        base_queries = [
            f"{topic} 2026",
            f"{topic} statistics data",
            f"{topic} news recent",
        ]

        if depth >= 2:
            base_queries.extend([
                f"{topic} controversy issues",
                f"{topic} expert opinion analysis",
            ])

        if depth >= 3:
            base_queries.extend([
                f"{topic} research study",
                f"{topic} impact effects",
                f"{topic} future trends",
            ])

        if depth >= 4:
            base_queries.extend([
                f"{topic} policy regulation",
                f"{topic} market industry",
                f"{topic} challenges problems",
            ])

        return base_queries[:depth * 3]

    async def _search_ddg_html(self, session: aiohttp.ClientSession, query: str) -> list[str]:
        snippets = []

        try:
            data = {"q": query, "b": ""}
            async with session.post(self.ddg_url, data=data, timeout=15) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()

            import re
            snippet_pattern = r'<a class="result__snippet"[^>]*>(.*?)</a>'
            matches = re.findall(snippet_pattern, html, re.DOTALL)

            for match in matches[:10]:
                text = re.sub(r'<[^>]+>', '', match)
                text = text.strip()
                if len(text) > 30:
                    snippets.append(text)

            title_pattern = r'<a class="result__a"[^>]*>(.*?)</a>'
            titles = re.findall(title_pattern, html, re.DOTALL)
            for title in titles[:5]:
                text = re.sub(r'<[^>]+>', '', title).strip()
                if len(text) > 20 and text not in snippets:
                    snippets.append(f"Topic: {text}")

        except Exception:
            pass

        return snippets

    def _categorize_snippet(self, snippet: str, results: dict):
        snippet_lower = snippet.lower()

        stat_indicators = ['%', 'percent', 'billion', 'million', 'trillion', '$', 'increased', 'decreased', 'growth', 'rate']
        if any(ind in snippet_lower for ind in stat_indicators) and any(c.isdigit() for c in snippet):
            results["statistics"].append(snippet)
        elif any(word in snippet_lower for word in ['study', 'research', 'found', 'according', 'report', 'data']):
            results["facts"].append(snippet)
        elif any(word in snippet_lower for word in ['debate', 'controversy', 'critics', 'opponents', 'supporters']):
            results["controversies"].append(snippet)
        elif any(word in snippet_lower for word in ['announced', 'launched', 'released', '2025', '2026']):
            results["recent_events"].append(snippet)
        else:
            results["facts"].append(snippet)

    def format_research_context(self, research: dict, max_items: int = 10) -> str:
        sections = []

        if research["facts"]:
            facts = research["facts"][:max_items]
            sections.append("VERIFIED FACTS:\n" + "\n".join(f"- {f}" for f in facts))

        if research["statistics"]:
            stats = research["statistics"][:max_items // 2]
            sections.append("STATISTICS:\n" + "\n".join(f"- {s}" for s in stats))

        if research["recent_events"]:
            events = research["recent_events"][:max_items // 2]
            sections.append("RECENT EVENTS:\n" + "\n".join(f"- {e}" for e in events))

        if research["controversies"]:
            controv = research["controversies"][:max_items // 3]
            sections.append("DEBATES/CONTROVERSIES:\n" + "\n".join(f"- {c}" for c in controv))

        return "\n\n".join(sections) if sections else "No specific research found - use general knowledge."


@dataclass
class ScriptSegment:
    text: str
    visual_cue: str
    duration_hint: int = 0


@dataclass
class VideoScript:
    title: str
    hook: str
    segments: list[ScriptSegment] = field(default_factory=list)
    outro: str = ""
    thumbnail_text: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    key_phrases: list[str] = field(default_factory=list)

    @property
    def full_narration(self) -> str:
        parts = [self.hook]
        for seg in self.segments:
            parts.append(seg.text)
        parts.append(self.outro)
        return " ".join(parts)

    @property
    def word_count(self) -> int:
        return len(self.full_narration.split())

    @property
    def estimated_duration(self) -> int:
        return int(self.word_count / config.words_per_minute * 60)


class ScriptGenerator:
    def __init__(self):
        self.researcher = TopicResearcher()

    def generate(self, topic: str, style: str = "educational", duration_minutes: int = 8, script_format: str = "monologue") -> VideoScript:
        target_words = duration_minutes * config.words_per_minute

        research_context = ""
        if style == "turboencabulator":
            research_depth = min(1 + (duration_minutes // 3), 5)
            try:
                research = self._run_research(topic, research_depth)
                max_items = 5 + (duration_minutes * 2)
                research_context = self.researcher.format_research_context(research, max_items=max_items)
                if research_context and research_context != "No specific research found - use general knowledge.":
                    print(f"      Research gathered: {len(research.get('facts', []))} facts, {len(research.get('statistics', []))} stats")
            except Exception as e:
                print(f"      Research failed (continuing without): {e}")
                research_context = ""

            if script_format in ["interview", "panel", "debate"]:
                prompt = self._turbo_conversation_prompt(topic, target_words, duration_minutes, research_context, script_format)
            else:
                prompt = self._turboencabulator_prompt(topic, target_words, duration_minutes, research_context)
        else:
            prompt = self._standard_prompt(topic, style, target_words, duration_minutes)

        temperature = 0.95 if style == "turboencabulator" else 0.7
        response = self._call_opencode(prompt, temperature=temperature)
        return self._parse_response(response)

    def _run_research(self, topic: str, depth: int) -> dict:
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.researcher.research_topic(topic, depth=depth))
                return future.result(timeout=30)
        except RuntimeError:
            return asyncio.run(self.researcher.research_topic(topic, depth=depth))

    def _standard_prompt(self, topic: str, style: str, target_words: int, duration_minutes: int) -> str:
        return f"""Create a YouTube video script about: {topic}

Style: {style}
Target length: {target_words} words (approximately {duration_minutes} minutes)

The script is for a FACELESS YouTube channel, so:
- No references to "showing you" or pointing at things
- Focus on narration that works with B-roll footage
- Include visual cues for what stock footage to show

Return a JSON object with this exact structure:
{{
    "title": "Catchy YouTube title (under 60 chars)",
    "hook": "Opening 2-3 sentences that grab attention immediately",
    "segments": [
        {{
            "text": "Narration text for this segment (50-100 words each)",
            "visual_cue": "Brief description of what footage/visuals to show"
        }}
    ],
    "outro": "Call to action and closing (2-3 sentences)",
    "thumbnail_text": "2-4 words for thumbnail overlay",
    "description": "YouTube description (2-3 sentences + key points)",
    "tags": ["relevant", "youtube", "tags"],
    "key_phrases": ["3-5 word impactful phrases from the script to display on screen", "shocking statistics or key takeaways", "memorable quotes or facts"]
}}

Make the content:
- Informative and valuable
- Engaging with a clear narrative arc
- Include surprising facts or contrarian takes
- End segments on mini-cliffhangers to maintain retention

Return ONLY the JSON, no other text."""

    def _generate_topic_seeds(self, topic: str) -> str:
        import random
        topic_lower = topic.lower()

        base_seeds = [
            "inverted logic", "suspiciously specific percentages", "fake institutes with plausible names",
            "circular reasoning delivered as insight", "analogies using unexpected objects",
            "made-up compound words with hyphens", "lost trains of thought that become the point",
            "fake academic citations", "rhetorical questions answered with more questions",
        ]

        domain_seeds = {
            "tech": ["firmware philosophies", "algorithmic karma", "protocol spirituality", "bandwidth ethics"],
            "politics": ["legislative origami", "constituency thermodynamics", "ballot harmonics", "partisan weather patterns"],
            "economics": ["fiscal astrology", "monetary choreography", "inflation semiotics", "market telepathy"],
            "social": ["discourse archaeology", "opinion tectonics", "narrative metabolism", "consensus fermentation"],
            "science": ["hypothesis gastronomy", "data cosmetology", "empirical interpretive dance", "peer review feng shui"],
            "ethics": ["moral cartography", "virtue plumbing", "ethical meteorology", "conscience acoustics"],
            "culture": ["meme paleontology", "trend hydrology", "zeitgeist dentistry", "vibe engineering"],
        }

        detected_domains = []
        if any(w in topic_lower for w in ["ai", "tech", "robot", "computer", "phone", "app", "social media"]):
            detected_domains.append("tech")
        if any(w in topic_lower for w in ["vote", "elect", "politic", "government", "law", "policy"]):
            detected_domains.append("politics")
        if any(w in topic_lower for w in ["money", "economy", "tax", "wage", "rich", "poor", "job"]):
            detected_domains.append("economics")
        if any(w in topic_lower for w in ["gender", "race", "culture", "social", "community"]):
            detected_domains.append("social")
        if any(w in topic_lower for w in ["climate", "science", "research", "study"]):
            detected_domains.append("science")
        if any(w in topic_lower for w in ["moral", "ethic", "right", "wrong", "should"]):
            detected_domains.append("ethics")

        if not detected_domains:
            detected_domains = ["culture"]

        selected_seeds = random.sample(base_seeds, 4)
        for domain in detected_domains[:2]:
            selected_seeds.extend(random.sample(domain_seeds[domain], 2))

        return "\n".join(f"- {seed}" for seed in selected_seeds)

    def _turboencabulator_prompt(self, topic: str, target_words: int, duration_minutes: int, research_context: str = "") -> str:
        import random
        num_segments = max(10, duration_minutes * 3)

        topic_seeds = self._generate_topic_seeds(topic)

        research_section = ""
        if research_context:
            research_section = f"""
RESEARCH TO USE (weave throughout, not just at the start):
{research_context}
"""

        nonsense_techniques = [
            "Compound fake words: combine real prefixes/suffixes into plausible-sounding nonsense",
            "False precision: suspiciously specific numbers (73.847%, a study of 2,847 participants)",
            "Invented anecdotes: stories that start normal and go nowhere ('I once met a guy in Des Moines who...' then never finish the point)",
            "Non-sequitur transitions: connect unrelated points with confident 'and that's exactly why'",
            "Appeal to fake authority: cite studies or experts that sound real but aren't",
            "Circular logic: prove things by restating them differently",
            "Lost train of thought: Rachel loses her point mid-sentence, then pretends it was intentional ('I lost my train of thought. That was the point.')",
            "Absurd analogies: compare the topic to something completely unrelated and act like it's profound",
            "Fake etymologies: confidently explain word origins that are completely made up",
            "The pivot that isn't: seem to take one side, then the other, then neither, all in one breath",
        ]
        chosen_techniques = random.sample(nonsense_techniques, 5)

        comedy_styles = [
            "corporate consultant who went off the rails",
            "TED talk that slowly becomes a fever dream",
            "documentary narrator who starts questioning reality",
            "news anchor having an existential crisis on air",
            "professor who forgot what class they're teaching",
        ]
        chosen_style = random.choice(comedy_styles)

        return f"""Create a podcast episode script for "The Deep Dive with Rachel"

TOPIC: {topic}
TARGET: {target_words} words, {num_segments} segments
{research_section}

WHO IS RACHEL:
Rachel is the host of "The Deep Dive" - a controversial topics podcast. She's in her early 20s, dropped out of communications school because "they weren't teaching anything real," and started this podcast from her apartment. She's curious, tenacious, and energetic. Think Brett Cooper energy - confident, opinionated delivery.

RACHEL'S STYLE:
- She does real research and knows the facts
- Presents both sides fairly... at first
- Then starts having "takes" - delivered with total confidence
- BUT her actual positions are nonsense that doesn't commit to either side
- She SOUNDS like she's taking a stand, but the actual thesis is vapor
- Gets genuinely passionate about her non-positions
- By the end, she may SEEM to have taken a side, but if you think about it, you can't tell which

THIS EPISODE'S COMEDY FLAVOR: {chosen_style}
(Let this influence HOW Rachel goes off the rails, not just THAT she does)

PODCAST STRUCTURE:
1. INTRO (same every episode, quick and punchy):
   "Hey everyone, welcome back to The Deep Dive. I'm Rachel, and today we're going somewhere... interesting."
   Then she teases the topic with genuine curiosity.

2. SETUP (use real research):
   Lay out the topic fairly. Both sides. Real facts and statistics.
   Rachel is calm, informative, genuinely curious.

3. EXPLORATION:
   Dig deeper. Present different perspectives.
   Rachel starts getting invested. "Now here's where it gets interesting..."
   Emotions should match the CONTENT - if discussing something sad, be reflective. If something outrageous, be fired up.

4. RACHEL'S TAKES:
   She starts injecting opinions. Confident. Passionate.
   But the actual positions don't land anywhere real.
   "And THIS is exactly why..." followed by something that sounds profound but commits to nothing.
   She may seem to take a side, then pivot, then take the other side, then neither.

5. OUTRO:
   Brief wrap-up. May or may not make sense.
   "Anyway, that's the deep dive. Let me know what you think. I'll see you next time."

EMOTIONAL RANGE (CONTEXTUAL - based on content, NOT linear progression):
- Use [excited] when discovering something interesting
- Use [frustrated] when presenting "obvious" points
- Use [calm] when laying out facts
- Use [passionate] when delivering her confident non-positions
- Use [reflective] or [sad] when topic calls for it
- Use [laughs] naturally, not forced
- VARY the emotions throughout based on what's being said

TURBOENCABULATOR TECHNIQUES (start subtle, escalate to COMICAL by the end):

The script MUST become ABSURD and FUNNY. By the final third, Rachel should be confidently spouting made-up jargon and circular logic. The audience should be BELLY LAUGHING at how confident she sounds while saying nothing.

GOALS:
1. EDUCATIONAL: The first half teaches real facts. People should learn something.
2. COMICAL: The second half is genuinely funny. Absurd conclusions, made-up words, confident nonsense.
3. AMBIGUOUS: Rachel seems to take a side, but it's impossible to tell which when you think about it.

BANNED PHRASES (NEVER USE THESE - they've been overused):
- "sandwich" or "policy" in the same sentence
- "trans-quadrilux-ification" or any word with "quadrilux"
- "omni-bilateral-duction" or any word with "bilateral-duction"
- "legislatorial-ambient-friction"
- "policy-geometrics"
- "proto-confabulation"
- "94-page memo"
- "on sabbatical"
- "I met a guy in Des Moines"
- "I lost my train of thought. That was the point."
- "Journal of Urgent [anything]"
- "if you understand that, you understand nothing"
- "that's not [X], it's [Y]" where X and Y mean the same thing

CREATE FRESH ABSURDITY:
Instead of copying patterns, INVENT NEW:
- Made-up compound words using prefixes/suffixes not listed above
- Fake institutions with names that sound plausible but aren't real
- Circular logic that's specific to THIS topic
- Absurd analogies using objects/concepts relevant to THIS topic
- Fake statistics with oddly specific numbers

VARIETY TECHNIQUES (use 2-3 per episode, rotate which ones):
{chr(10).join(f"- {t}" for t in chosen_techniques)}

CREATIVE SEEDS FOR THIS TOPIC (use as inspiration, don't copy literally):
{topic_seeds}

BE WILDLY ORIGINAL. Invent new metaphors, new fake jargon, new absurd logic specific to THIS topic.
If a phrase sounds like something you've written before, DON'T USE IT.

THE KEY: Rachel doesn't realize she's being absurd. She delivers nonsense with the same confidence as facts. That's the comedy.

ESCALATION ARC:
- First 40%: Real facts, real research, calm and informative
- Middle 30%: Start mixing in confident non-positions, vague profundity
- Final 30%: FULL TURBOENCABULATOR - made-up words, circular logic, absurd conclusions delivered passionately

CRITICAL RULES:
1. Rachel SEEMS to take a side - she's passionate, she's confident - but when you think about it, you can't tell which side she's actually on. That's the magic.
2. Emotions are CONTEXTUAL - match the content, not the position in the script
3. Each episode should feel DIFFERENT - vary the comedy style, the structure, the techniques
4. First half = EDUCATIONAL. People should learn real facts about the topic.
5. Second half = COMICAL. Escalate to absurdity. Belly laughs by the end.
6. THE ENDING MUST BE GENUINELY FUNNY - not just jargon, but absurd situations and logic
7. NO stage directions like [scoffs] [gasps] - only emotional markers for TTS
8. INVENT NEW FAKE JARGON each time - never reuse terms between episodes
9. Don't be predictable - vary which techniques you use, how you escalate, where the absurdity appears

EMOTIONAL MARKERS FOR TTS (use these inline):
[excited] [frustrated] [calm] [passionate] [reflective] [sad] [angry] [hopeful] [friendly] [whispering] [shouting]

Return JSON:
{{
    "title": "Catchy episode title",
    "hook": "Rachel's standard intro + topic tease",
    "segments": [
        {{"text": "[emotional_marker] Segment text...", "visual_cue": "B-roll description"}}
    ],
    "outro": "Rachel's casual sign-off",
    "thumbnail_text": "2-4 words",
    "description": "Episode description",
    "tags": ["{topic}", "deep dive", "rachel"],
    "key_phrases": ["Notable quotes from the episode"]
}}

Return ONLY valid JSON."""

    def _turbo_conversation_prompt(self, topic: str, target_words: int, duration_minutes: int, research_context: str, script_format: str) -> str:
        import random
        num_segments = max(12, duration_minutes * 3)

        research_section = ""
        if research_context:
            research_section = f"""
REAL RESEARCH (use in host intro and first 25% to establish credibility):
{research_context}
"""

        fake_institutions = [
            "the Brookings Institute", "Harvard Kennedy School", "Stanford Policy Center",
            "MIT Media Lab", "the Council on Foreign Relations", "Georgetown University",
            "the Rand Corporation", "UC Berkeley", "the Aspen Institute", "Columbia University",
            "the Cato Institute", "Princeton's Woodrow Wilson School", "the Heritage Foundation",
        ]

        fake_titles = [
            "Senior Fellow", "Distinguished Professor", "Director of Research",
            "Chief Analyst", "Policy Director", "Senior Research Scientist",
            "Executive Director", "Chair of", "Lead Investigator", "Principal Economist",
        ]

        fake_male_names = ["Dr. Marcus", "Professor Michael", "Dr. Jonathan", "Dr. William",
                          "Professor David", "Dr. Richard", "Professor James", "Dr. Robert"]
        fake_female_names = ["Professor Elena", "Dr. Sarah", "Dr. Catherine", "Dr. Rebecca",
                            "Professor Jennifer", "Dr. Victoria", "Professor Amanda", "Dr. Patricia"]
        fake_last_names = ["Thornberry", "Whitfield", "Castellano", "Pembrook", "Harrington",
                          "Ashworth", "Sinclair", "Beaumont", "Fitzgerald", "Holloway",
                          "Montgomery", "Blackwell", "Crawford", "Harwood", "Sterling"]
        used_last_names = []

        guest_types = [
            "tenured professor who's been awake for 48 hours",
            "think tank expert speaking entirely in buzzwords",
            "industry insider 'blowing the whistle' on nothing",
            "author promoting a book that doesn't exist",
            "retired official who keeps going off-topic",
            "tech entrepreneur who pivots every sentence",
            "philosopher who answers questions with questions",
            "statistician who makes up numbers confidently",
        ]

        panel_dynamics = [
            "everyone agrees violently while saying different things",
            "one expert keeps derailing, others get frustrated",
            "two experts have personal beef, moderator is oblivious",
            "everyone's competing to sound smartest with bigger words",
            "one expert is clearly confused, others don't notice",
        ]

        debate_energy = [
            "starts civil, becomes screaming match, ends with bizarre friendship",
            "passive-aggressive escalating to aggressive-aggressive",
            "one side keeps 'winning' while saying nothing",
            "both sides argue past each other about different topics",
            "host takes a side, then switches, then gives up",
        ]

        crosstalk_moments = [
            "[interrupts] Wait, wait, wait-- [crosstalk]",
            "[talking over] That's not what I-- [crosstalk]",
            "[both speaking] --completely misrepresenting-- --if you'd let me finish--",
            "[heated crosstalk for 3 seconds]",
            "[interrupts mid-sentence] Sorry, I have to stop you there--",
            "[talks over] --and FURTHERMORE-- [other voice fading]",
            "[simultaneous shouting, unintelligible for 2 seconds]",
        ]

        def generate_guest_intro(guest_type: str, gender: str = None) -> tuple[str, str, str, str]:
            if gender is None:
                gender = random.choice(["male", "female"])
            first_names = fake_male_names if gender == "male" else fake_female_names
            first_name = random.choice(first_names)
            available_last_names = [ln for ln in fake_last_names if ln not in used_last_names]
            if not available_last_names:
                available_last_names = fake_last_names
            last_name = random.choice(available_last_names)
            used_last_names.append(last_name)
            name = f"{first_name} {last_name}"
            title = random.choice(fake_titles)
            inst = random.choice(fake_institutions)
            return name, title, inst, gender

        if script_format == "interview":
            chosen_guest = random.choice(guest_types)
            guest_name, guest_title, guest_inst, guest_gender = generate_guest_intro(chosen_guest)
            chosen_crosstalk = random.sample(crosstalk_moments, 2)
            format_instructions = f"""
FORMAT: Interview

GUEST: {guest_name}, {guest_title} at {guest_inst}
GUEST PERSONA: {chosen_guest}

SPEAKER TAGS:
- [HOST] = The show's host (female voice, professional, warm)
- [GUEST_{guest_gender.upper()}: {guest_name}] = The guest expert

MANDATORY OPENING STRUCTURE:
The hook MUST be a proper host introduction. Use this format:
"[HOST] Welcome back to the show. Today we're diving deep into {topic}, and I am thrilled to be joined by {guest_name}, {guest_title} at {guest_inst}, who has spent over [X] years studying this exact issue. {guest_name}, thank you so much for being here."
"[GUEST: {guest_name}] Thank you for having me, it's a pleasure."

Then HOST asks first real question using research facts.

ARC:
- First 25%: Legitimate interview. Host asks insightful questions. Guest gives real answers. This must feel like a REAL interview.
- 25-50%: Guest starts using one weird term. Host doesn't notice or politely ignores it.
- 50-75%: Terms multiply. Host starts asking clarifying questions. Guest doubles down.
- 75-90%: Host is visibly confused. Guest is in full nonsense mode but supremely confident.
- Final 10%: Both exhausted. Somehow agree on something neither understands.

CROSSTALK TO USE (in later segments):
{chr(10).join(f"- {c}" for c in chosen_crosstalk)}

MOMENTS TO INCLUDE:
- Host repeating guest's nonsense term with audible question mark
- Guest citing a study that clearly doesn't exist
- Awkward pause where host processes something insane
- Guest getting emotional about something incomprehensible
- Host giving up and just nodding along"""

        elif script_format == "panel":
            chosen_dynamic = random.choice(panel_dynamics)
            num_panelists = random.choice([2, 3, 3, 3, 4])
            panelist_types = random.sample(guest_types, num_panelists)
            panelists = [generate_guest_intro(pt) for pt in panelist_types]
            chosen_crosstalk = random.sample(crosstalk_moments, 3)

            panelist_intros = []
            panelist_tags = []
            for i, (name, title, inst, gender) in enumerate(panelists, 1):
                panelist_intros.append(f"- {name}, {title} at {inst}")
                panelist_tags.append(f"[PANELIST_{i}_{gender.upper()}: {name}]")

            format_instructions = f"""
FORMAT: Panel Discussion with {num_panelists} experts

PANELISTS:
{chr(10).join(panelist_intros)}

DYNAMIC: {chosen_dynamic}

SPEAKER TAGS:
- [HOST] = The show's host/moderator (female voice, professional)
{chr(10).join(f"- {tag} = Panelist {i+1}" for i, tag in enumerate(panelist_tags))}

MANDATORY OPENING STRUCTURE:
The hook MUST start with HOST introducing the topic and each panelist. Use this format:
"[HOST] Welcome to today's discussion on {topic}. This is a topic that has sparked significant debate in recent months, and we've assembled an incredible panel to break it down for you."

Then HOST introduces EACH panelist individually:
"[HOST] Joining us today is {panelists[0][0]}, {panelists[0][1]} at {panelists[0][2]}, who has been studying this issue for over [X] years..."
Continue for each panelist.

"[HOST] Let's dive right in. [First panelist name], I'd like to start with you..."

ARC:
- First 20%: HOST introduces topic professionally, introduces EACH panelist with their credentials. First question is directed to a specific panelist. Real points made.
- 20-40%: First invented term appears. Others nod as if they understand. HOST directs questions to different panelists.
- 40-60%: Multiple made-up frameworks. Panelists start talking past each other. HOST tries to mediate.
- 60-80%: Chaos. Interruptions. Crosstalk. Someone references something no one said. HOST losing control.
- 80-95%: Incomprehensible arguments delivered with passion. People talking over each other.
- Final 5%: HOST summarizes with something that was never said. All agree despite saying opposite things.

CROSSTALK MOMENTS (use in heated sections):
{chr(10).join(f"- {c}" for c in chosen_crosstalk)}

HOST BEHAVIORS THROUGHOUT:
- Directs questions: "Let me bring in [Name] here..."
- Tries to mediate: "Let's let [Name] finish their point..."
- Summarizes (wrongly later): "So what you're saying is..."
- Redirects: "That's interesting, but [Name], what do you think about..."

MOMENTS TO INCLUDE:
- Two panelists agreeing while clearly meaning opposite things
- Someone going on tangent about personal anecdote, HOST tries to redirect
- HOST asking question that reveals they weren't listening
- Panelists talking over each other in heated disagreement
- Panelist citing their own fake study
- Awkward silence followed by complete non-sequitur"""

        else:  # debate
            chosen_energy = random.choice(debate_energy)
            side_a_type = random.choice(guest_types)
            side_b_type = random.choice([g for g in guest_types if g != side_a_type])
            side_a_name, side_a_title, side_a_inst, side_a_gender = generate_guest_intro(side_a_type)
            side_b_name, side_b_title, side_b_inst, side_b_gender = generate_guest_intro(side_b_type)
            chosen_crosstalk = random.sample(crosstalk_moments, 4)

            format_instructions = f"""
FORMAT: Moderated Debate

SIDE A: {side_a_name}, {side_a_title} at {side_a_inst}
SIDE A PERSONA: {side_a_type}

SIDE B: {side_b_name}, {side_b_title} at {side_b_inst}
SIDE B PERSONA: {side_b_type}

ENERGY: {chosen_energy}

SPEAKER TAGS:
- [HOST] = The show's host/moderator (female voice, professional but firm)
- [SIDE_A_{side_a_gender.upper()}: {side_a_name}] = First debater
- [SIDE_B_{side_b_gender.upper()}: {side_b_name}] = Second debater

MANDATORY OPENING STRUCTURE:
The hook MUST start with HOST setting up the debate professionally:
"[HOST] Welcome to tonight's debate on {topic}. This is an issue that has divided experts and policymakers alike, and tonight we're bringing together two leading voices to hash it out."

"[HOST] On one side, we have {side_a_name}, {side_a_title} at {side_a_inst}, who argues that [brief position]. On the other, {side_b_name}, {side_b_title} at {side_b_inst}, who takes the opposing view that [brief counter-position]."

"[HOST] Each debater will have time for an opening statement. {side_a_name}, let's start with you."

Then SIDE_A gives a reasonable, coherent opening statement using real research.
Then HOST invites SIDE_B's opening statement.
Then HOST asks first question or invites rebuttal.

ARC:
- First 15%: HOST introduces topic and BOTH debaters with full credentials. Opening statements are reasonable and coherent. Audience should think this is a real debate.
- 15-35%: Rebuttals get heated. First personal jab. HOST tries to maintain order.
- 35-55%: Logical fallacies fly. Neither addresses actual arguments. Crosstalk begins.
- 55-75%: SHOUTING. Interruptions. Made-up statistics as weapons. HOST struggling to control.
- 75-90%: Complete chaos. Both saying nonsense. Both think they're winning. People talking over each other.
- Final 10%: HOST calls time. Exhausted ceasefire. Bizarre agreement on nothing.

CROSSTALK/INTERRUPTIONS (use increasingly throughout):
{chr(10).join(f"- {c}" for c in chosen_crosstalk)}

HOST BEHAVIORS:
- Sets rules: "Let's keep this civil..."
- Intervenes: "Let them finish their point..."
- Loses patience: "[sighs] Can we please..."
- Eventually gives up: "[resigned] ...okay, sure..."
- Tries to summarize: "So if I understand correctly..."

DEBATE TACTICS (use after opening statements):
- Misquoting opponent immediately after they speak
- Citing fake authority with absurd specificity
- Straw-manning into oblivion
- Righteous indignation about invented positions
- Sarcastic dismissal escalating to genuine anger
- Personal attacks disguised as policy concerns
- Declaring victory while making no sense

VOICES: Each debater has a DISTINCT speech pattern. One uses long academic sentences, one uses punchy soundbites, etc."""

        return f"""Create a satirical {script_format} about: {topic}

Target: {target_words} words, {num_segments} exchanges
{research_section}
THE GOAL: Start as a COMPLETELY LEGITIMATE {script_format} that hooks viewers. The host introduction must be professional and believable. By the end, complete chaos that makes them laugh and wonder what they just watched.

{format_instructions}

EMOTIONAL MARKERS: [laughs] [sighs] [gasps] [scoffs] [stammers] [interrupts] [whispers] [yells] [crosstalk] [talking over] ...

CRITICAL RULES:
1. NEVER TAKE A SIDE. Speakers sound like they're building to a strong position... then pivot, qualify, or agree with what they just argued against. The audience keeps waiting for someone to commit - no one does.
2. The HOST introduction must be COMPLETELY PROFESSIONAL and use real facts - this is THE TRAP
3. First quarter must be GENUINELY GOOD - real research, real points, coherent arguments
4. Each speaker has a UNIQUE voice - different vocabulary, rhythm, tics
5. NO repeated phrases or terms within the script
6. Invented terminology starts subtle, becomes obviously absurd
7. The passion is for NOTHING - speakers get heated while saying nothing. "And THIS is exactly why..." followed by jargon that explains nothing.
8. Include crosstalk and people talking over each other in heated moments
9. HOST must direct the conversation - introduce speakers, ask questions, try to mediate

Return JSON:
{{
    "title": "Title about {topic}",
    "hook": "[HOST] Professional introduction of topic and guests...",
    "segments": [
        {{"text": "[SPEAKER] Dialogue...", "visual_cue": "Description"}}
    ],
    "outro": "Final exhausted exchange where HOST tries to wrap up",
    "thumbnail_text": "2-4 words",
    "description": "Description",
    "tags": ["{script_format}", "{topic}"],
    "key_phrases": ["Best nonsense", "Funniest moments"]
}}

Return ONLY valid JSON. Make it FUNNY."""

    def generate_from_outline(self, topic: str, key_points: list[str], style: str = "educational") -> VideoScript:
        points_text = "\n".join(f"- {p}" for p in key_points)

        prompt = f"""Create a YouTube video script about: {topic}

Key points to cover:
{points_text}

Style: {style}

The script is for a FACELESS YouTube channel. Return a JSON object with:
{{
    "title": "Catchy YouTube title",
    "hook": "Opening hook (2-3 sentences)",
    "segments": [
        {{"text": "Narration text", "visual_cue": "What to show"}}
    ],
    "outro": "Closing and CTA",
    "thumbnail_text": "2-4 words for thumbnail",
    "description": "YouTube description",
    "tags": ["tags"]
}}

Return ONLY valid JSON."""

        response = self._call_opencode(prompt)
        return self._parse_response(response)

    def _call_opencode(self, prompt: str, temperature: float = 0.7) -> str:
        if config.azure_openai_foundry_endpoint and config.azure_openai_foundry_key:
            return self._call_azure_openai(prompt, temperature)

        result = subprocess.run(
            [OPENCODE_PATH, "run", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(f"opencode failed: {result.stderr}")

        return result.stdout

    def _call_azure_openai(self, prompt: str, temperature: float = 0.9) -> str:
        import requests

        url = f"{config.azure_openai_foundry_endpoint}openai/deployments/{config.azure_openai_script_deployment}/chat/completions?api-version=2024-10-21"

        headers = {
            "api-key": config.azure_openai_foundry_key,
            "Content-Type": "application/json",
        }

        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_completion_tokens": 16000,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)

        if response.status_code != 200:
            raise RuntimeError(f"Azure OpenAI failed: {response.status_code} {response.text}")

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _parse_response(self, text: str) -> VideoScript:
        text = text.strip()

        if not text:
            raise RuntimeError("LLM returned empty response")

        json_match = re.search(r'\{[\s\S]*"title"[\s\S]*"segments"[\s\S]*\}', text)
        if json_match:
            text = json_match.group(0)

        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\n?', '', text)
            text = re.sub(r'\n?```$', '', text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"      JSON parse error. Raw response:\n{text[:500]}...")
            raise RuntimeError(f"Failed to parse LLM response as JSON: {e}")

        segments = []
        for seg in data.get("segments", []):
            text = seg["text"]
            text = re.sub(r'^Segment\s+\d+\.?\s*', '', text)
            text = re.sub(r'\[(?:scoffs?|laughs?|gasps?|sighs?|whispers?|chuckles?|coughs?|clears throat|pauses?)\]', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s{2,}', ' ', text).strip()
            segments.append(ScriptSegment(
                text=text,
                visual_cue=seg.get("visual_cue", ""),
                duration_hint=seg.get("duration_hint", 0)
            ))

        return VideoScript(
            title=data.get("title", ""),
            hook=data.get("hook", ""),
            segments=segments,
            outro=data.get("outro", ""),
            thumbnail_text=data.get("thumbnail_text", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            key_phrases=data.get("key_phrases", []),
        )
