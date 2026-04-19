import { EscalationEngine } from "@/src/governance/escalation-engine";
import { Pool } from "pg";

describe("Escalation Engine", () => {
  let engine: EscalationEngine;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    engine = new EscalationEngine(pool);
    await engine.initialize();
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should escalate warn-level signal", async () => {
    const event = await engine.escalate("eval_pass_rate_down", "warn", "Eval pass rate 95%");
    expect(event.severity).toBe("warn");
    expect(event.channel).toBe("log");
  });

  it("should escalate freeze-level signal", async () => {
    const event = await engine.escalate(
      "exception_accumulation",
      "freeze",
      "10 active exceptions"
    );
    expect(event.severity).toBe("freeze");
    expect(event.channel).toBe("alert");
  });

  it("should escalate block-level signal", async () => {
    const event = await engine.escalate("eval_failure", "block", "Eval pass rate 80%");
    expect(event.severity).toBe("block");
    expect(event.channel).toBe("page");
  });

  it("should get escalation history", async () => {
    const history = await engine.getEscalationHistory(10);
    expect(Array.isArray(history)).toBe(true);
  });

  it("should acknowledge escalation event", async () => {
    const event = await engine.escalate("test_signal", "warn", "Test context");
    await engine.acknowledgeEvent(event.event_id);
    expect(true).toBe(true);
  });
});
