<template>
  <div style="display: flex; min-height: 100vh; margin-top: 95px;">
    <!-- Left sidebar -->
    <aside style="width: 280px; background-color: #f5f5f5; padding: 30px 20px;">
      <h3 style="font-weight: bold; font-size: 22px; margin-bottom: 24px;">Reporting</h3>
      <ul style="list-style: none; padding-left: 0;">
        <li
          @click="switchSubtab('generate')"
          :style="{
            cursor: 'pointer',
            color: !isDownloadMode ? '#ff612c' : '#333',
            fontWeight: !isDownloadMode ? '600' : 'normal',
            marginBottom: '10px',
            fontSize: '20px'
          }"
        >
          ▸ Generate Reports
        </li>
        <li
          @click="switchSubtab('download')"
          :style="{
            cursor: 'pointer',
            color: isDownloadMode ? '#ff612c' : '#333',
            fontWeight: isDownloadMode ? '600' : 'normal',
            fontSize: '20px'
          }"
        >
          ▸ Download Reports
        </li>
      </ul>
    </aside>

    <!-- Main content -->
    <main style="flex-grow: 1; padding: 40px;">
      <!-- Breadcrumb -->
      <nav aria-label="breadcrumb" class="breadcrumb-nav">
        <ol class="breadcrumb-list">
          <li><svg style="width:16px; height:16px; fill:#666; vertical-align:middle;" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg> Home</li>
          <li>Reporting</li>
          <li>{{ isDownloadMode ? 'Download Reports' : 'Generate Reports' }}</li>
        </ol>
      </nav>

      <!-- Generate Reports：Confirmed Run Results + Reporting Records -->
      <template v-if="!isDownloadMode">
        <!-- Confirmed Run Results -->
        <div style="margin-bottom: 40px;">
          <h2 style="font-size: 20px; font-weight: 600; margin-bottom: 8px;">Confirmed Run Results</h2>
          <p style="color: #888; margin-bottom: 15px; font-size: 14px;">
            Runs confirmed in Run Management. Select exactly two runs with different reporting dates, then click Generate Reports to trigger generating reports.
          </p>
          <div v-if="confirmedRunsLoading" style="text-align: center; padding: 24px; color: #666;">
            <div class="spinner" style="margin: 0 auto 12px;"></div>
            Loading confirmed runs...
          </div>
          <div v-else-if="confirmedRunList.length === 0" style="padding: 24px; border: 1px solid #e0e0e0; border-radius: 4px; background: #fafafa; color: #666;">
            No confirmed runs. Please confirm completed runs in Run Management first.
          </div>
          <div v-else style="max-height: 400px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; background: white; min-width: 900px;">
            <table style="width: 100%; border-collapse: collapse; background: white;">
              <thead style="background: #f7f7f7; position: sticky; top: 0; z-index: 1;">
                <tr>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 30px;"></th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Maker</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 150px;">Time</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Settings</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Action</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Status</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Checker</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in confirmedRunList" :key="item.id || index">
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                    <input
                      type="checkbox"
                      v-model="item.selected"
                      :disabled="item.status !== 'Confirmed'"
                    />
                  </td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.maker }}</td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.time }}</td>
                  <td class="parameters-cell">
                    <div class="param-item">
                      <span class="param-label">Reporting Date:</span>
                      <span class="param-value">{{ item.reportingDate || 'N/A' }}</span>
                    </div>
                    <div class="param-item">
                      <span class="param-label">Run mode:</span>
                      <span class="param-value">{{ item.runMode || 'N/A' }}</span>
                    </div>
                  </td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.action }}</td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.status }}</td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.checker }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div style="margin-top: 3px; text-align: right; display: flex; gap: 10px; justify-content: flex-end;">
            <button
              class="upload-button"
              style="background: #FF612C;"
              @click="generateDualReport"
            >
              Generate Reports
            </button>
          </div>
        </div>

        <!-- Reporting Records table -->
        <div style="margin-bottom: 40px;">
          <h2 style="font-size: 20px; font-weight: 600; margin-bottom: 8px;">Reporting Records</h2>
          <p style="color: #888; margin-bottom: 15px; font-size: 14px;">
            Reporting jobs generated from confirmed runs. You can monitor their status and download logs or reports.
          </p>

          <div style="margin-bottom: 15px; display: flex; gap: 15px; align-items: center; flex-wrap: nowrap; white-space: nowrap; overflow-x: auto;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <label style="font-weight: 500; color: #333;">Current Reporting Date:</label>
              <select v-model="currentReportingDateFilter" class="select-input-full" style="min-width: 150px; max-width: 220px;">
                <option value="">All Dates</option>
                <option v-for="date in uniqueCurrentReportingDates" :key="date" :value="date">{{ date }}</option>
              </select>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <label style="font-weight: 500; color: #333;">Previous Reporting Date:</label>
              <select v-model="previousReportingDateFilter" class="select-input-full" style="min-width: 150px; max-width: 220px;">
                <option value="">All Dates</option>
                <option v-for="date in uniquePreviousReportingDates" :key="date" :value="date">{{ date }}</option>
              </select>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <label style="font-weight: 500; color: #333;">Status:</label>
              <select v-model="reportingStatusFilter" class="select-input-full" style="min-width: 120px; max-width: 180px;">
                <option value="">All Status</option>
                <option value="Running">Running</option>
                <option value="Completed">Completed</option>
                <option value="Failed">Failed</option>
              </select>
            </div>
            <button
              class="step-btn"
              style="background: #6c757d; color: #fff; padding: 8px 16px; font-size: 14px;"
              @click="clearReportingFilters"
            >
              Clear Filters
            </button>
          </div>

          <div style="max-height: 400px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; background: white; min-width: 1000px;">
            <table style="width: 100%; border-collapse: collapse; background: white;">
              <thead style="background: #f7f7f7; position: sticky; top: 0; z-index: 1;">
                <tr>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Maker</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 150px;">Time</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 250px;">Settings</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 250px;">Action</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Status</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Checker</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 80px;">Download Logs</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 80px;">Download Reports</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(item, index) in filteredReportingRecords"
                  :key="item.id || index"
                >
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.maker }}</td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.time }}</td>
                  <td class="parameters-cell">
                    <div class="param-item">
                      <span class="param-label">Current Reporting Date:</span>
                      <span class="param-value">{{ item.settings.current_reporting_date || 'N/A' }}</span>
                    </div>
                    <div class="param-item">
                      <span class="param-label">Previous Reporting Date:</span>
                      <span class="param-value">{{ item.settings.previous_reporting_date || 'N/A' }}</span>
                    </div>
                    <div v-if="item.settings.current_record" class="param-item">
                      <span class="param-label">Current Run:</span>
                      <span class="param-value">{{ formatRecordTime(item.settings.current_record.timestamp) }}</span>
                    </div>
                    <div v-if="item.settings.previous_record" class="param-item">
                      <span class="param-label">Previous Run:</span>
                      <span class="param-value">{{ formatRecordTime(item.settings.previous_record.timestamp) }}</span>
                    </div>
                  </td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.action }}</td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.status }}</td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.checker }}</td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                    <button
                      @click="downloadReportingLogs(index)"
                      style="color: #333; cursor: pointer; font-size: 18px; background: none; border: none;"
                      :title="'Download logs'"
                    >
                      ⬇️
                    </button>
                  </td>
                  <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                    <button
                      @click="downloadReportingReports(index)"
                      :disabled="item.status !== 'Completed'"
                      style="color: #333; cursor: pointer; font-size: 18px; background: none; border: none;"
                      :style="{
                        color: item.status === 'Completed' ? '#333' : '#ccc',
                        cursor: item.status === 'Completed' ? 'pointer' : 'not-allowed'
                      }"
                      :title="item.status === 'Completed' ? 'Download reports' : 'Reports not ready'"
                    >
                      ▶️
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <!-- Download Reports -->
      <div v-else>
        <div v-if="!timestamp" class="config-outer-box">
          <div class="config-inner-box">
            <h2 class="upload-title">Download Reports</h2>
            <p style="color: #888; margin-bottom: 24px;">
              Please go to Generate Reports, select a reporting run from Reporting Records and click "Download Reports" to choose a version first.
            </p>
          </div>
        </div>

        <div v-else class="config-outer-box">
          <div class="config-inner-box">
            <h2 class="upload-title">Reporting</h2>
            <p style="color: #888; margin-bottom: 24px;">
              Download ECL reporting documents for the selected run.
            </p>

            <!-- Loading Message -->
            <div v-if="loading" style="text-align: center; padding: 40px; color: #666;">
              <h3 style="font-size: 20px; margin-bottom: 10px;">Checking Report Availability...</h3>
              <div class="spinner"></div>
            </div>

            <!-- Download cards grid -->
            <div v-if="!loading" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px;">
              <div
                v-for="(report, idx) in reports"
                :key="idx"
                style="border: 1px solid #e0e0e0; padding: 24px; border-radius: 10px; background: #fff; box-shadow: 0 2px 8px rgba(21,61,119,0.04);"
              >
                <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">{{ report.title }}</h3>
                <p style="font-size: 15px; color: #888; margin-bottom: 16px;">{{ report.description }}</p>
                <button
                  class="step-btn"
                  style="background: #2563eb; color: #fff; font-size: 15px;"
                  @click="downloadReport(report.key)"
                >
                  Download
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Generate Reports Processing Popup -->
    <div v-if="showProcessPopup" class="process-popup">
      <div class="process-popup-content">
        <h3>Reporting Job Triggered</h3>
        <p>Generate reports has been triggered. You can monitor progress in Reporting Records.</p>
        <div class="spinner"></div>
        <button @click="processPopupClosed = true; showProcessPopup = false" style="margin-top: 16px; padding: 8px 20px; border-radius: 6px; border: none; background: #eee; cursor: pointer;">Close</button>
      </div>
    </div>

    <!-- Download Processing Popup -->
    <div v-if="showDownloadPopup" class="process-popup">
      <div class="process-popup-content">
        <h3>Preparing Download</h3>
        <p>Report is being prepared for download. Please wait...</p>
        <div class="spinner"></div>
        <button @click="closeDownloadPopup" style="margin-top: 16px; padding: 8px 20px; border-radius: 6px; border: none; background: #eee; cursor: pointer;">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { getUserDisplayName } from '../services/authService'

const route = useRoute()
const router = useRouter()

// Get timestamp from route query parameters (reactive to route changes)
const timestamp = ref(String(route.query.timestamp || ''))

// Mode: generate vs download
const isDownloadMode = computed(() => route.query.mode === 'download')

function switchSubtab(target) {
  if (target === 'download') {
    router.push({
      path: '/reporting',
      query: {
        ...route.query,
        mode: 'download'
      }
    })
  } else {
    const nextQuery = { ...route.query }
    delete nextQuery.mode
    router.push({
      path: '/reporting',
      query: nextQuery
    })
  }
}

// State for report availability and loading
const reportsAvailable = ref(false)
const loading = ref(true)

// Confirmed run results (from Run Management, status=Confirmed)
const confirmedRunList = ref([])
const confirmedRunsLoading = ref(true)

// Reporting records (reporting jobs)
const reportingRecords = ref([])
const currentReportingDateFilter = ref('')
const previousReportingDateFilter = ref('')
const reportingStatusFilter = ref('')

watch(() => route.query.timestamp, (val) => {
  timestamp.value = String(val || '')
  if (timestamp.value) checkReportAvailability()
}, { immediate: false })

const showProcessPopup = ref(false)
const processPopupClosed = ref(false)
const showDownloadPopup = ref(false)
const downloadPopupClosed = ref(false)

// Fetch confirmed run records (ECL engine records with status=Confirmed)
async function fetchConfirmedRuns() {
  confirmedRunsLoading.value = true
  try {
    const res = await axios.get('/api/get_eclengine_records')
    const records = res.data.records || []
    confirmedRunList.value = records
      .filter((item) => item.status === 'Confirmed')
      .map((item) => {
        let settings = {}
        try {
          settings = typeof item.settings === 'string' ? JSON.parse(item.settings) : (item.settings || {})
        } catch (_) {}
        return {
          id: item.id,
          maker: item.maker,
          time: item.time,
          reportingDate: settings.reportingDate || '',
          runMode: settings.runMode || '',
          action: item.action,
          status: item.status,
          checker: item.checker || 'Waiting',
          timestamp: settings.timestamp || '',
          selected: false
        }
      })
  } catch (e) {
    console.error('Error fetching confirmed runs:', e)
    confirmedRunList.value = []
  } finally {
    confirmedRunsLoading.value = false
  }
}

// Check report availability
async function checkReportAvailability() {
  if (!timestamp.value) {
    reportsAvailable.value = false
    loading.value = false
    return
  }
  loading.value = true
  try {
    const response = await axios.get(`/api/check_report_availability/${timestamp.value}`)
    reportsAvailable.value = response.data.has_reports
  } catch (error) {
    console.error('Error checking report availability:', error)
    reportsAvailable.value = false
  } finally {
    loading.value = false
  }
}

const selectedConfirmedRuns = computed(() =>
  confirmedRunList.value.filter((item) => item.selected)
)

async function generateDualReport() {
  const selected = selectedConfirmedRuns.value
  if (selected.length !== 2) {
    alert('Please select exactly two records to generate reports.')
    return
  }
  const [a, b] = selected
  if (!a.reportingDate || !b.reportingDate || a.reportingDate === b.reportingDate) {
    alert('Please select two records with different reporting dates.')
    return
  }

  const recordIds = [a.id, b.id]
  if (recordIds.some((id) => id == null)) {
    alert('Invalid record id in selection.')
    return
  }

  const now = new Date()
  const pad = (n) => n.toString().padStart(2, '0')
  const uiTimestamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(
    now.getHours()
  )}${pad(now.getMinutes())}${pad(now.getSeconds())}`

  try {
    showProcessPopup.value = true
    processPopupClosed.value = false

    const response = await axios.post('/api/generate_dual_report_from_records', {
      record_ids: recordIds,
      ui_timestamp: uiTimestamp,
      maker: getUserDisplayName()
    })

    console.log('Dual report generation started:', response.data)

    confirmedRunList.value.forEach((item) => {
      item.selected = false
    })
    await fetchReportingRecords()
  } catch (error) {
    console.error('Error generating report:', error)
    const msg =
      error.response?.data?.error ||
      error.response?.data?.message ||
      error.message ||
      'Failed to generate report.'
    alert(msg)
  } finally {
    showProcessPopup.value = false
  }
}

// Reporting records helpers
const uniqueCurrentReportingDates = computed(() => {
  const dates = new Set()
  reportingRecords.value.forEach((record) => {
    const s = record.settings || {}
    if (s.current_reporting_date) {
      dates.add(s.current_reporting_date)
    }
  })
  return Array.from(dates).sort((a, b) => b.localeCompare(a))
})

const uniquePreviousReportingDates = computed(() => {
  const dates = new Set()
  reportingRecords.value.forEach((record) => {
    const s = record.settings || {}
    if (s.previous_reporting_date) {
      dates.add(s.previous_reporting_date)
    }
  })
  return Array.from(dates).sort((a, b) => b.localeCompare(a))
})

const filteredReportingRecords = computed(() => {
  let result = reportingRecords.value

  if (currentReportingDateFilter.value) {
    const target = currentReportingDateFilter.value
    result = result.filter((record) => {
      const s = record.settings || {}
      return s.current_reporting_date === target
    })
  }

  if (previousReportingDateFilter.value) {
    const target = previousReportingDateFilter.value
    result = result.filter((record) => {
      const s = record.settings || {}
      return s.previous_reporting_date === target
    })
  }

  if (reportingStatusFilter.value) {
    result = result.filter((record) => record.status === reportingStatusFilter.value)
  }
  return result
})

function clearReportingFilters() {
  currentReportingDateFilter.value = ''
  previousReportingDateFilter.value = ''
  reportingStatusFilter.value = ''
}

async function fetchReportingRecords() {
  try {
    const res = await axios.get('/api/get_reporting_records')
    reportingRecords.value = (res.data.records || []).map((r) => ({
      ...r,
      settings: r.settings || {}
    }))
  } catch (error) {
    console.error('Error fetching reporting records:', error)
    reportingRecords.value = []
  }
}

function formatRecordTime(timestamp) {
  if (!timestamp || typeof timestamp !== 'string') {
    return 'N/A'
  }

  let ts = timestamp
  if (timestamp.includes('_')) {
    const parts = timestamp.split('_')
    ts = parts[parts.length - 1] || parts[0]
  }

  if (!/^\d{14}$/.test(ts)) {
    return timestamp
  }

  const year = ts.substring(0, 4)
  const month = ts.substring(4, 6)
  const day = ts.substring(6, 8)
  const hour = ts.substring(8, 10)
  const minute = ts.substring(10, 12)
  const second = ts.substring(12, 14)

  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}

async function downloadReportingLogs(index) {
  const item = filteredReportingRecords.value[index]
  if (!item || !item.task_id) {
    alert('No task ID found for this reporting record.')
    return
  }

  try {
    const response = await axios.get(`/api/download_reporting_logs/${item.task_id}`, {
      responseType: 'blob'
    })
    const blob = new Blob([response.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `reporting_logs_${item.original_timestamp || 'unknown'}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Download reporting logs failed:', error)
    const msg =
      error.response?.data?.error ||
      error.response?.data?.message ||
      error.message ||
      'Download reporting logs failed. Please try again.'
    alert(msg)
  }
}

async function downloadReportingReports(index) {
  const item = filteredReportingRecords.value[index]
  if (!item || !item.task_id) {
    alert('No task ID found for this reporting record.')
    return
  }

  try {
    const response = await axios.get(`/api/download_reporting_reports/${item.task_id}`)
    if (response.data?.redirect && response.data?.url) {
      router.push(response.data.url)
    } else {
      alert('No redirect information received for reporting reports.')
    }
  } catch (error) {
    console.error('Download reporting reports failed:', error)
    const msg =
      error.response?.data?.error ||
      error.response?.data?.message ||
      error.message ||
      'Download reporting reports failed. Please try again.'
    alert(msg)
  }
}

const reports = [
  {
    key: 'ecl_monthly',
    title: 'ECL Monthly Report',
    description: 'Comprehensive monthly ECL calculations and analysis',
    format: 'XLSX'
  },
  {
    key: 'ecl_summary',
    title: 'ECL Summary Report',
    description: 'Summary by stage, business unit and products',
    format: 'XLSX'
  },
  {
    key: 'ecl_gl_posting',
    title: 'ECL GL Posting Report',
    description: 'General Ledger posting details',
    format: 'XLSX'
  },
  {
    key: 'ecl_bu',
    title: 'ECL BU Reports',
    description: 'Detailed monthly reports by business units (ON/OFF balance)',
    format: 'XLSX'
  },
  {
    key: 'ecl_hkma',
    title: 'ECL HKMA Reports',
    description: 'HKMA returns and related ECL templates',
    format: 'XLSX'
  },
  {
    key: 'ecl_movement',
    title: 'ECL Movement Reports',
    description: 'ECL movement explanation and Top 10 reports',
    format: 'XLSX'
  },
  {
    key: 'ecl_annual_disclosure',
    title: 'ECL Annual Disclosure Reports',
    description: 'Annual disclosure templates and related schedules',
    format: 'XLSX'
  }
]

async function downloadReport(groupKey) {
  if (!timestamp.value) {
    alert('Please go to Generate Reports, select a reporting run from Reporting Records and click "Download Reports" to choose a version first.')
    return
  }

  try {
    // Show download popup
    showDownloadPopup.value = true
    downloadPopupClosed.value = false

    const response = await axios.get(`/api/download_grouped_reports/${groupKey}`, {
      params: {
        timestamp: timestamp.value,
        maker: getUserDisplayName()
      },
      responseType: 'blob'
    })
    
    // Download the file
    const blob = new Blob([response.data], { type: 'application/zip' })
    const downloadUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = `${groupKey}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(downloadUrl)
    
    // Close download popup
    showDownloadPopup.value = false
    
    console.log(`Successfully downloaded group ${groupKey} for timestamp ${timestamp.value}`)
  } catch (error) {
    console.error(`Error downloading group ${groupKey}:`, error)
    showDownloadPopup.value = false
    if (!downloadPopupClosed.value) {
      alert('Failed to download report. Please try again.')
    }
  }
}

// Initialize when component mounts
onMounted(() => {
  fetchConfirmedRuns()
  fetchReportingRecords()
  if (timestamp.value) checkReportAvailability()
  else loading.value = false
})
</script>

<style scoped>
.breadcrumb-nav {
  margin-bottom: 18px;
}
.breadcrumb-list {
  display: flex;
  align-items: center;
  gap: 8px;
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 18px;
  color: #555;
}
.breadcrumb-list li:not(:last-child)::after {
  content: '>';
  margin: 0 6px;
  color: #bbb;
}
.config-outer-box {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(21,61,119,0.06);
  padding: 0 0 30px 0;
  margin-bottom: 40px;
  position: relative;
}
.config-inner-box {
  padding: 30px 30px 0 30px;
}
.upload-title {
  font-size: 18px;
  font-weight: bold;
  color: #153D77;
  margin-bottom: 24px;
}
.upload-button {
  padding: 12px 24px;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.3s;
}
.upload-button:hover {
  filter: brightness(90%);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}
.parameters-cell {
  text-align: left;
  padding: 16px 18px;
  border-bottom: 1px solid #e0e0e0;
  min-width: 260px;
  font-size: 15px;
  line-height: 1.7;
}
.param-item {
  margin-bottom: 4px;
  display: flex;
  align-items: baseline;
}
.param-item:last-child {
  margin-bottom: 0;
}
.param-label {
  font-weight: 600;
  color: #153D77;
  margin-right: 6px;
  min-width: 110px;
  display: inline-block;
}
.param-value {
  color: #333;
  font-weight: 400;
  word-break: break-all;
}
.select-input-full {
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #ddd;
  font-size: 14px;
  width: 100%;
  box-sizing: border-box;
}
.step-btn {
  padding: 10px 28px;
  background: #f0f0f0;
  color: #333;
  border-radius: 20px;
  border: none;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.3s;
  margin: 0 5px;
}
.step-btn:hover {
  background: #e0e0e0;
}
.spinner {
  width: 40px;
  height: 40px;
  margin: 20px auto;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #153D77;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.process-popup {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.process-popup-content {
  background: white;
  padding: 30px;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.spinner {
  width: 40px;
  height: 40px;
  margin: 20px auto;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #153D77;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style> 