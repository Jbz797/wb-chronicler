import { KingdomRegistry } from '../interfaces';

// Mutable bridge populated at app init so the DI-less marked renderer can resolve kingdoms by id.
export const KINGDOM_REGISTRY: KingdomRegistry = {};
