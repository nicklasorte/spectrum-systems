#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const GOVERNANCE_MANIFEST = ".spectrum-governance.json";

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
    console.error("Usage: node run-cross-repo-compliance.js <config-path>");
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

function validateManifest(manifest, repoConfig, failures) {
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
    });
  }

  if (!manifest.contracts || typeof manifest.contracts !== "object") {
    failures.push({
      severity: "error",
      type: "contracts_section_missing",
      repo: repoConfig.repo_name,
      repo_path: repoConfig.repo_path,
    });
    return;
  }

  repoConfig.required_contracts.forEach((contractName) => {
    if (!manifest.contracts[contractName]) {
      failures.push({
        severity: "error",
        type: "missing_required_contract_pin",
        repo: repoConfig.repo_name,
        repo_path: repoConfig.repo_path,
        contract: contractName,
      });
    }
  });
}

function checkRepo(repoConfig) {
  const repoPath = path.resolve(repoConfig.repo_path);
  const missingRequirements = [];
  const warnings = [];
  const failures = [];

  if (!isDirectory(repoPath)) {
    missingRequirements.push("repository path not found");
    return {
      repo_name: repoConfig.repo_name,
      repo_path: repoPath,
      compliant: false,
      missing_requirements: missingRequirements,
      failures,
      warnings,
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
    });
  } else {
    manifest = loadGovernanceManifest(manifestPath, repoConfig.repo_name, failures);
    validateManifest(manifest, repoConfig, failures);
  }

  return {
    repo_name: repoConfig.repo_name,
    repo_path: repoPath,
    expected_system_id: repoConfig.expected_system_id,
    expected_repo_type: repoConfig.expected_repo_type,
    compliant: missingRequirements.length === 0 && failures.length === 0,
    missing_requirements: missingRequirements,
    failures,
    warnings,
  };
}

function run() {
  const repos = loadConfig(process.argv[2]);
  const results = repos.map(checkRepo);

  const report = {
    schema_version: "1.0.0",
    scan_date: new Date().toISOString().slice(0, 10),
    repos: results,
  };

  console.log(JSON.stringify(report, null, 2));
}

run();
