import { formatPaperForPublication } from "../../src/mvp-12/publication-formatter";

describe("MVP-12: Publication Formatting", () => {
  it("should format paper for publication", async () => {
    const mockDraft = {
      sections: { abstract: "Test abstract", findings: "Test findings" },
    };

    const result = await formatPaperForPublication(mockDraft, {
      title: "Test Paper",
      authors: ["Author 1"],
    });

    expect(result.success).toBe(true);
    expect(result.formatted_paper_artifact?.artifact_type).toBe("formatted_paper_artifact");
    expect(result.formatted_paper_artifact?.schema_version).toBe("1.0.0");
    expect(result.formatted_paper_artifact?.title).toBe("Test Paper");
    expect(result.formatted_paper_artifact?.content_hash.startsWith("sha256:")).toBe(true);
  });

  it("should accept draft.outputs.sections shape", async () => {
    const mockDraft = {
      outputs: { sections: { abstract: "Test", findings: "Test" } },
    };

    const result = await formatPaperForPublication(mockDraft, { title: "Alt Shape" });

    expect(result.success).toBe(true);
    expect(Object.keys(result.formatted_paper_artifact?.sections || {}).length).toBe(2);
  });

  it("should derive deterministic doi_placeholder from title", async () => {
    const r1 = await formatPaperForPublication({ sections: {} }, { title: "Same Title" });
    const r2 = await formatPaperForPublication({ sections: {} }, { title: "Same Title" });
    expect(r1.formatted_paper_artifact?.publication_metadata.doi_placeholder).toBe(
      r2.formatted_paper_artifact?.publication_metadata.doi_placeholder
    );
  });
});
