# 既知の限界と、まだ達成していないこと

**このパッケージは完成した基板製品、FPGA bitstream、製造済みTPUではない。競合を超えるLLM tokens/sを実証したものでもない。**

実装は本格的なパイプライン・GEMV/GEMM tile・group scale・scratchpad・ping-pong・command controlを含むが、完全なTransformerの全operatorを含まない。Attention、Softmax、RMSNorm、RoPE、KV cache、embedding/LM head、tokenizer、サンプリング、モデルloaderの実機統合は未了。

CXXRTLは二値のRTLシミュレーションであり、4-state unknown propagation、CDC、metastability、gate delay、PVT corner、基板のsignal integrityを検証しない。SATは三値product・T5・丸め幅変更という局所組合せ性質のみ。全ての長さのtransaction列に対する全体formal proofではない。

Yosysのtechnology mappingは資源見積もりの証拠になるが、実際のVivado資源利用率、合法配置、route congestion、Fmax、消費電力の証明にはならない。250 MHz、0.512 TOPS-equivalent、12 tokens/s等の数字は、それぞれ前提付き計算値または目標値であり、実物で測った数字ではない。

T5はcodecとdecoder primitiveまで。現在のtopへ圧縮streamを直接渡す経路はない。zero weightは結果に0を足すが、cycleを圧縮するzero-skip schedulerではない。したがって、zero率からスピード倍率を自動算出しない。

FP32 scaleから固定小数点への変換は数値差を生む。今回証明した整数一致は変換後の契約との一致であり、元モデルの品質保持を証明していない。rotationが必要なモデルでは、入力変換を別に実施しなければならない。

load validityは「初期化済みか」を確認するだけで、過去jobの内容が最新かを自動認識しない。generation管理はhost contractに含まれる。単一clock・同期resetを前提とし、外部busとのCDC wrapperは未実装。

SDKのcompiled shared libraryはこのLinux x86_64環境用の便宜的成果物で、Windows native向けの配布binaryではない。ソースからの再構築方法をREADMEに記載する。古いbinaryが新しいRTLをテストしてしまわないよう、buildとsource hashを確認する。

参考研究は著者の一次資料を確認したが、本環境で競合実装を動かしたわけではない。exact checkpointや電力測定境界の不明点を残したまま、同条件比較が成立したとはしない。
