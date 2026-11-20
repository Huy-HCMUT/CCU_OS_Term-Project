#!/usr/bin/env python3
"""Random weights on purpose: background load only, not a classifier (DECISIONS.md D10)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper


def build_cnn1d(width: int) -> tuple[onnx.ModelProto, int]:
    """Construct a synthetic 4-block 1D CNN model (opset 17) and return (model, param_count)."""
    rng = np.random.default_rng(1234 + width)
    initializers: list[onnx.TensorProto] = []
    nodes: list[onnx.NodeProto] = []
    param_count = 0

    def add_param(name: str, shape: tuple[int, ...]) -> None:
        nonlocal param_count
        arr = rng.normal(loc=0.0, scale=0.05, size=shape).astype(np.float32)
        initializers.append(numpy_helper.from_array(arr, name=name))
        param_count += int(arr.size)

    prev = "x"
    in_channels = 1
    for block_idx in range(4):
        w_name = f"conv{block_idx}_w"
        b_name = f"conv{block_idx}_b"
        conv_out = f"conv{block_idx}_out"
        relu_out = f"relu{block_idx}_out"
        pool_out = f"pool{block_idx}_out"

        add_param(w_name, (width, in_channels, 7))
        add_param(b_name, (width,))

        nodes.append(
            helper.make_node(
                "Conv",
                inputs=[prev, w_name, b_name],
                outputs=[conv_out],
                kernel_shape=[7],
                pads=[3, 3],
                strides=[1],
            )
        )
        nodes.append(helper.make_node("Relu", inputs=[conv_out], outputs=[relu_out]))
        nodes.append(
            helper.make_node(
                "MaxPool",
                inputs=[relu_out],
                outputs=[pool_out],
                kernel_shape=[2],
                strides=[2],
            )
        )
        prev = pool_out
        in_channels = width

    flat_out = "flat_out"
    nodes.append(helper.make_node("Flatten", inputs=[prev], outputs=[flat_out], axis=1))

    flat_dim = 64 * width  # 1024 / 2^4 = 64
    add_param("fc_w", (flat_dim, 4))
    add_param("fc_b", (4,))
    nodes.append(
        helper.make_node(
            "Gemm",
            inputs=[flat_out, "fc_w", "fc_b"],
            outputs=["y"],
        )
    )

    graph = helper.make_graph(
        nodes=nodes,
        name=f"cnn1d_w{width}",
        inputs=[helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 1, 1024])],
        outputs=[helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 4])],
        initializer=initializers,
    )
    model = helper.make_model(
        graph,
        producer_name="ccu_os_realload",
        opset_imports=[helper.make_opsetid("", 17)],
        ir_version=8,
    )
    onnx.checker.check_model(model)
    return model, param_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Output directory for ONNX models")
    parser.add_argument(
        "--widths",
        type=str,
        default="64,128,192,256,384",
        help="Comma-separated list of channel widths",
    )
    args = parser.parse_args(argv)

    widths = [int(tok.strip()) for tok in args.widths.split(",") if tok.strip()]
    args.out.mkdir(parents=True, exist_ok=True)

    for w in widths:
        model, n_params = build_cnn1d(w)
        out_path = args.out / f"cnn1d_w{w}.onnx"
        onnx.save(model, str(out_path))
        print(f"{out_path.name} params={n_params}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

