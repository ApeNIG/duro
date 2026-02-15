/**
 * Project Constitution Schema v1
 *
 * The "laws of this project" - tiny (1-3K tokens), enforceable, versioned, traceable.
 * Loaded by Context Assembler as the Project Pack.
 */

export interface ProjectConstitution {
  // ─────────────────────────────────────────
  // IDENTITY
  // ─────────────────────────────────────────
  project_id: string;           // "msj", "cinematch"
  name: string;                 // "My Swim Journey"
  version: string;              // "0.4.0" (semver)
  updated_at: string;           // ISO timestamp

  // ─────────────────────────────────────────
  // NORTH STAR (what this project is about)
  // ─────────────────────────────────────────
  north_star: {
    statement: string;          // One sentence vision
    primary_user_job: string;   // What users come here to do
    tone?: string;              // Voice/personality
  };

  // ─────────────────────────────────────────
  // LAWS (atomic, enforceable rules)
  // ─────────────────────────────────────────
  laws: Law[];

  // ─────────────────────────────────────────
  // CONSTRAINTS (boundaries and limits)
  // ─────────────────────────────────────────
  constraints: {
    do_not: string[];           // Things to never do
    accessibility?: {
      min_contrast?: string;    // "WCAG AA"
      touch_target_min_px?: number;
    };
    performance?: {
      max_bundle_kb?: number;
      max_api_latency_ms?: number;
    };
  };

  // ─────────────────────────────────────────
  // PATTERNS (best practices, not mandatory)
  // ─────────────────────────────────────────
  patterns_top: Pattern[];

  // ─────────────────────────────────────────
  // DECIDING AXES (meta-heuristics for taste)
  // ─────────────────────────────────────────
  deciding_axes: string[];      // "Glanceability beats identity when..."

  // ─────────────────────────────────────────
  // CONFLICT RESOLUTION
  // ─────────────────────────────────────────
  conflict_policy: {
    order: string[];            // Priority order for rule types
    tie_break: 'newer_version_wins' | 'stricter_wins' | 'ask_user';
  };
}

export interface Law {
  id: string;                   // "law.palette.primary"
  rule: string;                 // The actual rule statement
  strength: 'hard' | 'soft';    // Hard = must enforce, Soft = prefer
  applies_to: string[];         // ["ui", "brand", "components"]
  rationale?: string;           // Why this rule exists
  provenance: string[];         // Decision IDs that created/updated this
  last_verified?: string;       // When last confirmed still valid

  // Optional machine-checkable enforcement
  enforce?: {
    pattern?: string;           // Regex or glob to check
    command?: string;           // CLI command to verify
  };
}

export interface Pattern {
  id: string;                   // "pattern.stats.card_hierarchy"
  pattern: string;              // Description of the pattern
  when: string;                 // When to apply it
  value: string;                // What benefit it provides
  examples?: string[];          // Optional examples
}
