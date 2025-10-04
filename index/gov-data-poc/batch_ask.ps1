param(
  [string]$u = "http://127.0.0.1:8010",
  [string]$csv = ".\sample.csv",
  [int]$top_k = 5,
  [int]$min_score = 0
  [string]$api_key = ""
)

if (-not (Test-Path $csv)) {
  Write-Error "CSV が見つかりません: $csv"
  exit 1
}

$uri = "$u/batch-ask?top_k=$top_k&min_score=$min_score"

Add-Type -AssemblyName System.Net.Http
$handler = New-Object System.Net.Http.HttpClientHandler
$client = New-Object System.Net.Http.HttpClient($handler)
if ($api_key -ne "") {
  $client.DefaultRequestHeaders.Add("x-api-key", $api_key)
}
$mp = New-Object System.Net.Http.MultipartFormDataContent

$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $csv))
$ba = New-Object System.Net.Http.ByteArrayContent($bytes)
$ba.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("text/csv")
$mp.Add($ba, "file", [System.IO.Path]::GetFileName($csv))

$res = $client.PostAsync($uri, $mp).Result
if (-not $res.IsSuccessStatusCode) {
  Write-Error "HTTP Error: $($res.StatusCode) $($res.ReasonPhrase)"
  $txt = $res.Content.ReadAsStringAsync().Result
  Write-Host $txt
  exit 1
}

$body = $res.Content.ReadAsByteArrayAsync().Result
$out = Join-Path (Get-Location) "answers.csv"
[System.IO.File]::WriteAllBytes($out, $body)
Write-Host "OK: $out"
