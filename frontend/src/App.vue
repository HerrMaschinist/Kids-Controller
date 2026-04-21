<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { deriveModeFromPresence } from './mode.js'

const tabs = [
  { key: 'dashboard', label: 'Dashboard', path: '/admin' },
  { key: 'draws', label: 'Draws', path: '/admin/draws' },
  { key: 'windows', label: 'Fenster', path: '/admin/windows' },
  { key: 'config', label: 'Konfiguration', path: '/admin/config' },
]

const overview = ref(null)
const loading = ref(true)
const error = ref('')
const actionMessage = ref('')
const busyAction = ref(null)

const presence = reactive({
  leon: true,
  emmi: true,
  elsa: true,
})

const activeTab = computed(() => routeToTab(window.location.pathname))

const status = computed(() => overview.value?.status ?? null)
const recentDraws = computed(() => overview.value?.recent_draws ?? [])
const recentWindows = computed(() => overview.value?.recent_windows ?? [])
const configEntries = computed(() => overview.value?.config ?? [])
const modePreview = computed(() => deriveModeFromPresence(presence))

const metrics = computed(() => {
  const current = status.value
  if (!current) {
    return []
  }

  return [
    {
      label: 'Systemstatus',
      value: current.status ?? '-',
      detail: 'Gesamtzustand des Dienstes',
      tone: 'good',
    },
    {
      label: 'Aktives Fenster',
      value: current.active_window_id ?? '-',
      detail: current.invariants?.exactly_one_active_window ? 'Fenster sauber aktiv' : 'Fenster pruefen',
      tone: current.invariants?.exactly_one_active_window ? 'good' : 'warn',
    },
    {
      label: 'Letzter Draw',
      value: current.last_successful_draw_id != null ? `#${current.last_successful_draw_id}` : '-',
      detail: current.last_successful_draw_date ? `${formatDate(current.last_successful_draw_date)} ${current.last_successful_draw_mode ?? ''}`.trim() : 'Kein Draw',
      tone: 'neutral',
    },
    {
      label: 'Router',
      value: current.router?.enabled ? 'aktiv' : 'deaktiviert',
      detail: current.router?.last_assessment_status ?? 'Supervisorisch getrennt',
      tone: current.router?.enabled ? 'good' : 'neutral',
    },
  ]
})

const invariantRows = computed(() => {
  const current = status.value
  if (!current?.invariants) {
    return []
  }

  return [
    {
      label: 'Genau ein aktives Fenster',
      value: current.invariants.exactly_one_active_window,
      tone: current.invariants.exactly_one_active_window ? 'good' : 'warn',
    },
    {
      label: 'Aktives Fenster vorhanden',
      value: current.invariants.active_window_present,
      tone: current.invariants.active_window_present ? 'good' : 'warn',
    },
    {
      label: 'Letzter effektiver Draw vorhanden',
      value: current.invariants.latest_effective_draw_present,
      tone: current.invariants.latest_effective_draw_present ? 'good' : 'warn',
    },
    {
      label: 'Fehler im Speicherstatus',
      value: current.invariants.last_error_present,
      tone: current.invariants.last_error_present ? 'warn' : 'good',
    },
  ]
})

const routerRows = computed(() => {
  const router = status.value?.router
  if (!router) {
    return []
  }

  return [
    { label: 'Verfuegbar', value: router.available ?? '-' },
    { label: 'Letzte Probe', value: router.last_checked_at ?? '-' },
    { label: 'Bewertung', value: router.last_assessment_status ?? '-' },
  ]
})

const activeTabLabel = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.label ?? 'Dashboard')

function routeToTab(pathname) {
  if (pathname.startsWith('/admin/draws')) return 'draws'
  if (pathname.startsWith('/admin/windows')) return 'windows'
  if (pathname.startsWith('/admin/config')) return 'config'
  return 'dashboard'
}

function formatDate(input) {
  if (!input) return '-'
  return new Intl.DateTimeFormat('de-DE', {
    dateStyle: 'medium',
    timeZone: 'Europe/Berlin',
  }).format(new Date(input))
}

function formatDateTime(input) {
  if (!input) return '-'
  return new Intl.DateTimeFormat('de-DE', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Europe/Berlin',
  }).format(new Date(input))
}

function formatBool(value) {
  return value ? 'ja' : 'nein'
}

function badgeClass(tone) {
  return `pill pill-${tone}`
}

function formatCell(value) {
  if (value === null || value === undefined || value === '') return '–'
  if (typeof value === 'boolean') return formatBool(value)
  return String(value)
}

async function loadOverview({ quiet = false } = {}) {
  if (!quiet) {
    loading.value = true
  }
  error.value = ''
  try {
    const response = await fetch('/admin/api/v1/overview', {
      credentials: 'same-origin',
    })
    if (!response.ok) {
      throw new Error(`Overview konnte nicht geladen werden (${response.status})`)
    }
    overview.value = await response.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unbekannter Fehler'
  } finally {
    loading.value = false
  }
}

async function runAction(url, payload = {}) {
  busyAction.value = url
  actionMessage.value = ''
  error.value = ''
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data?.detail ?? `Aktion fehlgeschlagen (${response.status})`)
    }
    actionMessage.value = data?.result?.detail ?? 'Aktion erfolgreich ausgefuehrt'
    await loadOverview({ quiet: true })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unbekannter Fehler'
  } finally {
    busyAction.value = null
  }
}

function submitDraw() {
  return runAction('/admin/api/v1/actions/draw', {
    leon_present: presence.leon,
    emmi_present: presence.emmi,
    elsa_present: presence.elsa,
  })
}

function probeRouter() {
  return runAction('/admin/api/v1/actions/router-probe')
}

function createBackup() {
  return runAction('/admin/api/v1/actions/backup')
}

onMounted(() => {
  loadOverview()
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">KIDS_CONTROLLER</p>
        <h1>Admin-Konsole</h1>
        <p class="lede">
          Vue 3 Oberflaeche fuer Betrieb, Draws, Fenster, Router und manuelle Aktionen.
        </p>
      </div>
      <div class="topbar-actions">
        <a class="ghost-button" href="/api/v1/status">API-Status</a>
        <button class="primary-button" type="button" @click="loadOverview()">Aktualisieren</button>
      </div>
    </header>

    <nav class="tabs" aria-label="Admin Navigation">
      <a
        v-for="tab in tabs"
        :key="tab.key"
        :href="tab.path"
        class="tab"
        :class="{ active: tab.key === activeTab }"
      >
        {{ tab.label }}
      </a>
    </nav>

    <main class="content">
      <section class="banner card">
        <div class="banner-copy">
          <span class="status-chip" :class="badgeClass(status?.invariants?.exactly_one_active_window ? 'good' : 'warn')">
            {{ status?.status ?? 'laden ...' }}
          </span>
          <h2>{{ activeTabLabel }}</h2>
          <p>
            Die Oberfläche zeigt den aktuellen Live-Zustand, die letzten effektiven Draws
            und die wichtigsten Betriebsinvarianten auf einen Blick.
          </p>
        </div>
        <div class="metrics">
          <article v-for="metric in metrics" :key="metric.label" class="metric-card">
            <p>{{ metric.label }}</p>
            <strong>{{ metric.value }}</strong>
            <span>{{ metric.detail }}</span>
          </article>
        </div>
      </section>

      <p v-if="actionMessage" class="flash success">{{ actionMessage }}</p>
      <p v-if="error" class="flash error">{{ error }}</p>
      <p v-else-if="loading" class="flash neutral">Lade Live-Daten ...</p>

      <section class="dashboard-grid">
        <article class="card">
          <div class="section-head">
            <div>
              <h3>Betriebsinvarianten</h3>
              <p>Die aktuelle Kernlage des Controllers.</p>
            </div>
          </div>
          <ul class="check-list">
            <li v-for="row in invariantRows" :key="row.label">
              <span>{{ row.label }}</span>
              <strong :class="badgeClass(row.tone)">{{ formatBool(row.value) }}</strong>
            </li>
          </ul>
        </article>

        <article class="card">
          <div class="section-head">
            <div>
              <h3>Router</h3>
              <p>Supervisorische Sicht, kein Schreibpfad.</p>
            </div>
            <span class="pill" :class="badgeClass(status?.router?.enabled ? 'good' : 'neutral')">
              {{ status?.router?.enabled ? 'aktiv' : 'deaktiviert' }}
            </span>
          </div>
          <ul class="check-list">
            <li v-for="row in routerRows" :key="row.label">
              <span>{{ row.label }}</span>
              <strong>{{ formatCell(row.value) }}</strong>
            </li>
          </ul>
          <p class="note">
            {{ status?.router?.last_probe_message || status?.router?.last_assessment_message || '-' }}
          </p>
        </article>

        <article class="card actions-card">
          <div class="section-head">
            <div>
              <h3>Manuelle Aktionen</h3>
              <p>Gezielt Draw, Router-Probe oder Backup ausloesen.</p>
            </div>
          </div>

          <div class="action-stack">
          <div class="action-box">
            <h4>Draw ausloesen</h4>
            <div class="presence-grid">
              <label><input v-model="presence.leon" type="checkbox" /> Leon</label>
              <label><input v-model="presence.emmi" type="checkbox" /> Emmi</label>
              <label><input v-model="presence.elsa" type="checkbox" /> Elsa</label>
            </div>
            <div class="preview-box">
              <p>Abgeleiteter Modus</p>
              <strong>{{ modePreview }}</strong>
              <span>Nur Vorschau. Das Backend bestimmt den finalen Modus.</span>
            </div>
            <button class="primary-button" type="button" :disabled="busyAction" @click="submitDraw()">
              {{ busyAction === '/admin/api/v1/actions/draw' ? 'Draw laeuft ...' : 'Draw starten' }}
            </button>
          </div>

            <div class="action-box">
              <h4>Router pruefen</h4>
              <p>Health-Check gegen den externen Router.</p>
              <button class="ghost-button" type="button" :disabled="busyAction" @click="probeRouter()">
                {{ busyAction === '/admin/api/v1/actions/router-probe' ? 'Pruefe ...' : 'Router-Probe starten' }}
              </button>
            </div>

            <div class="action-box">
              <h4>Backup</h4>
              <p>Kopiert das Live-Deployment in das Backup-Verzeichnis.</p>
              <button class="ghost-button" type="button" :disabled="busyAction" @click="createBackup()">
                {{ busyAction === '/admin/api/v1/actions/backup' ? 'Sichere ...' : 'App-Backup erstellen' }}
              </button>
            </div>
          </div>
        </article>
      </section>

      <section v-if="activeTab === 'dashboard'" class="grid-two">
        <article class="card">
          <div class="section-head">
            <div>
              <h3>Letzte Draws</h3>
              <p>Die juengsten effektiven Ergebnisse aus der Datenbank.</p>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Datum</th>
                  <th>Modus</th>
                  <th>Fenster</th>
                  <th>Positionen</th>
                  <th>Stops</th>
                  <th>Effektiv</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="draw in recentDraws.slice(0, 8)" :key="draw.id">
                  <td>{{ draw.id }}</td>
                  <td>{{ formatDateTime(draw.draw_date) }}</td>
                  <td><span class="pill pill-good">{{ draw.mode }}</span></td>
                  <td>{{ draw.window_id || '–' }}</td>
                  <td>{{ [draw.pos1, draw.pos2, draw.pos3].filter((value) => value != null).join(' / ') || '–' }}</td>
                  <td>{{ draw.stop_morning }} / {{ draw.stop_midday }}</td>
                  <td>{{ formatBool(draw.is_effective) }}</td>
                </tr>
                <tr v-if="!recentDraws.length">
                  <td colspan="7">Keine Draws vorhanden.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article class="card">
          <div class="section-head">
            <div>
              <h3>Letzte Fenster</h3>
              <p>Fensterhistorie mit Status und letzter Vollordnung.</p>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Window ID</th>
                  <th>Status</th>
                  <th>Index</th>
                  <th>Letzte Vollordnung</th>
                  <th>Letzter Modus</th>
                  <th>Start</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="window in recentWindows.slice(0, 8)" :key="window.id">
                  <td>{{ window.id }}</td>
                  <td>{{ window.window_id }}</td>
                  <td>
                    <span class="pill" :class="badgeClass(window.window_status === 'ACTIVE' ? 'good' : 'warn')">
                      {{ window.window_status }}
                    </span>
                  </td>
                  <td>{{ window.window_index }}</td>
                  <td>{{ window.last_full_order || '–' }}</td>
                  <td>{{ window.last_mode || '–' }}</td>
                  <td>{{ formatDateTime(window.window_start_date) }}</td>
                </tr>
                <tr v-if="!recentWindows.length">
                  <td colspan="7">Keine Fenster vorhanden.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <section v-else-if="activeTab === 'draws'" class="card">
        <div class="section-head">
          <div>
            <h3>Alle Draws</h3>
            <p>Chronologische Sicht auf die gespeicherten Ergebnisse.</p>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Datum</th>
                <th>Modus</th>
                <th>Window</th>
                <th>Positionen</th>
                <th>Stops</th>
                <th>Effektiv</th>
                <th>Replay</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="draw in recentDraws" :key="draw.id">
                <td>{{ draw.id }}</td>
                <td>{{ formatDateTime(draw.draw_date) }}</td>
                <td><span class="pill pill-good">{{ draw.mode }}</span></td>
                <td>{{ draw.window_id || '–' }}</td>
                <td>{{ [draw.pos1, draw.pos2, draw.pos3].filter((value) => value != null).join(' / ') || '–' }}</td>
                <td>{{ draw.stop_morning }} / {{ draw.stop_midday }}</td>
                <td>{{ formatBool(draw.is_effective) }}</td>
                <td><code>{{ draw.replay_context_hash ? `${draw.replay_context_hash.slice(0, 12)}...` : '–' }}</code></td>
              </tr>
              <tr v-if="!recentDraws.length">
                <td colspan="8">Keine Draws vorhanden.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-else-if="activeTab === 'windows'" class="card">
        <div class="section-head">
          <div>
            <h3>Alle Fenster</h3>
            <p>Historie der Fairness-Fenster mit Zustand und Startdatum.</p>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Window ID</th>
                <th>Status</th>
                <th>Index</th>
                <th>Letzte Vollordnung</th>
                <th>Letzter Modus</th>
                <th>Start</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="window in recentWindows" :key="window.id">
                <td>{{ window.id }}</td>
                <td>{{ window.window_id }}</td>
                <td>
                  <span class="pill" :class="badgeClass(window.window_status === 'ACTIVE' ? 'good' : 'warn')">
                    {{ window.window_status }}
                  </span>
                </td>
                <td>{{ window.window_index }}</td>
                <td>{{ window.last_full_order || '–' }}</td>
                <td>{{ window.last_mode || '–' }}</td>
                <td>{{ formatDateTime(window.window_start_date) }}</td>
                <td>{{ formatDateTime(window.updated_at) }}</td>
              </tr>
              <tr v-if="!recentWindows.length">
                <td colspan="8">Keine Fenster vorhanden.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-else class="card">
        <div class="section-head">
          <div>
            <h3>Konfiguration</h3>
            <p>Nur die relevanten Laufzeitwerte fuer den Betrieb.</p>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Schluessel</th>
                <th>Wert</th>
                <th>Editierbar</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in configEntries" :key="item.key">
                <td>{{ item.key }}</td>
                <td>{{ formatCell(item.value) }}</td>
                <td>{{ formatBool(item.editable) }}</td>
              </tr>
              <tr v-if="!configEntries.length">
                <td colspan="3">Keine Konfigurationswerte vorhanden.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <footer class="footer card">
        <span>API: <a href="/api/v1/health">/api/v1/health</a> und <a href="/api/v1/status">/api/v1/status</a></span>
        <span>Admin JSON: <a href="/admin/api/v1/overview">/admin/api/v1/overview</a></span>
      </footer>
    </main>
  </div>
</template>
