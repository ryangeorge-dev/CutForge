import { useState } from 'react';
import type { Settings } from './types';

export function AnalysisSettings({ initial, busy, analyzed, run }: { initial: Settings; busy: boolean; analyzed: boolean; run: (settings: Settings) => void }) {
  const [settings, setSettings] = useState(initial);
  const changed = JSON.stringify(settings) !== JSON.stringify(initial);
  return <section className="panel">
    <h2>Silence detection</h2>
    <form onSubmit={e => { e.preventDefault(); run(settings); }}>
      <div className="grid sm:grid-cols-3 gap-3">
        <label>Threshold (dBFS)<input type="number" required min="-90" max="-5" step="1" value={settings.threshold_db} onChange={e => setSettings({ ...settings, threshold_db: e.target.valueAsNumber })}/></label>
        <label>Minimum silence (s)<input type="number" required min="0.1" max="30" step="0.05" value={settings.min_silence} onChange={e => setSettings({ ...settings, min_silence: e.target.valueAsNumber })}/></label>
        <label>Speech padding (s)<input type="number" required min="0" max="2" step="0.01" value={settings.padding} onChange={e => setSettings({ ...settings, padding: e.target.valueAsNumber })}/></label>
      </div>
      <p className="muted my-3">Higher thresholds classify more sound as silence. Padding keeps room around speech. Start conservatively and listen before accepting.</p>
      <button className="primary" disabled={busy} type="submit">{analyzed ? 'Rerun detection' : 'Detect silences'}</button>
      {changed && <p className="text-sm mt-2">Settings changed. Rerun to update suggestions; existing decisions will remain.</p>}
    </form>
  </section>;
}
