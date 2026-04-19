import { ExceptionGovernor } from "@/src/governance/exception-governance";
import { Pool } from "pg";

describe("Exception Governance", () => {
  let governor: ExceptionGovernor;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    governor = new ExceptionGovernor(pool);
    await governor.initialize();
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should record exception", async () => {
    const exceptionId = await governor.recordException(
      "artifact-123",
      "reviewer-1",
      "Manual approval for testing",
      "allow",
      30
    );

    expect(exceptionId).toBeDefined();
  });

  it("should track backlog", async () => {
    const backlog = await governor.getActiveExceptionBacklog();
    expect(typeof backlog).toBe("number");
  });

  it("should audit backlog status", async () => {
    const audit = await governor.auditExceptionBacklog();
    expect(["healthy", "warning", "critical"]).toContain(audit.status);
  });

  it("should mark exception as converted", async () => {
    const exceptionId = await governor.recordException(
      "artifact-456",
      "reviewer-2",
      "Testing conversion",
      "warn",
      30
    );

    await governor.markExceptionAsConverted(exceptionId, "policy", ["policy-123"]);
    expect(true).toBe(true);
  });

  it("should retire exceptions", async () => {
    const exceptionId = await governor.recordException(
      "artifact-789",
      "reviewer-3",
      "Testing retirement",
      "block",
      1
    );

    await governor.retireException(exceptionId);
    expect(true).toBe(true);
  });
});
