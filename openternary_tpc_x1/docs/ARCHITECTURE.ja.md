# TPC-X1 アーキテクチャ設計書

版：0.1、2026-09-20。対象はOpenTernaryと連携する三値専用テンソルアクセラレータである。Google製品としてのTPUではなく、テンソル処理専用NPUの研究設計を指す。

## 1. 実装済みの計算システム

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

## 2. デフォルト構成

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

## 3. データフローをこうした理由

decodeでは一つのactivation vectorを16出力行へ配り、同時に256個のweight termを処理する。prefillでは同じweight群を最大4 tokenで共有し、最大1024 terms/accepted cycleを処理する。三値productは入力の選択・符号反転・ゼロ化で構成し、通常の乗算器に頼らない。

16-laneのdotは、product registerと4段の幅を拡張したbalanced adder treeを持つ。registerで分割した理由は、16項を直列加算する長い組合せ経路を避けるためである。ただし、これだけで250 MHzが保証されるわけではない。global enableのfanout、64出力の配置、scale丸め、コマンド検証回路などもtiming closureの対象となる。

G128なら8 input beatで一つのgroupを形成する。K末尾はmaskで無効laneをゼロ化し、groupを閉じる。group sumと係数を取り違えないため、4-entry metadata FIFOを用い、係数はgroup FIRSTで一度だけ捕捉する。

## 4. コントロールとパイプライン

MACは全体を停止できるパイプラインとしている。出力がvalidなのに受け取られない間は、payload・累算・タグ・validの進行をまとめて停止する。これは最大限のelastic pipelineより保守的だが、順序と数値を保ちやすい。metadata FIFOが満杯なら新しいgroup FIRSTの受け付けも止める。

scale側はproduct、RNE、累算の3段。groupごとの丸め後に、共通のrow-domainでINT64加算する。tile FIRSTでそのtileの累算とerrorを初期化し、tile LASTで出力する。groupをまたいで係数が違うため、全groupを先に一つの整数dotへ潰して最後にscaleを掛ける実装にはしない。

`out_error`が立った結果は数値として採用せず、そのコマンドを失敗扱いにする。reserved weight、scale reserved bits、shift範囲、group sum範囲などを検出する。演算器単体の不正なFIRST/LAST列はMACで検出できるが、stream engineは正しいframe契約を前提とする。通常は上位sequencerがframeを生成する。

## 5. scratchpadと所有権

Aは512 bits×256 wordsで16 KiB。Wは512 bits×512 wordsで32 KiBを2 bankに分ける。Sは512 bits×64 wordsで4 KiBを2 bankに分ける。これは論理payload容量であり、実際のBRAM消費は幅・深さ・port構成とmappingの断片化で増える。

実行中はAへの書き込みを拒否する。W/Sはactive bankへの書き込みを拒否し、inactive bankだけ受け付ける。これにより次のweight tileを準備できる。Aは二重化していないので、次のtoken chunkへ移るA loadまで完全に隠せる設計ではない。

validity bitmapにより、reset後に一度も初期化していないaddressを使うコマンドを拒否する。一方、以前のtileのデータが残っているかまで追跡するgeneration管理ではない。ホストはbank所有権、データ版、必要な全wordの更新を管理する。最後のloadと同じedgeにcommandを出すのではなく、load完了後の次cycle以降にcommitする。

resetはvalidityとpipelineを消すが、BRAM内容の物理的消去を保証しない。メモリは再loadしてから利用する。

## 6. 実装済みインターフェース

| ポート群 | 契約 |
|---|---|
| A load | a_valid/a_ready、block address、B×L×INT8 |
| W load | w_valid/w_ready、bank、block address、R×L×2 bits |
| S load | s_valid/s_ready、bank、group address、R×32-bit config |
| command | valid/ready、bank、K、rows、batch、16-bit tag |
| status | busy、1-cycle done、status code |
| output | valid/ready、B×R×INT64、error、tag |

statusは0=正常、1=shape不正、2=初期化不足、3=数値/encoding error。busy中の新commandはreadyが下がる。タグはaccepted commandのものを最後まで保持する。

## 7. OpenTernaryからの変換

元のpacking契約は要素0がbyte[7:6]で、byte単位の順序とは別に決まる。内部512-bit busではbyte0をbits[7:0]へ置き、そのbyteの上位2 bitsから読む。`sim/rtl.py` とbus image exporterが同じ規約を使用する。

元checkpointを無条件でそのままDMAできるという意味ではない。元のtensorを検証してから、[K block][row][lane]へ並べ替える。内部rowやtokenの余白はmask付きで埋める。元ファイルの末尾padding `00` と、内部の無効要素を論理zeroで埋める操作を混同しない。

FP32 scaleは、元のまま保存して数値比較の基準とする。ハードウェアへ送るものは別形式のm/shiftであり、変換の誤差を計算してから採用する。rotationレシピが入力変換を要求する場合は、変換済みとの明示がなければcompilerが拒否する。HadamardやTWLAの入力変換を「重みが三値だから不要」として削除しない。

## 8. 大きい行列への拡張

`model/compiler.py` はBを4、Rを16、Kを4096単位に分割する。Kの切れ目はG128境界に合わせ、全K tileで同じrow output unitを保持する。tileごとにunitを再計算すると加算できなくなるため禁止する。K tileのINT64部分出力をホストで合算し、INT32/INT8への飽和・再量子化は最後に行う。

実装した順序はtoken chunk→K tile→row tileで、Aを出力行間で再利用しやすい。デバッグ用CXXRTL transportは再現性のためAも毎回loadする。実運用のDMAループは未実装なので、理論的な再利用と現在のデバッグ転送量を別に測る。

## 9. 完成系TPUのシステム設計：ここからは未統合

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

## 10. ASICへの移植方針

計算RTLとmemory interfaceを分離したため、SRAM macroへ置き換える余地がある。ただしFPGAのLUT数からnm世代のASIC mm²、W、量産価格を直接推定しない。標準セル、SRAM macro、STA corners、clock tree、DFT、IR drop、EM、パッケージ、I/O、製造テストを別工程として扱う。今回ASICのGDS、製造依頼、実物チップは作成していない。
