import { Request, Response, NextFunction } from "express";

/**
 * RBAC Middleware
 * Ensure user has governance viewer role
 */

export function requireGovernanceAccess(req: Request, res: Response, next: NextFunction) {
  const userRole = req.headers["x-user-role"] as string;

  if (!userRole || !["governance-viewer", "governance-admin", "sre", "lead"].includes(userRole)) {
    return res.status(403).json({ error: "Access denied" });
  }

  next();
}

export function requireGovernanceAdmin(req: Request, res: Response, next: NextFunction) {
  const userRole = req.headers["x-user-role"] as string;

  if (!userRole || !["governance-admin", "lead"].includes(userRole)) {
    return res.status(403).json({ error: "Admin access required" });
  }

  next();
}
