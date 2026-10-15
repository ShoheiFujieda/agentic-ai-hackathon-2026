# 本番の URL に、サンプル条件で検索を1回ずつ流して、共有キャッシュを温める（撮影・審査の前に実行する）。
# パスワードは Secret Manager から読む（画面にもファイルにも出さない）。実行する人に、その秘密の閲覧権限が必要。
param([string]$Base = "https://hackathon-agent-525978871269.us-central1.run.app")
$env:PYTHONUTF8 = 1; [Console]::OutputEncoding = [Text.Encoding]::UTF8
$pw = (gcloud secrets versions access latest --secret=scholarship-app-password --project agentic-hackathon-2026-510706).Trim()
$auth = "Basic " + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("tester:$pw"))
$h = @{Authorization = $auth; "Content-Type" = "application/json; charset=utf-8" }
$texts = @(
  "筑波大学（茨城県）の理工学群、大学3年（立場: 大学生）です。出身高校は埼玉県、今は茨城県に住んでいて、保護者は埼玉県に住んでいます。奨学金は何も受けていません。利用の目的は学業・生活費です。",
  "高校3年生（立場: 高校生）です。出身も今の住まいも埼玉県で、保護者も埼玉県に住んでいます。奨学金は何も受けていません。利用の目的は学業・生活費です。",
  "東京大学（東京都）の経済学部、大学3年（立場: 大学生）です。出身高校は神奈川県、今は東京都に住んでいて、保護者は神奈川県に住んでいます。奨学金は何も受けていません。利用の目的は留学です。"
)
foreach ($t in $texts) {
  $sid = "warm-" + [guid]::NewGuid().ToString("N").Substring(0, 6)
  Invoke-RestMethod -Method Post "$Base/apps/hackathon_agent/users/warm/sessions/$sid" -Headers $h -Body '{}' | Out-Null
  $b = @{app_name = "hackathon_agent"; user_id = "warm"; session_id = $sid; new_message = @{role = "user"; parts = @(@{text = $t }) } } | ConvertTo-Json -Depth 6
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $r = Invoke-RestMethod -Method Post "$Base/run" -Headers $h -Body ([Text.Encoding]::UTF8.GetBytes($b)) -TimeoutSec 600
  $fr = ($r | ForEach-Object { $_.content.parts } | Where-Object { $_.functionResponse }).functionResponse.response
  "{0,6:N1}s  {1}…  → 応募できる={2} 要確認={3} 未確認={4} 募集終了={5}" -f $sw.Elapsed.TotalSeconds, $t.Substring(0, 12), $fr.eligible.Count, $fr.needs_check.Count, $fr.unverified.Count, $fr.closed.Count
}
