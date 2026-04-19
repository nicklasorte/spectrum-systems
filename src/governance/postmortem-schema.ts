import { v4 as uuidv4 } from "uuid";

/**
 * Postmortem Schema
 * Structured capture of incident root causes, actions, and links
 */

export interface PostmortemArtifact {
  artifact_kind: "postmortem_artifact";
  artifact_id: string;
  incident_id: string;
  failed_artifact_id: string;
  failed_at: string;
  root_causes: RootCause[];
  actions: Action[];
  timeline: TimelineEvent[];
  linked_artifacts: {
    artifact_id: string;
    artifact_kind: string;
    relationship: "caused_by" | "contributed_to" | "detected_by";
  }[];
  owner: string;
  severity: "S0" | "S1" | "S2" | "S3" | "S4";
  created_at: string;
  status: "open" | "in_progress" | "resolved";
  due_date?: string;
}

export interface RootCause {
  root_cause_id: string;
  category: "schema_violation" | "policy_violation" | "eval_failure" | "drift" | "human_error" | "unknown";
  description: string;
  confidence: number;
  evidence: string[];
}

export interface Action {
  action_id: string;
  title: string;
  description: string;
  action_type: "immediate" | "preventive" | "detective" | "corrective";
  owner: string;
  due_date: string;
  status: "not_started" | "in_progress" | "completed" | "blocked";
  linked_policy_ids?: string[];
  linked_eval_ids?: string[];
}

export interface TimelineEvent {
  timestamp: string;
  event_type: string;
  description: string;
  artifact_id?: string;
}

export function createPostmortem(
  incidentId: string,
  failedArtifactId: string,
  owner: string,
  severity: "S0" | "S1" | "S2" | "S3" | "S4"
): PostmortemArtifact {
  return {
    artifact_kind: "postmortem_artifact",
    artifact_id: uuidv4(),
    incident_id: incidentId,
    failed_artifact_id: failedArtifactId,
    failed_at: new Date().toISOString(),
    root_causes: [],
    actions: [],
    timeline: [],
    linked_artifacts: [],
    owner,
    severity,
    created_at: new Date().toISOString(),
    status: "open",
  };
}

export function addRootCause(
  postmortem: PostmortemArtifact,
  category: RootCause["category"],
  description: string,
  evidence: string[],
  confidence: number
): void {
  postmortem.root_causes.push({
    root_cause_id: uuidv4(),
    category,
    description,
    confidence,
    evidence,
  });
}

export function addAction(
  postmortem: PostmortemArtifact,
  title: string,
  description: string,
  actionType: Action["action_type"],
  owner: string,
  dueDate: string
): void {
  postmortem.actions.push({
    action_id: uuidv4(),
    title,
    description,
    action_type: actionType,
    owner,
    due_date: dueDate,
    status: "not_started",
  });
}
