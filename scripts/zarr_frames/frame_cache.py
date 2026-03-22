import os
import json
from typing import Sequence, Callable, List, Any, Dict

import numpy as np
import torch
import zarr
from numcodecs import Blosc


# =========================================================
# dtype utilities
# =========================================================

def torch_dtype_to_str(dtype: torch.dtype) -> str:
    return str(dtype).replace("torch.", "")


def str_to_torch_dtype(dtype_str: str) -> torch.dtype:
    mapping = {
        "float16": torch.float16,
        "float32": torch.float32,
        "float64": torch.float64,
        "uint8": torch.uint8,
        "int8": torch.int8,
        "int16": torch.int16,
        "int32": torch.int32,
        "int64": torch.int64,
        "bool": torch.bool,
        "bfloat16": torch.bfloat16,
        "complex64": torch.complex64,
        "complex128": torch.complex128,
    }
    if dtype_str not in mapping:
        raise TypeError(f"Unsupported dtype string: {dtype_str}")
    return mapping[dtype_str]


def storage_numpy_dtype(torch_dtype: torch.dtype):
    """
    落盘存储时使用的 numpy dtype。
    bfloat16 特殊处理为 uint16 位模式，无损。
    """
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
        torch.complex64: np.complex64,
        torch.complex128: np.complex128,
        torch.bfloat16: np.uint16,
    }
    if torch_dtype not in mapping:
        raise TypeError(f"Unsupported torch dtype: {torch_dtype}")
    return mapping[torch_dtype]


def tensor_to_numpy_for_storage(t: torch.Tensor) -> np.ndarray:
    """
    将 tensor 转为无损存储的 numpy array
    - CPU
    - contiguous
    - bfloat16 按 uint16 位模式存
    """
    if t.device.type != "cpu":
        t = t.cpu()
    if not t.is_contiguous():
        t = t.contiguous()

    if t.dtype == torch.bfloat16:
        return t.view(torch.uint16).numpy()

    np_dtype = storage_numpy_dtype(t.dtype)
    return t.numpy().astype(np_dtype, copy=False)


def numpy_from_storage_to_tensor(arr: np.ndarray, torch_dtype: torch.dtype) -> torch.Tensor:
    """
    从存储格式恢复 torch tensor
    """
    if torch_dtype == torch.bfloat16:
        t = torch.from_numpy(arr.view(np.uint16))
        return t.view(torch.bfloat16)
    return torch.from_numpy(arr)


# =========================================================
# analysis
# =========================================================

def analyze_dataset(
    get_frame: Callable[[int], Sequence[torch.Tensor]],
    num_frames: int,
    num_fields: int = 15,
) -> Dict[str, Any]:
    """
    第一遍分析：
    - 每个字段 dtype 是否固定
    - ndim 是否固定
    - shape 是否固定

    返回：
    {
        "fixed_shape": [...],
        "dtypes": [...],
        "ndims": [...],
        "sample_shapes": [...]
    }
    """
    if num_frames <= 0:
        raise ValueError("num_frames must > 0")

    sample0 = get_frame(0)
    if len(sample0) != num_fields:
        raise ValueError(f"frame 0 len != {num_fields}")

    dtypes = [sample0[k].dtype for k in range(num_fields)]
    ndims = [sample0[k].ndim for k in range(num_fields)]
    sample_shapes = [tuple(sample0[k].shape) for k in range(num_fields)]
    fixed_shape = [True] * num_fields

    for i in range(1, num_frames):
        frame = get_frame(i)
        if len(frame) != num_fields:
            raise ValueError(f"frame {i} len != {num_fields}")

        for k in range(num_fields):
            t = frame[k]
            if t.dtype != dtypes[k]:
                raise TypeError(
                    f"Field {k}: dtype mismatch at frame {i}, "
                    f"expected {dtypes[k]}, got {t.dtype}"
                )
            if t.ndim != ndims[k]:
                raise ValueError(
                    f"Field {k}: ndim mismatch at frame {i}, "
                    f"expected {ndims[k]}, got {t.ndim}"
                )
            if tuple(t.shape) != sample_shapes[k]:
                fixed_shape[k] = False

    return {
        "fixed_shape": fixed_shape,
        "dtypes": dtypes,
        "ndims": ndims,
        "sample_shapes": sample_shapes,
    }


# =========================================================
# stream writer
# =========================================================

class StreamFrameCacheWriter:
    """
    真正可流式写入的实现：

    固定 shape 字段：
        直接写入 zarr dataset: [num_frames, ...]

    变长字段：
        写入 append-only 二进制文件 field_k_data.bin
        同时内存记录 offsets/shapes
        finalize 时把 offsets/shapes 和元信息写到 zarr

    最终读取时仍然可还原为：
        frame = [tensor0, tensor1, ..., tensor14]
    """

    def __init__(
        self,
        out_dir: str,
        num_frames: int,
        sample_frame: Sequence[torch.Tensor],
        fixed_shape_flags: Sequence[bool],
        compressor_name: str = "zstd",
        clevel: int = 3,
        shuffle: str = "bitshuffle",
        chunk_frames_fixed: int = 64,
    ):
        if len(sample_frame) != len(fixed_shape_flags):
            raise ValueError("sample_frame and fixed_shape_flags length mismatch")

        self.out_dir = out_dir
        self.zarr_path = os.path.join(out_dir, "cache.zarr")
        self.var_dir = os.path.join(out_dir, "var_data")
        self.meta_json = os.path.join(out_dir, "meta.json")

        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(self.var_dir, exist_ok=True)

        shuffle_map = {
            "shuffle": Blosc.SHUFFLE,
            "bitshuffle": Blosc.BITSHUFFLE,
            "noshuffle": Blosc.NOSHUFFLE,
        }
        if shuffle not in shuffle_map:
            raise ValueError(f"Invalid shuffle: {shuffle}")

        self.compressor = Blosc(
            cname=compressor_name,
            clevel=clevel,
            shuffle=shuffle_map[shuffle],
        )

        self.root = zarr.open_group(self.zarr_path, mode="w")
        self.root.attrs["format"] = "stream_frame_cache_v1"
        self.root.attrs["num_frames"] = int(num_frames)
        self.root.attrs["num_fields"] = int(len(sample_frame))

        self.fields_group = self.root.create_group("fields")

        self.num_frames = int(num_frames)
        self.num_fields = int(len(sample_frame))
        self.chunk_frames_fixed = int(chunk_frames_fixed)

        self.fixed_shape_flags = [bool(x) for x in fixed_shape_flags]
        self.current_index = 0

        # 固定 shape 字段的 dataset
        self.fixed_datasets: Dict[int, Any] = {}

        # 变长字段的信息
        self.var_infos: Dict[int, Dict[str, Any]] = {}

        self.field_meta: List[Dict[str, Any]] = []

        self._init_fields(sample_frame)

    def _init_fields(self, sample_frame: Sequence[torch.Tensor]):
        for k, t in enumerate(sample_frame):
            fg = self.fields_group.create_group(f"field_{k}")

            torch_dtype_str = torch_dtype_to_str(t.dtype)
            ndim = int(t.ndim)
            sample_shape = tuple(t.shape)
            fixed_shape = self.fixed_shape_flags[k]

            fg.attrs["torch_dtype"] = torch_dtype_str
            fg.attrs["ndim"] = ndim
            fg.attrs["fixed_shape"] = fixed_shape
            fg.attrs["sample_shape"] = sample_shape

            storage_arr = tensor_to_numpy_for_storage(t)
            storage_dtype = storage_arr.dtype

            meta = {
                "field_idx": k,
                "torch_dtype": torch_dtype_str,
                "storage_dtype": str(np.dtype(storage_dtype)),
                "ndim": ndim,
                "fixed_shape": fixed_shape,
                "sample_shape": list(sample_shape),
            }

            if fixed_shape:
                ds = fg.create_dataset(
                    "data",
                    shape=(self.num_frames,) + sample_shape,
                    chunks=(min(self.chunk_frames_fixed, self.num_frames),) + sample_shape,
                    dtype=storage_dtype,
                    compressor=self.compressor,
                    overwrite=True,
                )
                self.fixed_datasets[k] = ds
            else:
                bin_path = os.path.join(self.var_dir, f"field_{k}_data.bin")
                fp = open(bin_path, "ab")

                self.var_infos[k] = {
                    "bin_path": bin_path,
                    "fp": fp,
                    "offsets": [0],           # 以“元素数”为单位，不是字节
                    "shapes": [],
                    "storage_dtype": np.dtype(storage_dtype),
                    "torch_dtype": t.dtype,
                    "ndim": ndim,
                }

                meta["bin_path"] = os.path.basename(bin_path)

            self.field_meta.append(meta)

    def write_frame(self, frame: Sequence[torch.Tensor]):
        """
        流式写入一帧
        """
        idx = self.current_index
        if idx >= self.num_frames:
            raise IndexError(
                f"Too many frames written: already {self.current_index}, num_frames={self.num_frames}"
            )
        if len(frame) != self.num_fields:
            raise ValueError(
                f"frame length mismatch: expected {self.num_fields}, got {len(frame)}"
            )

        for k, t in enumerate(frame):
            meta = self.field_meta[k]
            expected_torch_dtype = str_to_torch_dtype(meta["torch_dtype"])
            if t.dtype != expected_torch_dtype:
                raise TypeError(
                    f"Field {k}: dtype mismatch at frame {idx}, "
                    f"expected {expected_torch_dtype}, got {t.dtype}"
                )
            if t.ndim != meta["ndim"]:
                raise ValueError(
                    f"Field {k}: ndim mismatch at frame {idx}, "
                    f"expected {meta['ndim']}, got {t.ndim}"
                )

            arr = tensor_to_numpy_for_storage(t)

            if meta["fixed_shape"]:
                expected_shape = tuple(meta["sample_shape"])
                if tuple(t.shape) != expected_shape:
                    raise ValueError(
                        f"Field {k}: fixed shape mismatch at frame {idx}, "
                        f"expected {expected_shape}, got {tuple(t.shape)}"
                    )
                self.fixed_datasets[k][idx] = arr
            else:
                info = self.var_infos[k]
                flat = arr.reshape(-1)
                # 直接追加写二进制
                flat.tofile(info["fp"])
                info["shapes"].append(tuple(t.shape))
                info["offsets"].append(info["offsets"][-1] + flat.size)

        self.current_index += 1

    def finalize(self):
        """
        完成写入：
        - 检查帧数
        - 将变长字段的 offsets/shapes 写入 zarr
        - 保存总 meta.json
        """
        if self.current_index != self.num_frames:
            raise ValueError(
                f"Written frames ({self.current_index}) != expected num_frames ({self.num_frames})"
            )

        for k, info in self.var_infos.items():
            # 关闭文件句柄
            info["fp"].flush()
            info["fp"].close()

            fg = self.fields_group[f"field_{k}"]

            offsets = np.asarray(info["offsets"], dtype=np.int64)
            shapes = np.asarray(info["shapes"], dtype=np.int64)
            if shapes.ndim == 1:
                shapes = shapes[:, None]

            fg.create_dataset(
                "offsets",
                data=offsets,
                shape=offsets.shape,
                chunks=offsets.shape,
                dtype=offsets.dtype,
                compressor=self.compressor,
                overwrite=True,
            )

            fg.create_dataset(
                "shapes",
                data=shapes,
                shape=shapes.shape,
                chunks=(min(len(shapes), 1024), shapes.shape[1]),
                dtype=shapes.dtype,
                compressor=self.compressor,
                overwrite=True,
            )

        with open(self.meta_json, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "format": "stream_frame_cache_v1",
                    "num_frames": self.num_frames,
                    "num_fields": self.num_fields,
                    "field_meta": self.field_meta,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


# =========================================================
# reader
# =========================================================

class StreamFrameCacheDataset:
    """
    按帧读取，返回的结构与你原始 frames[i] 一样：
        List[torch.Tensor]  # 长度=num_fields
    """

    def __init__(self, out_dir: str, device: str = "cpu"):
        self.out_dir = out_dir
        self.zarr_path = os.path.join(out_dir, "cache.zarr")
        self.var_dir = os.path.join(out_dir, "var_data")
        self.meta_json = os.path.join(out_dir, "meta.json")
        self.device = device

        self.root = zarr.open_group(self.zarr_path, mode="r")
        self.fields_group = self.root["fields"]

        with open(self.meta_json, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.num_frames = int(meta["num_frames"])
        self.num_fields = int(meta["num_fields"])
        self.field_meta = meta["field_meta"]

        self.var_mmaps: Dict[int, np.memmap] = {}
        self.var_offsets = {}
        self.var_shapes = {}

        self._init_var_fields()

    def _init_var_fields(self):
        for meta in self.field_meta:
            k = int(meta["field_idx"])
            if meta["fixed_shape"]:
                continue

            fg = self.fields_group[f"field_{k}"]
            offsets = np.asarray(fg["offsets"][:], dtype=np.int64)
            shapes = np.asarray(fg["shapes"][:], dtype=np.int64)

            bin_path = os.path.join(self.var_dir, meta["bin_path"])
            storage_dtype = np.dtype(meta["storage_dtype"])

            total_elems = int(offsets[-1])
            mm = np.memmap(bin_path, mode="r", dtype=storage_dtype, shape=(total_elems,))

            self.var_offsets[k] = offsets
            self.var_shapes[k] = shapes
            self.var_mmaps[k] = mm

    def __len__(self):
        return self.num_frames

    def _load_field(self, field_idx: int, frame_idx: int) -> torch.Tensor:
        meta = self.field_meta[field_idx]
        fg = self.fields_group[f"field_{field_idx}"]
        torch_dtype = str_to_torch_dtype(meta["torch_dtype"])

        if meta["fixed_shape"]:
            arr = np.asarray(fg["data"][frame_idx])
            t = numpy_from_storage_to_tensor(arr, torch_dtype)
            if self.device != "cpu":
                t = t.to(self.device, non_blocking=True)
            return t

        offsets = self.var_offsets[field_idx]
        shapes = self.var_shapes[field_idx]
        mm = self.var_mmaps[field_idx]

        start = int(offsets[frame_idx])
        end = int(offsets[frame_idx + 1])
        shape = tuple(int(x) for x in shapes[frame_idx].tolist())

        flat = np.asarray(mm[start:end])
        arr = flat.reshape(shape)
        t = numpy_from_storage_to_tensor(arr, torch_dtype)

        if self.device != "cpu":
            t = t.to(self.device, non_blocking=True)
        return t

    def __getitem__(self, idx: int) -> List[torch.Tensor]:
        if idx < 0:
            idx += self.num_frames
        if idx < 0 or idx >= self.num_frames:
            raise IndexError(idx)

        return [self._load_field(k, idx) for k in range(self.num_fields)]


# =========================================================
# helper APIs
# =========================================================

def build_stream_cache(
    get_frame: Callable[[int], Sequence[torch.Tensor]],
    num_frames: int,
    out_dir: str,
    num_fields: int = 15,
    compressor_name: str = "zstd",
    clevel: int = 3,
    shuffle: str = "bitshuffle",
    chunk_frames_fixed: int = 64,
    verbose_every: int = 100,
):
    """
    标准构建流程：
    1) 第一遍分析 fixed_shape
    2) 第二遍流式写入
    """
    info = analyze_dataset(get_frame, num_frames, num_fields=num_fields)
    sample0 = get_frame(0)

    writer = StreamFrameCacheWriter(
        out_dir=out_dir,
        num_frames=num_frames,
        sample_frame=sample0,
        fixed_shape_flags=info["fixed_shape"],
        compressor_name=compressor_name,
        clevel=clevel,
        shuffle=shuffle,
        chunk_frames_fixed=chunk_frames_fixed,
    )

    for i in range(num_frames):
        frame = get_frame(i)
        writer.write_frame(frame)
        if verbose_every > 0 and (i % verbose_every == 0):
            print(f"[build_stream_cache] writing frame {i}/{num_frames}")

    writer.finalize()
    print(f"[build_stream_cache] done: {out_dir}")


def verify_lossless(
    get_frame: Callable[[int], Sequence[torch.Tensor]],
    cache_dir: str,
    num_frames: int,
    num_fields: int = 15,
    check_all: bool = True,
    max_check_frames: int = 100,
):
    """
    校验缓存读回结果是否与原始逐帧结果一致。
    """
    ds = StreamFrameCacheDataset(cache_dir)
    assert len(ds) == num_frames

    if check_all:
        indices = range(num_frames)
    else:
        indices = range(min(num_frames, max_check_frames))

    for i in indices:
        orig = get_frame(i)
        rec = ds[i]
        assert len(orig) == len(rec) == num_fields

        for k in range(num_fields):
            a = orig[k].cpu()
            b = rec[k].cpu()

            assert a.dtype == b.dtype, f"dtype mismatch at frame={i}, field={k}"
            assert tuple(a.shape) == tuple(b.shape), f"shape mismatch at frame={i}, field={k}"
            assert torch.equal(a, b), f"value mismatch at frame={i}, field={k}"

    print("[verify_lossless] passed.")


class TorchFrameDataset(torch.utils.data.Dataset):
    """
    方便直接喂给 PyTorch DataLoader
    """
    def __init__(self, cache_dir: str, device: str = "cpu"):
        self.ds = StreamFrameCacheDataset(cache_dir, device=device)

    def __len__(self):
        return len(self.ds)

    def __getitem__(self, idx):
        return self.ds[idx]