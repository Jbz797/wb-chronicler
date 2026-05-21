import { Tokens } from 'marked';

import { IconKind } from './types';

export interface IconToken extends Tokens.Generic { id: string; tokens?: Tokens.Generic[]; type: IconKind }
export interface LexerThis { lexer: { inline: (source_: string, tokens: Tokens.Generic[]) => void } }
export interface ParserThis { parser: { parseInline: (tokens: Tokens.Generic[]) => string } }
