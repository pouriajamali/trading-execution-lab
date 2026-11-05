import { createRoot } from 'react-dom/client';
import { useState, type FormEvent } from 'react';
import { call, commandFrom, HttpError, requestFor, type Command, type Decision, type Snapshot } from './protocol';
import './styles.css';

function App() {
  const [token, setToken] = useState('');
  const [code, setCode] = useState('');
  const [state, setState] = useState<Snapshot>();
  const [fresh, setFresh] = useState(false);
  const [unresolved, setUnresolved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [id, setId] = useState('sample-001');
  const [quantity, setQuantity] = useState('2');
  const [last, setLast] = useState<Command>();
  const [decision, setDecision] = useState<Decision>();

  function signOut() {
    setToken('');
    setCode('');
    setState(undefined);
    setFresh(false);
    // Preserve the in-memory exact retry across token expiry / reauthentication.
    // It is not persisted across page reloads or browser closure.
    setError('');
  }

  function handleError(problem: unknown) {
    if (problem instanceof HttpError && (problem.status === 401 || problem.status === 403)) signOut();
    setError(problem instanceof Error ? problem.message : 'An unexpected error occurred.');
  }

  async function action(run: () => Promise<void>) {
    setError('');
    setBusy(true);
    try { await run(); } catch (problem) { handleError(problem); } finally { setBusy(false); }
  }

  function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    void action(async () => {
      const session = await call('/panel/api/session', undefined, {
        method: 'POST', body: JSON.stringify({ code })
      });
      setCode('');
      const snapshot = await call('/panel/api/state', session.token);
      setToken(session.token);
      setState(snapshot);
      setFresh(true);
    });
  }

  async function refresh(session: string) {
    setFresh(false);
    setState(await call('/panel/api/state', session));
    setFresh(true);
  }

  async function submit(command: Command) {
    setLast(command);
    setUnresolved(true);
    setFresh(false);
    setDecision(undefined);
    const result = await call('/reservations', token, requestFor(command));
    setDecision(result);
    setUnresolved(false);
    // A denied command can still consume a cursor, and a replay is historical.
    // Always read current state separately from the receipt.
    await refresh(token);
  }

  function reserve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Form/Enter submission must obey the same guard as the visible button.
    if (busy || !fresh || unresolved || !state?.reconciled || state.stopped) return;
    void action(() => submit(commandFrom(crypto.randomUUID(), id, quantity)));
  }

  const ready = state?.reconciled && !state.stopped;
  return <main>
    <header className="brand"><span className="logo" aria-hidden="true">EL</span><span>Execution Lab</span><span className="env">SYNTHETIC · LOOPBACK</span></header>
    <section className="intro">
      <p className="eyebrow">CONTROL PLANE / OPERATOR CONSOLE</p>
      <h1>Execution monitor</h1>
      <p>Review order exposure and test reservation decisions in a single-instrument sandbox.</p>
    </section>
    {error && <p className="notice" role="alert">{error}</p>}
    {!token ? <section className="surface login" aria-labelledby="login-title">
      <h2 id="login-title">Operator sign-in</h2>
      <p>Use the operator code configured when starting the local lab.</p>
      <form onSubmit={login}>
        <label htmlFor="code">Operator code</label>
        <input id="code" type="password" autoComplete="off" value={code} onChange={e => setCode(e.target.value)} required minLength={16} maxLength={128} />
        <button disabled={busy} type="submit">{busy ? 'Connecting…' : 'Connect to local API'}</button>
      </form>
    </section> : state && <>
      <section className="surface status" aria-label="Last fetched gate status">
        <div><p className="eyebrow">GATE STATUS</p><strong className={fresh && ready ? 'ok' : 'halt'}>{fresh ? (ready ? 'Ready' : 'Halted') : 'Unknown · stale snapshot'}</strong><span className="sequence">Sequence {state.sequence}</span><p>{fresh ? 'Last successful fetch; refresh to observe later changes.' : 'Values below are last known, not a confirmed current state.'}</p></div>
        <div className="actions"><button className="secondary" disabled={busy} onClick={() => void action(() => refresh(token))}>Refresh state</button><button className="secondary" disabled={busy} onClick={signOut}>Sign out</button></div>
      </section>
      <section className="metrics" aria-label={fresh ? 'Last fetched exposure metrics' : 'Stale exposure metrics'}>
        {[['Filled position', state.position], ['Working orders', state.pending], ['Reserved exposure', state.exposure], ['Exposure limit', state.limit]].map(([label, value]) =>
          <div className="surface metric" key={label}><p>{label}</p><strong>{value}</strong><span> lots</span></div>)}
      </section>
      <div className="workspace">
        <section className="surface" aria-labelledby="orders-title">
          <h2 id="orders-title">Working orders</h2>
          <div className="table-wrap"><table><thead><tr><th>Order ID</th><th>Lots left</th><th>State</th></tr></thead>
            <tbody>{state.orders.length ? state.orders.map(order => <tr key={order.id}><td>{order.id}</td><td>{order.remaining}</td><td>{order.cancelRequested ? 'Cancel pending' : 'Working'}</td></tr>) : <tr><td colSpan={3}>No working orders</td></tr>}</tbody>
          </table></div>
        </section>
        <section className="surface" aria-labelledby="reservation-title">
          <h2 id="reservation-title">Test a reservation</h2>
          <p>Only the local synthetic risk gate evaluates this request.</p>
          {unresolved && <p className="notice" role="status">{busy ? 'Request pending. The API may commit before its response arrives.' : 'Receipt unknown. Replay the exact request before starting a new one. Signing out keeps this retry in the tab; reloading or closing the tab loses it.'}</p>}
          <form onSubmit={reserve}>
            <div className="fields"><div><label htmlFor="id">Order ID</label><input id="id" value={id} onChange={e => setId(e.target.value)} maxLength={64} required /></div>
            <div><label htmlFor="quantity">Lots</label><input id="quantity" value={quantity} onChange={e => setQuantity(e.target.value)} type="number" min={1} step={1} required /></div></div>
            <div className="actions"><button disabled={busy || !fresh || unresolved || !ready} type="submit">Evaluate reservation</button>{last && <button type="button" className="secondary" disabled={busy} onClick={() => void action(() => submit(last))}>Replay last request</button>}</div>
          </form>
          {decision && <div className="receipt" role="status">
            <strong className={decision.accepted ? 'ok' : 'halt'}>{decision.accepted ? 'Accepted' : 'Denied'}</strong> <span>{decision.replayed ? '· Replayed receipt' : '· New receipt'}</span>
            <p>{decision.reason} · Sequence {decision.sequence} · Exposure {decision.exposure} lots</p>
          </div>}
        </section>
      </div>
    </>}
    <footer>Independent .NET / React sample. No broker, exchange connection or real orders.</footer>
  </main>;
}

createRoot(document.getElementById('root')!).render(<App />);
