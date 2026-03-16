#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const GOVERNANCE_MANIFEST = ".spectrum-governance.json";
const GOVERNANCE_DECLARATION = ".governance-declaration.json";

// Required fields in a governance declaration file
const GOVERNANCE_DECLARATION_REQUIRED_FIELDS = [
  "governance_declaration_version",
  "architecture_source",
  "standards_manifest_version",
  "system_id",
  "implementation_repo",
  "declared_at",
  "contract_pins",
  "schema_pins",
  "evaluation_manifest_path",
  "last_evaluation_date",
  "external_storage_policy",
];

// Detects unfilled template placeholders like "<YOUR_SYSTEM_ID>"
function isPlaceholder(value) {
  if (typeof value !== "string") return false;
  return value.startsWith("<") && value.endsWith(">");
}

function parseArgs(argv) {
  const args = argv.slice(2);
  let configPath = null;
  let outputPath = null;
  let standardsManifestPath = null;

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--config" || arg === "-c") {
      if (i + 1 >= args.length) {
        console.error("Missing value for --config");
        process.exit(1);
      }
      configPath = args[i + 1];
      i += 1;
    } else if (arg === "--output" || arg === "-o") {
      if (i + 1 >= args.length) {
        console.error("Missing value for --output");
        process.exit(1);
      }
      outputPath = args[i + 1];
      i += 1;
    } else if (arg === "--standards-manifest") {
      if (i + 1 >= args.length) {
        console.error("Missing value for --standards-manifest");
        process.exit(1);
      }
      standardsManifestPath = args[i + 1];
      i += 1;
    } else if (!arg.startsWith("-") && !configPath) {
      configPath = arg;
    } else {
      console.error(`Unknown argument: ${arg}`);
      process.exit(1);
    }
  }

  return { configPath, outputPath, standardsManifestPath };
}

// Load contracts/standards-manifest.json from the governance repo root.
function loadStandardsManifest(manifestPath) {
  if (!manifestPath) return null;
  try {
    const content = fs.readFileSync(path.resolve(manifestPath), "utf-8");
    return JSON.parse(content);
  } catch {
    return null;
  }
}

// Build a map from artifact_type → contract entry from the standards manifest.
function buildStandardsContractMap(standards) {
  const contracts = (standards && Array.isArray(standards.contracts)) ? standards.contracts : [];
  const map = {};
  for (const contract of contracts) {
    if (contract.artifact_type) {
      map[contract.artifact_type] = contract;
    }
  }
  return map;
}

function normalizeRepoConfig(raw, index) {
  const repoConfig = {
    repo_name: raw.repo_name || raw.name,
    repo_path: raw.repo_path || raw.path,
    expected_system_id: raw.expected_system_id,
    expected_repo_type: raw.expected_repo_type,
    required_contracts: Array.isArray(raw.required_contracts) ? raw.required_contracts : [],
  };

  const missingFields = [];
  if (!repoConfig.repo_name) missingFields.push("repo_name");
  if (!repoConfig.repo_path) missingFields.push("repo_path");
  if (!repoConfig.expected_system_id) missingFields.push("expected_system_id");
  if (!repoConfig.expected_repo_type) missingFields.push("expected_repo_type");

  if (missingFields.length > 0) {
    throw new Error(
      `Repo config at index ${index} is missing required fields: ${missingFields.join(", ")}`
    );
  }

  if (
    typeof repoConfig.repo_name !== "string" ||
    typeof repoConfig.repo_path !== "string" ||
    typeof repoConfig.expected_system_id !== "string" ||
    typeof repoConfig.expected_repo_type !== "string"
  ) {
    throw new Error(`Repo config at index ${index} must use string values for all identifiers and paths.`);
  }

  if (!Array.isArray(raw.required_contracts)) {
    throw new Error(`Repo config at index ${index} must include required_contracts as an array.`);
  }

  return repoConfig;
}

function loadConfig(configPath) {
  if (!configPath) {
    console.error(
      "Usage: node run-cross-repo-compliance.js --config <config-path> [--output <output-path>]"
    );
    process.exit(1);
  }

  const resolvedPath = path.resolve(configPath);
  if (!fs.existsSync(resolvedPath)) {
    console.error(`Config not found: ${resolvedPath}`);
    process.exit(1);
  }

  try {
    const content = fs.readFileSync(resolvedPath, "utf-8");
    const parsed = JSON.parse(content);
    if (!Array.isArray(parsed.repos)) {
      throw new Error("Config must include a 'repos' array.");
    }
    return parsed.repos.map(normalizeRepoConfig);
  } catch (error) {
    console.error(`Failed to load config: ${error.message}`);
    process.exit(1);
  }
}

function pathExists(targetPath) {
  try {
    fs.accessSync(targetPath);
    return true;
  } catch {
    return false;
  }
}

function isDirectory(targetPath) {
  try {
    return fs.statSync(targetPath).isDirectory();
  } catch {
    return false;
  }
}

function hasWorkflowFiles(workflowsPath) {
  if (!isDirectory(workflowsPath)) {
    return false;
  }
  const entries = fs.readdirSync(workflowsPath);
  return entries.some((entry) => entry.endsWith(".yml") || entry.endsWith(".yaml"));
}

function readReadme(repoPath) {
  const readmePath = path.join(repoPath, "README.md");
  if (!pathExists(readmePath)) {
    return null;
  }
  return fs.readFileSync(readmePath, "utf-8");
}

function loadGovernanceManifest(manifestPath, repoName, failures) {
  try {
    const manifestRaw = fs.readFileSync(manifestPath, "utf-8");
    return JSON.parse(manifestRaw);
  } catch (error) {
    failures.push({
      severity: "error",
      type: "invalid_governance_manifest",
      repo: repoName,
      repo_path: path.dirname(manifestPath),
      detail: error.message,
    });
    return null;
  }
}

function validateManifest(manifest, repoConfig, standardsContractMap, failures) {
  if (!manifest) {
    return;
  }

  if (repoConfig.expected_system_id && manifest.system_id !== repoConfig.expected_system_id) {
    failures.push({
      severity: "error",
      type: "system_id_mismatch",
      repo: repoConfig.repo_name,
      repo_path: repoConfig.repo_path,
      expected: repoConfig.expected_system_id,
      actual: manifest.system_id,
      detail: `Expected system_id '${repoConfig.expected_system_id}' but manifest declares '${manifest.system_id}'.`,
    });
  }

  if (!manifest.contracts || typeof manifest.contracts !== "object") {
    failures.push({
      severity: "error",
      type: "contracts_section_missing",
      repo: repoConfig.repo_name,
      repo_path: repoConfig.repo_path,
      detail: "Governance manifest is missing the 'contracts' section.",
    });
    return;
  }

  // Check that required contract pins are present.
  repoConfig.required_contracts.forEach((contractName) => {
    if (!manifest.contracts[contractName]) {
      failures.push({
        severity: "error",
        type: "missing_required_contract_pin",
        repo: repoConfig.repo_name,
        repo_path: repoConfig.repo_path,
        contract: contractName,
        detail: `Required contract '${contractName}' is not pinned in the governance manifest.`,
      });
    }
  });

  // Validate pinned contract versions against the standards manifest when available.
  if (standardsContractMap && Object.keys(standardsContractMap).length > 0) {
    for (const [artifactType, pinnedVersion] of Object.entries(manifest.contracts)) {
      const standard = standardsContractMap[artifactType];
      if (!standard) {
        failures.push({
          severity: "error",
          type: "unknown_contract_pin",
          repo: repoConfig.repo_name,
          repo_path: repoConfig.repo_path,
          contract: artifactType,
          detail: `Contract '${artifactType}' is not defined in the standards manifest.`,
        });
        continue;
      }
      const canonicalVersion = standard.schema_version;
      if (pinnedVersion !== canonicalVersion) {
        failures.push({
          severity: "error",
          type: "contract_version_pin_mismatch",
          repo: repoConfig.repo_name,
          repo_path: repoConfig.repo_path,
          contract: artifactType,
          pinned_version: pinnedVersion,
          canonical_version: canonicalVersion,
          detail: `Contract '${artifactType}' is pinned at '${pinnedVersion}' but the standards manifest defines version '${canonicalVersion}'.`,
        });
      }
    }
  }
}

function validateGovernanceDeclaration(declarationPath, repoRoot, repoConfig, standardsContractMap, failures, warnings) {
  let declaration;
  try {
    declaration = JSON.parse(fs.readFileSync(declarationPath, "utf-8"));
  } catch (error) {
    failures.push({
      severity: "error",
      type: "invalid_governance_declaration",
      repo: repoConfig.repo_name,
      repo_path: repoConfig.repo_path,
      detail: `Failed to parse .governance-declaration.json: ${error.message}`,
    });
    return;
  }

  // Check required fields exist and are not placeholder values.
  for (const field of GOVERNANCE_DECLARATION_REQUIRED_FIELDS) {
    const value = declaration[field];
    if (value === undefined || value === null) {
      failures.push({
        severity: "error",
        type: "governance_declaration_missing_field",
        repo: repoConfig.repo_name,
        repo_path: repoConfig.repo_path,
        field,
        detail: `Governance declaration is missing required field '${field}'.`,
      });
      continue;
    }
    if (isPlaceholder(value)) {
      failures.push({
        severity: "error",
        type: "governance_declaration_unfilled_placeholder",
        repo: repoConfig.repo_name,
        repo_path: repoConfig.repo_path,
        field,
        detail: `Field '${field}' still contains a template placeholder: ${value}`,
      });
    }
  }

  // Validate standards_manifest_version matches if we have the standards manifest.
  if (standardsContractMap && Object.keys(standardsContractMap).length > 0) {
    // We can check contract_pins against the map.
    const contractPins = declaration.contract_pins;
    if (contractPins && typeof contractPins === "object") {
      for (const [artifactType, pinnedVersion] of Object.entries(contractPins)) {
        if (isPlaceholder(artifactType) || isPlaceholder(pinnedVersion)) continue;
        const standard = standardsContractMap[artifactType];
        if (!standard) {
          failures.push({
            severity: "error",
            type: "governance_declaration_unknown_contract_pin",
            repo: repoConfig.repo_name,
            repo_path: repoConfig.repo_path,
            contract: artifactType,
            detail: `contract_pins references '${artifactType}' which is not defined in the standards manifest.`,
          });
          continue;
        }
        const canonicalVersion = standard.schema_version;
        if (pinnedVersion !== canonicalVersion) {
          failures.push({
            severity: "error",
            type: "governance_declaration_contract_version_mismatch",
            repo: repoConfig.repo_name,
            repo_path: repoConfig.repo_path,
            contract: artifactType,
            pinned_version: pinnedVersion,
            canonical_version: canonicalVersion,
            detail: `contract_pins entry for '${artifactType}' is pinned at '${pinnedVersion}' but the standards manifest defines version '${canonicalVersion}'.`,
          });
        }
      }
    }
  }

  // Validate schema_pins: each referenced file path must exist relative to the governance repo root.
  const schemaPins = declaration.schema_pins;
  if (schemaPins && typeof schemaPins === "object") {
    for (const [schemaPath, _schemaVersion] of Object.entries(schemaPins)) {
      if (isPlaceholder(schemaPath)) continue;
      const resolvedSchemaPath = path.resolve(repoRoot, schemaPath);
      if (!pathExists(resolvedSchemaPath)) {
        failures.push({
          severity: "error",
          type: "governance_declaration_schema_pin_missing",
          repo: repoConfig.repo_name,
          repo_path: repoConfig.repo_path,
          schema_path: schemaPath,
          detail: `schema_pins references '${schemaPath}' which does not exist in the governance repo.`,
        });
      }
    }
  }

  // Warn if this looks like a stale declaration (very old last_evaluation_date).
  const lastEval = declaration.last_evaluation_date;
  if (lastEval && !isPlaceholder(lastEval)) {
    const evalDate = new Date(lastEval);
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    if (!isNaN(evalDate.getTime()) && evalDate < oneYearAgo) {
      warnings.push(
        `Governance declaration last_evaluation_date '${lastEval}' is more than one year old.`
      );
    }
  }
}

function checkRepo(repoConfig, repoRoot, standardsContractMap) {
  const repoPath = path.resolve(repoConfig.repo_path);
  const missingRequirements = [];
  const warnings = [];
  const failures = [];

  // If the repo path doesn't exist, mark it as not_yet_enforceable rather than failing.
  if (!isDirectory(repoPath)) {
    return {
      repo_name: repoConfig.repo_name,
      repo_path: repoPath,
      expected_system_id: repoConfig.expected_system_id,
      expected_repo_type: repoConfig.expected_repo_type,
      status: "not_yet_enforceable",
      compliant: false,
      missing_requirements: ["repository path not found or not yet cloned"],
      failures: [],
      warnings: [],
    };
  }

  const requiredFiles = ["README.md", "CLAUDE.md", "CODEX.md", "SYSTEMS.md"];
  const requiredDirectories = ["docs", "tests"];

  requiredFiles.forEach((fileName) => {
    if (!pathExists(path.join(repoPath, fileName))) {
      missingRequirements.push(fileName);
    }
  });

  requiredDirectories.forEach((dirName) => {
    const dirPath = path.join(repoPath, dirName);
    if (!isDirectory(dirPath)) {
      missingRequirements.push(`${dirName}/`);
    }
  });

  const readmeContent = readReadme(repoPath);
  if (readmeContent) {
    if (!readmeContent.toLowerCase().includes("spectrum-systems")) {
      warnings.push("README missing reference to spectrum-systems");
    }
  }

  const workflowsPath = path.join(repoPath, ".github", "workflows");
  if (!hasWorkflowFiles(workflowsPath)) {
    warnings.push("GitHub workflows directory missing or empty");
  }

  const manifestPath = path.join(repoPath, GOVERNANCE_MANIFEST);
  let manifest = null;
  if (!pathExists(manifestPath)) {
    failures.push({
      severity: "error",
      type: "missing_governance_manifest",
      repo: repoConfig.repo_name,
      repo_path: repoPath,
      detail: `Expected '${GOVERNANCE_MANIFEST}' not found in repository root.`,
    });
  } else {
    manifest = loadGovernanceManifest(manifestPath, repoConfig.repo_name, failures);
    validateManifest(manifest, repoConfig, standardsContractMap, failures);
  }

  // If a governance declaration file exists, validate it too.
  const declarationPath = path.join(repoPath, GOVERNANCE_DECLARATION);
  if (pathExists(declarationPath)) {
    validateGovernanceDeclaration(
      declarationPath,
      repoRoot,
      repoConfig,
      standardsContractMap,
      failures,
      warnings
    );
  }

  const isCompliant = missingRequirements.length === 0 && failures.length === 0;
  let status;
  if (isCompliant) {
    status = warnings.length > 0 ? "warning" : "pass";
  } else {
    status = "fail";
  }

  return {
    repo_name: repoConfig.repo_name,
    repo_path: repoPath,
    expected_system_id: repoConfig.expected_system_id,
    expected_repo_type: repoConfig.expected_repo_type,
    status,
    compliant: isCompliant,
    missing_requirements: missingRequirements,
    failures,
    warnings,
  };
}

function printHumanSummary(report) {
  const statusCounts = { pass: 0, fail: 0, warning: 0, not_yet_enforceable: 0 };
  for (const repo of report.repos) {
    const s = repo.status || (repo.compliant ? "pass" : "fail");
    statusCounts[s] = (statusCounts[s] || 0) + 1;
  }

  console.log("");
  console.log("=== Cross-Repo Compliance Scan Results ===");
  console.log(`Scan date   : ${report.scan_date}`);
  console.log(`Repos in config : ${report.repos.length}`);
  console.log(`  PASS               : ${statusCounts.pass}`);
  console.log(`  FAIL               : ${statusCounts.fail}`);
  console.log(`  WARNING            : ${statusCounts.warning}`);
  console.log(`  NOT YET ENFORCEABLE: ${statusCounts.not_yet_enforceable}`);
  console.log("");

  for (const repo of report.repos) {
    const s = (repo.status || "fail").toUpperCase().replace(/_/g, " ");
    console.log(`── ${repo.repo_name} [${s}]`);

    if (repo.status === "not_yet_enforceable") {
      console.log(`   ⚠ Repository path not accessible; validation deferred until repo is cloned.`);
      continue;
    }

    for (const req of repo.missing_requirements || []) {
      console.log(`   ✗ MISSING REQUIREMENT: ${req}`);
    }
    for (const failure of repo.failures || []) {
      const label = failure.type ? failure.type.toUpperCase() : "ERROR";
      console.log(`   ✗ ${label}: ${failure.detail || JSON.stringify(failure)}`);
    }
    for (const warning of repo.warnings || []) {
      console.log(`   ⚠ WARNING: ${warning}`);
    }
    if (repo.status === "pass") {
      console.log(`   ✓ All checks passed.`);
    }
  }
  console.log("");
}

function run() {
  const { configPath, outputPath, standardsManifestPath } = parseArgs(process.argv);
  const repoRoot = process.cwd();

  const resolvedManifestPath =
    standardsManifestPath ||
    path.join(repoRoot, "contracts", "standards-manifest.json");
  const standards = loadStandardsManifest(resolvedManifestPath);
  const standardsContractMap = buildStandardsContractMap(standards);

  if (!standards) {
    console.error(
      `Warning: standards manifest not found at '${resolvedManifestPath}'. Contract version pin validation will be skipped.`
    );
  }

  const repos = loadConfig(configPath);
  const results = repos.map((repo) => checkRepo(repo, repoRoot, standardsContractMap));

  const report = {
    schema_version: "1.0.0",
    scan_date: new Date().toISOString().slice(0, 10),
    repos: results,
  };

  if (outputPath) {
    const resolvedOutput = path.resolve(outputPath);
    fs.writeFileSync(resolvedOutput, JSON.stringify(report, null, 2));
    printHumanSummary(report);
  } else {
    console.log(JSON.stringify(report, null, 2));
  }
}

run();
