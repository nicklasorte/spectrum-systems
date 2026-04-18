export const FIXTURE_VALID_TRANSCRIPT = `Alice: Good morning everyone, thanks for joining.
Bob: Hi Alice, great to be here.
Carol: Looking forward to discussing spectrum findings.
Alice: Let's start with the agenda items.
Bob: I have three major topics to cover.
Alice: Perfect, please go ahead.
Bob: First, we identified a critical process issue.
Carol: Can you elaborate on that?
Bob: Sure, it affects our deployment timeline.
Alice: What's the impact?
Bob: About two weeks delay if not addressed.
Carol: Have we identified solutions?
Alice: We should discuss mitigation strategies.
Bob: I have three proposals prepared.
Alice: Great, let's break them down.`;

export const FIXTURE_EMPTY_TRANSCRIPT = ``;

export const FIXTURE_MALFORMED_TRANSCRIPT = `This is a transcript without proper speaker labels.
Just regular text on multiple lines.
No colons or structure.
How will the parser handle this?`;

export const FIXTURE_SHORT_TRANSCRIPT = `A: Hi`;

export const FIXTURE_WITH_TIMESTAMPS = `Alice: [00:00:00] Good morning.
Bob: [00:01:30] Hi Alice.
Alice: [00:03:45] Let's begin.`;

export const FIXTURE_MANY_SPEAKERS = `Speaker1: Turn 1
Speaker2: Turn 2
Speaker3: Turn 3
Speaker4: Turn 4
Speaker5: Turn 5
Speaker1: Turn 6
Speaker2: Turn 7`;
