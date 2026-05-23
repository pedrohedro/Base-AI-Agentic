import json

transcript_path = "/Users/pedrohedro/.gemini/antigravity/brain/384b1aaa-9dd3-4504-ba3a-9db691d9c46f/.system_generated/logs/transcript.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            step = json.loads(line)
            if step.get("step_index") == 344:
                print(step.get("content"))
                break
        except Exception:
            pass
