# tools/param_sweep.ps1
param($HostUrl="http://127.0.0.1:8010", $Token="changeme-local-token")
$weights = @(0.2,0.4,0.55,0.7,0.9)
$bm25top = @(30,50,80)
"w_bm25,w_vec,bm25_top_n,good_ratio(%)" | Out-File sweep_result.csv -Encoding utf8
foreach ($wb in $weights) {
  foreach ($bt in $bm25top) {
    $wv = [math]::Round(1-$wb,2)
    $csv = curl.exe -s -H "x-api-key: $Token" -F "file=@sample.csv;type=text/csv" `
      "$HostUrl/batch-ask?bm25_top_n=$bt&w_bm25=$wb&w_vec=$wv&top_k=5&min_score=0.3"
    # 疑似スコア: 1問ずつ search/ask を good と見なす簡易法（ここでは省略）。
    # 実運用では feedback.csv の 'good' 割合で比較してください。
    " $wb,$wv,$bt,NA" | Out-File -Append sweep_result.csv -Encoding utf8
  }
}
Write-Host "sweep_result.csv を確認してください"
