from __future__ import annotations

from pathlib import Path
import sys

README_PATH = Path("README.md")
START_MARKER = "<!-- SSOS_MENTAL_MAP_START -->"
END_MARKER = "<!-- SSOS_MENTAL_MAP_END -->"

SECTION_BODY = """## Mental Map System View

```text
                           ┌──────────────────────┐
                           │    system-factory    │
                           │ repo scaffolding     │
                           └──────────┬───────────┘
                                      │
                                      v
                           ┌──────────────────────┐
                           │   spectrum-systems   │
                           │ constitution / law   │
                           │ schemas, rules,      │
                           │ prompts, workflows   │
                           └──────────┬───────────┘
                                      │ governs
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        v                             v                             v
┌──────────────────┐       ┌──────────────────────┐       ┌──────────────────────┐
│ spectrum-data-   │       │ spectrum-pipeline-   │       │ spectrum-program-    │
│ lake             │<----->│ engine               │<---   │ engine               │<----->│ advisor              │
│ raw + normalized │       │ orchestration        │       │ PM / risk / cadence  │
│ artifact store   │       │ runs workflows       │       │ guidance             │
└────────┬─────────┘       └──────────┬───────────┘       └──────────────────────┘
         │                             │
         │ feeds                       │ invokes
         │                             │
         v                             v
┌──────────────────┐       ┌──────────────────────┐
│ meeting-minutes- │       │ meeting-agenda-      │
│ engine           │       │ engine               │
│ transcript ->    │       │ minutes/comments/    │
│ notes/decisions  │       │ open issues -> agenda│
└────────┬─────────┘       └──────────────────────┘
         │
         │ derives
         v
┌──────────────────┐
│ FAQ / knowledge  │
│ engine           │
│ transcript +     │
│ comments + notes │
│ -> report-ready  │
│ Q/A + claims     │
└────────┬─────────┘
         │
         │ informs
         v
┌─────────────────────────┐      ┌────────────────────────┐
│ working-paper-review-   │ - report-ready  │
│ Q/A + claims     │
└────────┬─────────┘
         │
         │ informs
         v
┌─────────────────────────┐      ┌────────────────────────┐
│ working-paper-review-   │ ---> │ comment-resolution-    │
│ engine                  │      │ engine                 │
│ PDF -> reviewer matrix  │      │ resolve/adjudicate     │
└──────────┬──────────────┘      └──────────┬─────────────┘
           │                                 │
           │ resolved comments               │ approved changes
           v                                 v
      ┌─────────────────────────────────────────────────────┐
      │        docx-comment-injection-engine                │
      │      matrix + line refs -> Word comments            │
      └──────────────────────┬──────────────────────────────┘
                             │
                             v
                  ┌──────────────────────────┐
                  │ report-compiler          │
                  │ approved text blocks,    │
                  │ FAQs, decisions, notes,  │
                  │ adjudications -> report  │
                  └──────────────────────────┘
```
"""


def build_section() -> str:
    return f"{START_MARKER}\n{SECTION_BODY.strip()}\n{END_MARKER}\n"


def update_readme() -> None:
    if not README_PATH.exists():
        sys.stderr.write("README.md not found. Run this script from the repository root.\n")
        raise SystemExit(1)

    readme_text = README_PATH.read_text(encoding="utf-8")
    new_section = build_section()

    start_index = readme_text.find(START_MARKER)
    end_index = readme_text.find(END_MARKER)

    if start_index != -1 and end_index != -1 and end_index > start_index:
        end_index += len(END_MARKER)
        updated_text = f"{readme_text[:start_index]}{new_section}{readme_text[end_index:]}"
    else:
        separator = "" if readme_text.endswith("\n") else "\n"
        updated_text = f"{readme_text}{separator}\n{new_section}"

    README_PATH.write_text(updated_text, encoding="utf-8")
    print("README.md mental map section updated successfully.")


if __name__ == "__main__":
    update_readme()
