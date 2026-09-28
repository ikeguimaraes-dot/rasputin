"""Recuperação conservadora de BIFF8. Resultado sempre parcial, nunca sobrescreve fonte."""

from __future__ import annotations

import struct
from io import BytesIO

import olefile


def rk(raw: int) -> float:
    if raw & 2:
        signed = struct.unpack("<i", struct.pack("<I", raw))[0]
        value = signed >> 2
    else:
        value = struct.unpack("<d", b"\0" * 4 + struct.pack("<I", raw & 0xFFFFFFFC))[0]
    return value / 100 if raw & 1 else value


class Chunks:
    def __init__(self, chunks):
        self.chunks, self.chunk, self.pos = chunks, 0, 0

    def read(self, n):
        out = b""
        while n:
            if self.chunk >= len(self.chunks):
                raise EOFError
            part = self.chunks[self.chunk]
            take = min(n, len(part) - self.pos)
            out += part[self.pos : self.pos + take]
            self.pos += take
            n -= take
            if self.pos == len(part) and n:
                self.chunk += 1
                self.pos = 0
        return out

    def characters(self, count, wide):
        out = ""
        for _ in range(count):
            if self.pos == len(self.chunks[self.chunk]):
                self.chunk += 1
                self.pos = 0
                wide = bool(self.read(1)[0] & 1)
            out += self.read(2 if wide else 1).decode("utf-16-le" if wide else "latin1")
        return out


def recover(data: bytes):
    warnings = ["XLS recuperado: conteúdo parcial; confira o arquivo com a origem."]
    stream = None
    try:
        with olefile.OleFileIO(BytesIO(data)) as ole:
            for name in ("Workbook", "Book"):
                if ole.exists(name):
                    stream = ole.openstream(name).read()
                    break
    except (OSError, ValueError):
        pass
    if stream is None:
        # Busca um BOF BIFF8 plausível. Setores OLE não são necessariamente contíguos:
        # o salvamento bruto é explicitamente parcial e pode perder células.
        for offset in range(512, len(data) - 8, 512):
            if data[offset : offset + 2] == b"\x09\x08":
                stream = data[offset:]
                break
    if stream is None:
        raise ValueError("Não foi possível recuperar um stream BIFF8 do XLS")
    records, pos = [], 0
    while pos + 4 <= len(stream):
        ident, size = struct.unpack_from("<HH", stream, pos)
        pos += 4
        if size > 8224 or pos + size > len(stream):
            warnings.append("Registro BIFF truncado; leitura interrompida.")
            break
        records.append((ident, stream[pos : pos + size]))
        pos += size
    strings, expected_refs = [], 0
    for index, (ident, payload) in enumerate(records):
        if ident != 0xFC or len(payload) < 8:
            continue
        expected_refs, unique = struct.unpack_from("<II", payload)
        chunks = [payload[8:]]
        for ident2, payload2 in records[index + 1 :]:
            if ident2 != 0x3C:
                break
            chunks.append(payload2)
        reader = Chunks(chunks)
        try:
            for _ in range(min(unique, 200000)):
                count = struct.unpack("<H", reader.read(2))[0]
                flags = reader.read(1)[0]
                runs = struct.unpack("<H", reader.read(2))[0] if flags & 8 else 0
                ext = struct.unpack("<I", reader.read(4))[0] if flags & 4 else 0
                strings.append(reader.characters(count, bool(flags & 1)))
                reader.read(runs * 4 + ext)
        except (EOFError, IndexError, UnicodeError, struct.error):
            warnings.append("Tabela de strings incompleta.")
        break
    cells, sheet, sheets, refs = {}, -1, {}, 0
    for ident, payload in records:
        try:
            if ident == 0x809 and len(payload) >= 4:
                subtype = struct.unpack_from("<H", payload, 2)[0]
                if subtype == 0x10:
                    sheet += 1
                    cells = sheets.setdefault(sheet, {})
            if sheet < 0 or len(payload) < 6:
                continue
            row, col = struct.unpack_from("<HH", payload)
            if row > 65535 or col > 255:
                continue
            if ident == 0xFD:
                s = struct.unpack_from("<I", payload, 6)[0]
                if s < len(strings):
                    cells[row, col] = strings[s]
                    refs += 1
            elif ident == 0x203:
                cells[row, col] = struct.unpack_from("<d", payload, 6)[0]
            elif ident == 0x27E:
                cells[row, col] = rk(struct.unpack_from("<I", payload, 6)[0])
            elif ident == 0xBD:
                last = struct.unpack_from("<H", payload, len(payload) - 2)[0]
                for c in range(col, min(last, 255) + 1):
                    cells[row, c] = rk(struct.unpack_from("<I", payload, 6 + (c - col) * 6)[0])
        except (struct.error, ValueError):
            warnings.append("Célula truncada descartada.")
    if not any(sheets.values()):
        raise ValueError("Nenhuma célula recuperável no XLS")
    if expected_refs > refs * 2:
        warnings.append(f"SST declara {expected_refs} referências; recuperadas {refs}.")
    result = {}
    for s, cells in sheets.items():
        if cells:
            rows, cols = max(r for r, c in cells) + 1, max(c for r, c in cells) + 1
            if rows * cols > 2_000_000:
                raise ValueError("Dimensão de planilha recuperada excede limite")
            result[f"Recuperada {s + 1}"] = [
                [cells.get((r, c)) for c in range(cols)] for r in range(rows)
            ]
    return result, warnings
