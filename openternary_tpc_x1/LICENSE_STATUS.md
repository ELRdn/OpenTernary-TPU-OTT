# ライセンス・出所

本パッケージの独自RTL、Python、C++ reference、テスト、ドキュメントは今回作成した実装である。参考研究のソースコードを丸ごと複製したものではない。OpenTernaryのpacking互換性は公開された数値・bit配置の契約として独立実装した。

独自部分は、元のOpenTernaryと同じApache License 2.0で公開する（リポジトリ直下の `LICENSE`・`NOTICE`・`TRADEMARKS.md`、2026-11-03決定）。第三者実装を将来取り込む場合は、その時点のライセンスとattributionを確認する。本レポートは特許調査や商用利用の適法性を保証する文書ではない。

CXXRTLの生成C++とcompiled modelはYosysのruntimeを使用する。そのpermissive noticeを `licenses/CXXRTL_RUNTIME_NOTICE.txt` に同梱した。Yosys/ABCのインストール用archive、wheel、他の開発ツール本体は同梱しない。再現用の版・出所・hashは `reference/toolchain.json` にある。

`reference/user_supplied_prior_report.md` はユーザーがこの依頼で提供した先行文章の保存用コピーであり、一次資料や今回の検証結果ではない。元の著者の条件に従い、Apache License 2.0の対象外とする（`NOTICE` 参照）。
