# SSOS GitHub Project Automation

This workflow keeps issues in sync with the SSOS GitHub Project v2 when they open or close.

## Required repository secret
- `PROJECT_TOKEN`

## Required repository variables
- `SSOS_PROJECT_ID`
- `SSOS_LIFECYCLE_FIELD_ID`
- `SSOS_RAW_EVIDENCE_OPTION_ID`
- `SSOS_COMPLETE_OPTION_ID`

## Fetching IDs with GitHub CLI and GraphQL
Run this query to fetch the project ID, fields, and single-select option IDs:

```bash
gh api graphql -f query='
query($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) {
      id
      title
      fields(first: 50) {
        nodes {
          ... on ProjectV2FieldCommon {
            id
            name
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
            }
          }
        }
      }
    }
  }
}' -F owner='nicklasorte' -F number=2
```

## ID mapping
- `SSOS_PROJECT_ID` is the ProjectV2 ID.
- `SSOS_LIFECYCLE_FIELD_ID` is the field ID for `Lifecycle Stage`.
- `SSOS_RAW_EVIDENCE_OPTION_ID` is the option ID for `Raw Evidence`.
- `SSOS_COMPLETE_OPTION_ID` is the option ID for `Complete`.

## Troubleshooting
- Missing secret: ensure `PROJECT_TOKEN` is added as a repository secret.
- Missing variables: set all four repository variables listed above.
- Issue not yet found in project: allow a moment after open/close events; the workflow adds the item on open.
- Insufficient token scope: `PROJECT_TOKEN` must have access to read issues and update the target project.
