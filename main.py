from fastapi import FastAPI, HTTPException
import requests
from pydantic import BaseModel
from dotenv import load_dotenv
import os

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_openai_tools_agent

load_dotenv()

app = FastAPI(title="Smart City Multi Agent")

TOMTOM_KEY = os.getenv("TOMTOM_API_KEY")
WEATHER_KEY = os.getenv("WEATHER_API_KEY")

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    api_key=os.getenv("OPEN_API_KEY"),
    http_client=None
)

@tool
def traffic_tool(city: str):
    """Get real-time traffic speed and congestion data."""
    try:
        url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
        params = {"key": TOMTOM_KEY, "point": "17.3850,78.4867"}
        res = requests.get(url, params=params)
        if res.status_code == 200:
            data = res.json()["flowSegmentData"]
            return f"Speed {data['currentSpeed']} km/h | FreeFlow {data['freeFlowSpeed']} km/h"
    except:
        pass
    return "Traffic fallback"

@tool
def weather_tool(city: str):
    """Get current weather data for a city."""
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": WEATHER_KEY, "units": "metric"}
        res = requests.get(url, params=params)
        if res.status_code == 200:
            data = res.json()
            return f"{data['main']['temp']}°C | {data['weather'][0]['description']}"
    except:
        pass
    return "Weather fallback"

@tool
def parking_tool(city: str):
    """Get parking availability using OpenStreetMap."""
    try:
        query = """
        [out:json];
        node["amenity"="parking"](around:5000,17.3850,78.4867);
        out;
        """
        url = "https://overpass-api.de/api/interpreter"
        r = requests.get(url, params={"data": query})
        if r.status_code == 200:
            data = r.json()
            return f"Parking spots: {len(data.get('elements', []))}"
    except:
        pass
    return "Parking fallback"

@tool
def pothole_tool(city: str):
    """Estimate pothole severity."""
    try:
        query = """
        [out:json];
        way["highway"](around:5000,17.3850,78.4867);
        out;
        """
        url = "https://overpass-api.de/api/interpreter"
        r = requests.get(url, params={"data": query})
        if r.status_code == 200:
            roads = len(r.json().get("elements", []))
            return f"Potholes: {int(roads * 0.02)} | Severity: Medium"
    except:
        pass
    return "Potholes fallback"

tools = [traffic_tool, weather_tool, parking_tool, pothole_tool]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a Smart City AI Agent."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_openai_tools_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools)

class Query(BaseModel):
    city: str
    question: str
    module: str

@app.post("/analyze")
def analyze(data: Query):
    try:
        if not data.city:
            raise HTTPException(status_code=400, detail="City required")

        query = f"""
City: {data.city}
Module: {data.module}
Question: {data.question}
Use tools: traffic_tool, weather_tool, parking_tool, pothole_tool
"""

        result = agent_executor.invoke({"input": query})

        return {
            "city": data.city,
            "module": data.module,
            "analysis": result.get("output", "No output returned")
        }

    except Exception as e:
        return {
            "error": str(e),
            "analysis": "Backend crashed"
        }