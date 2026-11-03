import numpy as np


def all_close(values, reference, tolerance) -> bool:
    """numpy.allclose without its per-call overhead"""
    reference = np.asarray(reference)
    return bool(
        (np.abs(values - reference) <= tolerance + tolerance * np.abs(reference)).all()
    )


def validate_indices(values, size, label):
    values = np.asarray(values)
    if values.ndim != 1 or (
        values.size
        and (
            not np.issubdtype(values.dtype, np.integer)
            or np.any(values < 0)
            or np.any(values >= size)
        )
    ):
        raise ValueError(f"{label} contains an invalid index for size {size}")


def validate_csr(row_ptr, rows, count, label):
    row_ptr = np.asarray(row_ptr)
    if (
        row_ptr.ndim != 1
        or len(row_ptr) != rows + 1
        or row_ptr[0] != 0
        or row_ptr[-1] != count
        or np.any(np.diff(row_ptr) < 0)
    ):
        raise ValueError(f"{label} has invalid sparse row offsets")


def build_csr_columns(num_rows, entries, row_key, value_keys):
    per_row = [[] for _ in range(num_rows)]
    for entry in entries:
        row = entry[row_key]
        if not isinstance(row, (int, np.integer)) or not 0 <= row < num_rows:
            raise ValueError("Sparse row index is outside the row table")
        per_row[row].append(tuple(entry[key] for key in value_keys))
    row_ptr = np.zeros(num_rows + 1, dtype=np.int32)
    for row, values in enumerate(per_row):
        row_ptr[row + 1] = row_ptr[row] + len(values)
    columns = [np.empty(row_ptr[-1], dtype=np.int32) for _ in value_keys]
    for row, values in enumerate(per_row):
        start = row_ptr[row]
        for offset, record in enumerate(values):
            for column, value in zip(columns, record):
                column[start + offset] = value
    return row_ptr, columns


def float32_bit_keys(values):
    """Return exact finite float32 bit patterns without modifying the input"""
    values = np.ascontiguousarray(values, dtype=np.float32)
    if not np.all(np.isfinite(values)):
        raise ValueError("Attribute values must be finite float32 numbers.")
    return values.view(np.int32)


def stable_unique_integer_rows(columns):
    """Return representative rows and inverse indices in first-appearance order"""
    blocks = []
    for values in columns:
        block = np.asarray(values)
        if block.dtype.kind not in "iu" or block.ndim not in (1, 2):
            raise ValueError("Row keys must be one- or two-dimensional integer arrays.")
        if block.ndim == 1:
            block = block[:, None]
        blocks.append(block)
    if not blocks:
        raise ValueError("At least one row-key column is required.")
    rows = len(blocks[0])
    if any(len(block) != rows for block in blocks):
        raise ValueError("Row-key columns must have matching row counts.")
    width = sum(block.shape[1] for block in blocks)
    if width == 0:
        raise ValueError("At least one row-key component is required.")
    bounds = [(int(b.min(initial=0)), int(b.max(initial=0))) for b in blocks]
    i64 = np.iinfo(np.int64)
    if any(lo < i64.min or hi > i64.max for lo, hi in bounds):
        raise ValueError("Row-key values exceed the signed 64-bit range.")
    i32 = np.iinfo(np.int32)
    dtype = (
        np.int32
        if all(i32.min <= lo and hi <= i32.max for lo, hi in bounds)
        else np.int64
    )
    packed = np.empty((rows, width), dtype=dtype)
    offset = 0
    for block in blocks:
        span = block.shape[1]
        packed[:, offset : offset + span] = block
        offset += span
    view = packed.view(np.dtype((np.void, packed.dtype.itemsize * width))).reshape(-1)
    _, representatives, inverse = np.unique(
        view, return_index=True, return_inverse=True
    )
    order = np.argsort(representatives, kind="stable")
    relabel = np.empty(len(order), dtype=np.int64)
    relabel[order] = np.arange(len(order), dtype=np.int64)
    return representatives[order], relabel[inverse.reshape(-1)]
