# 数値・符号・パッキング契約

## 演算の定義

Aは `[B,K]` signed INT8、Qは `[R,K]` の三値列。group gの整数和は

`d[b,r,g] = sum_k A[b,k] * Q[r,k]`。

FP32 weight scaleを `sw[r,g]`、token activation scaleを `sa[b]` とすると、基準となる実数出力は `sa[b] * sum_g sw[r,g] * d[b,r,g]` となる。これは元BF16モデルとの一致を意味せず、既に量子化された表現を実行する基準である。

各rowに共通の正のunit `u[r]` を選び、`sw/u ≈ m * 2^-shift` とする。mは0..65535、shiftは0..31。本機は

`Y64[b,r] = sum_g RNE(d[b,r,g] * m[r,g] / 2^shift[r,g])`

を計算する。実数へ戻すときは `Y64 * u[r] * sa[b]`。groupごとにunitを変えた整数をそのまま加算してはいけない。

## 必要なbit幅

`-128 × -1 = +128` のためproductはINT9。L16の部分和は最大絶対値2048。G128のgroup和は最大絶対値16384で、signed16 bitsに収まる。MACの外部group形式はINT32とし、scaler入口で範囲を検証してから16 bitsへ狭める。

scale mantissaはunsigned16なので、signed演算時に先頭zeroを追加して17 bitsとする。GP16×17で33-bit product。INT64の最終累算を使うため、例えばK4096、全A=-128、全Q=-1、m=65535、shift=0でも34,359,214,080を保持する。INT32へ先に落とすと結果が壊れる。

## RNE：負数も対称に扱う

`abs(product)`を除算し、remainderが半分より大きい場合に切り上げ、ちょうど半分なら商が奇数のときだけ切り上げる。その後に符号を戻す。例：1/2→0、3/2→2、-1/2→0、-3/2→-2。単純な算術右shiftや正数だけのbias加算では代用しない。

最初の実装は64-bit幅で丸めていた。今回、productの実幅33 bitsで丸め、最後だけINT64へsign extendする形に変更した。`formal/rne_equivalence.sv` は旧64-bit関数と新関数について、すべての33-bit入力と8-bit shift入力で等価であることをSATで検証する。これは全acceleratorの逐次回路証明とは別の局所的な証明である。

## 係数変換誤差

`e[r,g]=abs(sw/u - m*2^-shift)` とすれば、整数出力domainでの誤差は保守的に

`abs(error[b,r]) <= sum_g (abs(d[b,r,g])*e[r,g] + 0.5)`。

元のactivation量子化、元weightの三値化、rotation近似、float演算順序の差はこの式の対象外。ランダムな数値検証が通ったことを、実モデルの日本語品質やperplexityの維持と読み替えない。underflowは変換時に検出し、黙ってzero化しない。

## 2bit-v1

`00=-1 / 01=0 / 10=+1 / 11=invalid`。byteは `(c0<<6)|(c1<<4)|(c2<<2)|c3`。unused tailは00。`[-1,0,+1,-1]` は0x18になる。元要素数、dtype、tensor shapeをメタデータとして保持する。strict decoderはused11、余分なbyte、非00paddingを拒否する。

## T5：可逆の圧縮候補

5 tritsを `code=sum_i (q[i]+1)*3^i` として1 byteに詰める。243通りをすべて保持し、243..255をinvalidとする。4 tritsの81通りを64通りへ削る方式とは異なる。

G128ごとに独立packingした場合、ceil(128/5)=26 bytes。FP32 scaleの4 bytesを加えると30 bytes、すなわち1.875 bits/weight。2bitの32+4=36 bytesに対するpayload節約は16.7%、同じ帯域で運べる量の倍率は1.2倍。これを「三値演算が1.2倍速くなった」とは呼ばない。

T5 software codecとdecoder RTL primitiveは実装したが、DMA展開・gearbox・tile transposeは未統合。実装済みacceleratorの転送量は2bit形式で評価する。
