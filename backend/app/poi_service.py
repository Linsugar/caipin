import httpx

from app.config import ProviderConfig
from app.schemas import NearbyPoiRequest, PoiCandidate


class PoiService:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    async def nearby(self, request: NearbyPoiRequest) -> list[PoiCandidate]:
        if not self.config.amap_key:
            return [
                PoiCandidate(id="mock_poi_1", name="附近家常菜馆", address="模拟地址 1", distance_m=80, rating="4.3", cost="45", tags=["家常菜"]),
                PoiCandidate(id="mock_poi_2", name="老街火锅", address="模拟地址 2", distance_m=160, rating="4.1", cost="88", tags=["火锅"]),
                PoiCandidate(id="mock_poi_3", name="快餐简餐", address="模拟地址 3", distance_m=230, rating="4.0", cost="28", tags=["简餐"]),
            ]

        params = {
            "key": self.config.amap_key,
            "location": f"{request.longitude},{request.latitude}",
            "radius": request.radius_m,
            "types": "050000",
            "show_fields": "business",
        }
        async with httpx.AsyncClient(timeout=self.config.request_timeout_seconds) as client:
            response = await client.get("https://restapi.amap.com/v5/place/around", params=params)
            response.raise_for_status()
        data = response.json()
        pois = data.get("pois", [])[:5]
        return [
            PoiCandidate(
                id=poi.get("id", ""),
                name=poi.get("name", ""),
                address=poi.get("address") or "",
                distance_m=int(poi["distance"]) if str(poi.get("distance", "")).isdigit() else None,
                rating=str(poi.get("business", {}).get("rating", "")) or None,
                cost=str(poi.get("business", {}).get("cost", "")) or None,
                tags=[tag for tag in str(poi.get("business", {}).get("tag", "")).split(",") if tag],
            )
            for poi in pois
        ]
