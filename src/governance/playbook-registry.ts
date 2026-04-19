/**
 * Playbook Registry
 * Maps reason codes and signal types to response workflows
 */

let stepCounter = 0;
function generateStepId(): string {
  return `step-${++stepCounter}`;
}

let playbookCounter = 0;
function generatePlaybookId(): string {
  return `playbook-${++playbookCounter}`;
}

export interface Playbook {
  playbook_id: string;
  playbook_name: string;
  trigger_type: "reason_code" | "signal_type" | "severity_level";
  trigger_value: string;
  steps: PlaybookStep[];
  owner: string;
  created_at: string;
  status: "active" | "deprecated";
}

export interface PlaybookStep {
  step_id: string;
  order: number;
  action: string;
  context: string;
  responsible_role: string;
  estimated_duration_minutes?: number;
}

export const DEFAULT_PLAYBOOKS: Omit<Playbook, "playbook_id" | "created_at">[] = [
  {
    playbook_name: "drift_metric_distribution",
    trigger_type: "signal_type",
    trigger_value: "metric_distribution",
    steps: [
      {
        step_id: generateStepId(),
        order: 1,
        action: "Investigate upstream changes",
        context: "Check model version, policy changes, context bundle updates in last 24h",
        responsible_role: "SRE",
        estimated_duration_minutes: 15,
      },
      {
        step_id: generateStepId(),
        order: 2,
        action: "Compare metrics to baseline",
        context: "Query artifact_intelligence for eval_pass_rate, cost_per_run trends",
        responsible_role: "SRE",
        estimated_duration_minutes: 10,
      },
      {
        step_id: generateStepId(),
        order: 3,
        action: "Decide: proceed or freeze",
        context: "If shift > 20%, freeze pipeline. If shift < 5%, continue monitoring.",
        responsible_role: "Team Lead",
        estimated_duration_minutes: 5,
      },
    ],
    owner: "governance-team",
    status: "active",
  },
  {
    playbook_name: "exception_accumulation_critical",
    trigger_type: "reason_code",
    trigger_value: "exception_backlog_critical",
    steps: [
      {
        step_id: generateStepId(),
        order: 1,
        action: "FREEZE promotion",
        context: "Stop all artifact promotion until backlog < 5",
        responsible_role: "CI/Orchestration",
        estimated_duration_minutes: 0,
      },
      {
        step_id: generateStepId(),
        order: 2,
        action: "Alert engineering lead",
        context: "Send emergency notification, escalate to team lead",
        responsible_role: "CI/Orchestration",
        estimated_duration_minutes: 5,
      },
      {
        step_id: generateStepId(),
        order: 3,
        action: "Review exception backlog",
        context: "Categorize: convert to policy, retire, or extend",
        responsible_role: "Engineering Lead",
        estimated_duration_minutes: 30,
      },
      {
        step_id: generateStepId(),
        order: 4,
        action: "UNFREEZE promotion",
        context: "Once backlog resolved, resume normal operations",
        responsible_role: "Engineering Lead",
        estimated_duration_minutes: 5,
      },
    ],
    owner: "governance-team",
    status: "active",
  },
  {
    playbook_name: "eval_pass_rate_block",
    trigger_type: "reason_code",
    trigger_value: "eval_pass_rate_block",
    steps: [
      {
        step_id: generateStepId(),
        order: 1,
        action: "BLOCK promotion",
        context: "Eval pass rate fell below 90%. No artifacts promoted until fixed.",
        responsible_role: "CI/Orchestration",
        estimated_duration_minutes: 0,
      },
      {
        step_id: generateStepId(),
        order: 2,
        action: "Create postmortem",
        context: "Capture root cause (model change, eval case regression, policy change)",
        responsible_role: "On-Call Engineer",
        estimated_duration_minutes: 20,
      },
      {
        step_id: generateStepId(),
        order: 3,
        action: "Investigate & fix",
        context: "Revert change, update policy, add eval case, or retrain model",
        responsible_role: "Engineering Team",
        estimated_duration_minutes: 60,
      },
      {
        step_id: generateStepId(),
        order: 4,
        action: "Verify fix",
        context: "Run evals again, confirm pass_rate > 95%",
        responsible_role: "On-Call Engineer",
        estimated_duration_minutes: 15,
      },
    ],
    owner: "governance-team",
    status: "active",
  },
];

export class PlaybookRegistry {
  private playbooks: Map<string, Playbook> = new Map();

  constructor() {
    for (const pb of DEFAULT_PLAYBOOKS) {
      const playbook: Playbook = {
        playbook_id: generatePlaybookId(),
        ...pb,
        created_at: new Date().toISOString(),
      };
      this.playbooks.set(`${pb.trigger_type}:${pb.trigger_value}`, playbook);
    }
  }

  async getPlaybookForSignal(
    triggerType: string,
    triggerValue: string
  ): Promise<Playbook | null> {
    return this.playbooks.get(`${triggerType}:${triggerValue}`) || null;
  }

  async getPlaybooksForSeverity(severity: "warn" | "freeze" | "block"): Promise<Playbook[]> {
    const playbookMap: Record<string, string[]> = {
      warn: ["drift_metric_distribution"],
      freeze: ["exception_accumulation_critical"],
      block: ["eval_pass_rate_block"],
    };

    return Array.from(this.playbooks.values()).filter((pb) =>
      playbookMap[severity]?.includes(pb.playbook_name)
    );
  }
}
