// A role the favourite still holds, as against one he merely founded — the panel tags the first and lets the chronicle tell the second.
export const ACTIVE_ROLES = new Set(['clan_chief', 'family_alpha']);

// ng-zorro nz-tag colors per relation status — green for allies, red for active enemies, default for everything else.
export const RELATION_STATUS_NZ_COLORS = { ally: 'green', enemy: 'red', neutral: 'default' } as const;
