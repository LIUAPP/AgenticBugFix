from agents import Agent, Runner, WebSearchTool
from dotenv import load_dotenv
load_dotenv()

agent = Agent(
    name="Web Search Agent",
    instructions=(
        "You are a web search agent that searches the web for information to "
        "answer the user's queries with high accuracy and precision."
        "Respond with the best summarized answer in minimum tokens, no more than 1000 words."
    ),
    tools=[WebSearchTool()],           # 👈 built-in hosted web search
    model="gpt-5",
)

async def web_search(query: str) -> str:
    result = await Runner.run(
        starting_agent=agent,
        input=query,
    )
    return(result.final_output)
if __name__ == "__main__":
    import asyncio
    print (asyncio.run(web_search("fixes for python mutable default arguments bug")))