import { FormEvent, useMemo, useState } from "react";

type Json = Record<string, unknown>;

const API_BASE = "http://localhost:4000";

async function callApi(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

export function App() {
  const [ambulanceId, setAmbulanceId] = useState("AMB-101");
  const [ambulanceType, setAmbulanceType] = useState("BLS");
  const [ambulanceStatus, setAmbulanceStatus] = useState("AVAILABLE");
  const [ambulanceLat, setAmbulanceLat] = useState(12.9716);
  const [ambulanceLon, setAmbulanceLon] = useState(77.5946);
  const [reliability, setReliability] = useState(0.85);

  const [incidentType, setIncidentType] = useState("TRAUMA");
  const [pickupLat, setPickupLat] = useState(12.975);
  const [pickupLon, setPickupLon] = useState(77.6);
  const [conscious, setConscious] = useState(true);
  const [breathingNormally, setBreathingNormally] = useState(true);
  const [severeBleeding, setSevereBleeding] = useState(false);

  const [latestIncidentId, setLatestIncidentId] = useState<string | null>(null);
  const [responseAmbulanceId, setResponseAmbulanceId] = useState("AMB-101");
  const [responseAction, setResponseAction] = useState("ACCEPT");
  const [insurance, setInsurance] = useState("STAR");
  const [selectedHospitalId, setSelectedHospitalId] = useState("HSP-001");
  const [hospitalReason, setHospitalReason] = useState("Insurance/doctor preference");
  const [output, setOutput] = useState<Json | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canCheckCandidates = useMemo(() => Boolean(latestIncidentId), [latestIncidentId]);
  const warning = (output?.warning as { code?: string; message?: string; missingCapabilities?: string[] } | undefined) ?? null;
  const costQuote =
    (output?.costQuote as
      | {
          total?: number;
          baseFare?: number;
          distanceCharge?: number;
          severitySurcharge?: number;
          overrideSurcharge?: number;
        }
      | undefined) ?? null;

  async function runAction(action: () => Promise<Json>) {
    setLoading(true);
    setError(null);
    try {
      const data = await action();
      setOutput(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  function submitHeartbeat(event: FormEvent) {
    event.preventDefault();
    runAction(() =>
      callApi(`/api/ambulances/${encodeURIComponent(ambulanceId)}/heartbeat`, {
        method: "POST",
        body: JSON.stringify({
          type: ambulanceType,
          status: ambulanceStatus,
          lat: Number(ambulanceLat),
          lon: Number(ambulanceLon),
          reliabilityScore: Number(reliability)
        })
      })
    );
  }

  function submitSos(event: FormEvent) {
    event.preventDefault();
    runAction(async () => {
      const data = (await callApi("/api/incidents/sos", {
        method: "POST",
        body: JSON.stringify({
          incidentType,
          pickupLat: Number(pickupLat),
          pickupLon: Number(pickupLon),
          conscious,
          breathingNormally,
          severeBleeding
        })
      })) as Json;

      const incident = data.incident as { id?: string } | undefined;
      if (incident?.id) {
        setLatestIncidentId(incident.id);
      }

      return data;
    });
  }

  function respondToDispatch(event: FormEvent) {
    event.preventDefault();
    if (!latestIncidentId) {
      return;
    }

    runAction(() =>
      callApi(`/api/dispatch/${latestIncidentId}/respond`, {
        method: "POST",
        body: JSON.stringify({
          ambulanceId: responseAmbulanceId,
          action: responseAction
        })
      })
    );
  }

  function selectHospital(event: FormEvent) {
    event.preventDefault();
    if (!latestIncidentId) {
      return;
    }

    runAction(() =>
      callApi(`/api/incidents/${latestIncidentId}/hospital/select`, {
        method: "POST",
        body: JSON.stringify({
          hospitalId: selectedHospitalId,
          reason: hospitalReason
        })
      })
    );
  }

  return (
    <main className="page">
      <h1>Ambulance MVP Console</h1>
      <p className="muted">Backend: {API_BASE}</p>

      <section className="grid">
        <form className="card" onSubmit={submitHeartbeat}>
          <h2>Ambulance Heartbeat</h2>
          <label>
            Ambulance ID
            <input value={ambulanceId} onChange={(e) => setAmbulanceId(e.target.value)} />
          </label>
          <label>
            Type
            <select value={ambulanceType} onChange={(e) => setAmbulanceType(e.target.value)}>
              <option>BLS</option>
              <option>ALS</option>
              <option>ICU</option>
            </select>
          </label>
          <label>
            Status
            <select value={ambulanceStatus} onChange={(e) => setAmbulanceStatus(e.target.value)}>
              <option>AVAILABLE</option>
              <option>ENROUTE</option>
              <option>AT_SCENE</option>
              <option>TRANSPORTING</option>
              <option>OFFLINE</option>
            </select>
          </label>
          <label>
            Latitude
            <input type="number" step="0.0001" value={ambulanceLat} onChange={(e) => setAmbulanceLat(Number(e.target.value))} />
          </label>
          <label>
            Longitude
            <input type="number" step="0.0001" value={ambulanceLon} onChange={(e) => setAmbulanceLon(Number(e.target.value))} />
          </label>
          <label>
            Reliability (0-1)
            <input type="number" step="0.01" min={0} max={1} value={reliability} onChange={(e) => setReliability(Number(e.target.value))} />
          </label>
          <button disabled={loading} type="submit">Send Heartbeat</button>
        </form>

        <form className="card" onSubmit={submitSos}>
          <h2>Patient SOS</h2>
          <label>
            Incident Type
            <select value={incidentType} onChange={(e) => setIncidentType(e.target.value)}>
              <option>TRAUMA</option>
              <option>CHEST_PAIN</option>
              <option>BREATHING</option>
              <option>UNCONSCIOUS</option>
              <option>PREGNANCY</option>
              <option>OTHER</option>
            </select>
          </label>
          <label>
            Pickup Latitude
            <input type="number" step="0.0001" value={pickupLat} onChange={(e) => setPickupLat(Number(e.target.value))} />
          </label>
          <label>
            Pickup Longitude
            <input type="number" step="0.0001" value={pickupLon} onChange={(e) => setPickupLon(Number(e.target.value))} />
          </label>
          <label className="inline">
            <input type="checkbox" checked={conscious} onChange={(e) => setConscious(e.target.checked)} /> Conscious
          </label>
          <label className="inline">
            <input type="checkbox" checked={breathingNormally} onChange={(e) => setBreathingNormally(e.target.checked)} /> Breathing Normally
          </label>
          <label className="inline">
            <input type="checkbox" checked={severeBleeding} onChange={(e) => setSevereBleeding(e.target.checked)} /> Severe Bleeding
          </label>
          <button disabled={loading} type="submit">Trigger SOS</button>
        </form>
      </section>

      <section className="card actions">
        <h2>Dispatch Tools</h2>
        <p className="muted">Latest Incident: {latestIncidentId ?? "none"}</p>
        <div className="row">
          <button
            disabled={loading || !canCheckCandidates}
            onClick={() => runAction(() => callApi(`/api/dispatch/candidates/${latestIncidentId}`))}
          >
            Get Candidates
          </button>
          <button disabled={loading} onClick={() => runAction(() => callApi("/api/debug/state"))}>
            Get Full State
          </button>
          <button
            disabled={loading || !canCheckCandidates}
            onClick={() => runAction(() => callApi(`/api/dispatch/state/${latestIncidentId}`))}
          >
            Get Dispatch State
          </button>
          <button
            disabled={loading || !canCheckCandidates}
            onClick={() =>
              runAction(() =>
                callApi(
                  `/api/incidents/${latestIncidentId}/hospitals/recommendations?insurance=${encodeURIComponent(insurance)}`
                )
              )
            }
          >
            Get Top 3 Hospitals
          </button>
          <button disabled={loading} onClick={() => runAction(() => callApi("/api/hospitals"))}>
            List Hospitals
          </button>
        </div>
        <form className="responseForm" onSubmit={respondToDispatch}>
          <label>
            Ambulance ID (for offer response)
            <input
              value={responseAmbulanceId}
              onChange={(e) => setResponseAmbulanceId(e.target.value)}
            />
          </label>
          <label>
            Action
            <select value={responseAction} onChange={(e) => setResponseAction(e.target.value)}>
              <option>ACCEPT</option>
              <option>DECLINE</option>
            </select>
          </label>
          <button disabled={loading || !canCheckCandidates} type="submit">
            Submit Offer Response
          </button>
        </form>
        <form className="responseForm" onSubmit={selectHospital}>
          <label>
            Insurance (for recommendations)
            <input value={insurance} onChange={(e) => setInsurance(e.target.value)} />
          </label>
          <label>
            Hospital ID (manual override allowed)
            <input value={selectedHospitalId} onChange={(e) => setSelectedHospitalId(e.target.value)} />
          </label>
          <label>
            Override Reason
            <input value={hospitalReason} onChange={(e) => setHospitalReason(e.target.value)} />
          </label>
          <button disabled={loading || !canCheckCandidates} type="submit">
            Select/Override Hospital
          </button>
        </form>
      </section>

      {error ? <pre className="error">{error}</pre> : null}
      {warning ? (
        <div className="warningBanner">
          <strong>{warning.code ?? "WARNING"}</strong>: {warning.message}
          {warning.missingCapabilities?.length ? (
            <span> Missing: {warning.missingCapabilities.join(", ")}</span>
          ) : null}
        </div>
      ) : null}
      {costQuote ? (
        <div className="costBanner">
          Estimated Cost: Rs. {costQuote.total ?? 0} (Base: Rs. {costQuote.baseFare ?? 0}, Distance: Rs. {costQuote.distanceCharge ?? 0}, Severity: Rs. {costQuote.severitySurcharge ?? 0}, Override: Rs. {costQuote.overrideSurcharge ?? 0})
        </div>
      ) : null}
      <pre className="output">{output ? JSON.stringify(output, null, 2) : "No output yet."}</pre>
    </main>
  );
}
