import { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix default marker icons (Leaflet webpack issue)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const agentIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

const customerIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

function FitBounds({ agentPos, customerPos }) {
  const map = useMap();
  useEffect(() => {
    if (agentPos && customerPos) {
      const bounds = L.latLngBounds([agentPos, customerPos]);
      map.fitBounds(bounds, { padding: [50, 50] });
    } else if (agentPos) {
      map.setView(agentPos, 15);
    } else if (customerPos) {
      map.setView(customerPos, 15);
    }
  }, [map, agentPos, customerPos]);
  return null;
}

const LiveTrackingMap = ({ agentLocation, customerLocation, agentName, etaMinutes }) => {
  const agentPos = agentLocation ? [agentLocation.lat, agentLocation.lng] : null;
  const customerPos = customerLocation ? [customerLocation.lat, customerLocation.lng] : null;
  const center = agentPos || customerPos || [19.076, 72.8777]; // Mumbai default

  return (
    <div className="relative" data-testid="live-tracking-map">
      <MapContainer center={center} zoom={14} style={{ height: '300px', width: '100%' }} scrollWheelZoom={false}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {agentPos && (
          <Marker position={agentPos} icon={agentIcon}>
            <Popup>{agentName || 'Delivery Agent'}</Popup>
          </Marker>
        )}
        {customerPos && (
          <Marker position={customerPos} icon={customerIcon}>
            <Popup>Delivery Location</Popup>
          </Marker>
        )}
        <FitBounds agentPos={agentPos} customerPos={customerPos} />
      </MapContainer>
      {etaMinutes && (
        <div className="absolute top-3 right-3 z-[1000] bg-[#4A3B32] text-white px-4 py-2 shadow-lg" data-testid="eta-badge">
          <p className="text-xs tracking-[0.1em] uppercase font-semibold">ETA</p>
          <p className="font-serif text-lg">{etaMinutes} min</p>
        </div>
      )}
    </div>
  );
};

export default LiveTrackingMap;
