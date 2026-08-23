export interface ApiStop {
  stop_id: number;
  name: string;
  ars_number: string;
  lat: number;
  lon: number;
  stop_type: string;
}

export interface StopsResponse {
  stops: ApiStop[];
}

export interface CongestionResponse {
  stop_id: number;
  name: string;
  hour: number;
  estimated_wait: number;
  grade: string;
}

export interface ApiTimelinePoint {
  hour: number;
  estimated_wait: number;
  grade: string;
}

export interface TimelineResponse {
  stop_id: number;
  name: string;
  timeline: ApiTimelinePoint[];
}

export interface StopContextResponse {
  stop_id: number;
  name: string;
  date: number;
  day_type: string;
  temperature: number;
  precipitation: number;
  humidity: number;
  snowfall: number;
  wind_speed: number;
  congestion_note: string;
  precipitation_type?: string;
  is_forecast?: boolean;
}

export interface ApiArrivalInfo {
  route_name: string;
  route_id: string;
  direction: string;
  arrival_message_1: string;
  arrival_message_2: string;
  congestion_1: string | null;
  congestion_2: string | null;
}

export interface ArrivalsResponse {
  stop_id: number;
  name: string;
  available: boolean;
  message: string | null;
  arrivals: ApiArrivalInfo[];
}
