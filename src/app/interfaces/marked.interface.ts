import { Tokens } from 'marked';

import { IconKind } from './types';

export interface IconToken extends Tokens.Generic { id: string; tokens?: Tokens.Generic[]; type: IconKind }
export interface ParserThis { parser: { parseInline: (tokens: Tokens.Generic[]) => string } }
