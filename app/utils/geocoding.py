import requests

def get_area_name(latitude: float, longitude: float) -> str | None:
    """
    GPS coordinates ko human-readable area name mein convert karta hai
    using Nominatim (OpenStreetMap) Reverse Geocoding API.
    """
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "json",
        "accept-language": "en"  # English mein response chahiye
    }
    headers = {
        "User-Agent": "CivicLensApp/1.0"   # Nominatim isko mandatory karta hai
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()

        address = data.get("address", {})

        # Priority: suburb/neighbourhood > town > city
        area = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("town")
            or address.get("city_district")
            or address.get("city")
        )

        return area

    except requests.exceptions.RequestException:
        return None