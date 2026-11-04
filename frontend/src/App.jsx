import { useEffect, useState } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || '/api'

function App() {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function loadSchedules(selectedDate = date) {
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`${API_URL}/schedules?event_date=${selectedDate}`)
      if (!response.ok) throw new Error(`Gagal memuat jadwal (${response.status})`)
      const result = await response.json()
      setEvents(result.events)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSchedules()
  }, [])

  return (
    <main className="app-shell">
      <header className="hero">
        <p className="eyebrow">AI SMART SCHEDULER</p>
        <h1>Rencanakan hari yang lebih tenang.</h1>
        <p className="subtitle">Jadwal terpusat untuk fokus, istirahat, dan hal penting lainnya.</p>
      </header>

      <section className="toolbar" aria-label="Pilih tanggal">
        <label htmlFor="schedule-date">Tanggal jadwal</label>
        <div className="date-row">
          <input id="schedule-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          <button type="button" onClick={() => loadSchedules()} disabled={loading}>
            {loading ? 'Memuat...' : 'Lihat jadwal'}
          </button>
        </div>
      </section>

      {error && <p className="error" role="alert">{error}</p>}

      <section className="schedule-card" aria-live="polite">
        <div className="section-heading">
          <div>
            <p className="eyebrow">AGENDA</p>
            <h2>{date}</h2>
          </div>
          <span>{events.length} aktivitas</span>
        </div>
        {events.length === 0 && !loading ? (
          <p className="empty-state">Belum ada jadwal untuk tanggal ini.</p>
        ) : (
          <div className="event-list">
            {events.map((event) => (
              <article className="event" key={event.id}>
                <time>{event.start} — {event.end}</time>
                <div>
                  <h3>{event.title}</h3>
                  <span>{event.category}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}

export default App
