export const FIXTURE_VALID_TRANSCRIPT = `Alice: [00:00:00] Good morning everyone, thanks for joining today.
Bob: Hi Alice, great to be here for this discussion.
Carol: [00:01:15] Looking forward to reviewing the spectrum findings together.
Alice: Let's start with the agenda items we prepared.
Bob: [00:02:30] I have three major topics to cover in this session.
Alice: Perfect, please go ahead with the first one.
Carol: Should we also review last week's action items before diving in?
Bob: [00:03:45] Good point Carol, I have prepared notes on those as well.`;

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
