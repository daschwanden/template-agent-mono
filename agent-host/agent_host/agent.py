# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import random

from google import adk
from google.adk.agents.llm_agent import Agent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.sessions import VertexAiSessionService
from google.adk.tools.example_tool import ExampleTool
from google.genai import types

user_id="DEMO-USER"

# Helper method to send query to the runner
#def call_agent(query, session_id, user_id):
#  content = types.Content(role='user', parts=[types.Part(text=query)])
#  events = runner.run(
#      user_id=user_id, session_id=session_id, new_message=content)
#
#  for event in events:
#      if event.is_final_response():
#          final_response = event.content.parts[0].text
#          print("Agent Response: ", final_response)

# --- Roll Die Sub-Agent ---
def roll_die(sides: int) -> int:
  """Roll a die and return the rolled result."""
  return random.randint(1, sides)

roll_agent = Agent(
    name="roll_agent",
    description="Handles rolling dice of different sizes.",
    instruction="""
      You are responsible for rolling dice based on the user's request.
      When asked to roll a die, you must call the roll_die tool with the number of sides as an integer.
    """,
    tools=[roll_die],
    generate_content_config=types.GenerateContentConfig(
        safety_settings=[
            types.SafetySetting(  # avoid false alarm about rolling dice.
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.OFF,
            ),
        ]
    ),
)

if "GOOGLE_AGENT_ENGINE" in os.environ:
  # Create the ADK runner with VertexAiSessionService
  session_service = VertexAiSessionService(
       os.getenv("GOOGLE_CLOUD_PROJECT"),
       os.getenv("GOOGLE_CLOUD_LOCATION"))

  runner = adk.Runner(
    agent=roll_agent,
    app_name=os.getenv("GOOGLE_AGENT_ENGINE"),
    session_service=session_service)


example_tool = ExampleTool([
    {
        "input": {
            "role": "user",
            "parts": [{"text": "Roll a 6-sided die."}],
        },
        "output": [
            {"role": "model", "parts": [{"text": "I rolled a 4 for you."}]}
        ],
    },
    {
        "input": {
            "role": "user",
            "parts": [{"text": "Is 7 a prime number?"}],
        },
        "output": [{
            "role": "model",
            "parts": [{"text": "Yes, 7 is a prime number."}],
        }],
    },
    {
        "input": {
            "role": "user",
            "parts": [{"text": "Roll a 10-sided die and check if it's prime."}],
        },
        "output": [
            {
                "role": "model",
                "parts": [{"text": "I rolled an 8 for you."}],
            },
            {
                "role": "model",
                "parts": [{"text": "8 is not a prime number."}],
            },
        ],
    },
])

remote_agents = []
with open('agent_host/agent_registry.csv') as file:
    while line := file.readline():
        name, base_url=line.rstrip().split(',')
        remote_agents.append(
            RemoteA2aAgent(
                name=name,
                agent_card=(f"{base_url}{AGENT_CARD_WELL_KNOWN_PATH}")
        )
    )

root_agent = Agent(
    model="gemini-2.5-flash",
    name="agent_host",
    instruction="""
      You are a helpful assistant that can roll dice and check if numbers are prime.
      You delegate rolling dice tasks to the roll_agent and prime checking tasks to the prime_agent.
      Follow these steps:
      1. If the user asks to roll a die, delegate to the roll_agent.
      2. If the user asks to check primes, delegate to the prime_agent.
      3. If the user asks to roll a die and then check if the result is prime, call roll_agent first, then pass the result to prime_agent.
      Always clarify the results before proceeding.
    """,
    global_instruction=(
        "You are DicePrimeBot, ready to roll dice and check prime numbers."
    ),
    sub_agents=[roll_agent] + remote_agents,
    tools=[example_tool],
    generate_content_config=types.GenerateContentConfig(
        safety_settings=[
            types.SafetySetting(  # avoid false alarm about rolling dice.
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.OFF,
            ),
        ]
    ),
)
