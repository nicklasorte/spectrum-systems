import {
  AUTHORITY_BOUNDARY_SYSTEMS,
  AUTHORITY_ROLES,
  DISPLAY_GROUPS,
  authorityRoleFor,
  groupForSystem,
  partitionByDisplayGroup,
} from '@/lib/displayGroups';

describe('DSH-06 — 3LS display groupings', () => {
  it('exposes the eight required display groups', () => {
    const ids = DISPLAY_GROUPS.map((g) => g.id);
    expect(ids).toEqual(
      expect.arrayContaining([
        'execution',
        'eval_and_trust',
        'control_and_enforcement',
        'replay_lineage_observability',
        'governance_and_certification',
        'artifact_intelligence',
        'dashboard_and_ux',
        'roadmap_and_planning',
      ])
    );
    expect(ids.length).toBe(8);
  });

  it('does not rename canonical system IDs (PQX, CDE, SEL stay as-is)', () => {
    expect(groupForSystem('PQX')?.id).toBe('execution');
    expect(groupForSystem('CDE')?.id).toBe('control_and_enforcement');
    expect(groupForSystem('SEL')?.id).toBe('control_and_enforcement');

    // Verify the literal IDs are still PQX/CDE/SEL inside the group definitions
    const allIds = DISPLAY_GROUPS.flatMap((g) => g.system_ids);
    expect(allIds).toContain('PQX');
    expect(allIds).toContain('CDE');
    expect(allIds).toContain('SEL');
    expect(allIds).toContain('AEX');
    expect(allIds).toContain('TPA');
    expect(allIds).toContain('EVL');
    expect(allIds).toContain('REP');
    expect(allIds).toContain('LIN');
    expect(allIds).toContain('OBS');
    expect(allIds).toContain('SLO');
  });

  it('returns null for unknown systems rather than guessing', () => {
    expect(groupForSystem('ZZZ')).toBeNull();
  });

  it('places CDE and SEL in the same group but exposes distinct IDs', () => {
    const group = groupForSystem('CDE');
    expect(group?.system_ids).toContain('CDE');
    expect(group?.system_ids).toContain('SEL');
    // CDE and SEL must remain distinct entries — never merged into one ID
    expect(group?.system_ids.filter((id) => id === 'CDE').length).toBe(1);
    expect(group?.system_ids.filter((id) => id === 'SEL').length).toBe(1);
  });
});

describe('DSH-07 — authority boundary preservation', () => {
  it('declares an authority role for each canonical authority system', () => {
    expect(AUTHORITY_ROLES.AEX).toBe('admits');
    expect(AUTHORITY_ROLES.PQX).toBe('executes');
    expect(AUTHORITY_ROLES.EVL).toBe('evaluates');
    expect(AUTHORITY_ROLES.TPA).toBe('adjudicates trust/policy');
    expect(AUTHORITY_ROLES.CDE).toBe('decides');
    expect(AUTHORITY_ROLES.SEL).toBe('enforces');
    expect(AUTHORITY_ROLES.REP).toBe('replays');
    expect(AUTHORITY_ROLES.LIN).toBe('links lineage');
    expect(AUTHORITY_ROLES.OBS).toBe('observes');
    expect(AUTHORITY_ROLES.SLO).toBe('manages reliability budget');
  });

  it('lists each authority-boundary system distinctly', () => {
    const expected = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL', 'REP', 'LIN', 'OBS', 'SLO'];
    for (const id of expected) {
      expect(AUTHORITY_BOUNDARY_SYSTEMS).toContain(id);
    }
    // No duplicates — distinctness is the contract
    expect(new Set(AUTHORITY_BOUNDARY_SYSTEMS).size).toBe(AUTHORITY_BOUNDARY_SYSTEMS.length);
  });

  it('returns null for systems with no declared authority role', () => {
    expect(authorityRoleFor('PRG')).toBeNull();
    expect(authorityRoleFor('PQX')).toBe('executes');
  });

  it('CDE and SEL roles are distinct — neither owns the other authority', () => {
    expect(AUTHORITY_ROLES.CDE).not.toBe(AUTHORITY_ROLES.SEL);
    expect(AUTHORITY_ROLES.CDE).toBe('decides');
    expect(AUTHORITY_ROLES.SEL).toBe('enforces');
  });
});

describe('partitionByDisplayGroup', () => {
  it('groups systems and preserves canonical IDs', () => {
    const systems = [
      { system_id: 'PQX' },
      { system_id: 'CDE' },
      { system_id: 'OBS' },
      { system_id: 'ZZZ' },
    ];
    const { groups, ungrouped } = partitionByDisplayGroup(systems);

    const flat = groups.flatMap((g) => g.systems.map((s) => s.system_id));
    expect(flat).toContain('PQX');
    expect(flat).toContain('CDE');
    expect(flat).toContain('OBS');
    expect(ungrouped.map((s) => s.system_id)).toEqual(['ZZZ']);
  });

  it('drops empty groups from the output', () => {
    const { groups } = partitionByDisplayGroup([{ system_id: 'PQX' }]);
    for (const entry of groups) {
      expect(entry.systems.length).toBeGreaterThan(0);
    }
  });
});
