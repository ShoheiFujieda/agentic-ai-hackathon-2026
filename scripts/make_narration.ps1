# 読み上げ原稿（docs/submission/narration/script.json）を、Windows の日本語の音声で WAV にする（スライドごとに1ファイル）。
# 使い方: powershell -File scripts/make_narration.ps1 [-Voice "Microsoft Ichiro"] [-Rate 1.25]
#   Voice: Microsoft Haruka / Ayumi / Ichiro（Windows の日本語の音声）。Rate: 話す速さ（1.0 が標準）
param([string]$Voice = "Microsoft Ichiro", [double]$Rate = 1.25)
$env:PYTHONUTF8 = 1; [Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[void][Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }

$dir = Join-Path $PSScriptRoot "..\docs\submission\narration"
$rows = Get-Content (Join-Path $dir "script.json") -Raw -Encoding UTF8 | ConvertFrom-Json
# 英字・略語は、そのままだと読み間違えるので、カナにしてから読ませる
$fix = [ordered]@{ "adk eval" = "エーディーケー イーバル"; "ADK" = "エーディーケー"; "Cloud Run" = "クラウドラン"; "Firestore" = "ファイアストア"; "CSV" = "シーエスブイ"; "AI" = "エーアイ"; "Gemini" = "ジェミニ" }

$syn = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$v = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -eq $Voice } | Select-Object -First 1
if (-not $v) { throw "音声 '$Voice' が見つかりません" }
$syn.Voice = $v
$syn.Options.SpeakingRate = $Rate
$total = 0
foreach ($r in $rows) {
  $t = $r.text
  foreach ($k in $fix.Keys) { $t = $t.Replace($k, $fix[$k]) }
  $stream = Await ($syn.SynthesizeTextToStreamAsync($t)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
  $f = Join-Path $dir ("slide{0:00}.wav" -f $r.slide)
  $in = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
  $out = [System.IO.File]::Create($f); $in.CopyTo($out); $out.Close(); $in.Close()
  $b = [System.IO.File]::ReadAllBytes($f)
  $sec = [math]::Round(($b.Length - 44) / [BitConverter]::ToInt32($b, 28), 1)
  $total += $sec
  "{0:00}  {1}  目標 {2}  → {3} 秒" -f $r.slide, (Split-Path $f -Leaf), $r.time, $sec
}
"合計 $([math]::Round($total,1)) 秒（目標は3分＝180秒以内。スライドの切り替えの間も入れる）"
