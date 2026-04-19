import { formatPaperForPublication } from "@/src/mvp-12/publication-formatter";

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
    expect(result.formatted_paper_artifact?.title).toBe("Test Paper");
  });
});
