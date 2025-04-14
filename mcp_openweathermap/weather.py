import os
import json
from pathlib import Path
from typing import Dict, Optional
from fastmcp import FastMCP
from dotenv import load_dotenv
from aiohttp import ClientSession

# Load environment variables
load_dotenv()

# Initialize FastMCP
mcp = FastMCP("mcp-openweathermap")

# Cache configuration
CACHE_DIR = Path.home() / ".cache" / "openweathermap"
LOCATION_CACHE_FILE = CACHE_DIR / "location_cache.json"

def get_cached_location_info(location: str) -> Optional[Dict]:
    """Get location info from cache."""
    if not LOCATION_CACHE_FILE.exists():
        return None
    
    try:
        with open(LOCATION_CACHE_FILE, "r") as f:
            cache = json.load(f)
            return cache.get(location)
    except (json.JSONDecodeError, FileNotFoundError):
        return None

def cache_location_info(location: str, location_info: Dict):
    """Cache location info for future use."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        if LOCATION_CACHE_FILE.exists():
            with open(LOCATION_CACHE_FILE, "r") as f:
                cache = json.load(f)
        else:
            cache = {}
        
        cache[location] = location_info
        
        with open(LOCATION_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to cache location info: {e}")

@mcp.tool()
async def get_current_weather(location: str) -> Dict:
    """Get current weather for a location."""
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        raise Exception("OPENWEATHERMAP_API_KEY environment variable not set")
    
    base_url = "https://api.openweathermap.org/data/2.5"
    geocoding_url = "https://api.openweathermap.org/geo/1.0/direct"
    
    # Try to get location info from cache first
    cached_location_info = get_cached_location_info(location)
    location_name = None
    country_name = None
    
    async with ClientSession() as session:
        if cached_location_info:
            lat = cached_location_info["lat"]
            lon = cached_location_info["lon"]
            location_name = cached_location_info["name"]
            country_name = cached_location_info["country"]
        else:
            # Location not in cache, fetch from API
            params = {
                "q": location,
                "limit": 1,
                "appid": api_key
            }
            async with session.get(geocoding_url, params=params) as response:
                geocode_data = await response.json()
                if response.status != 200:
                    raise Exception(f"Error fetching location data: {response.status}, {geocode_data}")
                if not geocode_data or len(geocode_data) == 0:
                    raise Exception("Location not found")
            
            # Extract location info
            location_data = geocode_data[0]
            lat = location_data["lat"]
            lon = location_data["lon"]
            location_name = location_data["name"]
            country_name = location_data["country"]
            
            # Cache the location info for future use
            location_info = {
                "lat": lat,
                "lon": lon,
                "name": location_name,
                "country": country_name
            }
            cache_location_info(location, location_info)
        
        # Get current weather using Weather API
        current_weather_url = f"{base_url}/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "units": "metric",
            "appid": api_key
        }
        
        async with session.get(current_weather_url, params=params) as response:
            weather_data = await response.json()
            if response.status != 200:
                raise Exception(f"Error fetching weather data: {response.status}, {weather_data}")
        
        # Format current conditions based on Current Weather API response
        current_data = {
            "temperature": {
                "value": weather_data["main"]["temp"],
                "unit": "C"
            },
            "weather_text": weather_data["weather"][0]["description"],
            "feels_like": weather_data["main"]["feels_like"],
            "humidity": weather_data["main"]["humidity"],
            "pressure": weather_data["main"]["pressure"],
            "wind_speed": weather_data["wind"]["speed"],
            "wind_direction": weather_data["wind"]["deg"],
            "cloudiness": weather_data["clouds"]["all"],
            "observation_time": weather_data["dt"]
        }
        
        # Add rain data if available
        if "rain" in weather_data:
            current_data["rain"] = weather_data["rain"]
        
        # Add snow data if available
        if "snow" in weather_data:
            current_data["snow"] = weather_data["snow"]
        
        # Add visibility if available
        if "visibility" in weather_data:
            current_data["visibility"] = weather_data["visibility"]
        
        return {
            "location": weather_data["name"],
            "coordinates": {"lat": lat, "lon": lon},
            "country": weather_data["sys"]["country"],
            "current_conditions": current_data
        } 