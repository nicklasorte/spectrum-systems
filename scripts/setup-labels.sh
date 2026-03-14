#!/usr/bin/env bash

set -e

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

create_label () {
  gh label create "$1" \
    --color "$2" \
    --description "$3" \
    --repo "$REPO" \
    2>/dev/null || echo "Label $1 already exists"
}

echo "Creating SSOS labels..."

# Artifact labels
create_label "artifact:transcript" "1D76DB" "Raw meeting transcript"
create_label "artifact:minutes" "1D76DB" "Meeting minutes artifact"
create_label "artifact:agenda" "1D76DB" "Meeting agenda artifact"
create_label "artifact:working-paper" "0E8A16" "Working paper artifact"
create_label "artifact:comment-matrix" "0E8A16" "Agency comment matrix"
create_label "artifact:faq" "5319E7" "FAQ entry derived from meetings"
create_label "artifact:report-section" "5319E7" "Report-ready text section"
create_label "artifact:decision" "BFD4F2" "Formal decision artifact"

# System layer labels
create_label "layer:factory" "AAAAAA" "System factory layer"
create_label "layer:governance" "6F42C1" "Architecture and standards layer"
create_label "layer:orchestrator" "0052CC" "Pipeline orchestration layer"
create_label "layer:engine" "0E8A16" "Operational processing engine"
create_label "layer:knowledge" "FBCA04" "Knowledge or artifact storage"
create_label "layer:advisor" "D93F0B" "Program advisor layer"

# Study / band labels
create_label "study:7ghz" "C2E0C6" "7 GHz spectrum study"
create_label "study:4.4ghz" "C2E0C6" "4.4–4.94 GHz study"
create_label "study:2.7ghz" "C2E0C6" "2.7 GHz study"
create_label "study:system" "C2E0C6" "SSOS system work"

# Priority labels
create_label "priority:critical" "B60205" "Critical priority"
create_label "priority:high" "D93F0B" "High priority"
create_label "priority:medium" "FBCA04" "Medium priority"
create_label "priority:low" "0E8A16" "Low priority"

echo "SSOS labels created."
