#!/usr/bin/env python3
"""Re-type the Abiray Inkling-2-Mini-Uncensored GGUF to Q8_0 dense/head tensors (T10).

Copies the source GGUF with every metadata field (the same walk as
gguf/scripts/gguf_new_metadata.py copy_with_new_metadata) and keeps all expert and
embedding tensors byte-identical. Only two groups are re-quantized to Q8_0:

  * output.weight (Q6_K -> Q8_0)
  * every non-expert 2-D IQ4_NL tensor except token_embd.weight (-> Q8_0)

Rationale: the maya-ik2 HIP engine's planar Q8_0 decode path (ik2_main.cu:535) and the
DSpark drafter check (ik2_main.cu:5065, "the output head is neither FP16 nor planar
Q8_0") both need type Q8_0 in the GGUF; the port author's ggml-org file has it and the
Abiray file does not.

Requires gguf-py from the inkling llama.cpp tree and numpy:

    python3 -I results/20261123-inkling-round/raw/retype_q8.py [--src P] [--dst P]

The destination is git-ignored (_tmp/maya/r23/model/). After writing, the script
re-opens the destination and asserts the invariants; it exits non-zero on any breach.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import sys
from pathlib import Path

import numpy as np

GGUF_PY = Path.home() / 'IA/Motores/src/llama.cpp-inkling-rdna3/gguf-py'
sys.path.insert(0, str(GGUF_PY))

import gguf  # noqa: E402
from gguf import GGMLQuantizationType as QType  # noqa: E402
from gguf.quants import dequantize, quantize, quant_shape_to_byte_shape  # noqa: E402

DEFAULT_SRC = Path.home() / 'IA/Modelos/Inkling-2-Mini-Uncensored-Abiray/Inkling-2-Mini-Uncensored-IQ4_NL.gguf'
DEFAULT_DST = Path.home() / 'IA/rx7900xtx-local-llm/_tmp/maya/r23/model/Inkling-2-Mini-Uncensored-IQ4_NL-q8dense.gguf'

# float32 elements converted per slab; bounds the dequantize/quantize peak at ~256 MiB
CHUNK_ELEMS = 64 * 1024 * 1024

# tensors that must stay byte-identical between source and destination
BYTE_IDENTICAL = (
    'blk.0.ffn_gate_up_exps.weight',
    'blk.0.ffn_down_exps.weight',
    'token_embd.weight',
)


def field_value(reader: gguf.GGUFReader, key: str):
    field = reader.get_field(key)
    return field.contents() if field else None


def retype_kind(tensor) -> str | None:
    """Return why a tensor is re-typed to Q8_0, or None to copy it unchanged."""
    if tensor.name == 'output.weight':
        return 'head'
    # maya-ik2 rejects K-quant expert rows ("a row is not whole Q6_K blocks"), e.g. bartowski's Unbound layers 0-4
    if '_exps' in tensor.name and tensor.tensor_type in (QType.Q4_K, QType.Q5_K, QType.Q6_K):
        return 'kquant-experts'
    if tensor.tensor_type != QType.IQ4_NL:
        return None
    if len(tensor.shape) != 2:
        return None
    if tensor.name == 'token_embd.weight' or '_exps' in tensor.name:
        return None
    return 'dense'


def row_width(tensor) -> int:
    """Element width of one row (ggml ne0); gguf reader dims are file order, data is reversed."""
    return int(tensor.shape[0])


def to_q8_0(tensor) -> np.ndarray:
    """dequantize -> quantize(Q8_0), slab by slab along the row axis of the gguf-py layout."""
    ne0 = row_width(tensor)
    rows_per_slab = max(1, CHUNK_ELEMS // ne0)
    # tensor.data of a quantized tensor holds whole blocks, so one row is data.shape[-1] bytes
    rows = tensor.data.reshape(-1, tensor.data.shape[-1])
    slabs = []
    for start in range(0, rows.shape[0], rows_per_slab):
        block = rows[start:start + rows_per_slab]
        slabs.append(quantize(dequantize(block, tensor.tensor_type), QType.Q8_0))
    quant = slabs[0] if len(slabs) == 1 else np.concatenate(slabs, axis=0)
    return quant.reshape(*tensor.data.shape[:-1], quant.shape[-1])


def max_dequant_diff(src_tensor, dst_tensor) -> tuple[float, float]:
    """Largest |src - dst| and largest |src| over the dequantized values of one tensor."""
    ne0 = row_width(src_tensor)
    rows_per_slab = max(1, CHUNK_ELEMS // ne0)
    src_rows = src_tensor.data.reshape(-1, src_tensor.data.shape[-1])
    dst_rows = dst_tensor.data.reshape(-1, dst_tensor.data.shape[-1])
    max_diff = 0.0
    max_abs = 0.0
    for start in range(0, src_rows.shape[0], rows_per_slab):
        src = dequantize(src_rows[start:start + rows_per_slab], src_tensor.tensor_type)
        dst = dequantize(dst_rows[start:start + rows_per_slab], QType.Q8_0)
        max_diff = max(max_diff, float(np.abs(src - dst).max()))
        max_abs = max(max_abs, float(np.abs(src).max()))
    return max_diff, max_abs


def type_counts(reader: gguf.GGUFReader) -> dict[str, int]:
    return dict(sorted(collections.Counter(t.tensor_type.name for t in reader.tensors).items()))


def write_dst(reader: gguf.GGUFReader, dst: Path) -> dict[str, str]:
    """Copy metadata and tensors to dst, re-typing the selected tensors. Returns name -> kind."""
    arch = field_value(reader, gguf.Keys.General.ARCHITECTURE)
    dst.parent.mkdir(parents=True, exist_ok=True)
    writer = gguf.GGUFWriter(dst, arch=arch, endianess=reader.endianess)

    alignment = field_value(reader, gguf.Keys.General.ALIGNMENT)
    if alignment is not None:
        writer.data_alignment = alignment

    for field in reader.fields.values():
        # general.architecture comes from GGUFWriter(arch=...); GGUF.* are virtual fields
        if field.name == gguf.Keys.General.ARCHITECTURE or field.name.startswith('GGUF.'):
            continue
        val_type = field.types[0]
        sub_type = field.types[-1] if val_type == gguf.GGUFValueType.ARRAY else None
        writer.add_key_value(field.name, field.contents(), val_type, sub_type=sub_type)

    retype: dict[str, str] = {}
    for tensor in reader.tensors:
        kind = retype_kind(tensor)
        if kind is None:
            writer.add_tensor_info(tensor.name, tensor.data.shape, tensor.data.dtype,
                                   tensor.data.nbytes, tensor.tensor_type)
            continue
        retype[tensor.name] = kind
        # Q8_0 keeps 34 bytes per 32 row elements, so the byte shape is known up front;
        # tensor.data.shape of a quantized source already holds byte widths, use the file dims
        elem_shape = tuple(reversed(tuple(int(d) for d in tensor.shape)))
        shape = quant_shape_to_byte_shape(elem_shape, QType.Q8_0)
        writer.add_tensor_info(tensor.name, shape, np.dtype(np.uint8), int(np.prod(shape)), QType.Q8_0)

    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_ti_data_to_file()

    for tensor in reader.tensors:
        if tensor.name in retype:
            quant = to_q8_0(tensor)
            print(f'retype {tensor.name}: {tensor.tensor_type.name} -> Q8_0 '
                  f'({tensor.n_bytes} -> {quant.nbytes} bytes)', flush=True)
            writer.write_tensor_data(quant, tensor_endianess=reader.endianess)
        else:
            writer.write_tensor_data(tensor.data, tensor_endianess=reader.endianess)
    writer.close()
    return retype


def check(src_reader: gguf.GGUFReader, dst_reader: gguf.GGUFReader, retype: dict[str, str]) -> None:
    src_by_name = {t.name: t for t in src_reader.tensors}
    dst_by_name = {t.name: t for t in dst_reader.tensors}

    assert len(src_reader.tensors) == len(dst_reader.tensors), \
        f'tensor count changed: {len(src_reader.tensors)} -> {len(dst_reader.tensors)}'
    assert list(src_by_name) == list(dst_by_name), 'tensor order changed'

    for name in retype:
        dst = dst_by_name[name]
        src = src_by_name[name]
        assert dst.tensor_type == QType.Q8_0, f'{name}: type is {dst.tensor_type.name}, not Q8_0'
        assert tuple(int(d) for d in dst.shape) == tuple(int(d) for d in src.shape), \
            f'{name}: shape {list(dst.shape)} != {list(src.shape)}'
    print(f'check: {len(retype)} tensors are Q8_0 with unchanged shapes')

    for name in BYTE_IDENTICAL:
        if name in retype:  # re-typed on purpose (K-quant experts)
            continue
        src, dst = src_by_name[name], dst_by_name[name]
        assert src.tensor_type == dst.tensor_type, \
            f'{name}: type {src.tensor_type.name} -> {dst.tensor_type.name}'
        assert src.n_bytes == dst.n_bytes, f'{name}: byte count changed'
        assert np.array_equal(src.data, dst.data), f'{name}: bytes differ from the source'
        print(f'check: {name} byte-identical ({dst.n_bytes} bytes)')

    head = 'output.weight'
    max_diff, max_abs = max_dequant_diff(src_by_name[head], dst_by_name[head])
    ratio = max_diff / max_abs if max_abs else 0.0
    assert ratio < 0.01, f'{head}: dequant diff {max_diff:.6g} is {ratio:.3%} of max abs {max_abs:.6g}'
    print(f'check: {head} max abs dequant diff {max_diff:.6g} = {ratio:.3%} of max abs {max_abs:.6g}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Re-type Inkling-2-Mini-Uncensored dense/head tensors to Q8_0')
    parser.add_argument('--src', type=Path, default=DEFAULT_SRC, help=f'source GGUF (default: {DEFAULT_SRC})')
    parser.add_argument('--dst', type=Path, default=DEFAULT_DST, help=f'destination GGUF (default: {DEFAULT_DST})')
    args = parser.parse_args()

    if args.dst.exists():
        print(f'destination exists, overwriting: {args.dst}')
    print(f'source: {args.src} ({args.src.stat().st_size} bytes)')

    print(f'loading {args.src} ...', flush=True)
    src_reader = gguf.GGUFReader(args.src, 'r')
    print('types before:', type_counts(src_reader))
    print(f'architecture: {field_value(src_reader, gguf.Keys.General.ARCHITECTURE)}')

    retype = write_dst(src_reader, args.dst)

    dst_reader = gguf.GGUFReader(args.dst, 'r')
    print('types after: ', type_counts(dst_reader))
    check(src_reader, dst_reader, retype)

    digest = hashlib.sha256()
    with open(args.dst, 'rb') as fp:
        for chunk in iter(lambda: fp.read(1 << 24), b''):
            digest.update(chunk)
    print(f'dst: {args.dst}')
    print(f'dst size: {args.dst.stat().st_size} bytes')
    print(f'dst sha256: {digest.hexdigest()}')
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
