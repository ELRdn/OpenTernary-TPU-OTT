# 性能比較と合格ゲート

## 1. 比較するものを固定する

同じcheckpoint revision、tensor fingerprint、量子化recipe、activation precision、KV precision、tokenizer、prompt、生成長、context長、batch、sampling設定を固定する。TeLLMeの0.7B exact checkpointを再現できない間は「TeLLMeを上回った」という判定をしない。別モデルなら別条件として比較表を分ける。

short-contextの9.51 tokens/sと1024-contextの約8 tokens/sを一つの基準値に混ぜない。prefill 64/128、decodeの各context、batch1/4は別測定にする。batch4の全token合計をbatch1の体感生成速度と比較しない。

## 2. 証拠の階層

| 階層 | 確認できること | 確認できないこと |
|---|---|---|
| Python/C++ golden | 数式・整数契約 | RTLの配線・時系列 |
| cycle仕様モデル | 設計したstall/latencyの振る舞い | 実際に書いたRTLとの一致 |
| CXXRTL | Yosysが読んだ実SystemVerilogの二値動作 | 4-state X、metastability、実配線delay |
| SAT局所証明 | 指定した組合せ性質の全入力 | 未指定の全chip性質 |
| Yosys technology mapping | そのflowの資源構成 | Vivadoでの適合性・配線後clock・W |
| Vivado実装 | device指定の配置配線とtiming | 基板の実電力、完全なLLM品質 |
| 基板測定 | clock、帯域、latency、測定境界内の電力 | 別model/別contextへの無条件一般化 |

## 3. 記録する性能

kernelはaccepted beat/cycle、terms/cycle、group/tile latency、load/compute/store別cycles、stall原因、weight bytes、scale bytes、activation bytesを記録する。TOPSを使う場合は三値MAC-equivalentで1 term=2 operationsという慣例を明記する。浮動小数点演算ではないのでTFLOPSと呼ばない。

全体はprefill/TTFT、decode median/p95 latency、tokens/s、最大context、品質指標、CPU占有、基板入力電力とFPGA推定電力を別に出す。ウォームアップ、最低複数run、thermal steady state、clock policy、測定器またはtoolの設定も保存する。

キャッシュ済みtileの演算時間から、loadと全LLM処理を含む性能を外挿しない。未統合のAttention、KV cache、SFU、ホストのコストをzeroにしない。

## 4. 現在の挑戦目標

短いcontextで12 tokens/s、64-token prefill 0.45 s以下、1024 contextで10 tokens/sを目標に設定する。電力はTeLLMeの6.72 Wと同じ測定境界を確定してから評価する。品質悪化の許容値はcheckpointと評価suiteを固定して明文化し、速度のために黙って変更しない。

## 5. 閉じる順序

G0：数学、packing、係数誤差、golden比較。

G1：実RTL compile、seed付きrandom、境界値、stall、reset、bank所有権。

G2：局所SAT、hot pathの乗算器ゼロ、generic/technology synthesis。

G3：Vivadoでexact partに対する合成・配置配線・timing closure、clock/reset/CDC/未制約path確認。

G4：AXI/DMA、データ転送の実測、matched numerical layer、元FP32 scaleとの誤差、メモリ保護。

G5：完全なモデルのprefill/decode、実品質、同条件の競合比較、電力境界の一致。

今回の結果は `reports/results.json` に記録する。未実行をPASSとみなさず、skip数を併記する。G5が閉じない限り、競合超え達成とは判定しない。
