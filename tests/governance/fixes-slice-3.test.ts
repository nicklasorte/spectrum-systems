import { tailorDriftRecommendations } from "@/src/governance/drift-detector-safe";

describe("Fix Slice #3: Drift Detection Safety", () => {
  it("should provide tailored recommendations per drift type", () => {
    const recs = tailorDriftRecommendations("decision_divergence");
    expect(recs.length).toBeGreaterThan(0);
    expect(recs[0]).toContain("outcome");
  });

  it("should provide metric-specific recommendations", () => {
    const recs = tailorDriftRecommendations("metric_distribution");
    expect(recs[0]).toContain("upstream");
  });
});
