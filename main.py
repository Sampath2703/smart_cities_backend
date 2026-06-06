from fastapi import FastAPI, HTTPException
import requests
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_openai_tools_agent
load_dotenv()

app = FastAPI(title="Smart City Multi Agent")

TOMTOM_KEY = "VRhvDH64wjOCnRlfHdDAye3MmILnOFTE"
WEATHER_KEY = "6535731cfb0fa2b427d26fc52f989cfe"

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0
)


@tool
def traffic_tool(city: str):
    try:
        url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
        params = {
            "key": TOMTOM_KEY,
            "point": "17.3850,78.4867"
        }

        res = requests.get(url, params=params)

        if res.status_code == 200:
            data = res.json()["flowSegmentData"]
            return f"Speed {data['currentSpeed']} km/h | FreeFlow {data['freeFlowSpeed']} km/h"

    except:
        pass

    return "Traffic: Normal flow (fallback)"



@tool
def weather_tool(city: str):
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": WEATHER_KEY,
            "units": "metric"
        }

        res = requests.get(url, params=params)

        if res.status_code == 200:
            data = res.json()
            return f"{data['main']['temp']}°C | {data['weather'][0]['description']}"

    except:
        pass

    return "Weather stable (fallback)"



@tool
def parking_tool(city: str):
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
            count = len(data.get("elements", []))
            return f"Parking spots found: {count}"

    except:
        pass

    return "Parking: 25 available spots (fallback)"



@tool
def pothole_tool(city: str):
    try:
        query = """
        [out:json];
        way["highway"](around:5000,17.3850,78.4867);
        out;
        """

        url = "https://overpass-api.de/api/interpreter"
        res = requests.get(url, params={"data": query})

        if res.status_code == 200:
            data = res.json()
            roads = len(data.get("elements", []))

            potholes = int(roads * 0.02)

            return f"Estimated potholes: {potholes} | Severity: medium"

    except:
        pass

    return "Potholes: 3 detected (fallback)"



tools = [traffic_tool, weather_tool, parking_tool, pothole_tool]


prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a Smart City AI Agent. Use tools and give analysis."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


agent = create_openai_tools_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


class Query(BaseModel):
    city: str
    question: str


@app.post("/analyze")
def analyse_data(data: Query):

    if not data.city:
        raise HTTPException(status_code=400, detail="City required")

    query = f"""
City: {data.city}
Question: {data.question}

Use tools:
- traffic_tool
- weather_tool
- parking_tool
- pothole_tool
"""

    result = agent_executor.invoke({"input": query})

    return {
        "city": data.city,
        "analysis": result["output"]
    }

@app.get("/")
def home():
    return {"status": "Smart City Running"}