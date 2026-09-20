# OpenTernary TPC-X1 — 設計・実装・検証レポート

**2026-09-20 / 競合性能を狙う三値専用テンソルアクセラレータ**

## 実行結果の要点

追加調査、アーキテクチャ設計、実SystemVerilogの実装、Yosys/CXXRTLでの実行、局所SAT証明、FPGA向けtechnology mappingまで実施した。今回作成したのはR16×L16×B4のタイル型アクセラレータと完成系SoCの設計書であり、以前の8-lane単発dot PoCではない。

**競合同等以上のLLM tokens/s、250 MHzの実機動作、基板電力は未実証。** 完全なTransformer、DMA、Vivado配置配線、基板評価は未統合または未実行である。この区別を維持したうえで、取得した証拠を以下に示す。

| 実施内容 | 結果 |
|---|---|
| テスト全体 | 24 passed / 0 failures / 0 skipped |
| 実RTL random試験 | 1,000 commands、64,000出力値、3,194,727有効termsを照合 |
| 実RTLの追加試験 | 境界値、tail、stall、reset、2 bank、不正入力、4096を超えるKのcompiler分割 |
| 数式・仕様モデル | 独立C++で1,500 random GEMM、cycle仕様で10,000 transactions |
| 組合せSAT | 三値product、T5、丸め幅変更の3性質PASS |
| hot path構造 | 三値MAC内の通常乗算cellなし |
| FPGA technology mapping | PASS。ただし配置配線・基板測定ではない |

## 合成で確認した最適化

同じ回路の丸め部分を必要bit幅へ狭めたところ、LUT1～LUT6ノード数は57,154から56,561へ約1.04%減、FFは39,258から37,274へ約5.05%減となった。64 DSP48E2、45 RAMB18E2を使用するmapping結果である。DSPはgroup scaleにあり、三値productの通常乗算器ではない。これを面積全体や消費電力の同率改善とは読み替えない。

## cycle測定と、周波数の仮定

実CXXRTLでは、load済みのR16/B4/K4096 tileがcommand受理から出力受け取りまで266 cyclesで完了した。確認したKでは `ceil(K/16)+10` cyclesだった。262,144 termsを266 cyclesで処理している。

250 MHzを仮定すると、ピークは0.512 TOPS-equivalent、上記tileは約0.493 TOPS-equivalentになる。これは1三値termを慣例的に2 operationsと数えた値であり、TFLOPSでも実機clockの測定でもない。DDR転送、Attention、KV、CPU処理を含めたtokens/sへ変換していない。

## 成果物の位置づけ

コード・検証log・合成netlistは実在する成果物。次に閉じるべきゲートは、exact partでのtiming closure、DMAと実checkpointの一層、完全モデルの品質と速度、電力境界を揃えた比較である。未実行ゲートはJSONでもNOT_RUNとして保持した。


---

## OpenTernary TPC-X1 — 追加調査レポート

**調査日：2026-09-20。対象：三値専用テンソルアクセラレータ。**

本書は、先行回答の文章を設計の根拠にせず、論文本体・図表・著者の公開リポジトリ・メーカー資料を読み直した結果である。数値は「論文の報告」「自分たちのRTL実行」「合成」「配置配線」「基板測定」を分離する。文献番号のURL・版・確認範囲は `reference/sources.json` に収録した。

### 1. 最初に修正すべき理解

| 論点 | 再確認した内容 | 今回の設計への影響 |
|---|---|---|
| TeLLMeの9.51 tokens/s | 0.7Bモデルの報告ピーク値。本文では512-token contextで9超、1024では約8と説明する。全contextで9.51という意味ではない。[S01] | 短いcontextと1024を別々の合格条件にする。 |
| TeLLMeの電力 | Table IIIに6.72 W。電源入力、FPGA部分、実測か推定かの測定境界を、今回確認した実験節だけから一意に確定できない。[S01] | その値を「基板全体の実測」と言い換えない。同じ境界が確定するまで効率比較を保留。 |
| TerEfficの非常に大きいtokens/s | MatMul-free LM系のモデル、U280、大きなオンチップメモリなどが前提。370Mを載せる構成は2枚のU280。電力内訳にはVivado power reportを利用している。[S02] | KV260上のTransformerと同一ランキングに並べない。 |
| KU Leuvenの約2.2倍 | 32×32・FP16の面積比較では、full-width baselineに2.23倍、sign-flip baselineに1.64倍。INT8ではLUT化の面積差が小さいと報告。[S03] | INT8の本機に「LUTなら2.2倍速い」を適用しない。 |
| 4 tritsを6 bitsへ | 81通りを64通りへ制限するTERINT-GEMVは、コードブック変更・fine-tuningを伴う。任意の三値列を可逆圧縮する話ではない。[S05] | 本機の可逆T5圧縮と明確に区別。 |
| 1.58-bitと実ファイルサイズ | 3状態の情報量log2(3)と、固定長パッキング・scale・padding込みの保存サイズは別。 | 2bit-v1、T5、scale込みのbytesを個別に数える。 |
| 「multiplier-free」 | 三値×INT8部分には通常の乗算器が不要でも、group scaleやAttentionでは乗算が必要。 | 「チップ全体にDSPゼロ」ではなく、三値の主演算経路にゼロを要求。 |

### 2. 主な先行研究と、比較が成立する範囲

#### TeLLMe：今回のエッジ性能目標の基準

TeLLMeはUCIの、三値行列演算だけでなくAttention・正規化を含むprefill/decode設計。KV260、250 MHz、0.7B、9.51 tokens/sピーク、64-token prefill 0.55 s、モデルサイズ257 MBを報告する。Table IVの全体資源は108,994 LUT、155,838 FF、356 DSP、206 BRAM、48 URAM。[S01]

**取り入れる設計原則**は、非線形演算を放置しないこと、Attentionのデータ移動削減、load/computeの重なり、実際のモデル全体での測定である。今回は同じcheckpointを取得しての再現は実施していない。BRAM欄はメーカーの144個という36 Kb単位表記とそのまま比較できず、18 Kb単位への正規化が必要になる。

#### TerEffic：オンチップ常駐が変える性能限界

v2では、370M・単一batchの2枚構成で16,300 tokens/sを報告し、より大きい2.7BにはHBMを利用する構成を示す。対象モデル構造、加速対象、カード数、電力推定方法がTeLLMeと異なる。[S02]

本機への示唆は「演算器を増やせば同じ値が出る」ではなく、**重みをどこに保存し、毎token何bytesを運ぶかを先に決める**ことである。KV260の設計をU280級へ拡張する場合も、帯域・メモリIP・動作周波数を別に検証し直す。

#### KU Leuven MICAS：LUTを選ぶための設計探索

Chiselによる生成器、TSMC 16 nmライブラリでの合成、データ型・タイル形状・groupingの探索が提供されている。Table IVの大きな面積改善はFP16条件であり、µ=1のsign-selectが比較対象にも含まれる。[S03,S04]

本機はまずINT8のdirect sign-selectを実装した。LUT方式は不採用と断定せず、同じ数値形式・同じ入出力帯域・同じ配置配線制約で比較する次の候補とする。論文のASIC面積をFPGA LUT数へ換算することはしない。

#### TERINT-GEMV：表現と回路を共同設計する例

公開内容はコードブックによる三値モデル変換、bit-serial GEMV、SystemVerilog、SoC推定モデルを含む。[S05] コードブックの制約を受けるため、OpenTernaryの任意の `{-1,0,+1}` 列をそのまま受け入れる本機とは互換性条件が異なる。モデル品質の再確認なしに置換しない。

#### 補助資料

T-MACはlow-bit演算をlookupへ置き換えるソフトウェア面の参考、BitNetはモデル・ランタイムの数値境界の参考、ternaryLLMは疎性活用の参考になる。[S06–S08] それぞれのCPU/GPUの倍率をFPGAの倍率へ流用しない。Gemminiのscratchpad、DMA、load/execute/storeの分離は完成系SoCの構成を考える材料になる。[S09] FINNは量子化ネットワークのFPGA実装基盤であり、今回のOpenTernary形式や完全なLLMを自動的に実装してくれると仮定しない。[S10]

### 3. 採用した研究目標

最終比較の中心は **TeLLMe級のKV260で、同じ0.7B checkpoint・同じ入出力条件・同等品質** とする。暫定の挑戦目標は、短いcontextで12 tokens/s、64-token prefill 0.45 s以下、1024 contextで10 tokens/sである。電力は、比較対象の測定境界が確定したうえで6.72 W以下を目標とする。

これらは**設計目標**であり、今回の達成値ではない。現在のタイル計算器のTOPSをtokens/sに置き換えて達成扱いにしない。TeLLMeのcheckpoint識別子・モデル品質評価・測定手順の完全な再現も未了である。代わりに別の2Bモデルを使った場合は別ベンチマークとして報告する。

### 4. 今回のアーキテクチャ判断

中心は `16 output rows × 16 K lanes × 4 token lanes` のタイル型演算器。batch=1のdecodeにも対応し、G128ごとのscaleを独立した経路で処理する。単なる単発dotではなく、複数group、最大K=4096のコマンド、tail mask、エラー伝播、メモリ、二重バッファ、backpressureを含めて設計・実装した。

最初から本機専用の三状態トランジスタを製造する案ではない。通常の二値デジタル回路で三値重み専用の演算とデータ表現を実現する。FPGA版の仕様を、のちにASICへ移植できるよう計算部と外部メモリ・ホストI/Oを分離している。

### 5. 勝つための本当の課題

演算器の加算性能だけでは不足する。実装済みの2bit重みでは、256 weights/beatに64 bytesが必要。G128のscaleを含めると平均72 bytes/beatで、250 MHzを連続稼働させるには18 GB/sとなる。19.2 GB/sというメモリの公称帯域に対して余裕が少ない。仮に70%効率なら13.44 GB/sで、他の通信を無視しても稼働率の上限は約74.7%になる。これは本機の式から得た分析で、基板の実測ではない。

prefillの4 token再利用は実装したが、64 token全体で重みを一度だけ読む実装ではない。CPUから細かいタイル命令を繰り返すだけでは制御コストが支配し得るため、完成系には自律的なループ制御とDMAが必要になる。Attention・KV cache・RMSNorm・RoPE・非三値LM headも、最終性能の合格条件から外さない。

### 6. 調査の限界

公開一次資料を照合したが、全世界の研究を網羅したとの主張はしない。論文著者の報告値は本環境で再測定していない。TeLLMeの電力境界・exact checkpoint、Vivado上の本機の実装適合性、実機上の消費電力、元モデルからの精度劣化は未確認である。これらを隠さず、`BENCHMARK_PROTOCOL.md` のゲートとして残した。


---

## TPC-X1 アーキテクチャ設計書

版：0.1、2026-09-20。対象はOpenTernaryと連携する三値専用テンソルアクセラレータである。Google製品としてのTPUではなく、テンソル処理専用NPUの研究設計を指す。

### 1. 実装済みの計算システム

```text
                          load ports (ready/valid)
                    ┌─────────┬─────────┬──────────┐
                    ▼         ▼         ▼          │
              A scratchpad   W bank0/1  S bank0/1  │
                 16 KiB      2×16 KiB   2×2 KiB    │
                    │         │         │          │
command ──► shape/validity checks ──► read sequencer │
                    │         │         │          │
                    └────┬────┘         │          │
                         ▼              │          │
               16 rows × 4 token lanes  │          │
               each: 16 ternary terms   │          │
                         │              │          │
             product(INT9), 4-level adder tree      │
                         │              │          │
                   group INT32 sums     │          │
                         │       coefficient FIFO  │
                         └───────┬──────┘          │
                                 ▼                 │
                       64 group-scale multipliers  │
                                 ▼                 │
                      signed RNE / INT64 accumulator
                                 ▼
                       output ready/valid matrix
```

この図の計算・メモリ・制御経路は `rtl/tpc_accelerator.sv` に統合した。外部DDRを直接操作するDMA、AXIインターコネクト、基板固有IPはこのtopの外側であり、まだ統合していない。512/4096-bitのポートはFPGA fabric内の接続であり、外部パッケージのピン本数を意味しない。

### 2. デフォルト構成

| 項目 | 実装仕様 |
|---|---|
| 出力行数R | 最大16、コマンドごとに1～16 |
| 同時token数B | 最大4、コマンドごとに1～4 |
| K並列度L | 16、RTLパラメータは2の累乗 |
| K長 | 1～4096、端数対応 |
| group | 128、K方向のrow-wise grouping |
| 入力activation | signed INT8、-128も有効 |
| 重み | {-1,0,+1}、canonical 2bit-v1を並べ替えて入力 |
| 三値product | signed INT9 |
| group sumの外部形式 | signed INT32 |
| scale | unsigned16-bit mantissa、right shift 0～31 |
| scale後の加算 | signed INT64、Kタイル間で早期飽和させない |
| valid/ready | 入出力のstall、出力payload保持、resetによるflush |
| 周波数 | 250 MHzは目標。配置配線で未確認 |

### 3. データフローをこうした理由

decodeでは一つのactivation vectorを16出力行へ配り、同時に256個のweight termを処理する。prefillでは同じweight群を最大4 tokenで共有し、最大1024 terms/accepted cycleを処理する。三値productは入力の選択・符号反転・ゼロ化で構成し、通常の乗算器に頼らない。

16-laneのdotは、product registerと4段の幅を拡張したbalanced adder treeを持つ。registerで分割した理由は、16項を直列加算する長い組合せ経路を避けるためである。ただし、これだけで250 MHzが保証されるわけではない。global enableのfanout、64出力の配置、scale丸め、コマンド検証回路などもtiming closureの対象となる。

G128なら8 input beatで一つのgroupを形成する。K末尾はmaskで無効laneをゼロ化し、groupを閉じる。group sumと係数を取り違えないため、4-entry metadata FIFOを用い、係数はgroup FIRSTで一度だけ捕捉する。

### 4. コントロールとパイプライン

MACは全体を停止できるパイプラインとしている。出力がvalidなのに受け取られない間は、payload・累算・タグ・validの進行をまとめて停止する。これは最大限のelastic pipelineより保守的だが、順序と数値を保ちやすい。metadata FIFOが満杯なら新しいgroup FIRSTの受け付けも止める。

scale側はproduct、RNE、累算の3段。groupごとの丸め後に、共通のrow-domainでINT64加算する。tile FIRSTでそのtileの累算とerrorを初期化し、tile LASTで出力する。groupをまたいで係数が違うため、全groupを先に一つの整数dotへ潰して最後にscaleを掛ける実装にはしない。

`out_error`が立った結果は数値として採用せず、そのコマンドを失敗扱いにする。reserved weight、scale reserved bits、shift範囲、group sum範囲などを検出する。演算器単体の不正なFIRST/LAST列はMACで検出できるが、stream engineは正しいframe契約を前提とする。通常は上位sequencerがframeを生成する。

### 5. scratchpadと所有権

Aは512 bits×256 wordsで16 KiB。Wは512 bits×512 wordsで32 KiBを2 bankに分ける。Sは512 bits×64 wordsで4 KiBを2 bankに分ける。これは論理payload容量であり、実際のBRAM消費は幅・深さ・port構成とmappingの断片化で増える。

実行中はAへの書き込みを拒否する。W/Sはactive bankへの書き込みを拒否し、inactive bankだけ受け付ける。これにより次のweight tileを準備できる。Aは二重化していないので、次のtoken chunkへ移るA loadまで完全に隠せる設計ではない。

validity bitmapにより、reset後に一度も初期化していないaddressを使うコマンドを拒否する。一方、以前のtileのデータが残っているかまで追跡するgeneration管理ではない。ホストはbank所有権、データ版、必要な全wordの更新を管理する。最後のloadと同じedgeにcommandを出すのではなく、load完了後の次cycle以降にcommitする。

resetはvalidityとpipelineを消すが、BRAM内容の物理的消去を保証しない。メモリは再loadしてから利用する。

### 6. 実装済みインターフェース

| ポート群 | 契約 |
|---|---|
| A load | a_valid/a_ready、block address、B×L×INT8 |
| W load | w_valid/w_ready、bank、block address、R×L×2 bits |
| S load | s_valid/s_ready、bank、group address、R×32-bit config |
| command | valid/ready、bank、K、rows、batch、16-bit tag |
| status | busy、1-cycle done、status code |
| output | valid/ready、B×R×INT64、error、tag |

statusは0=正常、1=shape不正、2=初期化不足、3=数値/encoding error。busy中の新commandはreadyが下がる。タグはaccepted commandのものを最後まで保持する。

### 7. OpenTernaryからの変換

元のpacking契約は要素0がbyte[7:6]で、byte単位の順序とは別に決まる。内部512-bit busではbyte0をbits[7:0]へ置き、そのbyteの上位2 bitsから読む。`sim/rtl.py` とbus image exporterが同じ規約を使用する。

元checkpointを無条件でそのままDMAできるという意味ではない。元のtensorを検証してから、[K block][row][lane]へ並べ替える。内部rowやtokenの余白はmask付きで埋める。元ファイルの末尾padding `00` と、内部の無効要素を論理zeroで埋める操作を混同しない。

FP32 scaleは、元のまま保存して数値比較の基準とする。ハードウェアへ送るものは別形式のm/shiftであり、変換の誤差を計算してから採用する。rotationレシピが入力変換を要求する場合は、変換済みとの明示がなければcompilerが拒否する。HadamardやTWLAの入力変換を「重みが三値だから不要」として削除しない。

### 8. 大きい行列への拡張

`model/compiler.py` はBを4、Rを16、Kを4096単位に分割する。Kの切れ目はG128境界に合わせ、全K tileで同じrow output unitを保持する。tileごとにunitを再計算すると加算できなくなるため禁止する。K tileのINT64部分出力をホストで合算し、INT32/INT8への飽和・再量子化は最後に行う。

実装した順序はtoken chunk→K tile→row tileで、Aを出力行間で再利用しやすい。デバッグ用CXXRTL transportは再現性のためAも毎回loadする。実運用のDMAループは未実装なので、理論的な再利用と現在のデバッグ転送量を別に測る。

### 9. 完成系TPUのシステム設計：ここからは未統合

```text
OpenTernary checkpoint + recipe
             │
      model compiler/runtime
             │
   descriptor ring / dependency scoreboard
             │
     AXI DMA + tile-layout adapter
       ┌─────┴────────────────────────┐
       ▼                              ▼
 TPC-X1 ternary tensor cluster    INT8 DSP matrix engine
       │                       (Attention / nonternary head)
       └───────────┬──────────────────┘
                   ▼
  vector unit: RMSNorm / RoPE / SiLU / requantization
                   │
       online softmax / tiled KV cache
                   │
                  DDR
```

AXI load/execute/storeは独立queueにし、bank generationと依存関係をscoreboardで管理する。K sliceやrow tileごとにCPUへ戻らず、descriptorのloop boundsをハードウェアが展開する。DDRの公称帯域を足し算で増やすことはできないため、複数AXI portでもメモリ全体の上限を共通予算にする。

Attentionには三値化されていないQ×K、score×Vが残る。INT8 DSP経路を別に用意し、stable online softmaxとKV blockingで中間N×N行列のDDR往復を抑える。これは設計方針であり、このZIPに完成したAttention RTLが入っているという意味ではない。RMSNorm、RoPE、SiLU、embedding、LM headのprecision・近似誤差もモデルごとに検証する。

FPGA全資源をternary coreだけで埋めず、control、DMA、SFU、Attention、clock/routeの余裕を残す。今回の合成値が小さく見えても、未統合機能の面積をゼロとして全体を比較しない。

### 10. ASICへの移植方針

計算RTLとmemory interfaceを分離したため、SRAM macroへ置き換える余地がある。ただしFPGAのLUT数からnm世代のASIC mm²、W、量産価格を直接推定しない。標準セル、SRAM macro、STA corners、clock tree、DFT、IR drop、EM、パッケージ、I/O、製造テストを別工程として扱う。今回ASICのGDS、製造依頼、実物チップは作成していない。


---

## 数値・符号・パッキング契約

### 演算の定義

Aは `[B,K]` signed INT8、Qは `[R,K]` の三値列。group gの整数和は

`d[b,r,g] = sum_k A[b,k] * Q[r,k]`。

FP32 weight scaleを `sw[r,g]`、token activation scaleを `sa[b]` とすると、基準となる実数出力は `sa[b] * sum_g sw[r,g] * d[b,r,g]` となる。これは元BF16モデルとの一致を意味せず、既に量子化された表現を実行する基準である。

各rowに共通の正のunit `u[r]` を選び、`sw/u ≈ m * 2^-shift` とする。mは0..65535、shiftは0..31。本機は

`Y64[b,r] = sum_g RNE(d[b,r,g] * m[r,g] / 2^shift[r,g])`

を計算する。実数へ戻すときは `Y64 * u[r] * sa[b]`。groupごとにunitを変えた整数をそのまま加算してはいけない。

### 必要なbit幅

`-128 × -1 = +128` のためproductはINT9。L16の部分和は最大絶対値2048。G128のgroup和は最大絶対値16384で、signed16 bitsに収まる。MACの外部group形式はINT32とし、scaler入口で範囲を検証してから16 bitsへ狭める。

scale mantissaはunsigned16なので、signed演算時に先頭zeroを追加して17 bitsとする。GP16×17で33-bit product。INT64の最終累算を使うため、例えばK4096、全A=-128、全Q=-1、m=65535、shift=0でも34,359,214,080を保持する。INT32へ先に落とすと結果が壊れる。

### RNE：負数も対称に扱う

`abs(product)`を除算し、remainderが半分より大きい場合に切り上げ、ちょうど半分なら商が奇数のときだけ切り上げる。その後に符号を戻す。例：1/2→0、3/2→2、-1/2→0、-3/2→-2。単純な算術右shiftや正数だけのbias加算では代用しない。

最初の実装は64-bit幅で丸めていた。今回、productの実幅33 bitsで丸め、最後だけINT64へsign extendする形に変更した。`formal/rne_equivalence.sv` は旧64-bit関数と新関数について、すべての33-bit入力と8-bit shift入力で等価であることをSATで検証する。これは全acceleratorの逐次回路証明とは別の局所的な証明である。

### 係数変換誤差

`e[r,g]=abs(sw/u - m*2^-shift)` とすれば、整数出力domainでの誤差は保守的に

`abs(error[b,r]) <= sum_g (abs(d[b,r,g])*e[r,g] + 0.5)`。

元のactivation量子化、元weightの三値化、rotation近似、float演算順序の差はこの式の対象外。ランダムな数値検証が通ったことを、実モデルの日本語品質やperplexityの維持と読み替えない。underflowは変換時に検出し、黙ってzero化しない。

### 2bit-v1

`00=-1 / 01=0 / 10=+1 / 11=invalid`。byteは `(c0<<6)|(c1<<4)|(c2<<2)|c3`。unused tailは00。`[-1,0,+1,-1]` は0x18になる。元要素数、dtype、tensor shapeをメタデータとして保持する。strict decoderはused11、余分なbyte、非00paddingを拒否する。

### T5：可逆の圧縮候補

5 tritsを `code=sum_i (q[i]+1)*3^i` として1 byteに詰める。243通りをすべて保持し、243..255をinvalidとする。4 tritsの81通りを64通りへ削る方式とは異なる。

G128ごとに独立packingした場合、ceil(128/5)=26 bytes。FP32 scaleの4 bytesを加えると30 bytes、すなわち1.875 bits/weight。2bitの32+4=36 bytesに対するpayload節約は16.7%、同じ帯域で運べる量の倍率は1.2倍。これを「三値演算が1.2倍速くなった」とは呼ばない。

T5 software codecとdecoder RTL primitiveは実装したが、DMA展開・gearbox・tile transposeは未統合。実装済みacceleratorの転送量は2bit形式で評価する。


---

## 性能比較と合格ゲート

### 1. 比較するものを固定する

同じcheckpoint revision、tensor fingerprint、量子化recipe、activation precision、KV precision、tokenizer、prompt、生成長、context長、batch、sampling設定を固定する。TeLLMeの0.7B exact checkpointを再現できない間は「TeLLMeを上回った」という判定をしない。別モデルなら別条件として比較表を分ける。

short-contextの9.51 tokens/sと1024-contextの約8 tokens/sを一つの基準値に混ぜない。prefill 64/128、decodeの各context、batch1/4は別測定にする。batch4の全token合計をbatch1の体感生成速度と比較しない。

### 2. 証拠の階層

| 階層 | 確認できること | 確認できないこと |
|---|---|---|
| Python/C++ golden | 数式・整数契約 | RTLの配線・時系列 |
| cycle仕様モデル | 設計したstall/latencyの振る舞い | 実際に書いたRTLとの一致 |
| CXXRTL | Yosysが読んだ実SystemVerilogの二値動作 | 4-state X、metastability、実配線delay |
| SAT局所証明 | 指定した組合せ性質の全入力 | 未指定の全chip性質 |
| Yosys technology mapping | そのflowの資源構成 | Vivadoでの適合性・配線後clock・W |
| Vivado実装 | device指定の配置配線とtiming | 基板の実電力、完全なLLM品質 |
| 基板測定 | clock、帯域、latency、測定境界内の電力 | 別model/別contextへの無条件一般化 |

### 3. 記録する性能

kernelはaccepted beat/cycle、terms/cycle、group/tile latency、load/compute/store別cycles、stall原因、weight bytes、scale bytes、activation bytesを記録する。TOPSを使う場合は三値MAC-equivalentで1 term=2 operationsという慣例を明記する。浮動小数点演算ではないのでTFLOPSと呼ばない。

全体はprefill/TTFT、decode median/p95 latency、tokens/s、最大context、品質指標、CPU占有、基板入力電力とFPGA推定電力を別に出す。ウォームアップ、最低複数run、thermal steady state、clock policy、測定器またはtoolの設定も保存する。

キャッシュ済みtileの演算時間から、loadと全LLM処理を含む性能を外挿しない。未統合のAttention、KV cache、SFU、ホストのコストをzeroにしない。

### 4. 現在の挑戦目標

短いcontextで12 tokens/s、64-token prefill 0.45 s以下、1024 contextで10 tokens/sを目標に設定する。電力はTeLLMeの6.72 Wと同じ測定境界を確定してから評価する。品質悪化の許容値はcheckpointと評価suiteを固定して明文化し、速度のために黙って変更しない。

### 5. 閉じる順序

G0：数学、packing、係数誤差、golden比較。

G1：実RTL compile、seed付きrandom、境界値、stall、reset、bank所有権。

G2：局所SAT、hot pathの乗算器ゼロ、generic/technology synthesis。

G3：Vivadoでexact partに対する合成・配置配線・timing closure、clock/reset/CDC/未制約path確認。

G4：AXI/DMA、データ転送の実測、matched numerical layer、元FP32 scaleとの誤差、メモリ保護。

G5：完全なモデルのprefill/decode、実品質、同条件の競合比較、電力境界の一致。

今回の結果は `reports/results.json` に記録する。未実行をPASSとみなさず、skip数を併記する。G5が閉じない限り、競合超え達成とは判定しない。


---

## 実機・完成系への統合設計

### 現在の成果物の境界

合成・シミュレーション可能なtile accelerator RTL、CPU golden、tile compiler、bus image exporterを用意した。外部メモリcontroller、AXI DMA、Linux driver、Attention、SFU、LLM runnerは未統合。`tpc_accelerator` のload portsへ正しいdataを供給することが動作の前提である。

### Host adapterの仕様案（未実装）

制御面はAXI4-Lite等のCSRとし、データ面はburst DMAとする。CSRの候補はCONTROL、STATUS、TAG、K、ROWS/BATCH/BANK、descriptor base、ring head/tail、性能counter。これは現在実装されているaddress mapではない。

commandのcommit時に全fieldをsnapshotする。実行中にhostがKやbankを書き換えてもin-flight jobへ反映させない。DMAは指定領域・長さ・alignmentを検証し、4 KiB境界、burst長、outstanding数、response error、timeoutに対処する。A/W/Sのgenerationごとにload完了を管理し、依存関係が満たされるまでcomputeを起動しない。

producer/consumerは別queueとする。CPUはmodel/layer単位のdescriptorを投入し、RTL側のloop engineがrow/K/token tileへ展開する。現在のPythonドライバはデバッグ用であり、実機でtileごとのPython呼び出しを行って高いtokens/sが出るとは想定しない。

### メモリ帯域とloop order

A-stationaryでは同じ4 token chunkを複数row tileへ再利用しやすいが、次のtoken chunkでWを再loadする。W-stationaryではweight tileを保持してtoken chunkを変えられるが、現在Aはsingle-bufferなのでA更新時に停止が必要になる。64-token prefillに対して、AもWも同時に一度だけ読む前提の性能式は作らない。

候補の改良はAの二重バッファ、token tileを8/16へ拡張、URAM weight cache、DMA側T5展開。ただしそれぞれclock、LUT/FF、port、bandwidthの再測定が必要。T5の保存payload節約を測定済みのruntime高速化と混同しない。

### Attention / SFUの役割分担案

AttentionのQKとPVはINT8×INT8のDSP経路へ分ける。KVはcontextのtile単位で読み、online softmaxではrunning maxとnormalizerを保持して数値安定性を確保する。RoPE、RMSNorm、SiLU、requantはvector unitへ集約する。これらの近似精度を含め、モデルを最後まで通したときのlogit/perplexityを確認する。

まずCPU参照とFPGAのoperatorを混在できるruntimeにするが、それは機能確認用。CPU fallbackを残したままの速度が目標に届くかは別に計測する。K26のCPU負荷も記録し、fallback時間を結果から除外しない。

### FPGA実装順序と停止条件

最初は元SystemVerilogをVivadoで再合成する。Yosys出力のprimitive netlistをそのまま実機へ送れると仮定しない。特に今回のmappingにはCARRY4やINVなどの表現が含まれ、UltraScale+向けの最終適合性はvendor flowで確認する必要がある。

OOCのtiming、実際のSoC wrapperでのtiming、配置配線後のclock、DDRロード時のstallを分ける。4 ns制約に失敗した場合、周波数を下げた値を正式に記録し、論文の250 MHzを達成した扱いにしない。電源・温度・電力の検証は完成した評価ボードの通常運用範囲で行い、電源回路の自作はこの計画の対象外。

### 優先順位

P0はvendor implementationとmemory transportの確立。P1は実checkpointの一層をbit-exact固定小数点で通し、scale変換の誤差を評価する。P2はAttention/SFU/LM headを統合し、完全モデルの計測へ移る。P3でmatched競合ベンチマークと電力評価を閉じる。ASIC検討は、この実機情報を得た後に別プロジェクトとして判断する。


---

## 既知の限界と、まだ達成していないこと

**このパッケージは完成した基板製品、FPGA bitstream、製造済みTPUではない。競合を超えるLLM tokens/sを実証したものでもない。**

実装は本格的なパイプライン・GEMV/GEMM tile・group scale・scratchpad・ping-pong・command controlを含むが、完全なTransformerの全operatorを含まない。Attention、Softmax、RMSNorm、RoPE、KV cache、embedding/LM head、tokenizer、サンプリング、モデルloaderの実機統合は未了。

CXXRTLは二値のRTLシミュレーションであり、4-state unknown propagation、CDC、metastability、gate delay、PVT corner、基板のsignal integrityを検証しない。SATは三値product・T5・丸め幅変更という局所組合せ性質のみ。全ての長さのtransaction列に対する全体formal proofではない。

Yosysのtechnology mappingは資源見積もりの証拠になるが、実際のVivado資源利用率、合法配置、route congestion、Fmax、消費電力の証明にはならない。250 MHz、0.512 TOPS-equivalent、12 tokens/s等の数字は、それぞれ前提付き計算値または目標値であり、実物で測った数字ではない。

T5はcodecとdecoder primitiveまで。現在のtopへ圧縮streamを直接渡す経路はない。zero weightは結果に0を足すが、cycleを圧縮するzero-skip schedulerではない。したがって、zero率からスピード倍率を自動算出しない。

FP32 scaleから固定小数点への変換は数値差を生む。今回証明した整数一致は変換後の契約との一致であり、元モデルの品質保持を証明していない。rotationが必要なモデルでは、入力変換を別に実施しなければならない。

load validityは「初期化済みか」を確認するだけで、過去jobの内容が最新かを自動認識しない。generation管理はhost contractに含まれる。単一clock・同期resetを前提とし、外部busとのCDC wrapperは未実装。

SDKのcompiled shared libraryはこのLinux x86_64環境用の便宜的成果物で、Windows native向けの配布binaryではない。ソースからの再構築方法をREADMEに記載する。古いbinaryが新しいRTLをテストしてしまわないよう、buildとsource hashを確認する。

参考研究は著者の一次資料を確認したが、本環境で競合実装を動かしたわけではない。exact checkpointや電力測定境界の不明点を残したまま、同条件比較が成立したとはしない。


---

## 参考資料

### S01 — TeLLMe: An Energy-Efficient Ternary LLM Accelerator for Prefill and Decode on Edge FPGAs

arXiv:2504.16266v2, 2025-04-24

```text
https://arxiv.org/pdf/2504.16266v2
```

### S02 — TerEffic: Highly Efficient Ternary LLM Inference on FPGA

arXiv:2502.16473v2, 2025-05-01

```text
https://arxiv.org/pdf/2502.16473v2
```

### S03 — Hardware Generation and Exploration of Lookup Table-Based Accelerators for 1.58-bit LLM Inference

arXiv:2604.25183v1, 2026-04-28

```text
https://arxiv.org/pdf/2604.25183v1
```

### S04 — KU Leuven MICAS ternary-lut-dse

accessed 2026-09-20

```text
https://github.com/KULeuven-MICAS/ternary-lut-dse
```

### S05 — TERINT-GEMV official repository

accessed 2026-09-20

```text
https://github.com/Notre-Dame-HW-SW-Codesign-Lab/TERINT-GEMV
```

### S06 — Microsoft T-MAC

accessed 2026-09-20

```text
https://github.com/microsoft/T-MAC
```

### S07 — Microsoft BitNet

accessed 2026-09-20

```text
https://github.com/microsoft/BitNet
```

### S08 — fpgasystems/ternaryLLM

accessed 2026-09-20

```text
https://github.com/fpgasystems/ternaryLLM
```

### S09 — Berkeley Gemmini

accessed 2026-09-20

```text
https://github.com/ucb-bar/gemmini
```

### S10 — FINN documentation

accessed 2026-09-20

```text
https://finn.readthedocs.io/en/latest/
```

### S11 — AMD KV260 Starter Kit Product Details DS986

DS986 1.3, 2025-06-25

```text
https://docs.amd.com/r/en-US/ds986-kv260-starter-kit/Product-Details
```

### S12 — OpenTernary canonical packing contract

commit 31564aeff6b03a46942ef048715058f4b5cba320

```text
https://github.com/ELRdn/OpenTernary/blob/31564aeff6b03a46942ef048715058f4b5cba320/src/openternary/quant/packing.py
```

### S13 — Official Yosys toolchain workflow

head d0e71cfb7bcafe2b437f3edc1789b69e99ecd55a, 2026-09-13

```text
https://github.com/YosysHQ/yosys/actions/runs/34751481437
```

### S14 — AMD K26 SOM datasheet DS987

accessed 2026-09-20

```text
https://docs.amd.com/r/en-US/ds987-k26-som
```

