# OpenTernary TPC-X1

**三値専用テンソルアクセラレータの設計・RTL・検証パッケージ**  
作成：2026-09-20 / 仮称：TPC-X1 / 標準構成：R16 × L16 × B4、G128

8-laneの最小dot PoCではなく、GEMV/GEMM tile、group scale、52 KiBの論理scratchpad、weight/scale二重バッファ、コマンド制御、tail、backpressure、エラー伝播まで実装した。SystemVerilogを**実際にYosys/CXXRTLへ通し、実行・照合し、FPGA向けtechnology mappingまで実施**した。

**ただし、競合同等以上のLLM tokens/sはまだ実証していない。** 完全なLLM runtime、DMA/基板統合、Vivadoでのtiming closure、電力測定は未完了である。0.512 TOPS-equivalentは250 MHzを仮定したピーク計算値であり、基板の測定値ではない。

## 最初に読むもの

`REPORT.html` は追加調査・設計・結果をまとめたブラウザ閲覧用レポート。`REPORT.md` は同じ内容のMarkdown版。実行結果の正本は `reports/results.json`、既知の限界は `docs/LIMITATIONS.md`。

## 検証結果

| 項目 | 結果 |
|---|---|
| pytest | 24 passed、0 failures、0 skipped |
| 実SystemVerilogのCXXRTL試験 | random 1,000 commands、64,000出力値照合 |
| random試験の有効weight terms | 3,194,727項 |
| 他の実RTL試験 | 境界値、reset、stall、bank所有権、不正入力、B5/R19/K4225の分割実行 |
| 独立C++ golden | random 1,500 GEMM、全INT8×三値境界など |
| cycle仕様モデル | random 10,000 transactions。実RTL試験とは別枠 |
| SAT | 三値product、T5 decoder、丸め幅変更の3性質を証明 |
| 三値MACの乗算器 | Yosys構造検査で通常の乗算cellなし |
| 配置配線・実機tokens/s・実電力 | 未実行 |

## technology mapping結果

同じYosys flowで、丸め演算を64-bit幅から必要なproduct幅へ変更した。数値等価性をSATで確認したうえで、LUT1～LUT6ノード合計は57,154→56,561（約1.04%減）、FDREは39,258→37,274（約5.05%減）。DSP48E2は64、RAMB18E2は45。

これらは**Yosysでのmapping結果**であり、Vivadoで配置された資源数ではない。CARRY4/INVなども別に存在し、LUTノード合計をチップ面積全体と同一視しない。全64 DSPはgroup scale側で、三値の主演算経路とは分けている。

## パッケージ構成

```text
rtl/         実SystemVerilog、計算器・scale・FIFO・RAM・sequencer
model/       独立golden、packing、数値契約、cycle仕様モデル、tile compiler
sim/         実CXXRTLのC ABI bridgeとPython bus driver
tests/       数学、cycle仕様、実RTL、compilerのテスト
formal/      組合せSATのmiter
scripts/     build、検証、合成、分析、export
constraints/ Vivado OOCの仮定付きtiming予算
config/      標準構成と未達の性能目標
examples/    synthetic入力とbus image。実モデル重みではない
reports/     実行log、JSON/XML、合成前後比較、正直なgate状態
reference/   一次資料、OpenTernary契約、toolchain出所とhash
build/       検証済みLinux model、生成C++、mapped netlist、source hash
```

## 再実行

Python 3.11以上、NumPy、pytest、C++17 compiler、CXXRTL headersを含むpyosysが必要。実際に使った版と公式workflow/commitは `reference/toolchain.json` に記録した。インストール用の29 MB wheelや175 MBのtoolchain archiveは同梱していない。GitHub artifactは期限切れになることがあるため、source commitも保存している。

同梱shared libraryはLinux x86_64用である。他環境では元RTLから再ビルドする。Windows nativeのFPGA driverやbitstreamは含まない。

プロジェクトrootから実行する。

```bash
# RTLを再生成・再コンパイルし、数値/実RTL/SAT/合成まで実行
python scripts/run_all.py --build-rtl --synth

# 同梱の検証済みLinux RTL libraryを利用して再試験
python scripts/run_all.py

# HDL toolなしで数値・仕様モデルだけ試す場合。RTL PASSとは扱わない
python scripts/run_all.py --models-only
```

`reports/results.json` は今回の保存snapshotである。再実行の状態・所要時間・各stageの成否は `reports/reproduction_run.json`、再試験の件数は `reports/reproduction_pytest.xml` に別保存する。数値モデルだけの実行を実RTLの合格へ混ぜない。

driverはRTL/bridge sourceのhashとcompiled libraryのhashを照合し、ソースを変更したのに古いbinaryをテストする事故を拒否する。`run_all.py` は必要なRTL binary/toolがなければ失敗し、黙って成功扱いにしない。

## 数値互換性

OpenTernary 2bit-v1の符号・bit順・paddingを固定commitで照合した。モデルの全tensorをそのまま処理できるという意味ではなく、tile配置への変換が必要。FP32 scaleは別のm/shift形式へ変換し、誤差を評価する。activation変換が必要なrotation recipeは黙って無視しない。

詳細は `docs/NUMERICS.md`、完成系SoCの未統合部分は `docs/INTEGRATION.md`、競合比較の条件は `docs/BENCHMARK_PROTOCOL.md` を参照。

## 開発の次の合格条件

次はexact partでのVivado実装、DMAと実際のモデル一層の検証、その後にAttention/SFUを含む全LLMの測定となる。基板なしのTOPS計算をtokens/sの実測へ読み替えない。研究の継続に必要な未完了項目を `reports/results.json` のG3～G5として残している。
