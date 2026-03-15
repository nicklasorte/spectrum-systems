#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

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
    return parsed.repos;
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

function checkRepo(repoConfig) {
  const repoPath = path.resolve(repoConfig.path);
  const missingRequirements = [];
  const warnings = [];

  if (!isDirectory(repoPath)) {
    missingRequirements.push("repository path not found");
    return {
      repo_name: repoConfig.name,
      repo_path: repoPath,
      compliant: false,
      missing_requirements: missingRequirements,
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

  return {
    repo_name: repoConfig.name,
    repo_path: repoPath,
    compliant: missingRequirements.length === 0,
    missing_requirements: missingRequirements,
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
