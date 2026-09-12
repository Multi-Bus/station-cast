"""Real-time next-arrival info from Seoul TOPIS (issue #48)."""

from fastapi import APIRouter, Depends

from stationcast.api import deps
from stationcast.api.data import CorridorData, get_corridor_data
from stationcast.api.schemas import ArrivalInfo, ArrivalsResponse
from stationcast.ingest.realtime_arrival import ArrivalInfoUnavailable, fetch_arrivals

router = APIRouter()


def _to_arrival_info(item: dict[str, str | None]) -> ArrivalInfo:
    return ArrivalInfo(
        route_name=item.get("busRouteAbrv") or "",
        route_id=item.get("busRouteId") or "",
        direction=item.get("adirection") or "",
        arrival_message_1=item.get("arrmsg1") or "",
        arrival_message_2=item.get("arrmsg2") or "",
        congestion_1=item.get("congestion1"),
        congestion_2=item.get("congestion2"),
    )


@router.get("/stops/{stop_id}/arrivals", response_model=ArrivalsResponse)
def get_arrivals(stop_id: int, data: CorridorData = Depends(get_corridor_data)) -> ArrivalsResponse:
    """
    Real-time next-arrival info for every route serving one stop (issue #48).
    Backed by Seoul TOPIS (ws.bus.go.kr) -- a live display feature.
    """
    name = deps.stop_name(data, stop_id)
    ars_number = deps.stop_ars_number(data, stop_id)

    try:
        items = fetch_arrivals(ars_number)
    except ArrivalInfoUnavailable:
        return ArrivalsResponse(
            stop_id=stop_id,
            name=name,
            available=False,
            message="일시적으로 도착정보를 가져올 수 없습니다.",
            arrivals=[],
        )

    return ArrivalsResponse(
        stop_id=stop_id,
        name=name,
        available=True,
        message=None,
        arrivals=[_to_arrival_info(item) for item in items],
    )
