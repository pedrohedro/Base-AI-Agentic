import json

transcript_path = "/Users/pedrohedro/.gemini/antigravity/brain/384b1aaa-9dd3-4504-ba3a-9db691d9c46f/.system_generated/logs/transcript.jsonl"

print("Searching transcript...")
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            step = json.loads(line)
            content = str(step.get("content", ""))
            tool_calls = str(step.get("tool_calls", ""))
            if "seerium" in content.lower() or "seerium" in tool_calls.lower():
                print(f"Step {step.get('step_index')}:")
                print(f"Source: {step.get('source')}, Type: {step.get('type')}")
                if content:
                    # Print first 500 chars of content
                    print(f"Content snippet: {content[:500]}...")
                if step.get("tool_calls"):
                    print(f"Tool Calls: {step.get('tool_calls')}")
                print("-" * 50)
        except Exception as e:
            pass
