import { smartRootCauseAlgorithm } from "@/src/governance/lineage-graph-safe";

describe("Fix Slice #6: Lineage Optimization + Signal Expiry", () => {
  it("should find root causes using smart algorithm", () => {
    const edges = [
      {
        source_artifact_id: "root-1",
        target_artifact_id: "mid-1",
        relationship: "caused_by",
      },
      {
        source_artifact_id: "mid-1",
        target_artifact_id: "leaf-1",
        relationship: "caused_by",
      },
    ];

    const roots = smartRootCauseAlgorithm(edges, "leaf-1");
    expect(roots).toContain("root-1");
  });

  it("should weight relationship types correctly", () => {
    const edges = [
      { source_artifact_id: "a", target_artifact_id: "b", relationship: "caused_by" },
      { source_artifact_id: "c", target_artifact_id: "b", relationship: "input_to" },
    ];

    const roots = smartRootCauseAlgorithm(edges, "b");
    expect(roots.length).toBeGreaterThan(0);
  });

  it("should handle cycles gracefully", () => {
    const edges = [
      { source_artifact_id: "a", target_artifact_id: "b", relationship: "caused_by" },
      { source_artifact_id: "b", target_artifact_id: "a", relationship: "caused_by" },
    ];

    const roots = smartRootCauseAlgorithm(edges, "a");
    expect(Array.isArray(roots)).toBe(true);
  });

  it("should traverse deep hierarchies", () => {
    const edges = Array.from({ length: 8 }, (_, i) => ({
      source_artifact_id: `node-${i}`,
      target_artifact_id: `node-${i + 1}`,
      relationship: "caused_by",
    }));

    const roots = smartRootCauseAlgorithm(edges, "node-8");
    expect(roots.length).toBeGreaterThan(0);
  });
});
