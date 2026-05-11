import { Tokens } from 'marked';

export interface SpeciesToken extends Tokens.Generic { id: string; tokens?: Tokens.Generic[]; type: 'species' }
