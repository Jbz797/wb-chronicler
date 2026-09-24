#!/usr/bin/env python3

# Reads WorldBox's `Assembly-CSharp.dll` to settle a mechanism the wiki leaves open — the dev's tool, never the chronicler's: an auditor flags, this settles.
# Needs `dnfile` and `dncil` (kept installed). Every lookup that finds nothing says so and fails, since a silent empty answer is the trap `dnfile` sets.

import argparse
import bisect
import logging
import os
import re
import sys
from pathlib import Path

try:
    import dnfile
    from dncil.cil.body import CilMethodBody
    from dncil.cil.body.reader import CilMethodBodyReaderBase
    from dncil.clr.token import InvalidToken, StringToken, Token
except ImportError:
    sys.exit("✗ needs `dnfile` and `dncil`: pip3 install dnfile dncil")

_CALLS = (b"\x28", b"\x6f", b"\xfe\x06")  # call, callvirt, ldftn: every way IL names a method it runs or hands on
_DEFAULT_DLL = "~/Library/Application Support/Steam/steamapps/common/worldbox/worldbox.app/Contents/Resources/Data/Managed/Assembly-CSharp.dll"
_DLL = Path(os.environ.get("WB_DLL", _DEFAULT_DLL)).expanduser()
_FIELD, _MEMBERREF, _METHOD, _METHODSPEC, _TYPEDEF, _TYPEREF = 4, 10, 6, 43, 2, 1  # ECMA-335 table numbers, which `dnfile` keys its tables by
_LDSTR = b"\x72"
_READS = (b"\x7e", b"\x7b", b"\x80", b"\x7d")  # ldsfld, ldfld, stsfld, stfld: a field read or written
_STRING_TABLE = 0x70  # the user-string heap, as a token's top byte names it


# The method body reader `dncil` wants, over the file's own bytes.
class _Body(CilMethodBodyReaderBase):
    def __init__(self, raw: bytes, offset: int):
        self._raw, self.offset = raw, offset

    def read(self, n: int) -> bytes:
        data = self._raw[self.offset : self.offset + n]
        self.offset += n
        return data

    def seek(self, rva: int) -> int:  # named as `dncil` names it, though it moves to a file offset: its own reader hands these back
        self.offset = rva
        return rva

    def tell(self) -> int:
        return self.offset


# The loaded DLL and its indexes: each method's owning type, and each body's start, so a byte offset tells which method it lies in.
class _Dll:
    def __init__(self, path: Path):
        self.pe = dnfile.dnPE(str(path))
        if (net := self.pe.net) is None or net.mdtables is None or net.user_strings is None:
            sys.exit(f"✗ {path} is no .NET assembly")
        self.raw, self.strings_heap = bytes(self.pe.__data__ or b""), net.user_strings  # bytes, not the mmap: the scans below want a plain buffer
        self.tables = {t.number: t for t in net.mdtables.tables_list}
        # `MethodList` holds table indexes, not rows: `row_index` is the rid a token names.
        self.owner = {ref.row_index: str(td.TypeName) for td in self.tables[_TYPEDEF].rows for ref in td.MethodList or []}
        starts = sorted((self.pe.get_offset_from_rva(m.Rva), rid) for rid, m in enumerate(self.tables[_METHOD].rows, start=1) if m.Rva)
        self._starts, self._rids = [offset for offset, _ in starts], [rid for _, rid in starts]

    # A method's IL, one instruction a line, every token resolved.
    def dump(self, rid: int) -> list[str]:
        row = self.tables[_METHOD].rows[rid - 1]
        if not row.Rva:
            return ["  (no body: abstract, extern or a runtime stub)"]
        lines = []
        for ins in CilMethodBody(_Body(self.raw, self.pe.get_offset_from_rva(row.Rva))).instructions:
            op = ins.operand
            text = self.name_of(op) if isinstance(op, Token) and not isinstance(op, InvalidToken) else ("" if op is None else str(op))
            lines.append(f"{ins.offset:5x} {ins.opcode.name} {text}")
        return lines

    # The method a byte of IL belongs to, by the last body that starts before it.
    def enclosing(self, offset: int) -> str:
        return self.method_name(self._rids[bisect.bisect_right(self._starts, offset) - 1])

    # The fields named exactly so, any type — a field name is often shared, so every one is scanned.
    def fields(self, name: str) -> list[int]:
        return [rid for rid, row in enumerate(self.tables[_FIELD].rows, start=1) if str(row.Name) == name]

    # Methods whose `Type::name` holds the pattern — `::init` for every library's setup, `WorldLogLibrary::` for one type's whole API.
    def find(self, pattern: str) -> list[tuple[int, str]]:
        return [(rid, name) for rid in range(1, len(self.tables[_METHOD].rows) + 1) if pattern in (name := self.method_name(rid))]

    def method_name(self, rid: int) -> str:
        return f"{self.owner.get(rid, '?')}::{self.tables[_METHOD].rows[rid - 1].Name}"

    # A token as the IL means it: a method with its type, a field, a type, a string's own text.
    def name_of(self, token: Token) -> str:
        table, rid = token.table, token.rid
        try:
            if isinstance(token, StringToken):
                item = self.strings_heap.get(rid)  # `.get`: the `get_us` of older `dnfile` now answers nothing, and without error
                return repr(item.value if item else None)
            if table == _METHOD:
                return self.method_name(rid)
            if table == _FIELD:
                return f"field {self.tables[_FIELD].rows[rid - 1].Name}"
            if table == _MEMBERREF:
                row = self.tables[_MEMBERREF].rows[rid - 1]
                owner = row.Class.row if hasattr(row.Class, "row") else None
                return f"{getattr(owner, 'TypeName', getattr(owner, 'Name', '?'))}::{row.Name}"
            if table in (_TYPEDEF, _TYPEREF):
                return f"type {self.tables[table].rows[rid - 1].TypeName}"  # a `HeapItemString`: the f-string reads its text
            if table == _METHODSPEC:
                method = self.tables[_METHODSPEC].rows[rid - 1].Method
                return f"spec {self.method_name(method.row_index)}" if method.table.number == _METHOD else "spec ?"
        except (AttributeError, IndexError) as e:
            return f"<{table}:{rid} {e}>"
        return f"<{table}:{rid}>"

    # User strings holding the needle, each with the methods that load it: an asset id is how IL names most of the game.
    def strings(self, needle: str) -> list[tuple[str, list[str]]]:
        logging.getLogger("dnfile").setLevel(logging.ERROR)  # the heap's last slot lacks its flag byte, and `dnfile` warns of it on every walk
        heap, out = self.strings_heap, []
        offset, size = 1, heap.sizeof()
        while offset < size and (item := heap.get(offset)) is not None:
            if needle in (value := item.value or ""):
                out.append((value, self.uses(_STRING_TABLE, offset, (_LDSTR,))))
            offset += item.raw_size
        return out

    # Every method whose IL names a token behind one of the given opcodes — a byte scan, far quicker than disassembling the whole DLL.
    def uses(self, table: int, rid: int, opcodes: tuple[bytes, ...]) -> list[str]:
        token = rid.to_bytes(3, "little") + bytes([table])
        return sorted({self.enclosing(m.start()) for op in opcodes for m in re.finditer(re.escape(op + token), self.raw)})


# A miss says what it missed and exits non-zero: a silent empty answer is the very trap this tool closes.
def _fail(message: str) -> int:
    print(f"✗ {message}", file=sys.stderr)
    return 1


# A heading, then its lines — or what their absence means, so an empty answer never reads as a missing one.
def _section(heading: str, lines: list[str], none: str) -> None:
    print(heading, *(f"  {line}" for line in lines or [none]), sep="\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="scripts/dll.py", description="Read WorldBox's Assembly-CSharp.dll: find, dump, callers, readers, strings.")
    parser.add_argument("command", choices=("callers", "dump", "find", "readers", "strings"))
    parser.add_argument("pattern", help="`Type::method` (a part of it for find, dump and callers), a field name for readers, text for strings")
    args = parser.parse_args(argv)
    if not _DLL.exists():
        return _fail(f"no DLL at {_DLL} — set WB_DLL to the game's Assembly-CSharp.dll")
    dll = _Dll(_DLL)

    if args.command in ("callers", "dump", "find"):
        if not (found := dll.find(args.pattern)):
            return _fail(f"no method matches « {args.pattern} » — try a shorter part, `Type::` alone lists a type")
        for rid, name in found:
            if args.command == "find":
                print(rid, name)
            elif args.command == "dump":
                print(f"== {rid} {name}", *dll.dump(rid), sep="\n")
            else:
                _section(f"== {name} is run by:", dll.uses(_METHOD, rid, _CALLS), "(no caller: an entry point, or reached by reflection)")
    elif args.command == "readers":
        if not (rids := dll.fields(args.pattern)):
            return _fail(f"no field named « {args.pattern} »")
        for rid in rids:
            _section(f"== field {args.pattern} (rid {rid}) is read or written by:", dll.uses(_FIELD, rid, _READS), "(no method touches it)")
    else:
        if not (hits := dll.strings(args.pattern)):
            return _fail(f"no string holds « {args.pattern} »")
        for value, loaders in hits:
            _section(f"== {value!r}", loaders, "(loaded by no method)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
