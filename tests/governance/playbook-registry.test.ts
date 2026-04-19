import { PlaybookRegistry } from "@/src/governance/playbook-registry";

describe("Playbook Registry", () => {
  let registry: PlaybookRegistry;

  beforeEach(() => {
    registry = new PlaybookRegistry();
  });

  it("should get playbook for drift signal", async () => {
    const playbook = await registry.getPlaybookForSignal("signal_type", "metric_distribution");
    expect(playbook).toBeDefined();
    expect(playbook?.steps.length).toBeGreaterThan(0);
  });

  it("should get playbooks for freeze severity", async () => {
    const playbooks = await registry.getPlaybooksForSeverity("freeze");
    expect(playbooks.length).toBeGreaterThan(0);
    expect(playbooks[0].playbook_name).toBe("exception_accumulation_critical");
  });

  it("should get playbooks for block severity", async () => {
    const playbooks = await registry.getPlaybooksForSeverity("block");
    expect(playbooks.length).toBeGreaterThan(0);
    expect(playbooks[0].playbook_name).toBe("eval_pass_rate_block");
  });

  it("should have complete playbook steps", async () => {
    const playbook = await registry.getPlaybookForSignal("signal_type", "metric_distribution");
    if (playbook) {
      expect(playbook.steps.every((s) => s.action && s.responsible_role)).toBe(true);
    }
  });

  it("should validate step ordering", async () => {
    const playbook = await registry.getPlaybookForSignal("reason_code", "exception_backlog_critical");
    if (playbook) {
      const orders = playbook.steps.map((s) => s.order);
      expect(orders).toEqual([...orders].sort((a, b) => a - b));
    }
  });
});
