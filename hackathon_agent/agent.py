from google.adk.agents import Agent

root_agent = Agent(
    name="hackathon_agent",
    model="gemini-3.8-flash",
    description="Agentic AI Hackathon の雛形エージェント",
    instruction=(
        "あなたは親切なアシスタントです。"
        "ユーザーの質問に日本語で答えてください。"
    ),
)
