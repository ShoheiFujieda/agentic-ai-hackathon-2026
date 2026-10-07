"""技術検証用: 募集要項PDFから締切・書類・併給条件を引用つきで抽出できるか試す。

使い方: uv run python scripts/spike_extract_pdf.py <PDFのパス>...
（.env の GOOGLE_CLOUD_PROJECT 等を環境変数に読み込んでから実行）
"""
import sys, time
from google import genai
from google.genai import types

PROMPT = """あなたは大学の奨学金担当職員の補助者です。添付の募集要項から次をJSONで抜き出してください。
推測はせず、書かれていない項目は null。各項目に必ず page（ページ番号）と quote（原文の短い引用）を付けること。
{
 "scholarship_name": ..., "deadlines": [{"what":..., "date":..., "page":..., "quote":...}],
 "required_documents": [{"name":..., "who_prepares":"学生/大学/財団", "condition":"全員/該当者のみ", "page":..., "quote":...}],
 "eligibility": [...同形式...],
 "concurrent_receipt_rules": [...同形式（併給・重複受給の可否）...],
 "unclear_points": ["読み取れなかった・あいまいな箇所"]
}"""

client = genai.Client(vertexai=True)
for path in sys.argv[1:]:
    data = open(path, "rb").read()
    t = time.time()
    r = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[types.Part.from_bytes(data=data, mime_type="application/pdf"), PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json",
                                           thinking_config=types.ThinkingConfig(thinking_level="LOW")),
    )
    u = r.usage_metadata
    print(f"===== {path}  {time.time()-t:.1f}s  in={u.prompt_token_count} out={u.candidates_token_count}")
    print(r.text)
