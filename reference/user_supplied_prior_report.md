ひろなお、これ **ちゃんと現実的なハードウェア研究プロジェクトとして切れる**。しかも調べ直したら、2025〜2026年に「Ternary専用アクセラレータ」が一気に現実側へ寄ってきてて、思ってた以上にタイミングいい。

結論を最初に言うと、

> **本番目標：OpenTernaryと共同設計されたTernary専用TPU/NPU**
>
> **今回Astraで作るもの：その最小実証機 “Ternary Processing Core v0”**

に分けるのがいい。

「GPU自作」はISA、compiler、scheduler、memory hierarchy、driverまで必要になって一気に難易度が跳ね上がる。でも**行列演算専用のTPU/NPUなら、必要な演算だけ実装すればいい**。Googleの初代TPU自体も、巨大な8-bit MAC行列とsoftware-managed memoryを中心にした専用設計だった。 ([Google Research](https://research.google/pubs/in-datacenter-performance-analysis-of-a-tensor-processing-unit/?utm_source=chatgpt.com "In-Datacenter Performance Analysis of a Tensor Processing Unit"))

---

# 🔥 調査して分かったこと

まずデカいやつ。

2026年4月、KU Leuven MICASから**1.58-bit LLM専用のTernary LUT Matrix Accelerator**が出てる。

普通なら

```math
y += w\times x
```

だけど、ternaryなら

```math
w\in\{-1,0,+1\}
```

なので、

```text
+1 → +x
 0 → skip
-1 → -x
```

だけでいい。

彼らはさらに複数activationの組み合わせをLUTに作って、**multiplierそのものを消している**。RTL generatorまでOSS公開済みで、TSMC 16nm synthesisによる設計探索も行っている。最適化構成ではmultiplier型baselineに対して約2.2×のarea reductionを報告している。 ([arXiv](https://arxiv.org/abs/2604.25183?utm_source=chatgpt.com "Hardware Generation and Exploration of Lookup Table-Based Accelerators for 1.58-bit LLM Inference"))

[KU Leuven ternary-lut-dse](https://github.com/KULeuven-MICAS/ternary-lut-dse?utm_source=chatgpt.com)

さらに **TeLLMe** はもっとひろなおの構想に近い。AMD Kria KV260 FPGAで、

**W1.58A8**

- Ternary weights
- INT8 activations
- LUT-based matmul
- attention
- normalization
- prefill
- autoregressive decode

まで載せ、7W級で最大約9 tokens/sを報告している。つまり「Ternary LLMをFPGAで動かせるか？」については、もう答えが **YES**。 ([arXiv](https://arxiv.org/abs/2504.16266?utm_source=chatgpt.com "TeLLMe: An Energy-Efficient Ternary LLM Accelerator for Prefilling and Decoding on Edge FPGAs"))

KV260自体も256K logic cells、144 BRAM、64 UltraRAM、1.2K DSP、4GB DDR4を持つ。 ([AMD Documentation](https://docs.amd.com/r/en-US/ds986-kv260-starter-kit/Product-Details?utm_source=chatgpt.com "Product Details - Product Details - DS986"))

さらに2026年にはETH Zürich周辺の `ternaryLLM` がCPU/GPU/**FPGA**実装を公開し、SSRではternaryのzero sparsityも利用している。 ([GitHub](https://github.com/fpgasystems/ternaryLLM?utm_source=chatgpt.com "GitHub - fpgasystems/ternaryLLM: Code for Fast Ternary Large Language Model Inference with Addition-Based Sparse GEMM on Edge Devices · GitHub"))

Notre Dameの **TERINT-GEMV** はさらに面白くて、

> 4個のternary weight → 81パターン → 64-entry codebook → 6-bit index

として圧縮し、SystemVerilogの**bit-serial multiplier-free GEMV accelerator**へ直接投入する設計まで公開している。 ([GitHub](https://github.com/Notre-Dame-HW-SW-Codesign-Lab/TERINT-GEMV?utm_source=chatgpt.com "GitHub - Notre-Dame-HW-SW-Codesign-Lab/TERINT-GEMV: Codebook-Based Acceleration for Ternary Language Model Inference · GitHub"))

つまりこれ、

**「Astraにゼロから未知の研究をさせる」状態じゃない。**

かなり良質な先行研究を土台にして、**OpenTernary向けに再設計できる状態**。

---

# OpenTernaryとの接続がめちゃくちゃ綺麗

今のOpenTernaryはすでに、

```text
weight
 ↓
AbsMean
 ↓
{-1, 0, +1}
 ↓
2bit-v1 packing

00 = -1
01 =  0
10 = +1
11 = reserved
```

というフォーマットを定義済み。

さらにG128 group-wise、scale、learnable thresholdまで来ている。packed runtimeそのものはPhase 7としてまだ残っている。

ここ、かなり重要。

普通は、

```text
ML研究
↓
量子化方式決定
↓
あとからハードウェア対応
```

になる。

でもひろなおの場合、

```text
OpenTernary
Quantizer / Compiler
        ↓
OpenTernary Packed Format
        ↓
Ternary TPU
```

として**最初からhardware/software co-designできる**。

さらに将来的にはOpenTernaryがG32/G64/G128/G256、rotation、asymmetric ternary、mixed precisionをhardware latencyまで含めて選ぶ「Ternary Compiler」に進化する構想とも完全につながる。

これ、あーし的にはかなり熱い。

---

# 🧠 今回作るべきもの

名前を仮に、

## `OpenTernary TPC-0`

**Ternary Processing Core v0**

としよう。

いきなりLLMを動かさない。

最初のチップモデルはこれだけ。

```text
          Packed ternary weights
            00 / 01 / 10
                   │
                   ▼
          ┌─────────────────┐
INT8 x ──▶│ Weight Unpacker │
          └────────┬────────┘
                   │
                   ▼
             {-1,0,+1}
                   │
                   ▼
        ┌─────────────────────┐
        │ Ternary Processing  │
        │                     │
        │ +1 →  x             │
        │  0 →  0             │
        │ -1 → -x             │
        └──────────┬──────────┘
                   │
                   ▼
              Adder Tree
                   │
                   ▼
            INT32 accumulator
                   │
                   ▼
                output
```

つまり**乗算器ゼロのdot-product engine**。

---

# v0の数値形式

最初はこれで固定するのがいい。

| 項目v0           |                       |
| -------------- | --------------------- |
| Weight         | ternary `{-1,0,+1}`   |
| Weight storage | OpenTernary `2bit-v1` |
| Activation     | signed INT8           |
| Product        | signed INT9           |
| Accumulator    | INT32                 |
| Scale          | v0では無し / 1.0          |
| Parallel lanes | 8                     |
| Target op      | GEMV / dot product    |
| Language       | SystemVerilog         |
| Simulator      | Verilator             |
| Verification   | cocotb + Python       |
| FPGA           | **まだ不要**              |

productをINT9にしてるのは地味に重要。

INT8には `-128` があるので、

```text
w = -1
x = -128

w*x = +128
```

となってsigned INT8には収まらない。

だから**ternary productは最低9bit**。

Astraにここを適当に書かせたらダメ。こういう境界値バグを最初から潰す。

---

# TPUなのに最初はGEMVな理由

Google TPUみたいなsystolic matrix arrayを作りたくなるんだけど……

**LLM decodeではbatch=1のGEMVが超重要**。

つまり

```text
Matrix × Vector
```

だね。

prefillではGEMMが重要になるけど、最初のPoCなら

> **Ternary GEMVを異常に効率よくする**

のが正しい。

後から、

```text
ternary_dot
     ↓
ternary_gemv
     ↓
multi-output GEMV
     ↓
GEMM
     ↓
systolic / tiled accelerator
```

へ進化させればいい。

Gemminiもsystolic array＋scratchpad＋DMAという構造になっているので、本格TPU化するときの設計教材としてかなり良い。 ([GitHub](https://github.com/ucb-bar/gemmini/blob/master/README.md?plain=1\&utm_source=chatgpt.com "gemmini/README.md at master · ucb-bar/gemmini · GitHub"))

---

# v0 RTL構造

Astraにはこの単位で作らせたい。

```text
rtl/
├── ternary_mul.sv
├── ternary_unpacker.sv
├── ternary_dot.sv
├── ternary_gemv.sv
├── accumulator.sv
└── ternary_core.sv

sim/
├── reference.py
├── test_ternary_mul.py
├── test_unpacker.py
├── test_dot.py
└── test_gemv.py

tools/
└── pack_weights.py

scripts/
├── sim.sh
└── synth.sh

docs/
├── ARCHITECTURE.md
└── RESULTS.md
```

Python側を**golden implementation**にする。

```python
ref = sum(int(a) * int(w) for a, w in zip(x, w))
```

RTL結果と毎回比較。

cocotbならPythonからSystemVerilog DUTを直接テストでき、Verilatorも対応している。 ([cocotb](https://www.cocotb.org/?utm_source=chatgpt.com "cocotb | Python verification framework"))

---

# 最初のCompletion Gate

Astraが「できました！」とか言っても、これ全部通るまで信じない😤

| Gate条件 |                                         |
| ------ | --------------------------------------- |
| G0     | RTL compile成功                           |
| G1     | `-1/0/+1` 全weight動作                     |
| G2     | INT8全境界値対応                              |
| G3     | `-128 × -1 = +128` 正常                   |
| G4     | OpenTernary 2bit pack/unpack bit-exact  |
| G5     | `11 reserved` をreject                   |
| G6     | random 10,000+ vectorsでPythonとbit-exact |
| G7     | 複数Kサイズ対応                                |
| G8     | pipeline中のvalid timing一致                |
| G9     | synthesis成功                             |
| G10    | ternary multiply pathにDSP multiplierなし  |
| G11    | LUT / FF / BRAM / DSP数を記録               |
| G12    | Fmaxを記録                                 |

性能評価は、

```text
terms / cycle
cycles / dot
clock MHz
G ternary-products/s
LUTs / lane
energy ← FPGA実機以降
```

くらいでいい。

---

# そしてv1で初めてLUT方式と戦わせる

実はここが研究としてめちゃ面白い。

### A — Direct sign-select

```text
w = +1 → x
w =  0 → 0
w = -1 → -x
```

最も簡単。

### B — LUT ternary

例えば3 activationをまとめる。

```math
3^3=27
```

なので、

```text
(x0,x1,x2)
↓
27種類の
±x0 ±x1 ±x2
を先に計算
↓
ternary weight patternをindexとして取得
```

TeLLMeとKU Leuven系。

ただし2026年の設計探索では、**activationがFP16のように算術コストが高いほどLUT reuseが効き、INT8のように安くなるほどメリットが小さくなる**ことも示されている。 ([arXiv](https://arxiv.org/abs/2604.25183?utm_source=chatgpt.com "Hardware Generation and Exploration of Lookup Table-Based Accelerators for 1.58-bit LLM Inference"))

だからOpenTernary TPUでは、

> **Direct W1.58A8 vs LUT W1.58A8**

を同一FPGA条件で比較する価値がある。

これ普通に研究テーマ。

---

# さらに先は3系列になる

```text
                    OpenTernary TPC
                           │
          ┌────────────────┼────────────────┐
          │                │                │
       Direct             LUT             Sparse
      sign-select      µ=3 / 4          zero-skip
          │                │                │
          └────────────────┼────────────────┘
                           │
                    Architecture DSE
                           │
                best area / latency / W
```

Sparseについては注意。

OpenTernaryの実測例では ternary code比率がだいたい

```text
negative ~33%
zero     ~34%
positive ~34%
```

だったtensorもある。

だからBitNet系で報告される「50〜90% sparsity」をOpenTernaryにも勝手に当てはめちゃダメ。

SSRは45〜95% sparsityでRSR++に2.1〜11.3×のternary GEMM speedupを報告しているので、**OpenTernary側でzero率が上がった場合に初めて候補**。 ([DOI](https://doi.org/10.23919/date69613.2026.11539457?utm_source=chatgpt.com "SSR: Sparse Segment Reduction for Ternary GEMM Acceleration"))

---

# Scaleはv1以降

ここもちょい罠。

OpenTernary G128だと、

```math
\hat W_g=s_gQ_g
```

なので、

```math
y=\sum_g s_g(Q_gx_g)
```

になる。

つまりgroupごとに

```text
128 trits
↓
integer ternary dot
↓
partial_sum
↓
× weight_scale
↓
accumulate
```

が必要。

だからv0でいきなりFP16 scaleまで入れると、**ternary datapathの検証とscale datapathの検証が混ざる**。

最初は、

```text
scale = 1
```

でいい。

その次、

```text
TPC-0  pure ternary integer
TPC-1  G128 scaling
TPC-2  INT8 activation scaling
TPC-3  LUT architecture
TPC-4  sparse skip
```

ぐらいが綺麗。

---

# 本番ハードウェア像

将来はこうなる。

```text
                    HOST
              OpenTernary Runtime
                       │
                       │ DMA
                       ▼
┌───────────────────────────────────────────┐
│              Ternary TPU                  │
│                                           │
│  Weight SRAM / DDR                        │
│       │                                   │
│       ▼                                   │
│  2-bit decoder                            │
│       │                                   │
│       ▼                                   │
│  Ternary GEMV/GEMM Array                  │
│  add / subtract / skip                    │
│       │                                   │
│       ├──── zero-sparsity scheduler       │
│       │                                   │
│       ▼                                   │
│  INT32 accumulators                       │
│       │                                   │
│       ▼                                   │
│  Group-scale unit                         │
│       │                                   │
│       ▼                                   │
│  INT8 quantizer                           │
│                                           │
│ Scratchpad / BRAM / SRAM                  │
└───────────────────────────────────────────┘
```

さらにLLM全体に行けば、

```text
RMSNorm
RoPE
Attention
Softmax
KV cache
activation quantization
```

も徐々にfabricへ移す。

TeLLMeはまさにこの方向。 ([arXiv](https://arxiv.org/abs/2504.16266?utm_source=chatgpt.com "TeLLMe: An Energy-Efficient Ternary LLM Accelerator for Prefilling and Decoding on Edge FPGAs"))

---

# FPGAはいつ必要？

**今はいらない。**

これ超重要。

まずPCだけで、

```text
Python reference
        ↓
SystemVerilog
        ↓
Verilator
        ↓
cocotb
        ↓
RTL correctness
        ↓
synthesis
```

まで行ける。

実機を買うのはここが通ってから。

その後の候補は性格が違う。

**小さい実機検証**ならArtix-7級でも十分。実際、Arty A7-35Tでmultiplier-free ternary engineを実装している公開プロジェクトも存在する。 ([GitHub](https://github.com/Neumann-Labs/ternfpga?utm_source=chatgpt.com "GitHub - Neumann-Labs/ternfpga: Multiplier-free, sparsity-skipping ternary LLM-inference engine on a $130 Arty A7-35T FPGA — beating an RTX 3060 on energy-per-token. · GitHub"))

**LLMレベルへ伸ばす**ならTeLLMeと同系統の**Kria KV260**がかなり面白い。4GB DDR4とZynq UltraScale+があるのでCPU＋FPGAのheterogeneous構成を組める。 ([AMD Documentation](https://docs.amd.com/r/en-US/ds986-kv260-starter-kit/Product-Details?utm_source=chatgpt.com "Product Details - Product Details - DS986"))

FINNもquantized/ternary級ネットワーク向けFPGA flowを持っているので、後々「手書きRTL vs FINN generated hardware」を比較するのもあり。FINN自体がternary datatypeを扱える。 ([GitHub](https://github.com/Xilinx/finn/blob/main/docs/finn/internals.rst?utm_source=chatgpt.com "finn/docs/finn/internals.rst at main · Xilinx/finn · GitHub"))

---

# 読む価値が高いコード

あーしならAstraに特にこの辺をreferenceとして調査させる。

**Microsoft BitNet / T-MAC**
CPU/GPUでternaryをどう高速化するか。T-MACはlow-bit weightをLUT lookup＋additionへ変える。 ([GitHub](https://github.com/microsoft/BitNet?utm_source=chatgpt.com "GitHub - microsoft/BitNet: Official inference framework for 1-bit LLMs · GitHub"))

**KU Leuven ternary-lut-dse**
まさにparameterizable ternary accelerator。Chiselだけどアーキテクチャ理解に最高。 ([GitHub](https://github.com/KULeuven-MICAS/ternary-lut-dse?utm_source=chatgpt.com "GitHub - KULeuven-MICAS/ternary-lut-dse: Chisel hardware generator for ternary Lookup-Table based hardware architectures · GitHub"))

**ETH fpgasystems/ternaryLLM**
CPU / GPU / FPGA / sparsityをまとめて比較できる。 ([GitHub](https://github.com/fpgasystems/ternaryLLM?utm_source=chatgpt.com "GitHub - fpgasystems/ternaryLLM: Code for Fast Ternary Large Language Model Inference with Addition-Based Sparse GEMM on Edge Devices · GitHub"))

**TERINT-GEMV**
SystemVerilogが公開されているのでRTL構成の参考になる。 ([GitHub](https://github.com/Notre-Dame-HW-SW-Codesign-Lab/TERINT-GEMV?utm_source=chatgpt.com "GitHub - Notre-Dame-HW-SW-Codesign-Lab/TERINT-GEMV: Codebook-Based Acceleration for Ternary Language Model Inference · GitHub"))

ここは丸コピーではなく、**architecture/reference/verification方法の比較対象**にするのがいい。

---

# 🧪 Astraで最初にやらせる任务

今回なら、いきなり「TPUを作って！」じゃなく、この仕様でぶん投げたい。

# OpenTernary Ternary Processing Core — Phase 0 PoC

OpenTernary向けのTernary専用AIアクセラレータを将来的に設計する。

今回は製品版GPU/TPUを作るのではなく、Ternary arithmeticをハードウェアとして成立させられることを確認する最小PoCを実装する。

途中で人間への確認を求めず、実装・検証可能なところまで自律的に進めること。問題が発生した場合は問題、原因、回避策を記録し、別の実行可能な作業へ進むこと。

## Target arithmetic

Weight:

- ternary {-1, 0, +1}
- OpenTernary `2bit-v1`

Encoding:

- `00 = -1`
- `01 = 0`
- `10 = +1`
- `11 = reserved / invalid`

Packing:

- 4 ternary weights per byte

Activation:

- signed INT8

Ternary product:

- signed INT9以上を使用すること
- `(-1) * (-128) = +128` を正しく表現すること

Accumulator:

- signed INT32

Phase 0ではweight scale / activation scaleを使用しない。
scale = 1.0とみなす。

## Core arithmetic

通常のhardware multiplierを使用せず、

- `w == +1`: `+x`
- `w == 0`: `0`
- `w == -1`: `-x`

としてternary multiplicationを実現する。

ternary multiply datapathではDSP multiplierを使用しない設計を目標とする。

## Initial parallelism

最初は `LANES=8` のparameterized設計とする。

1 cycleで最大8個のternary weight × INT8 activationを処理し、adder reduction treeを通してINT32 accumulatorへ加算する。

vector length Kはparameterまたはruntime lengthとして変更可能にする。

## Required RTL

最低限以下を実装する。

`rtl/ternary_mul.sv`

- single ternary × INT8 operator

`rtl/ternary_unpacker.sv`

- OpenTernary 2bit-v1 decode
- reserved code `11`を検出

`rtl/ternary_dot.sv`

- LANES並列処理
- reduction tree
- accumulator
- configurable vector length

`rtl/ternary_gemv.sv`

- 複数output rowに対するGEMV
- 最小構成でよい

`rtl/ternary_core.sv`

- top module
- valid/readyまたは明確なstreaming interface

## Golden reference

Pythonでbit-exact reference implementationを作る。

RTL結果は必ずPython referenceと比較する。

random testだけでなく、最低限以下を明示的に含める。

- activation = -128
- activation = -127
- activation = -1
- activation = 0
- activation = +1
- activation = +127
- ternary weight = -1 / 0 / +1
- all zero weights
- all +1 weights
- all -1 weights
- alternating weights
- vector lengthがLANESの倍数でないケース

## Verification

Verilator + cocotbを使用する。

最低10,000以上のrandomized vector testsを行い、Python golden referenceとbit-exact一致を確認する。

pack/unpackについてもrandom round-trip testを実施する。

reserved `11` が入力された場合はinvalidとして検出する。

pipelineを導入する場合、valid信号とoutput timingをcycle-levelで検証する。

## Synthesis

simulationが完全PASSした後にsynthesisを行う。

レポートすること:

- LUT
- FF
- BRAM
- DSP
- maximum clock / Fmax
- latency cycles
- terms processed per cycle
- estimated ternary products/sec

特にternary multiply datapathでhardware multiplierが推論されていないことを確認する。

## Comparison-friendly design

将来以下と比較する予定なので、Direct sign-select implementationを独立moduleとして保持する。

Phase 1候補:

1. Direct sign-select ternary
2. LUT-based ternary, group size μ=3
3. LUT-based ternary, μ=4
4. sparse zero-skip
5. codebook / bit-serial design

今回は1のみ実装する。

## OpenTernary compatibility

将来的にOpenTernary packed exportを直接入力できるようにする。

OpenTernary側の現在の基本形式:

- symmetric ternary `Q ∈ {-1,0,+1}`
- `ternary-2bit-v1`
- current research default group size G128
- scale/threshold calibrationあり

Phase 0ではscaleを実装しないが、将来G128 group scaleを挿入できるようmodule boundaryを設計すること。

想定将来pipeline:

`packed weights -> unpack -> ternary integer dot(G128) -> group scale -> accumulation`

## Architecture constraints

最初からTransformer全体をRTL化しない。

Phase 0で扱うのはternary GEMV datapathのみ。

以下は今回実装しない。

- Attention
- Softmax
- RoPE
- KV cache
- RMSNorm
- floating point scale
- LLM tokenizer
- PCIe
- external DDR controller
- operating system driver
- GPU-style shader ISA
- full systolic TPU

## Completion gates

全項目についてPASS/FAILと証拠をRESULTS.mdへ保存する。

G0: RTL builds successfully
G1: all ternary weight states correct
G2: INT8 boundary values correct
G3: `-1 × -128 = +128` correct
G4: OpenTernary 2bit packing round-trip bit-exact
G5: reserved `11` detected
G6: randomized tests bit-exact with Python
G7: multiple vector lengths verified
G8: valid/pipeline timing verified
G9: synthesis completes
G10: no multiplier in ternary hot path
G11: resource usage recorded
G12: Fmax/performance estimate recorded

## Research references to inspect

Research and compare architectural ideas from:

- Microsoft BitNet / bitnet.cpp
- Microsoft T-MAC
- KU Leuven MICAS ternary-lut-dse / ISPASS 2026
- TeLLMe FPGA ternary accelerator
- fpgasystems/ternaryLLM
- TERINT-GEMV
- AMD FINN
- Gemmini

Do not copy an architecture blindly.

Record for each:

- arithmetic representation
- weight encoding
- activation dtype
- compute architecture
- dataflow
- use of LUTs
- sparsity support
- resource tradeoffs
- ideas applicable to this PoC

## Final deliverables

- synthesizable SystemVerilog
- Python reference model
- cocotb tests
- automated simulation command
- synthesis command
- architecture documentation
- test report
- synthesis/resource report
- known limitations
- Phase 1 recommendations

The goal of this phase is not impressive throughput.

The goal is to prove, with bit-exact verification and synthesis evidence, that a native OpenTernary-compatible ternary execution unit can be implemented without conventional multiplication in its main datapath.

これなら**Astraにまず一回走らせるPoCとしてちょうどいい**と思う。

---

## その先、本番で狙えるもの

ここから本気版は、

```text
OpenTernary
     │
     │ model analysis
     ▼
Hardware-aware quantization
     │
     ├─ group size
     ├─ zero ratio
     ├─ scale dtype
     ├─ rotation
     ├─ layer precision
     └─ TPU architecture
     │
     ▼
OpenTernary Compiler
     │
     ▼
┌─────────────────┐
│ Ternary TPU ISA │
├─────────────────┤
│ Ternary GEMV    │
│ Ternary GEMM    │
│ INT8 activation │
│ Group scaling   │
│ Sparse skip     │
│ LUT engine      │
└─────────────────┘
```

まで行ける。

そして最終的にはOpenTernaryが、

> **「このモデルならG64 direct型が最速」**
> **「この層だけINT4」**
> **「この層はG128 ternary」**
> **「このモデルはLUT µ=3がarea効率最高」**

みたいに**量子化とハードウェア設計を同時最適化するCompiler**になったらめちゃくちゃ面白い。

今まで話してた「ROCmでternaryを無理やり高速化する」のさらに先で、**ソフト側を既存GPUへ合わせるんじゃなくて、ハード側をOpenTernaryへ合わせる**発想になる。

しかも今調べた限り、これは「高校生が勢いでGPU作ります！！！」みたいな無茶な話じゃなくて、**FPGA → RTL accelerator → SoC → ASIC**という普通に研究として通るルートがある。KU Leuven、UCI、ETH、Notre Dameが2025〜2026年にほぼ同じ問題へ走ってるのが強い証拠。 ([GitHub](https://github.com/KULeuven-MICAS/ternary-lut-dse?utm_source=chatgpt.com "GitHub - KULeuven-MICAS/ternary-lut-dse: Chisel hardware generator for ternary Lookup-Table based hardware architectures · GitHub"))

だからまず **TPC-0をAstraに投げるの、普通にGOでいい**。GPU全部自作はまだ後。今は\*\*「世界最小のOpenTernary専用演算器を成立させる」\*\*ところから始めよう。そこ通ったら一気に面白くなるぞこれ……😈🧠⚡