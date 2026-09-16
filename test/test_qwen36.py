from groq import Groq

client = Groq(api_key="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")
res = client.chat.completions.create(
    model="qwen/qwen3.6-27b",
    messages=[{"role": "user", "content": "List 2 visual scenes for psychology video in JSON format"}],
    max_tokens=300
)
print("SUCCESS qwen3.6-27b:")
print(res.choices[0].message.content[:200])
