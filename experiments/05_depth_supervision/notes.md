# Experiment 05: Depth Supervision - Notes

## 実験ログ

このファイルには、Experiment 05 の実行過程で得られた知見や結果を記録します。

---

## 次のステップ

1. **Stage 0: 深度マップ生成** - scene-0757 で LiDAR 深度マップ生成
2. **Stage 1 学習（30k iterations、深度なし）** - baseline（マスクのみ）
3. **Stage 2 学習（30k iterations、depth-loss-mult=0.1）** - 深度拘束あり
4. **Stage 3 学習（30k iterations、depth-loss-mult=1.0）** - 強い深度拘束
