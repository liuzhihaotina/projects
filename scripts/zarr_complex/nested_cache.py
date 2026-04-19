import os
import io
import json
from typing import Any, Dict, List, Tuple, Callable

import numpy as np
import torch
import zarr
from numcodecs import Blosc


# =========================================================
# dtype utils
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
        raise TypeError(f"Unsupported torch dtype string: {dtype_str}")
    return mapping[dtype_str]


def storage_numpy_dtype_from_torch(torch_dtype: torch.dtype):
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
    if t.device.type != "cpu":
        t = t.cpu()
    if not t.is_contiguous():
        t = t.contiguous()

    if t.dtype == torch.bfloat16:
        return t.view(torch.uint16).numpy()

    return t.numpy().astype(storage_numpy_dtype_from_torch(t.dtype), copy=False)


def numpy_to_tensor_from_storage(arr: np.ndarray, torch_dtype: torch.dtype) -> torch.Tensor:
    if torch_dtype == torch.bfloat16:
        t = torch.from_numpy(arr.view(np.uint16))
        return t.view(torch.bfloat16)
    return torch.from_numpy(arr)


# =========================================================
# path utils
# =========================================================

def path_join(path: Tuple[str, ...]) -> str:
    return "/".join(path)


def sanitize_path_str(path_str: str) -> str:
    # 仅作为文件名使用
    return path_str.replace("/", "__")


# =========================================================
# schema inference
# =========================================================

def infer_node_schema(obj: Any, path: Tuple[str, ...] = ()) -> Dict[str, Any]:
    """
    推断单个样本的 schema。
    要求后续样本结构与类型一致：
    - dict 的 key 集合一致
    - list/tuple 的长度一致（除 list[str] / tensor 这种叶子）
    """
    if obj is None:
        return {"kind": "none", "path": path}

    if isinstance(obj, torch.Tensor):
        return {
            "kind": "tensor",
            "path": path,
            "torch_dtype": torch_dtype_to_str(obj.dtype),
            "ndim": int(obj.ndim),
            "sample_shape": list(obj.shape),
        }

    if isinstance(obj, np.ndarray):
        return {
            "kind": "ndarray",
            "path": path,
            "dtype": str(obj.dtype),
            "ndim": int(obj.ndim),
            "sample_shape": list(obj.shape),
        }

    if isinstance(obj, str):
        return {"kind": "str", "path": path}

    if isinstance(obj, bool):
        return {"kind": "bool", "path": path}

    if isinstance(obj, int) and not isinstance(obj, bool):
        return {"kind": "int", "path": path}

    if isinstance(obj, float):
        return {"kind": "float", "path": path}

    if isinstance(obj, dict):
        keys = list(obj.keys())
        children = []
        for k in keys:
            child_schema = infer_node_schema(obj[k], path + (f"d:{k}",))
            children.append({
                "key": k,
                "schema": child_schema,
            })
        return {
            "kind": "dict",
            "path": path,
            "keys": keys,
            "children": children,
        }

    if isinstance(obj, tuple):
        children = []
        for i, x in enumerate(obj):
            child_schema = infer_node_schema(x, path + (f"t:{i}",))
            children.append(child_schema)
        return {
            "kind": "tuple",
            "path": path,
            "length": len(obj),
            "children": children,
        }

    if isinstance(obj, list):
        # 特判 list[str]
        if all(isinstance(x, str) for x in obj):
            return {"kind": "list_str", "path": path}

        # 一般 list：要求长度固定，递归子节点
        children = []
        for i, x in enumerate(obj):
            child_schema = infer_node_schema(x, path + (f"l:{i}",))
            children.append(child_schema)

        return {
            "kind": "list",
            "path": path,
            "length": len(obj),
            "children": children,
        }

    raise TypeError(f"Unsupported object type at path={path}: {type(obj)}")


def validate_against_schema(obj: Any, schema: Dict[str, Any], path: Tuple[str, ...] = ()):
    kind = schema["kind"]

    if kind == "none":
        if obj is not None:
            raise TypeError(f"path={path}: expected None, got {type(obj)}")
        return

    if kind == "tensor":
        if not isinstance(obj, torch.Tensor):
            raise TypeError(f"path={path}: expected torch.Tensor, got {type(obj)}")
        expected_dtype = str_to_torch_dtype(schema["torch_dtype"])
        if obj.dtype != expected_dtype:
            raise TypeError(
                f"path={path}: tensor dtype mismatch, expected {expected_dtype}, got {obj.dtype}"
            )
        if obj.ndim != schema["ndim"]:
            raise ValueError(
                f"path={path}: tensor ndim mismatch, expected {schema['ndim']}, got {obj.ndim}"
            )
        return

    if kind == "ndarray":
        if not isinstance(obj, np.ndarray):
            raise TypeError(f"path={path}: expected np.ndarray, got {type(obj)}")
        if str(obj.dtype) != schema["dtype"]:
            raise TypeError(
                f"path={path}: ndarray dtype mismatch, expected {schema['dtype']}, got {obj.dtype}"
            )
        if obj.ndim != schema["ndim"]:
            raise ValueError(
                f"path={path}: ndarray ndim mismatch, expected {schema['ndim']}, got {obj.ndim}"
            )
        return

    if kind == "str":
        if not isinstance(obj, str):
            raise TypeError(f"path={path}: expected str, got {type(obj)}")
        return

    if kind == "list_str":
        if not isinstance(obj, list):
            raise TypeError(f"path={path}: expected list[str], got {type(obj)}")
        for x in obj:
            if not isinstance(x, str):
                raise TypeError(f"path={path}: expected list[str], got element {type(x)}")
        return

    if kind == "bool":
        if not isinstance(obj, bool):
            raise TypeError(f"path={path}: expected bool, got {type(obj)}")
        return

    if kind == "int":
        if not (isinstance(obj, int) and not isinstance(obj, bool)):
            raise TypeError(f"path={path}: expected int, got {type(obj)}")
        return

    if kind == "float":
        if not isinstance(obj, float):
            raise TypeError(f"path={path}: expected float, got {type(obj)}")
        return

    if kind == "dict":
        if not isinstance(obj, dict):
            raise TypeError(f"path={path}: expected dict, got {type(obj)}")
        expected_keys = schema["keys"]
        if list(obj.keys()) != expected_keys:
            raise ValueError(
                f"path={path}: dict keys mismatch, expected {expected_keys}, got {list(obj.keys())}"
            )
        for child in schema["children"]:
            k = child["key"]
            validate_against_schema(obj[k], child["schema"], path + (f"d:{k}",))
        return

    if kind == "tuple":
        if not isinstance(obj, tuple):
            raise TypeError(f"path={path}: expected tuple, got {type(obj)}")
        if len(obj) != schema["length"]:
            raise ValueError(
                f"path={path}: tuple length mismatch, expected {schema['length']}, got {len(obj)}"
            )
        for i, child_schema in enumerate(schema["children"]):
            validate_against_schema(obj[i], child_schema, path + (f"t:{i}",))
        return

    if kind == "list":
        if not isinstance(obj, list):
            raise TypeError(f"path={path}: expected list, got {type(obj)}")
        if len(obj) != schema["length"]:
            raise ValueError(
                f"path={path}: list length mismatch, expected {schema['length']}, got {len(obj)}"
            )
        for i, child_schema in enumerate(schema["children"]):
            validate_against_schema(obj[i], child_schema, path + (f"l:{i}",))
        return

    raise TypeError(f"Unknown schema kind: {kind}")


def collect_leaf_schemas(schema: Dict[str, Any], out: List[Dict[str, Any]]):
    kind = schema["kind"]
    if kind in ("dict", "tuple", "list"):
        if kind == "dict":
            for child in schema["children"]:
                collect_leaf_schemas(child["schema"], out)
        else:
            for child in schema["children"]:
                collect_leaf_schemas(child, out)
    else:
        out.append(schema)


# =========================================================
# fixed-shape analysis for tensor / ndarray leaves
# =========================================================

def get_by_schema_path(obj: Any, path: Tuple[str, ...]) -> Any:
    cur = obj
    for p in path:
        if p.startswith("d:"):
            cur = cur[p[2:]]
        elif p.startswith("l:"):
            cur = cur[int(p[2:])]
        elif p.startswith("t:"):
            cur = cur[int(p[2:])]
        else:
            raise ValueError(f"Invalid path token: {p}")
    return cur


def analyze_fixed_shape(
    get_sample: Callable[[int], Any],
    num_samples: int,
    schema: Dict[str, Any],
) -> Dict[str, bool]:
    """
    对所有 tensor / ndarray leaf 判断 shape 是否固定
    返回 {path_str: bool}
    """
    leaves = []
    collect_leaf_schemas(schema, leaves)

    tensor_like_leaves = []
    for leaf in leaves:
        if leaf["kind"] in ("tensor", "ndarray"):
            tensor_like_leaves.append(leaf)

    fixed = {}
    first = get_sample(0)

    for leaf in tensor_like_leaves:
        path = tuple(leaf["path"])
        path_str = path_join(path)
        x0 = get_by_schema_path(first, path)
        shape0 = tuple(x0.shape)
        same = True

        for i in range(1, num_samples):
            x = get_by_schema_path(get_sample(i), path)
            if tuple(x.shape) != shape0:
                same = False
                break

        fixed[path_str] = same

    return fixed


# =========================================================
# scalar dtype mapping
# =========================================================

SCALAR_KIND_TO_NP = {
    "bool": np.bool_,
    "int": np.int64,
    "float": np.float64,
}


# =========================================================
# writer
# =========================================================

class NestedStreamCacheWriter:
    def __init__(
        self,
        out_dir: str,
        num_samples: int,
        sample0: Any,
        schema: Dict[str, Any],
        fixed_shape_map: Dict[str, bool],
        compressor_name: str = "zstd",
        clevel: int = 3,
        shuffle: str = "bitshuffle",
        chunk_samples_fixed: int = 64,
    ):
        self.out_dir = out_dir
        self.zarr_path = os.path.join(out_dir, "cache.zarr")
        self.bin_dir = os.path.join(out_dir, "bin")
        self.schema_json = os.path.join(out_dir, "schema.json")

        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(self.bin_dir, exist_ok=True)

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
        self.root.attrs["format"] = "nested_stream_cache_v1"
        self.root.attrs["num_samples"] = int(num_samples)

        self.leaves_group = self.root.create_group("leaves")

        self.num_samples = int(num_samples)
        self.schema = schema
        self.fixed_shape_map = fixed_shape_map
        self.chunk_samples_fixed = int(chunk_samples_fixed)
        self.current_index = 0

        # leaf writers by path_str
        self.leaf_writers: Dict[str, Dict[str, Any]] = {}

        self._init_leaf_writers(sample0)

        with open(self.schema_json, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "format": "nested_stream_cache_v1",
                    "num_samples": self.num_samples,
                    "schema": self.schema,
                    "fixed_shape_map": self.fixed_shape_map,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _leaf_group(self, path_str: str):
        name = sanitize_path_str(path_str if path_str else "__root__")
        return self.leaves_group.create_group(name)

    def _init_leaf_writers(self, sample0: Any):
        leaves = []
        collect_leaf_schemas(self.schema, leaves)

        for leaf in leaves:
            path = tuple(leaf["path"])
            path_str = path_join(path)
            kind = leaf["kind"]
            obj0 = get_by_schema_path(sample0, path)

            lg = self._leaf_group(path_str)
            lg.attrs["path_str"] = path_str
            lg.attrs["kind"] = kind

            if kind == "tensor":
                torch_dtype = str_to_torch_dtype(leaf["torch_dtype"])
                storage_arr = tensor_to_numpy_for_storage(obj0)
                storage_dtype = storage_arr.dtype
                fixed = self.fixed_shape_map[path_str]

                lg.attrs["torch_dtype"] = leaf["torch_dtype"]
                lg.attrs["ndim"] = int(leaf["ndim"])
                lg.attrs["fixed_shape"] = bool(fixed)

                if fixed:
                    shape0 = tuple(obj0.shape)
                    ds = lg.create_dataset(
                        "data",
                        shape=(self.num_samples,) + shape0,
                        chunks=(min(self.chunk_samples_fixed, self.num_samples),) + shape0,
                        dtype=storage_dtype,
                        compressor=self.compressor,
                        overwrite=True,
                    )
                    self.leaf_writers[path_str] = {
                        "kind": kind,
                        "fixed": True,
                        "dataset": ds,
                        "shape0": shape0,
                        "torch_dtype": torch_dtype,
                    }
                else:
                    bin_path = os.path.join(self.bin_dir, f"{sanitize_path_str(path_str)}.bin")
                    fp = open(bin_path, "ab")
                    self.leaf_writers[path_str] = {
                        "kind": kind,
                        "fixed": False,
                        "bin_path": os.path.basename(bin_path),
                        "fp": fp,
                        "offsets": [0],
                        "shapes": [],
                        "storage_dtype": str(np.dtype(storage_dtype)),
                        "torch_dtype": torch_dtype,
                    }
                    lg.attrs["bin_path"] = os.path.basename(bin_path)
                    lg.attrs["storage_dtype"] = str(np.dtype(storage_dtype))

            elif kind == "ndarray":
                storage_dtype = obj0.dtype
                fixed = self.fixed_shape_map[path_str]

                lg.attrs["dtype"] = str(obj0.dtype)
                lg.attrs["ndim"] = int(obj0.ndim)
                lg.attrs["fixed_shape"] = bool(fixed)

                if fixed:
                    shape0 = tuple(obj0.shape)
                    ds = lg.create_dataset(
                        "data",
                        shape=(self.num_samples,) + shape0,
                        chunks=(min(self.chunk_samples_fixed, self.num_samples),) + shape0,
                        dtype=storage_dtype,
                        compressor=self.compressor,
                        overwrite=True,
                    )
                    self.leaf_writers[path_str] = {
                        "kind": kind,
                        "fixed": True,
                        "dataset": ds,
                        "shape0": shape0,
                        "dtype": str(obj0.dtype),
                    }
                else:
                    bin_path = os.path.join(self.bin_dir, f"{sanitize_path_str(path_str)}.bin")
                    fp = open(bin_path, "ab")
                    self.leaf_writers[path_str] = {
                        "kind": kind,
                        "fixed": False,
                        "bin_path": os.path.basename(bin_path),
                        "fp": fp,
                        "offsets": [0],
                        "shapes": [],
                        "storage_dtype": str(np.dtype(storage_dtype)),
                        "dtype": str(obj0.dtype),
                    }
                    lg.attrs["bin_path"] = os.path.basename(bin_path)
                    lg.attrs["storage_dtype"] = str(np.dtype(storage_dtype))

            elif kind in ("bool", "int", "float"):
                np_dtype = SCALAR_KIND_TO_NP[kind]
                ds = lg.create_dataset(
                    "data",
                    shape=(self.num_samples,),
                    chunks=(min(self.chunk_samples_fixed, self.num_samples),),
                    dtype=np_dtype,
                    compressor=self.compressor,
                    overwrite=True,
                )
                self.leaf_writers[path_str] = {
                    "kind": kind,
                    "dataset": ds,
                }

            elif kind == "none":
                # 不需要实际存值
                self.leaf_writers[path_str] = {
                    "kind": kind
                }

            elif kind == "str":
                bin_path = os.path.join(self.bin_dir, f"{sanitize_path_str(path_str)}.bin")
                fp = open(bin_path, "ab")
                lg.attrs["bin_path"] = os.path.basename(bin_path)
                self.leaf_writers[path_str] = {
                    "kind": kind,
                    "fp": fp,
                    "bin_path": os.path.basename(bin_path),
                    "offsets": [0],  # byte offsets
                }

            elif kind == "list_str":
                # 两层：
                # 1) 所有字符串 utf8 bytes 拼到一个bin
                # 2) str_offsets: 每个字符串边界
                # 3) sample_offsets: 每个样本对应字符串个数边界
                bin_path = os.path.join(self.bin_dir, f"{sanitize_path_str(path_str)}.bin")
                fp = open(bin_path, "ab")
                lg.attrs["bin_path"] = os.path.basename(bin_path)
                self.leaf_writers[path_str] = {
                    "kind": kind,
                    "fp": fp,
                    "bin_path": os.path.basename(bin_path),
                    "str_byte_offsets": [0],
                    "sample_str_offsets": [0],
                }

            else:
                raise TypeError(f"Unsupported leaf kind: {kind}")

    def write_sample(self, sample: Any):
        idx = self.current_index
        if idx >= self.num_samples:
            raise IndexError(
                f"Too many samples written: {idx} >= {self.num_samples}"
            )

        validate_against_schema(sample, self.schema)

        leaves = []
        collect_leaf_schemas(self.schema, leaves)

        for leaf in leaves:
            path = tuple(leaf["path"])
            path_str = path_join(path)
            writer = self.leaf_writers[path_str]
            obj = get_by_schema_path(sample, path)
            kind = leaf["kind"]

            if kind == "tensor":
                arr = tensor_to_numpy_for_storage(obj)
                if writer["fixed"]:
                    if tuple(obj.shape) != writer["shape0"]:
                        raise ValueError(
                            f"path={path_str}: fixed tensor shape mismatch, "
                            f"expected {writer['shape0']}, got {tuple(obj.shape)}"
                        )
                    writer["dataset"][idx] = arr
                else:
                    flat = arr.reshape(-1)
                    flat.tofile(writer["fp"])
                    writer["shapes"].append(tuple(obj.shape))
                    writer["offsets"].append(writer["offsets"][-1] + flat.size)

            elif kind == "ndarray":
                arr = obj
                if writer["fixed"]:
                    if tuple(arr.shape) != writer["shape0"]:
                        raise ValueError(
                            f"path={path_str}: fixed ndarray shape mismatch, "
                            f"expected {writer['shape0']}, got {tuple(arr.shape)}"
                        )
                    writer["dataset"][idx] = arr
                else:
                    flat = arr.reshape(-1)
                    flat.tofile(writer["fp"])
                    writer["shapes"].append(tuple(arr.shape))
                    writer["offsets"].append(writer["offsets"][-1] + flat.size)

            elif kind in ("bool", "int", "float"):
                writer["dataset"][idx] = obj

            elif kind == "none":
                pass

            elif kind == "str":
                b = obj.encode("utf-8")
                writer["fp"].write(b)
                writer["offsets"].append(writer["offsets"][-1] + len(b))

            elif kind == "list_str":
                for s in obj:
                    b = s.encode("utf-8")
                    writer["fp"].write(b)
                    writer["str_byte_offsets"].append(writer["str_byte_offsets"][-1] + len(b))
                writer["sample_str_offsets"].append(writer["sample_str_offsets"][-1] + len(obj))

            else:
                raise TypeError(f"Unsupported kind: {kind}")

        self.current_index += 1

    def finalize(self):
        if self.current_index != self.num_samples:
            raise ValueError(
                f"Written samples ({self.current_index}) != expected num_samples ({self.num_samples})"
            )

        leaves = []
        collect_leaf_schemas(self.schema, leaves)

        for leaf in leaves:
            path_str = path_join(tuple(leaf["path"]))
            writer = self.leaf_writers[path_str]
            lg = self._get_existing_leaf_group(path_str)
            kind = writer["kind"]

            if kind in ("tensor", "ndarray") and not writer.get("fixed", True):
                writer["fp"].flush()
                writer["fp"].close()

                offsets = np.asarray(writer["offsets"], dtype=np.int64)
                shapes = np.asarray(writer["shapes"], dtype=np.int64)
                if shapes.ndim == 1:
                    shapes = shapes[:, None]

                lg.create_dataset(
                    "offsets",
                    data=offsets,
                    shape=offsets.shape,
                    chunks=offsets.shape,
                    dtype=offsets.dtype,
                    compressor=self.compressor,
                    overwrite=True,
                )
                lg.create_dataset(
                    "shapes",
                    data=shapes,
                    shape=shapes.shape,
                    chunks=(min(len(shapes), 1024), shapes.shape[1]),
                    dtype=shapes.dtype,
                    compressor=self.compressor,
                    overwrite=True,
                )

            elif kind == "str":
                writer["fp"].flush()
                writer["fp"].close()
                offsets = np.asarray(writer["offsets"], dtype=np.int64)
                lg.create_dataset(
                    "offsets",
                    data=offsets,
                    shape=offsets.shape,
                    chunks=offsets.shape,
                    dtype=offsets.dtype,
                    compressor=self.compressor,
                    overwrite=True,
                )

            elif kind == "list_str":
                writer["fp"].flush()
                writer["fp"].close()

                str_byte_offsets = np.asarray(writer["str_byte_offsets"], dtype=np.int64)
                sample_str_offsets = np.asarray(writer["sample_str_offsets"], dtype=np.int64)

                lg.create_dataset(
                    "str_byte_offsets",
                    data=str_byte_offsets,
                    shape=str_byte_offsets.shape,
                    chunks=str_byte_offsets.shape,
                    dtype=str_byte_offsets.dtype,
                    compressor=self.compressor,
                    overwrite=True,
                )
                lg.create_dataset(
                    "sample_str_offsets",
                    data=sample_str_offsets,
                    shape=sample_str_offsets.shape,
                    chunks=sample_str_offsets.shape,
                    dtype=sample_str_offsets.dtype,
                    compressor=self.compressor,
                    overwrite=True,
                )

    def _get_existing_leaf_group(self, path_str: str):
        name = sanitize_path_str(path_str if path_str else "__root__")
        return self.leaves_group[name]


# =========================================================
# reader
# =========================================================

class NestedStreamCacheDataset:
    def __init__(self, out_dir: str, device: str = "cpu"):
        self.out_dir = out_dir
        self.zarr_path = os.path.join(out_dir, "cache.zarr")
        self.bin_dir = os.path.join(out_dir, "bin")
        self.schema_json = os.path.join(out_dir, "schema.json")
        self.device = device

        self.root = zarr.open_group(self.zarr_path, mode="r")
        self.leaves_group = self.root["leaves"]

        with open(self.schema_json, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.num_samples = int(meta["num_samples"])
        self.schema = meta["schema"]

        self.leaf_readers: Dict[str, Dict[str, Any]] = {}
        self._init_leaf_readers()

    def _leaf_group(self, path_str: str):
        name = sanitize_path_str(path_str if path_str else "__root__")
        return self.leaves_group[name]

    def _init_leaf_readers(self):
        leaves = []
        collect_leaf_schemas(self.schema, leaves)

        for leaf in leaves:
            path_str = path_join(tuple(leaf["path"]))
            kind = leaf["kind"]
            lg = self._leaf_group(path_str)

            if kind == "tensor":
                fixed = bool(lg.attrs["fixed_shape"])
                torch_dtype = str_to_torch_dtype(lg.attrs["torch_dtype"])

                if fixed:
                    self.leaf_readers[path_str] = {
                        "kind": kind,
                        "fixed": True,
                        "dataset": lg["data"],
                        "torch_dtype": torch_dtype,
                    }
                else:
                    storage_dtype = np.dtype(lg.attrs["storage_dtype"])
                    offsets = np.asarray(lg["offsets"][:], dtype=np.int64)
                    shapes = np.asarray(lg["shapes"][:], dtype=np.int64)
                    bin_path = os.path.join(self.bin_dir, lg.attrs["bin_path"])
                    total_elems = int(offsets[-1])
                    mm = np.memmap(bin_path, mode="r", dtype=storage_dtype, shape=(total_elems,))
                    self.leaf_readers[path_str] = {
                        "kind": kind,
                        "fixed": False,
                        "torch_dtype": torch_dtype,
                        "offsets": offsets,
                        "shapes": shapes,
                        "mm": mm,
                    }

            elif kind == "ndarray":
                fixed = bool(lg.attrs["fixed_shape"])
                dtype = np.dtype(lg.attrs["dtype"])

                if fixed:
                    self.leaf_readers[path_str] = {
                        "kind": kind,
                        "fixed": True,
                        "dataset": lg["data"],
                        "dtype": dtype,
                    }
                else:
                    storage_dtype = np.dtype(lg.attrs["storage_dtype"])
                    offsets = np.asarray(lg["offsets"][:], dtype=np.int64)
                    shapes = np.asarray(lg["shapes"][:], dtype=np.int64)
                    bin_path = os.path.join(self.bin_dir, lg.attrs["bin_path"])
                    total_elems = int(offsets[-1])
                    mm = np.memmap(bin_path, mode="r", dtype=storage_dtype, shape=(total_elems,))
                    self.leaf_readers[path_str] = {
                        "kind": kind,
                        "fixed": False,
                        "dtype": dtype,
                        "offsets": offsets,
                        "shapes": shapes,
                        "mm": mm,
                    }

            elif kind in ("bool", "int", "float"):
                self.leaf_readers[path_str] = {
                    "kind": kind,
                    "dataset": lg["data"],
                }

            elif kind == "none":
                self.leaf_readers[path_str] = {
                    "kind": kind
                }

            elif kind == "str":
                offsets = np.asarray(lg["offsets"][:], dtype=np.int64)
                bin_path = os.path.join(self.bin_dir, lg.attrs["bin_path"])
                total_bytes = int(offsets[-1])
                mm = np.memmap(bin_path, mode="r", dtype=np.uint8, shape=(total_bytes,))
                self.leaf_readers[path_str] = {
                    "kind": kind,
                    "offsets": offsets,
                    "mm": mm,
                }

            elif kind == "list_str":
                str_byte_offsets = np.asarray(lg["str_byte_offsets"][:], dtype=np.int64)
                sample_str_offsets = np.asarray(lg["sample_str_offsets"][:], dtype=np.int64)
                bin_path = os.path.join(self.bin_dir, lg.attrs["bin_path"])
                total_bytes = int(str_byte_offsets[-1])
                mm = np.memmap(bin_path, mode="r", dtype=np.uint8, shape=(total_bytes,))
                self.leaf_readers[path_str] = {
                    "kind": kind,
                    "str_byte_offsets": str_byte_offsets,
                    "sample_str_offsets": sample_str_offsets,
                    "mm": mm,
                }

            else:
                raise TypeError(f"Unsupported kind: {kind}")

    def __len__(self):
        return self.num_samples

    def _read_leaf(self, path_str: str, idx: int):
        reader = self.leaf_readers[path_str]
        kind = reader["kind"]

        if kind == "tensor":
            if reader["fixed"]:
                arr = np.asarray(reader["dataset"][idx])
                t = numpy_to_tensor_from_storage(arr, reader["torch_dtype"])
            else:
                s = int(reader["offsets"][idx])
                e = int(reader["offsets"][idx + 1])
                shape = tuple(int(x) for x in reader["shapes"][idx].tolist())
                arr = np.asarray(reader["mm"][s:e]).reshape(shape)
                t = numpy_to_tensor_from_storage(arr, reader["torch_dtype"])
            if self.device != "cpu":
                t = t.to(self.device, non_blocking=True)
            return t

        if kind == "ndarray":
            if reader["fixed"]:
                return np.asarray(reader["dataset"][idx])
            s = int(reader["offsets"][idx])
            e = int(reader["offsets"][idx + 1])
            shape = tuple(int(x) for x in reader["shapes"][idx].tolist())
            return np.asarray(reader["mm"][s:e]).reshape(shape)

        if kind == "bool":
            return bool(reader["dataset"][idx])

        if kind == "int":
            return int(reader["dataset"][idx])

        if kind == "float":
            return float(reader["dataset"][idx])

        if kind == "none":
            return None

        if kind == "str":
            s = int(reader["offsets"][idx])
            e = int(reader["offsets"][idx + 1])
            b = bytes(np.asarray(reader["mm"][s:e]))
            return b.decode("utf-8")

        if kind == "list_str":
            s_idx = int(reader["sample_str_offsets"][idx])
            e_idx = int(reader["sample_str_offsets"][idx + 1])

            result = []
            for j in range(s_idx, e_idx):
                bs = int(reader["str_byte_offsets"][j])
                be = int(reader["str_byte_offsets"][j + 1])
                b = bytes(np.asarray(reader["mm"][bs:be]))
                result.append(b.decode("utf-8"))
            return result

        raise TypeError(f"Unsupported kind: {kind}")

    def _reconstruct(self, schema: Dict[str, Any], idx: int):
        kind = schema["kind"]
        path_str = path_join(tuple(schema["path"]))

        if kind in ("tensor", "ndarray", "str", "list_str", "bool", "int", "float", "none"):
            return self._read_leaf(path_str, idx)

        if kind == "dict":
            out = {}
            for child in schema["children"]:
                out[child["key"]] = self._reconstruct(child["schema"], idx)
            return out

        if kind == "tuple":
            return tuple(self._reconstruct(child, idx) for child in schema["children"])

        if kind == "list":
            return [self._reconstruct(child, idx) for child in schema["children"]]

        raise TypeError(f"Unsupported schema kind: {kind}")

    def __getitem__(self, idx: int):
        if idx < 0:
            idx += self.num_samples
        if idx < 0 or idx >= self.num_samples:
            raise IndexError(idx)
        return self._reconstruct(self.schema, idx)


# =========================================================
# build helper
# =========================================================

def build_nested_stream_cache(
    get_sample: Callable[[int], Any],
    num_samples: int,
    out_dir: str,
    compressor_name: str = "zstd",
    clevel: int = 3,
    shuffle: str = "bitshuffle",
    chunk_samples_fixed: int = 64,
    verbose_every: int = 100,
):
    """
    两遍构建：
    1) 从第一个样本推断 schema
    2) 全量检查 tensor/ndarray 的 fixed shape
    3) 第二遍流式写入
    """
    sample0 = get_sample(0)
    schema = infer_node_schema(sample0)

    # 先验证所有样本结构一致
    for i in range(num_samples):
        s = get_sample(i)
        validate_against_schema(s, schema)
        if verbose_every > 0 and (i % verbose_every == 0):
            print(f"[validate] {i}/{num_samples}")

    fixed_shape_map = analyze_fixed_shape(get_sample, num_samples, schema)

    writer = NestedStreamCacheWriter(
        out_dir=out_dir,
        num_samples=num_samples,
        sample0=sample0,
        schema=schema,
        fixed_shape_map=fixed_shape_map,
        compressor_name=compressor_name,
        clevel=clevel,
        shuffle=shuffle,
        chunk_samples_fixed=chunk_samples_fixed,
    )

    for i in range(num_samples):
        s = get_sample(i)
        writer.write_sample(s)
        if verbose_every > 0 and (i % verbose_every == 0):
            print(f"[write] {i}/{num_samples}")

    writer.finalize()
    print(f"[build_nested_stream_cache] done: {out_dir}")


# =========================================================
# verify
# =========================================================

def deep_equal(a: Any, b: Any) -> bool:
    if type(a) != type(b):
        return False

    if isinstance(a, torch.Tensor):
        return a.dtype == b.dtype and tuple(a.shape) == tuple(b.shape) and torch.equal(a.cpu(), b.cpu())

    if isinstance(a, np.ndarray):
        return a.dtype == b.dtype and a.shape == b.shape and np.array_equal(a, b)

    if isinstance(a, dict):
        if list(a.keys()) != list(b.keys()):
            return False
        return all(deep_equal(a[k], b[k]) for k in a.keys())

    if isinstance(a, tuple):
        return len(a) == len(b) and all(deep_equal(x, y) for x, y in zip(a, b))

    if isinstance(a, list):
        return len(a) == len(b) and all(deep_equal(x, y) for x, y in zip(a, b))

    return a == b


def verify_nested_stream_cache(
    get_sample: Callable[[int], Any],
    cache_dir: str,
    num_samples: int,
    check_all: bool = True,
    max_check: int = 100,
):
    ds = NestedStreamCacheDataset(cache_dir)
    assert len(ds) == num_samples

    indices = range(num_samples) if check_all else range(min(num_samples, max_check))

    for i in indices:
        a = get_sample(i)
        b = ds[i]
        if not deep_equal(a, b):
            raise AssertionError(f"Mismatch at index {i}")

    print("[verify_nested_stream_cache] passed.")