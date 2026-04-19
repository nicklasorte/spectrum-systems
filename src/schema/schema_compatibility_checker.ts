/**
 * Schema Compatibility Checker
 * Validates schema evolution rules and backward compatibility
 */

import { ArtifactSchema } from "./artifact_schema_validator";

export interface CompatibilityCheckResult {
  compatible: boolean;
  breaking_changes: BreakingChange[];
  warnings: string[];
  migration_required: boolean;
  migration_strategy?: string;
}

export interface BreakingChange {
  change_type:
    | "required_field_removed"
    | "field_type_changed"
    | "field_constraint_tightened"
    | "enum_values_removed";
  field_name?: string;
  old_constraint?: string;
  new_constraint?: string;
  impact: "high" | "medium" | "low";
  remediation: string;
}

export function checkSchemaCompatibility(
  oldSchema: ArtifactSchema,
  newSchema: ArtifactSchema
): CompatibilityCheckResult {
  const breakingChanges: BreakingChange[] = [];
  const warnings: string[] = [];

  // Check required fields
  const oldRequired = new Set(oldSchema.required_fields);
  const newRequired = new Set(newSchema.required_fields);

  // New required fields = backward incompatible for old artifacts
  const newRequiredFields = Array.from(newRequired).filter(
    (f) => !oldRequired.has(f)
  );
  if (newRequiredFields.length > 0) {
    for (const field of newRequiredFields) {
      breakingChanges.push({
        change_type: "required_field_removed",
        field_name: field,
        new_constraint: "required",
        impact: "high",
        remediation: `Provide default value for ${field} or make it optional`,
      });
    }
  }

  // Old required fields removed = breaking change
  const removedRequired = Array.from(oldRequired).filter(
    (f) => !newRequired.has(f)
  );
  if (removedRequired.length > 0) {
    for (const field of removedRequired) {
      warnings.push(`Previously required field ${field} is no longer required`);
    }
  }

  // Check JSON Schema constraints (simplified check)
  const oldProps = getSchemaProperties(oldSchema.json_schema);
  const newProps = getSchemaProperties(newSchema.json_schema);

  for (const [fieldName, oldProp] of Object.entries(oldProps)) {
    const newProp = newProps[fieldName];
    if (!newProp) {
      warnings.push(`Field ${fieldName} was removed from schema`);
      continue;
    }

    // Check type compatibility
    const oldType = getPropertyType(oldProp as any);
    const newType = getPropertyType(newProp as any);
    if (oldType !== newType) {
      breakingChanges.push({
        change_type: "field_type_changed",
        field_name: fieldName,
        old_constraint: oldType,
        new_constraint: newType,
        impact: "high",
        remediation: `Add type coercion or migration function for ${fieldName}`,
      });
    }

    // Check constraint changes (e.g., minLength, pattern)
    const oldConstraints = getConstraints(oldProp as any);
    const newConstraints = getConstraints(newProp as any);
    if (!isConstraintCompatible(oldConstraints, newConstraints)) {
      breakingChanges.push({
        change_type: "field_constraint_tightened",
        field_name: fieldName,
        old_constraint: JSON.stringify(oldConstraints),
        new_constraint: JSON.stringify(newConstraints),
        impact: "medium",
        remediation: `Update existing values to meet new constraints for ${fieldName}`,
      });
    }

    // Check enum compatibility
    const oldEnum = (oldProp as any)?.enum;
    const newEnum = (newProp as any)?.enum;
    if (oldEnum && newEnum) {
      const removedEnumValues = oldEnum.filter(
        (v: any) => !newEnum.includes(v)
      );
      if (removedEnumValues.length > 0) {
        breakingChanges.push({
          change_type: "enum_values_removed",
          field_name: fieldName,
          old_constraint: `enum: ${JSON.stringify(oldEnum)}`,
          new_constraint: `enum: ${JSON.stringify(newEnum)}`,
          impact: "high",
          remediation: `Migrate enum values: ${JSON.stringify(removedEnumValues)} no longer valid`,
        });
      }
    }
  }

  const compatible = breakingChanges.length === 0;
  const migrationRequired =
    breakingChanges.length > 0 || removedRequired.length > 0;

  return {
    compatible,
    breaking_changes: breakingChanges,
    warnings,
    migration_required: migrationRequired,
    migration_strategy: migrationRequired
      ? generateMigrationStrategy(breakingChanges)
      : undefined,
  };
}

function getSchemaProperties(schema: any): Record<string, any> {
  return schema?.properties || {};
}

function getPropertyType(prop: any): string {
  return prop?.type || "unknown";
}

function getConstraints(prop: any): Record<string, any> {
  const constraints: Record<string, any> = {};
  if (prop?.minLength !== undefined) constraints.minLength = prop.minLength;
  if (prop?.maxLength !== undefined) constraints.maxLength = prop.maxLength;
  if (prop?.minimum !== undefined) constraints.minimum = prop.minimum;
  if (prop?.maximum !== undefined) constraints.maximum = prop.maximum;
  if (prop?.pattern !== undefined) constraints.pattern = prop.pattern;
  return constraints;
}

function isConstraintCompatible(
  oldConstraints: Record<string, any>,
  newConstraints: Record<string, any>
): boolean {
  // New minimum > old minimum = incompatible
  if (
    newConstraints.minimum !== undefined &&
    oldConstraints.minimum !== undefined &&
    newConstraints.minimum > oldConstraints.minimum
  ) {
    return false;
  }

  // New maximum < old maximum = incompatible
  if (
    newConstraints.maximum !== undefined &&
    oldConstraints.maximum !== undefined &&
    newConstraints.maximum < oldConstraints.maximum
  ) {
    return false;
  }

  // New minLength > old minLength = incompatible
  if (
    newConstraints.minLength !== undefined &&
    oldConstraints.minLength !== undefined &&
    newConstraints.minLength > oldConstraints.minLength
  ) {
    return false;
  }

  // Pattern changes are generally incompatible
  if (
    newConstraints.pattern !== undefined &&
    oldConstraints.pattern !== undefined &&
    newConstraints.pattern !== oldConstraints.pattern
  ) {
    return false;
  }

  return true;
}

function generateMigrationStrategy(
  breakingChanges: BreakingChange[]
): string {
  const strategies = breakingChanges.map((change) => {
    return `- ${change.field_name || "schema"}: ${change.remediation}`;
  });

  return [
    "Migration strategy:",
    ...strategies,
    "",
    "1. Validate all existing artifacts against new schema",
    "2. Apply migration transformations",
    "3. Re-validate after migration",
    "4. Archive old schema artifacts if needed",
  ].join("\n");
}
