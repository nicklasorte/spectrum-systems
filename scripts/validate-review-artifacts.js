#!/usr/bin/env node

/**
 * Validate Claude design review artifacts for schema compliance, pairing, and identifier alignment.
 *
 * Usage:
 *   node scripts/validate-review-artifacts.js              # validate all design review artifacts
 *   node scripts/validate-review-artifacts.js <files...>   # optionally validate a subset of action files
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
      'Ajv is required for schema validation. Install it with "npm install --no-save --no-package-lock ajv@^8 ajv-formats@^2".'
    );
  }
}

function formatAjvError(error) {
  const instancePath = error.instancePath && error.instancePath.length ? error.instancePath : '(root)';
  if (error.keyword === 'additionalProperties' && error.params?.additionalProperty) {
    return `${instancePath} has unknown property "${error.params.additionalProperty}"`;
  }
  if (error.keyword === 'required' && error.params?.missingProperty) {
    return `${instancePath} is missing required property "${error.params.missingProperty}"`;
  }
  return `${instancePath} ${error.message}`;
}

function extractMarkdownFindingIds(text) {
  const matches = [...text.matchAll(/\[F-(\d+)\]/g)];
  return new Set(matches.map((match) => `F-${match[1]}`));
}

function collectJsonFindingIds(data) {
  if (!Array.isArray(data.findings)) return {ids: [], duplicates: []};
  const counts = data.findings
    .map((item) => (item && typeof item === 'object' ? item.id : null))
    .filter(Boolean)
    .reduce((acc, id) => acc.set(id, (acc.get(id) || 0) + 1), new Map());

  const ids = Array.from(counts.keys());
  const duplicates = Array.from(counts.entries())
    .filter(([, count]) => count > 1)
    .map(([id]) => id)
    .sort();

  return {ids, duplicates};
}

function collectDueDateIssues(data, filePath) {
  const errors = [];
  const dateFields = [];

  if (Array.isArray(data.findings)) {
    for (const finding of data.findings) {
      if (finding && typeof finding === 'object' && finding.due_date !== undefined) {
        dateFields.push({
          value: finding.due_date,
          context: `${filePath} findings[id=${finding.id || 'unknown'}].due_date`,
        });
      }
    }
  }

  if (Array.isArray(data.actions)) {
    for (const action of data.actions) {
      if (action && typeof action === 'object' && action.due_date !== undefined) {
        dateFields.push({
          value: action.due_date,
          context: `${filePath} actions[id=${action.id || 'unknown'}].due_date`,
        });
      }
    }
  }

  if (data.follow_up && typeof data.follow_up === 'object' && data.follow_up.next_review_due !== undefined) {
    dateFields.push({
      value: data.follow_up.next_review_due,
      context: `${filePath} follow_up.next_review_due`,
    });
  }

  const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

  for (const field of dateFields) {
    if (typeof field.value !== 'string' || !DATE_PATTERN.test(field.value)) {
      errors.push(`${field.context} must use YYYY-MM-DD format`);
    }
  }

  return errors;
}

async function discoverArtifacts(designReviewsDir) {
  const entries = await fs.readdir(designReviewsDir);
  const markdown = [];
  const actions = [];

  for (const entry of entries) {
    if (entry.endsWith('.md') && entry !== 'README.md' && entry !== 'claude-review-template.md') {
      markdown.push(path.join(designReviewsDir, entry));
    } else if (entry.endsWith('.actions.json')) {
      actions.push(path.join(designReviewsDir, entry));
    }
  }

  return {markdown, actions};
}

function slugFromPath(filePath) {
  const base = path.basename(filePath);
  if (base.endsWith('.actions.json')) {
    return base.replace(/\.actions\.json$/, '');
  }
  if (base.endsWith('.md')) {
    return base.replace(/\.md$/, '');
  }
  return base;
}

async function validateJsonAgainstSchema(validator, filePath) {
  let data;
  try {
    const contents = await fs.readFile(filePath, 'utf8');
    data = JSON.parse(contents);
  } catch (error) {
    throw new Error(`Invalid JSON in ${filePath}: ${error.message}`);
  }

  const valid = validator(data);
  if (!valid) {
    const details = (validator.errors || []).map((err) => formatAjvError(err)).join('; ');
    throw new Error(`Schema validation failed for ${filePath}: ${details}`);
  }

  return data;
}

async function buildPairs(markdownFiles, actionFiles) {
  const markdownBySlug = new Map(markdownFiles.map((file) => [slugFromPath(file), file]));
  const actionsBySlug = new Map(actionFiles.map((file) => [slugFromPath(file), file]));
  const errors = [];
  const pairs = [];

  for (const [slug, mdPath] of markdownBySlug.entries()) {
    const actionsPath = actionsBySlug.get(slug);
    if (!actionsPath) {
      errors.push(`Missing actions JSON for markdown review: ${mdPath} (expected ${slug}.actions.json)`);
      continue;
    }
    pairs.push({slug, markdownPath: mdPath, actionsPath});
  }

  for (const [slug, actionsPath] of actionsBySlug.entries()) {
    if (!markdownBySlug.has(slug)) {
      errors.push(`Missing markdown review for actions JSON: ${actionsPath} (expected ${slug}.md)`);
    }
  }

  return {pairs, errors};
}

async function validatePair(pair, validator) {
  const errors = [];

  const markdownText = await fs.readFile(pair.markdownPath, 'utf8');
  const markdownIds = extractMarkdownFindingIds(markdownText);
  if (markdownIds.size === 0) {
    errors.push(`No finding IDs ([F-#]) found in markdown: ${pair.markdownPath}`);
  }

  let data;
  try {
    data = await validateJsonAgainstSchema(validator, pair.actionsPath);
  } catch (error) {
    errors.push(error.message);
    return errors;
  }

  const {ids: jsonIds, duplicates} = collectJsonFindingIds(data);
  if (duplicates.length) {
    errors.push(`Duplicate finding IDs in JSON ${pair.actionsPath}: ${duplicates.join(', ')}`);
  }

  const missingInJson = [...markdownIds].filter((id) => !jsonIds.includes(id));
  const missingInMarkdown = jsonIds.filter((id) => !markdownIds.has(id));

  if (missingInJson.length) {
    errors.push(
      `Finding IDs present in markdown but missing in JSON (${pair.slug}): ${missingInJson.sort().join(', ')}`
    );
  }
  if (missingInMarkdown.length) {
    errors.push(
      `Finding IDs present in JSON but missing in markdown (${pair.slug}): ${missingInMarkdown
        .sort()
        .join(', ')}`
    );
  }

  const dueDateIssues = collectDueDateIssues(data, pair.actionsPath);
  errors.push(...dueDateIssues);

  if (!errors.length) {
    console.log(`Validated ${pair.slug}: schema, ID alignment, and due dates OK`);
  }

  return errors;
}

async function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const designReviewsDir = path.join(repoRoot, 'design-reviews');
  const schemaPath = path.join(designReviewsDir, 'claude-review.schema.json');

  const args = process.argv.slice(2);
  const targetedActions = args.filter((arg) => arg.endsWith('.actions.json')).map((p) => path.resolve(p));

  const {markdown, actions} = await discoverArtifacts(designReviewsDir);
  const actionsToUse = targetedActions.length ? targetedActions : actions;
  const targetSlugs = new Set(actionsToUse.map((file) => slugFromPath(file)));
  const markdownToUse = targetedActions.length
    ? markdown.filter((file) => targetSlugs.has(slugFromPath(file)))
    : markdown;

  const {pairs, errors: pairingErrors} = await buildPairs(markdownToUse, actionsToUse);

  if (!pairs.length && !pairingErrors.length) {
    console.log('No review artifacts found to validate.');
    return;
  }

  const schemaRaw = await fs.readFile(schemaPath, 'utf8');
  const schema = JSON.parse(schemaRaw);
  const ajv = await loadAjv();
  const validator = ajv.compile(schema);

  const allErrors = [...pairingErrors];
  for (const pair of pairs) {
    const pairErrors = await validatePair(pair, validator);
    allErrors.push(...pairErrors);
  }

  if (allErrors.length) {
    console.error('Review artifact validation failed:');
    for (const message of allErrors) {
      console.error(`- ${message}`);
    }
    process.exitCode = 1;
    return;
  }

  console.log(`Success: validated ${pairs.length} review artifact pair(s).`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
