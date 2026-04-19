import { buildEscalationContext, formatEscalationMessage } from "@/src/governance/escalation-engine-enhanced";

describe("Fix Slice #7: Playbook Tracking + Enhanced Escalation", () => {
  it("should build escalation context with full details", () => {
    const context = buildEscalationContext("metric_distribution", "artifact-123", "trace-456", 105.5, 100);

    expect(context).toContain("artifact-123");
    expect(context).toContain("5.5%");
    expect(context).toContain("/dashboard/artifacts/");
  });

  it("should calculate shift percentage correctly", () => {
    const context = buildEscalationContext("test", "art-1", "trace-1", 120, 100);
    expect(context).toContain("20.0%");
  });

  it("should format escalation message with severity", () => {
    const msg = formatEscalationMessage("warn", "test_signal", "context info", "art-123");
    expect(msg).toContain("WARN");
    expect(msg).toContain("test_signal");
    expect(msg).toContain("art-123");
  });

  it("should use correct emoji for block severity", () => {
    const msg = formatEscalationMessage("block", "critical_issue", "details", "art-1");
    expect(msg).toContain("🛑");
  });

  it("should use correct emoji for freeze severity", () => {
    const msg = formatEscalationMessage("freeze", "frozen_status", "details", "art-1");
    expect(msg).toContain("🔒");
  });

  it("should use correct emoji for warn severity", () => {
    const msg = formatEscalationMessage("warn", "warning_status", "details", "art-1");
    expect(msg).toContain("⚠️");
  });
});
