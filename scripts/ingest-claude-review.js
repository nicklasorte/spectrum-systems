#!/usr/bin/env node

/**
 * Validate Claude design review action files and create GitHub issues
 * for findings marked with `create_issue: true`.
 *
 * Usage:
 *   node scripts/ingest-claude-review.js --mode validate --schema design-reviews/claude-review.schema.json <files>
 *   node scripts/ingest-claude-review.js --mode ingest --schema design-reviews/claude-review.schema.json <files>
 */

const fs = require('fs/promises');
const path = require('path');

async function loadAjv() {
  try {
    const Ajv = (await import('ajv/dist/2020.js')).default;
    const addFormats = (await import('ajv-formats')).default;
    const ajv = new Ajv({allErrors: true, strict: false});
    addFormats(ajv);
    return ajv;
  } catch (error) {
    throw new Error(
      `Ajv is required for schema validation. Install it with "npm install --no-save --no-package-lock ajv@^8 ajv-formats@^2".\n${error.message}`
    );
  }
}

function parseArgs(argv) {
  const args = {mode: 'ingest', schema: null, files: []};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--mode' && argv[i + 1]) {
      args.mode = argv[i + 1];
      i += 1;
    } else if (arg === '--schema' && argv[i + 1]) {
      args.schema = argv[i + 1];
      i += 1;
    } else {
      args.files.push(arg);
    }
  }
  return args;
}

function formatAjvError(error) {
  const path = error.instancePath && error.instancePath.length ? error.instancePath : '(root)';
  if (error.keyword === 'additionalProperties' && error.params?.additionalProperty) {
    return `${path} has unknown property "${error.params.additionalProperty}"`;
  }
  if (error.keyword === 'required' && error.params?.missingProperty) {
    return `${path} is missing required property "${error.params.missingProperty}"`;
  }
  return `${path} ${error.message}`;
}

async function fileExists(candidatePath) {
  try {
    await fs.access(candidatePath);
    return true;
  } catch {
    return false;
  }
}

async function validateFiles(schemaPath, files) {
  if (!schemaPath) {
    throw new Error('Schema path is required for validation.');
  }
  const schemaRaw = await fs.readFile(schemaPath, 'utf8');
  const schema = JSON.parse(schemaRaw);
  const ajv = await loadAjv();
  const validate = ajv.compile(schema);

  const results = [];
  for (const file of files) {
    const content = await fs.readFile(file, 'utf8');
    let data;
    try {
      data = JSON.parse(content);
    } catch (error) {
      throw new Error(`Invalid JSON in ${file}: ${error.message}`);
    }

    const valid = validate(data);
    if (!valid) {
      const errors = validate.errors || [];
      const details = errors.map((e) => formatAjvError(e)).join('; ');
      throw new Error(`Schema validation failed for ${file}: ${details}`);
    }

    const reviewMetadata = data.review_metadata || {};
    const normalizedFilePath = path.relative(process.cwd(), path.resolve(file));
    const actionsArtifact = reviewMetadata.actions_artifact;
    if (!actionsArtifact) {
      throw new Error(`review_metadata.actions_artifact is required in ${file}`);
    }
    const normalizedActionsArtifact = path.relative(
      process.cwd(),
      path.resolve(actionsArtifact)
    );
    if (normalizedActionsArtifact !== normalizedFilePath) {
      throw new Error(
        `Actions artifact path mismatch for ${file}: review_metadata.actions_artifact is "${actionsArtifact}" but expected "${normalizedFilePath}"`
      );
    }

    const sourceArtifact = reviewMetadata.source_artifact;
    if (!sourceArtifact) {
      throw new Error(`review_metadata.source_artifact is required in ${file}`);
    }
    const resolvedSourceArtifact = path.isAbsolute(sourceArtifact)
      ? sourceArtifact
      : path.join(process.cwd(), sourceArtifact);
    if (!(await fileExists(resolvedSourceArtifact))) {
      throw new Error(
        `Paired markdown review not found at ${sourceArtifact} referenced by ${file}`
      );
    }

    const slugFromFilename = path.basename(file).replace(/\.actions\.json$/, '');
    if (reviewMetadata.review_id && reviewMetadata.review_id !== slugFromFilename) {
      throw new Error(
        `review_id "${reviewMetadata.review_id}" must match actions filename slug "${slugFromFilename}" for ${file}`
      );
    }

    results.push(data);
    console.log(`Validated ${file} against ${schemaPath}`);
  }

  return results;
}

function normalizeList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  return [value];
}

function buildIssueBody(reviewMetadata, finding, sourceFile) {
  const filesAffected = normalizeList(finding.files_affected);
  const recommendedAction = normalizeList(finding.recommended_action).join('\n') ||
    (typeof finding.recommended_action === 'string' ? finding.recommended_action : '');

  const lines = [];
  lines.push('## Claude Review Finding');
  lines.push('');
  lines.push('**Review metadata**');
  lines.push(`- Repo: ${reviewMetadata.repository || 'unknown'}`);
  lines.push(`- Review date: ${reviewMetadata.review_date || 'unknown'}`);
  lines.push(`- Model: ${reviewMetadata.model || 'unknown'}`);
  lines.push(`- Scope: ${reviewMetadata.scope || 'unknown'}`);
  lines.push(`- Trigger: ${finding.trigger || reviewMetadata.trigger || 'not specified'}`);
  lines.push('');
  lines.push('**Finding**');
  lines.push(`- ID: ${finding.id || 'N/A'}`);
  lines.push(`- Severity: ${finding.severity || 'unspecified'}`);
  lines.push(`- Category: ${finding.category || 'unspecified'}`);
  lines.push(`- Description: ${finding.description || 'No description provided.'}`);
  lines.push('');
  lines.push('**Recommended Action**');
  lines.push(recommendedAction || 'Not specified.');
  lines.push('');
  lines.push('**Files Affected**');
  if (filesAffected.length) {
    for (const file of filesAffected) {
      lines.push(`- ${file}`);
    }
  } else {
    lines.push('- Not specified');
  }
  lines.push('');
  lines.push('**Source Review File**');
  lines.push(sourceFile);

  return lines.join('\n');
}

async function createIssue(owner, repo, title, body, labels, token) {
  const response = await fetch(`https://api.github.com/repos/${owner}/${repo}/issues`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/vnd.github+json',
    },
    body: JSON.stringify({title, body, labels}),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(
      `Failed to create issue in ${owner}/${repo}: ${response.status} ${response.statusText} - ${text}`
    );
  }

  const issue = await response.json();
  console.log(`Created issue #${issue.number} in ${owner}/${repo}: ${issue.html_url}`);
}

async function ingestFindings(files, schemaPath) {
  if (!process.env.GITHUB_TOKEN) {
    throw new Error('GITHUB_TOKEN is required to create issues.');
  }

  const token = process.env.GITHUB_TOKEN;
  const validatedData = await validateFiles(schemaPath, files);

  for (let i = 0; i < files.length; i += 1) {
    const file = files[i];
    const data = validatedData[i];
    const reviewMetadata = data.review_metadata || {};
    const findings = Array.isArray(data.findings) ? data.findings : [];

    if (!findings.length) {
      console.log(`No findings marked for issue creation in ${file}.`);
      continue;
    }

    for (const finding of findings) {
      if (finding.create_issue === false) {
        continue;
      }

      const targetRepo = finding.target_repo || reviewMetadata.repository || process.env.GITHUB_REPOSITORY;
      if (!targetRepo || !targetRepo.includes('/')) {
        throw new Error(`Missing target repository for finding ${finding.id || '(unknown)'} in ${file}.`);
      }

      const [owner, repo] = targetRepo.split('/');
      const title =
        finding.suggested_issue_title ||
        (finding.id ? `Review finding ${finding.id}` : 'Claude review finding');
      const labels = Array.isArray(finding.suggested_labels)
        ? finding.suggested_labels
        : Array.isArray(finding.labels)
          ? finding.labels
          : undefined;
      const body = buildIssueBody(reviewMetadata, finding, path.relative(process.cwd(), file));

      await createIssue(owner, repo, title, body, labels, token);
    }
  }
}

async function main() {
  const {mode, schema, files} = parseArgs(process.argv.slice(2));
  if (!files.length) {
    console.log('No files provided; nothing to do.');
    return;
  }

  if (mode === 'validate') {
    await validateFiles(schema, files);
    return;
  }

  if (mode === 'ingest') {
    await ingestFindings(files, schema);
    return;
  }

  throw new Error(`Unknown mode "${mode}". Use "validate" or "ingest".`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
