'use client';

import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMap, useMapEvents } from 'react-leaflet';

function LocationPinDropper({ onPinDrop }) {
  useMapEvents({
    click(e) {
      onPinDrop(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function MapController({ center, zoom = 16 }) {
  const map = useMap();
  useEffect(() => {
    if (map && center && center[0] && center[1]) {
      map.flyTo(center, zoom, { animate: true, duration: 1.5 });
    }
  }, [center, zoom, map]);
  return null;
}

const DIVISIONS = [
  { code: '10', name: 'ঢাকা (Dhaka)' },
  { code: '20', name: 'চট্টগ্রাম (Chattogram)' },
  { code: '50', name: 'রাজশাহী (Rajshahi)' },
  { code: '60', name: 'সিলেট (Sylhet)' },
  { code: '40', name: 'খুলনা (Khulna)' },
  { code: '30', name: 'বরিশাল (Barishal)' },
  { code: '55', name: 'রংপুর (Rangpur)' },
  { code: '45', name: 'ময়মনসিংহ (Mymensingh)' },
];

export default function DigitalMouzaMap({ activePlot, activeMouzaCode, targetRecord, onPinDrop }) {
  const [districts, setDistricts] = useState([]);
  const [upazilas, setUpazilas] = useState([]);
  const [mouzas, setMouzas] = useState([]);

  const [selectedDiv, setSelectedDiv] = useState('20'); // Default Chattogram Division (Brahmanbaria)
  const [selectedDist, setSelectedDist] = useState('2012'); // Brahmanbaria
  const [selectedUpazila, setSelectedUpazila] = useState('201294'); // Sarail
  const [selectedMouzaCode, setSelectedMouzaCode] = useState('201294082069'); // Bhatbaria

  const [geoData, setGeoData] = useState(null);
  const [pinnedLocation, setPinnedLocation] = useState(null);
  const [mapCenter, setMapCenter] = useState([24.1165, 91.1245]);
  const [mapZoom, setMapZoom] = useState(16);
  const [loading, setLoading] = useState(true);

  // Selected Plot Action Dock state
  const [activePlotMeta, setActivePlotMeta] = useState(null);
  const [customQuestion, setCustomQuestion] = useState('');

  // Sync location from targetRecord or activeMouzaCode
  useEffect(() => {
    if (targetRecord) {
      const d = targetRecord.details || targetRecord || {};
      const dist = String(d.DISTRICT_NAME || "").toLowerCase();
      const upa = String(d.UPAZILA_NAME || "").toLowerCase();
      const mouza = String(d.MOUZA_NAME || "").toLowerCase();

      // 1. Brahmanbaria / Sarail / Bhatbaria
      if (dist.includes("ব্রাহ্মণবাড়িয়া") || dist.includes("brahmanbaria") || upa.includes("সরাইল") || upa.includes("sarail") || mouza.includes("ভাট")) {
        // Prop-driven selection must sync the interactive map controls.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSelectedDiv('20');
        setSelectedDist('2012');
        setSelectedUpazila('201294');
        setSelectedMouzaCode('201294082069');
        return;
      }

      // 2. Habiganj / Bahubal
      if (dist.includes("হবিগঞ্জ") || dist.includes("habiganj") || upa.includes("বাহুবল") || upa.includes("bahubal")) {
        setSelectedDiv('60');
        setSelectedDist('6036');
        setSelectedUpazila('603605');
        setSelectedMouzaCode('603605413003');
        return;
      }
    }

    if (activeMouzaCode) {
      let codeStr = String(activeMouzaCode);
      if (codeStr.startsWith('601215') || codeStr === '603605413003' || codeStr === '601215413003') {
        codeStr = '201294082069';
      }

      if (codeStr.length >= 6) {
        setSelectedDiv(codeStr.substring(0, 2));
        setSelectedDist(codeStr.substring(0, 4));
        setSelectedUpazila(codeStr.substring(0, 6));
        setSelectedMouzaCode(codeStr);
      }
    }
  }, [targetRecord, activeMouzaCode]);

  // Auto zoom to activePlot if present in geoData
  useEffect(() => {
    if (activePlot && geoData && geoData.features) {
      const match = geoData.features.find(
        (f) => String(f.properties?.plot_no) === String(activePlot)
      );
      if (match && match.properties?.center_lat && match.properties?.center_lon) {
        // The map camera tracks an externally selected record.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setMapCenter([match.properties.center_lat, match.properties.center_lon]);
        setMapZoom(18);
      }
    }
  }, [activePlot, geoData]);

  // 1. Fetch Districts when Division changes
  useEffect(() => {
    if (!selectedDiv) return;
    fetch(`/api/map-admin?level=forDist&division_code=${selectedDiv}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.items && data.items.length > 0) {
          setDistricts(data.items);
          setSelectedDist((prev) => {
            const match = data.items.find((item) => String(item.code) === String(prev));
            return match ? prev : data.items[0].code;
          });
        } else {
          setDistricts([]);
          setSelectedDist('');
        }
      })
      .catch((err) => console.error('Error fetching districts:', err));
  }, [selectedDiv]);

  // 2. Fetch Upazilas/Thanas when District changes
  useEffect(() => {
    if (!selectedDist || !selectedDiv) return;
    fetch(`/api/map-admin?level=forThana&division_code=${selectedDiv}&district_code=${selectedDist}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.items && data.items.length > 0) {
          setUpazilas(data.items);
          setSelectedUpazila((prev) => {
            const match = data.items.find((item) => String(item.code) === String(prev));
            return match ? prev : data.items[0].code;
          });
        } else {
          setUpazilas([]);
          setSelectedUpazila('');
        }
      })
      .catch((err) => console.error('Error fetching upazilas:', err));
  }, [selectedDiv, selectedDist]);

  // 3. Fetch Mouzas when Upazila changes
  useEffect(() => {
    if (!selectedUpazila || !selectedDist || !selectedDiv) return;
    fetch(`/api/map-admin?level=forMauza&division_code=${selectedDiv}&district_code=${selectedDist}&thana_code=${selectedUpazila}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.items && data.items.length > 0) {
          setMouzas(data.items);
          setSelectedMouzaCode((prev) => {
            const match = data.items.find((item) => String(item.code) === String(prev));
            return match ? prev : data.items[0].code;
          });
        } else {
          setMouzas([]);
          setSelectedMouzaCode('');
        }
      })
      .catch((err) => console.error('Error fetching mouzas:', err));
  }, [selectedDiv, selectedDist, selectedUpazila]);

  // 4. Fetch Mouza Plot Polygons when selectedMouzaCode changes
  useEffect(() => {
    if (!selectedMouzaCode) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    fetch(`/api/plot-geometry?mauza_code=${selectedMouzaCode}`)
      .then((res) => res.json())
      .then((data) => {
        setGeoData(data);
        setLoading(false);

        // Auto-center map to the average bounding box of features
        if (data.features && data.features.length > 0) {
          let sumLat = 0, sumLon = 0, count = 0;
          data.features.forEach((f) => {
            if (f.properties && f.properties.center_lat && f.properties.center_lon) {
              sumLat += f.properties.center_lat;
              sumLon += f.properties.center_lon;
              count++;
            }
          });
          if (count > 0) {
            setMapCenter([sumLat / count, sumLon / count]);
          }
        }
      })
      .catch((err) => {
        console.error('Error fetching plot geometry:', err);
        setLoading(false);
      });
  }, [selectedMouzaCode]);

  const handlePin = (lat, lng, extraProps = {}) => {
    setPinnedLocation({ lat, lng });

    const curDistObj = districts.find((d) => String(d.code) === String(selectedDist));
    const curUpazilaObj = upazilas.find((u) => String(u.code) === String(selectedUpazila));
    const curMouzaObj = mouzas.find((m) => String(m.code) === String(selectedMouzaCode));

    const rawPlot = extraProps.plot_no || extraProps.label;
    const plotNo = (rawPlot && rawPlot !== 'N/A' && rawPlot !== 'undefined') ? String(rawPlot) : null;
    const rawJl = extraProps.jl_no;
    const jlNo = (rawJl && rawJl !== 'N/A') ? String(rawJl) : null;

    const meta = {
      lat,
      lng,
      mauza_code: extraProps.mauza_code || selectedMouzaCode,
      plot_no: plotNo,
      jl_no: jlNo,
      district_name: curDistObj?.name_bn || curDistObj?.name_en || '',
      upazila_name: curUpazilaObj?.name_bn || curUpazilaObj?.name_en || '',
      mouza_name: curMouzaObj?.name_bn || curMouzaObj?.name_en || '',
    };

    // Open plot selection panel
    setActivePlotMeta(meta);
  };

  const handleAskQuestion = (questionText) => {
    if (!activePlotMeta || !onPinDrop) return;
    onPinDrop(activePlotMeta.lat, activePlotMeta.lng, {
      ...activePlotMeta,
      custom_prompt: questionText,
    });
    setActivePlotMeta(null);
    setCustomQuestion('');
  };

  const styleFeature = (feature) => {
    const isTarget = activePlot && String(feature.properties.plot_no) === String(activePlot);
    return {
      fillColor: isTarget ? '#10b981' : '#3b82f6',
      weight: isTarget ? 3 : 1.5,
      opacity: 1,
      color: isTarget ? '#047857' : '#1d4ed8',
      fillOpacity: isTarget ? 0.75 : 0.45,
    };
  };

  const onEachFeature = (feature, layer) => {
    const props = feature.properties;
    layer.bindPopup(`
      <div style="font-size: 13px; font-family: sans-serif;">
        <strong style="color: #10b981; font-size: 14px;">🗺️ দাগ নম্বর: ${props.plot_no || props.label || 'N/A'}</strong><br/>
        <b>মৌজা কোড:</b> ${props.mauza_code || selectedMouzaCode}<br/>
        <b>জেএল নম্বর:</b> ${props.jl_no || 'N/A'}<br/>
        ${props.major_class ? `<b>ভূমি শ্রেণী:</b> ${props.major_class} (${props.sub_class || ''})<br/>` : ''}
        <div style="margin-top: 6px; font-size: 11px; color: #34d399; font-weight: bold;">
          📍 পিন ক্লিক করে সরাসরি প্রশ্ন করুন
        </div>
      </div>
    `);
    layer.on('click', (e) => {
      if (e.latlng) {
        handlePin(e.latlng.lat, e.latlng.lng, props);
      }
    });
  };

  return (
    <div className="flex flex-col w-full h-full min-h-[480px] rounded-2xl overflow-hidden border border-slate-800 shadow-2xl bg-slate-950">
      {/* Top Location Selection Toolbar */}
      <div className="bg-slate-900/95 backdrop-blur-xl px-4 py-3 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs z-[1001] shrink-0">
        <div className="flex items-center space-x-2 font-semibold text-emerald-400">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>ডিজিটাল মৌজা ম্যাপ (map.land.gov.bd)</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Division Select */}
          <select
            value={selectedDiv}
            onChange={(e) => setSelectedDiv(e.target.value)}
            className="bg-slate-950 text-slate-200 border border-slate-700/80 rounded-xl px-3 py-1.5 focus:outline-none focus:border-emerald-500 text-xs font-medium"
          >
            {DIVISIONS.map((div) => (
              <option key={div.code} value={div.code}>
                {div.name}
              </option>
            ))}
          </select>

          {/* District Select */}
          <select
            value={selectedDist}
            onChange={(e) => setSelectedDist(e.target.value)}
            className="bg-slate-950 text-slate-200 border border-slate-700/80 rounded-xl px-3 py-1.5 focus:outline-none focus:border-emerald-500 text-xs font-medium"
          >
            <option value="">-- জেলা --</option>
            {districts.map((d) => (
              <option key={d.code} value={d.code}>
                {d.name_bn || d.name_en}
              </option>
            ))}
          </select>

          {/* Upazila Select */}
          <select
            value={selectedUpazila}
            onChange={(e) => setSelectedUpazila(e.target.value)}
            className="bg-slate-950 text-slate-200 border border-slate-700/80 rounded-xl px-3 py-1.5 focus:outline-none focus:border-emerald-500 text-xs font-medium"
          >
            <option value="">-- উপজেলা --</option>
            {upazilas.map((u) => (
              <option key={u.code} value={u.code}>
                {u.name_bn || u.name_en}
              </option>
            ))}
          </select>

          {/* Mouza Select */}
          <select
            value={selectedMouzaCode}
            onChange={(e) => setSelectedMouzaCode(e.target.value)}
            className="bg-slate-950 text-slate-200 border border-slate-700/80 rounded-xl px-3 py-1.5 focus:outline-none focus:border-emerald-500 max-w-[180px] truncate text-xs font-medium"
          >
            <option value="">-- মৌজা --</option>
            {mouzas.map((m) => (
              <option key={m.code} value={m.code}>
                {m.name_bn || m.name_en}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Map View Container */}
      <div className="relative flex-1 w-full h-full overflow-hidden">
        {loading && (
          <div className="absolute inset-0 z-[1002] bg-slate-950/80 backdrop-blur-md flex items-center justify-center text-slate-200 text-xs font-medium">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500 mr-3"></div>
            <span>মৌজার প্লট ও জ্যামিতিক মানচিত্র লোড হচ্ছে...</span>
          </div>
        )}

        <MapContainer
          center={mapCenter}
          zoom={16}
          scrollWheelZoom={true}
          className="w-full h-full z-[999]"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MapController center={mapCenter} zoom={mapZoom} />

          {geoData && (
            <GeoJSON
              key={selectedMouzaCode + '-' + (geoData.features ? geoData.features.length : 0)}
              data={geoData}
              style={styleFeature}
              onEachFeature={onEachFeature}
            />
          )}

          <LocationPinDropper onPinDrop={handlePin} />

          {pinnedLocation && (
            <Marker position={[pinnedLocation.lat, pinnedLocation.lng]}>
              <Popup>
                📍 পিন লোকেশন: {pinnedLocation.lat.toFixed(5)}, {pinnedLocation.lng.toFixed(5)}
              </Popup>
            </Marker>
          )}
        </MapContainer>

        {/* Interactive Specific Question Dock for Selected Plot/Pin */}
        {activePlotMeta && (
          <div className="absolute bottom-4 left-4 right-4 z-[1003] bg-slate-900/95 border border-emerald-500/50 backdrop-blur-xl p-4 rounded-2xl shadow-2xl animate-fade-in text-slate-100 flex flex-col space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center space-x-2">
                <span className="bg-emerald-500/20 text-emerald-300 text-xs px-2.5 py-1 rounded-lg font-bold border border-emerald-500/30">
                  {activePlotMeta.plot_no ? `📍 নির্বাচিত দাগ: #${activePlotMeta.plot_no}` : `📍 চিহ্নিত অবস্থান (${activePlotMeta.lat.toFixed(4)}, ${activePlotMeta.lng.toFixed(4)})`}
                </span>
                <span className="text-xs text-slate-300">
                  {activePlotMeta.mouza_name ? `${activePlotMeta.mouza_name} মৌজা` : ''} 
                  {activePlotMeta.upazila_name ? ` (${activePlotMeta.upazila_name}, ${activePlotMeta.district_name})` : ''}
                </span>
              </div>
              <button
                onClick={() => setActivePlotMeta(null)}
                className="text-slate-400 hover:text-slate-100 text-xs px-2 py-0.5 rounded-lg bg-slate-800 hover:bg-slate-700"
              >
                ✕ বন্ধ করুন
              </button>
            </div>

            {/* Quick Specific Question Actions */}
            <div className="flex flex-wrap gap-2 text-xs">
              {activePlotMeta.plot_no ? (
                <>
                  <button
                    onClick={() => handleAskQuestion(`দাগ নম্বর ${activePlotMeta.plot_no} এর মালিক কে?`)}
                    className="bg-slate-950 hover:bg-emerald-950/80 border border-slate-800 hover:border-emerald-500/40 text-slate-200 hover:text-emerald-300 px-3 py-1.5 rounded-xl transition-all font-medium active:scale-95"
                  >
                    👤 এই দাগের মালিক কে?
                  </button>
                  <button
                    onClick={() => handleAskQuestion(`দাগ নম্বর ${activePlotMeta.plot_no} এর বিএস (BS) খতিয়ান ও বর্তমান বিবরণ দিন`)}
                    className="bg-emerald-950/60 hover:bg-emerald-900/80 border border-emerald-500/40 text-emerald-300 px-3 py-1.5 rounded-xl transition-all font-medium active:scale-95"
                  >
                    📜 বিএস (BS) বর্তমান খতিয়ান
                  </button>
                  <button
                    onClick={() => handleAskQuestion(`দাগ নম্বর ${activePlotMeta.plot_no} এর আরএস (RS) রেকর্ড ও খতিয়ান দিন`)}
                    className="bg-slate-950 hover:bg-emerald-950/80 border border-slate-800 hover:border-emerald-500/40 text-slate-200 hover:text-emerald-300 px-3 py-1.5 rounded-xl transition-all font-medium active:scale-95"
                  >
                    🏛️ আরএস (RS) রেকর্ড
                  </button>
                  <button
                    onClick={() => handleAskQuestion(`দাগ নম্বর ${activePlotMeta.plot_no} এর সিএস (CS) মূল রেকর্ড দিন`)}
                    className="bg-slate-950 hover:bg-emerald-950/80 border border-slate-800 hover:border-emerald-500/40 text-slate-200 hover:text-emerald-300 px-3 py-1.5 rounded-xl transition-all font-medium active:scale-95"
                  >
                    📋 সিএস (CS) রেকর্ড
                  </button>
                  <button
                    onClick={() => handleAskQuestion(`দাগ নম্বর ${activePlotMeta.plot_no} এর জমির শ্রেণী ও বিবরণী দিন`)}
                    className="bg-slate-950 hover:bg-emerald-950/80 border border-slate-800 hover:border-emerald-500/40 text-slate-200 hover:text-emerald-300 px-3 py-1.5 rounded-xl transition-all font-medium active:scale-95"
                  >
                    📐 জমির শ্রেণী ও বিবরণী
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => handleAskQuestion(`${activePlotMeta.mouza_name || 'এই'} মৌজার সামগ্রিক খতিয়ান ও ভূমির তথ্য দিন`)}
                    className="bg-slate-950 hover:bg-emerald-950/80 border border-slate-800 hover:border-emerald-500/40 text-slate-200 hover:text-emerald-300 px-3 py-1.5 rounded-xl transition-all font-medium"
                  >
                    📜 মৌজার খতিয়ান ও রেকর্ডসমূহ
                  </button>
                  <button
                    onClick={() => handleAskQuestion(`এই অবস্থানের (${activePlotMeta.lat.toFixed(4)}, ${activePlotMeta.lng.toFixed(4)}) ভূমি শ্রেণী ও আইনগত তথ্য কী?`)}
                    className="bg-slate-950 hover:bg-emerald-950/80 border border-slate-800 hover:border-emerald-500/40 text-slate-200 hover:text-emerald-300 px-3 py-1.5 rounded-xl transition-all font-medium"
                  >
                    🌾 ভূমি শ্রেণী ও অবস্থান সংক্রান্ত তথ্য
                  </button>
                </>
              )}
            </div>

            {/* Custom Specific Question Input */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (customQuestion.trim()) {
                  handleAskQuestion(customQuestion);
                }
              }}
              className="flex items-center gap-2 pt-1"
            >
              <input
                type="text"
                value={customQuestion}
                onChange={(e) => setCustomQuestion(e.target.value)}
                placeholder={activePlotMeta.plot_no ? `দাগ নম্বর ${activePlotMeta.plot_no} সম্পর্কে নির্দিষ্ট প্রশ্ন লিখুন...` : `এই এলাকা/মৌজা সম্পর্কে আপনার প্রশ্ন লিখুন...`}
                className="flex-1 bg-slate-950 border border-slate-700 focus:border-emerald-500 text-slate-100 text-xs rounded-xl px-3.5 py-2.5 focus:outline-none"
              />
              <button
                type="submit"
                disabled={!customQuestion.trim()}
                className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 text-white font-semibold px-4 py-2.5 rounded-xl text-xs transition-all shadow-md shrink-0 active:scale-95"
              >
                💬 এআই চ্যাটে জানুন ➔
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

