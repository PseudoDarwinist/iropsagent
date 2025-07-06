import os
import requests
import json
from amadeus import Client, ResponseError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)
config = os.environ

# --- API KEYS AND CLIENTS ---
FLIGHTAWARE_API_KEY = config.get("FLIGHTAWARE_API_KEY")
AMADEUS_CLIENT_ID = config.get("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = config.get("AMADEUS_CLIENT_SECRET")

print(f"=== TOOLS.PY INITIALIZATION ===")
print(f"FLIGHTAWARE_API_KEY: {'SET' if FLIGHTAWARE_API_KEY else 'NOT SET'}")
print(f"AMADEUS_CLIENT_ID: {'SET' if AMADEUS_CLIENT_ID else 'NOT SET'}")
print(f"AMADEUS_CLIENT_SECRET: {'SET' if AMADEUS_CLIENT_SECRET else 'NOT SET'}")

# Initialize the Amadeus client
try:
    amadeus = Client(
        client_id=AMADEUS_CLIENT_ID,
        client_secret=AMADEUS_CLIENT_SECRET
    )
    print("Amadeus client initialized successfully")
except Exception as e:
    print(f"ERROR initializing Amadeus client: {e}")
    amadeus = None

# --- TOOL IMPLEMENTATIONS ---

def get_flight_status(flight_identifier: str) -> str:
    """
    Checks the status of a specific flight using the FlightAware AeroAPI.
    """
    print(f"\n=== GET_FLIGHT_STATUS CALLED ===")
    print(f"Flight identifier: {flight_identifier}")
    print(f"FlightAware API Key: {'SET' if FLIGHTAWARE_API_KEY else 'NOT SET'}")
    
    if not FLIGHTAWARE_API_KEY:
        error_msg = "ERROR: FLIGHTAWARE_API_KEY not found in environment variables"
        print(error_msg)
        return error_msg
    
    api_url = f"https://aeroapi.flightaware.com/aeroapi/flights/{flight_identifier}"
    headers = {"x-apikey": FLIGHTAWARE_API_KEY}
    
    print(f"API URL: {api_url}")
    print(f"Headers: {{'x-apikey': '***HIDDEN***'}}")

    try:
        print("Making request to FlightAware API...")
        response = requests.get(api_url, headers=headers, timeout=10)
        
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            error_msg = f"FlightAware API Error - Status: {response.status_code}, Response: {response.text}"
            print(error_msg)
            return error_msg
            
        response.raise_for_status()
        data = response.json()
        
        print(f"FlightAware API Response (raw JSON):")
        print(json.dumps(data, indent=2))

        if 'flights' in data and data['flights']:
            flight = data['flights'][0]
            print(f"Flight data found: {json.dumps(flight, indent=2)}")
            
            status = flight.get('status', 'Status Unknown')
            origin = flight.get('origin', {}).get('code', 'Unknown')
            destination = flight.get('destination', {}).get('code', 'Unknown')
            
            result = f"Flight {flight_identifier}: Status = {status}, Origin = {origin}, Destination = {destination}"
            
            if flight.get('cancelled'):
                result += " (CANCELLED)"
                
            print(f"Returning result: {result}")
            return result
        else:
            error_msg = f"Flight {flight_identifier} not found in FlightAware response"
            print(error_msg)
            return error_msg

    except requests.exceptions.Timeout:
        error_msg = f"ERROR: FlightAware API request timed out after 10 seconds"
        print(error_msg)
        return error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"ERROR calling FlightAware API: {str(e)}"
        print(error_msg)
        return error_msg
    except json.JSONDecodeError as e:
        error_msg = f"ERROR: Invalid JSON response from FlightAware API: {str(e)}"
        print(error_msg)
        print(f"Raw response text: {response.text}")
        return error_msg
    except Exception as e:
        error_msg = f"UNEXPECTED ERROR in get_flight_status: {str(e)}"
        print(error_msg)
        return error_msg

def find_alternative_flights(origin: str, destination: str, date: str) -> str:
    """
    Finds alternative flight options for a given route and date using the Amadeus API.
    """
    print(f"\n=== FIND_ALTERNATIVE_FLIGHTS CALLED ===")
    print(f"Origin: {origin}")
    print(f"Destination: {destination}")
    print(f"Date: {date}")
    print(f"Amadeus client: {'AVAILABLE' if amadeus else 'NOT AVAILABLE'}")
    
    if not amadeus:
        error_msg = "ERROR: Amadeus client not initialized"
        print(error_msg)
        return error_msg
    
    try:
        print("Making request to Amadeus API...")
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode=origin,
            destinationLocationCode=destination,
            departureDate=date,
            adults=1,
            max=5
        )
        
        print(f"Amadeus API Response Status: {response.status_code}")
        print(f"Amadeus API Response Data:")
        print(json.dumps(response.data, indent=2))
        
        if not response.data:
            error_msg = f"No alternative flights found for {origin} to {destination} on {date}"
            print(error_msg)
            return error_msg

        alternatives = []
        for i, offer in enumerate(response.data):
            print(f"Processing offer {i+1}: {json.dumps(offer, indent=2)}")
            
            itinerary = offer['itineraries'][0]
            segment = itinerary['segments'][0]
            carrier = segment['carrierCode']
            flight_number = segment['number']
            departure_time = segment['departure']['at']
            arrival_time = segment['arrival']['at']
            price = offer['price']['total']
            currency = offer['price']['currency']
            
            flight_info = f"Flight {carrier}{flight_number}: Departs {departure_time}, Arrives {arrival_time}, Price: {price} {currency}"
            alternatives.append(flight_info)
        
        result = f"Found {len(alternatives)} alternative flights:\n" + "\n".join(alternatives)
        print(f"Returning result: {result}")
        return result

    except ResponseError as e:
        error_msg = f"ERROR calling Amadeus API: {str(e)}"
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"UNEXPECTED ERROR in find_alternative_flights: {str(e)}"
        print(error_msg)
        return error_msg 