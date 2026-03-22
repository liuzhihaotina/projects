import os
import math
from typing import List, Sequence, Union

import numpy as np
import torch
import zarr
from numcodecs import Blosc


TensorLikeFrame = Sequence[torch.Tensor]


def _torch_dtype_to_numpy_dtype(torch_dtype: torch.dtype):
    mapping = {
        torch.float16: np.float16,
        torch.float32: np.float32,
        torch.float64: np.float64,
        torch.uint8: np.uint8,
        torch.int8: np.int8,
        torch.int16: np.int16,
        torch.int32: np.int32,
        torch.int64: np.int64,
        torch.bool: np.bool_,
        torch.bfloat16: None,  # numpy 原生支持较麻烦，这里先不直接处理
        torch.complex64: np.complex64,
        torch.complex128: np.complex128,
    }
    if torch_dtype not in mapping:
        raise TypeError(f"Unsupported torch dtype: {torch_dtype}")
    np_dtype = mapping[torch_dtype]
    if np_dtype is None:
        raise TypeError(
            "bfloat16 is not directly supported in this implementation. "
            "If you need strict lossless bfloat16 storage, tell me and I can give a uint16-view version."
        )
    return np_dtype


def _to_numpy_lossless(t: torch.Tensor) -> np.ndarray:
    if t.device.type != "cpu":
        t = t.cpu()
    if not t.is_contiguous():
        t = t.contiguous()
    np_dtype = _torch_dtype_to_numpy_dtype(t.dtype)
    return t.numpy().astype(np_dtype, copy=False)


def analyze_frames(frames: Sequence[TensorLikeFrame], num_fields: int = 15):
    """
    分析每个字段是否固定 shape、dtype 是否一致。
    """
    if len(frames) == 0:
        raise ValueError("frames is empty")

    meta = []

    for k in range(num_fields):
        first = frames[0][k]
        dtype = first.dtype
        shape0 = tuple(first.shape)

        same_dtype = True
        fixed_shape = True
        ndim = first.ndim

        for i, frame in enumerate(frames):
            t = frame[k]
            if t.dtype != dtype:
                same_dtype = False
            if t.ndim != ndim:
                raise ValueError(
                    f"Field {k}: ndim changed across frames, "
                    f"frame0 ndim={ndim}, frame{i} ndim={t.ndim}"
                )
            if tuple(t.shape) != shape0:
                fixed_shape = False

        if not same_dtype:
            raise ValueError(f"Field {k}: dtype is not consistent across frames")

        meta.append({
            "field_idx": k,
            "dtype": str(dtype),
            "fixed_shape": fixed_shape,
            "shape0": shape0,
            "ndim": ndim,
        })

    return meta


def save_frames_to_zarr(
    frames: Sequence[TensorLikeFrame],
    out_path: str,
    num_fields: int = 15,
    compressor_name: str = "zstd",
    clevel: int = 3,
    shuffle: str = "bitshuffle",
    chunk_frames_fixed: int = 64,
):
    """
    将 frames 保存到 zarr。
    每个 frame 是长度为 num_fields 的 tensor 列表/元组。
    无损保存。

    参数：
    - compressor_name: "zstd" / "lz4" / "blosclz"
    - clevel: 压缩级别，建议 1~5 平衡速度与压缩率
    - shuffle: "shuffle" / "bitshuffle" / "noshuffle"
    - chunk_frames_fixed: 固定 shape 字段每个 chunk 放多少帧
    """
    if len(frames) == 0:
        raise ValueError("frames is empty")

    os.makedirs(out_path, exist_ok=True)

    shuffle_map = {
        "shuffle": Blosc.SHUFFLE,
        "bitshuffle": Blosc.BITSHUFFLE,
        "noshuffle": Blosc.NOSHUFFLE,
    }
    if shuffle not in shuffle_map:
        raise ValueError(f"Invalid shuffle: {shuffle}")

    compressor = Blosc(
        cname=compressor_name,
        clevel=clevel,
        shuffle=shuffle_map[shuffle],
    )

    root = zarr.open_group(out_path, mode="w")
    root.attrs["num_frames"] = len(frames)
    root.attrs["num_fields"] = num_fields
    root.attrs["format"] = "frame15_zarr_v1"

    meta = analyze_frames(frames, num_fields=num_fields)

    meta_group = root.create_group("meta")
    fields_group = root.create_group("fields")

    # 存一份 metadata
    meta_group.attrs["fields"] = meta

    num_frames = len(frames)

    for k in range(num_fields):
        info = meta[k]
        field_group = fields_group.create_group(f"field_{k}")
        field_group.attrs["dtype"] = info["dtype"]
        field_group.attrs["fixed_shape"] = info["fixed_shape"]
        field_group.attrs["ndim"] = info["ndim"]

        if info["fixed_shape"]:
            # 直接 [N, ...] 存
            shape0 = info["shape0"]
            first_np = _to_numpy_lossless(frames[0][k])
            np_dtype = first_np.dtype

            full_shape = (num_frames,) + shape0
            chunks = (min(chunk_frames_fixed, num_frames),) + shape0

            ds = field_group.create_dataset(
                "data",
                shape=full_shape,
                chunks=chunks,
                dtype=np_dtype,
                compressor=compressor,
                overwrite=True,
            )

            for i in range(num_frames):
                ds[i] = _to_numpy_lossless(frames[i][k])

        else:
            # 变长：flatten 后拼接 + offsets + shapes
            shapes = []
            flat_arrays = []
            total_elems = 0
            np_dtype = None

            for i in range(num_frames):
                arr = _to_numpy_lossless(frames[i][k])
                if np_dtype is None:
                    np_dtype = arr.dtype
                elif arr.dtype != np_dtype:
                    raise ValueError(f"Field {k}: numpy dtype changed at frame {i}")

                shapes.append(arr.shape)
                flat = arr.reshape(-1)
                flat_arrays.append(flat)
                total_elems += flat.size

            ndim = info["ndim"]
            max_ndim = ndim  # 因为同字段 ndim 已固定

            offsets = np.zeros(num_frames + 1, dtype=np.int64)
            for i, flat in enumerate(flat_arrays):
                offsets[i + 1] = offsets[i] + flat.size

            shapes_arr = np.zeros((num_frames, max_ndim), dtype=np.int64)
            for i, shp in enumerate(shapes):
                shapes_arr[i, :] = np.array(shp, dtype=np.int64)

            data_ds = field_group.create_dataset(
                "data",
                shape=(total_elems,),
                chunks=(min(max(total_elems // 128, 1024 * 1024), total_elems) if total_elems > 0 else 1,),
                dtype=np_dtype,
                compressor=compressor,
                overwrite=True,
            )

            field_group.create_dataset(
                "offsets",
                data=offsets,
                shape=offsets.shape,
                chunks=offsets.shape,
                dtype=offsets.dtype,
                compressor=compressor,
                overwrite=True,
            )

            field_group.create_dataset(
                "shapes",
                data=shapes_arr,
                shape=shapes_arr.shape,
                chunks=(min(num_frames, 1024), max_ndim),
                dtype=shapes_arr.dtype,
                compressor=compressor,
                overwrite=True,
            )

            if total_elems > 0:
                write_pos = 0
                for flat in flat_arrays:
                    n = flat.size
                    if n > 0:
                        data_ds[write_pos:write_pos + n] = flat
                    write_pos += n

    print(f"Saved {num_frames} frames to {out_path}")