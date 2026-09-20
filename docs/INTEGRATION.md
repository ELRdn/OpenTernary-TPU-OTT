# 実機・完成系への統合設計

## 現在の成果物の境界

合成・シミュレーション可能なtile accelerator RTL、CPU golden、tile compiler、bus image exporterを用意した。外部メモリcontroller、AXI DMA、Linux driver、Attention、SFU、LLM runnerは未統合。`tpc_accelerator` のload portsへ正しいdataを供給することが動作の前提である。

## Host adapterの仕様案（未実装）

制御面はAXI4-Lite等のCSRとし、データ面はburst DMAとする。CSRの候補はCONTROL、STATUS、TAG、K、ROWS/BATCH/BANK、descriptor base、ring head/tail、性能counter。これは現在実装されているaddress mapではない。

commandのcommit時に全fieldをsnapshotする。実行中にhostがKやbankを書き換えてもin-flight jobへ反映させない。DMAは指定領域・長さ・alignmentを検証し、4 KiB境界、burst長、outstanding数、response error、timeoutに対処する。A/W/Sのgenerationごとにload完了を管理し、依存関係が満たされるまでcomputeを起動しない。

producer/consumerは別queueとする。CPUはmodel/layer単位のdescriptorを投入し、RTL側のloop engineがrow/K/token tileへ展開する。現在のPythonドライバはデバッグ用であり、実機でtileごとのPython呼び出しを行って高いtokens/sが出るとは想定しない。

## メモリ帯域とloop order

A-stationaryでは同じ4 token chunkを複数row tileへ再利用しやすいが、次のtoken chunkでWを再loadする。W-stationaryではweight tileを保持してtoken chunkを変えられるが、現在Aはsingle-bufferなのでA更新時に停止が必要になる。64-token prefillに対して、AもWも同時に一度だけ読む前提の性能式は作らない。

候補の改良はAの二重バッファ、token tileを8/16へ拡張、URAM weight cache、DMA側T5展開。ただしそれぞれclock、LUT/FF、port、bandwidthの再測定が必要。T5の保存payload節約を測定済みのruntime高速化と混同しない。

## Attention / SFUの役割分担案

AttentionのQKとPVはINT8×INT8のDSP経路へ分ける。KVはcontextのtile単位で読み、online softmaxではrunning maxとnormalizerを保持して数値安定性を確保する。RoPE、RMSNorm、SiLU、requantはvector unitへ集約する。これらの近似精度を含め、モデルを最後まで通したときのlogit/perplexityを確認する。

まずCPU参照とFPGAのoperatorを混在できるruntimeにするが、それは機能確認用。CPU fallbackを残したままの速度が目標に届くかは別に計測する。K26のCPU負荷も記録し、fallback時間を結果から除外しない。

## FPGA実装順序と停止条件

最初は元SystemVerilogをVivadoで再合成する。Yosys出力のprimitive netlistをそのまま実機へ送れると仮定しない。特に今回のmappingにはCARRY4やINVなどの表現が含まれ、UltraScale+向けの最終適合性はvendor flowで確認する必要がある。

OOCのtiming、実際のSoC wrapperでのtiming、配置配線後のclock、DDRロード時のstallを分ける。4 ns制約に失敗した場合、周波数を下げた値を正式に記録し、論文の250 MHzを達成した扱いにしない。電源・温度・電力の検証は完成した評価ボードの通常運用範囲で行い、電源回路の自作はこの計画の対象外。

## 優先順位

P0はvendor implementationとmemory transportの確立。P1は実checkpointの一層をbit-exact固定小数点で通し、scale変換の誤差を評価する。P2はAttention/SFU/LM headを統合し、完全モデルの計測へ移る。P3でmatched競合ベンチマークと電力評価を閉じる。ASIC検討は、この実機情報を得た後に別プロジェクトとして判断する。
