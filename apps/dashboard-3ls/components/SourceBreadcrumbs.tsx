import React from 'react';

interface Props {
  artifactPaths: string[];
  schemaPaths?: string[];
  producingScript?: string | null;
  lastValidated?: string | null;
  testid?: string;
}

const MISSING = 'Unknown / Missing';

function joinOrMissing(items: string[] | undefined): string {
  if (!items || items.length === 0) return MISSING;
  return items.join(', ');
}

export function SourceBreadcrumbs({
  artifactPaths,
  schemaPaths,
  producingScript,
  lastValidated,
  testid = 'source-breadcrumbs',
}: Props) {
  return (
    <div className="border-l-2 border-slate-300 pl-2 text-xs text-slate-700 space-y-0.5" data-testid={testid}>
      <p>
        artifact path: <span data-testid={`${testid}-artifact`}>{joinOrMissing(artifactPaths)}</span>
      </p>
      <p>
        schema path: <span data-testid={`${testid}-schema`}>{joinOrMissing(schemaPaths)}</span>
      </p>
      <p>
        producing script: <span data-testid={`${testid}-script`}>{producingScript || MISSING}</span>
      </p>
      <p>
        last validation: <span data-testid={`${testid}-validated`}>{lastValidated || MISSING}</span>
      </p>
    </div>
  );
}
