<template>
  <div style="display: flex; min-height: 100vh; margin-top: 95px;">
    <!-- 左侧导航栏 -->
    <aside style="width: 280px; background-color: #f5f5f5; padding: 30px 20px;">
      <h3 style="font-weight: bold; font-size: 22px; margin-bottom: 24px;">Run Management</h3>
    </aside>
 
    <!-- 主体内容 -->
    <main style="flex-grow: 1; padding: 40px;">
     
      <!-- 面包屑导航 -->
      <nav aria-label="breadcrumb" class="breadcrumb-nav">
        <ol class="breadcrumb-list">
          <li><svg style="width:16px; height:16px; fill:#666; vertical-align:middle;" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg> Home</li>
          <li>Run Management</li>
          <li>Production</li>
        </ol>
      </nav>
     
      <!-- Configuration Box with Progress Bar -->
      <div class="config-outer-box">
        <div class="progress-bar">
          <div class="progress-bar-inner" :style="{ width: getProgressWidth() }"></div>
        </div>
        <div class="config-inner-box">
          <div class="steps-row">
            <div class="step-box">
              <div class="step-title">
                <div class="step-circle">
                  <svg style="width:10px; height:10px; stroke:#4CAF50;" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 6L9 17l-5-5"/>
                  </svg>
                </div>
                1. Initiate Run
              </div>
              <div class="step-status">Ready to submit</div>
              <div style="display: flex; gap: 10px; margin-bottom: 15px; flex-direction: column;">
                <div style="display: flex; gap: 10px;">
                  <select v-model="selectedReportingDate" class="select-input">
                    <option disabled value="">Select current reporting date</option>
                    <option v-for="date in reportingDateOptions" :key="date" :value="date">{{ date }}</option>
                  </select>
                  <select v-model="selectedRunMode" class="select-input">
                    <option disabled value="">Select Run mode</option>
                    <option v-for="mode in runModes" :key="mode" :value="mode">{{ mode }}</option>
                  </select>
                </div>
                <div style="display: flex; gap: 10px;">
                  <input v-model="actionComment" placeholder="Provide action comment here" class="select-input" style="flex: 1;" />
                </div>
              </div>
              <div style="text-align: right; margin-top: 8px;">
                <button @click="onSubmit" :disabled="!canSubmit" class="step-btn">Submit</button>
              </div>
            </div>
            <div class="step-box">
              <div class="step-title">
                <div class="step-circle" :class="{ active: !step3Complete, done: step3Complete }">
                  <svg v-if="!step3Complete" style="width:10px; height:10px; stroke:#ff4848;" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="6" x2="12" y2="12" />
                    <line x1="12" y1="18" x2="12" y2="18" />
                  </svg>
                  <svg v-else style="width:10px; height:10px; stroke:#4CAF50;" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 6L9 17l-5-5"/>
                  </svg>
                </div>
                2. Resume Run
              </div>
              <div class="step-status">{{ step3Complete ? 'Complete' : 'Ready to resume' }}</div>
              <div style="display: flex; gap: 10px; margin-bottom: 15px; flex-direction: column;">
                <div style="display: flex; gap: 10px;">
                  <select v-model="selectedResumeConfig" :disabled="step3Complete" class="select-input">
                    <option disabled value="">Select configuration file</option>
                    <option v-for="config in resumeConfigOptions" :key="config" :value="config">{{ config }}</option>
                  </select>
                  <select v-model="selectedResumeRunMode" :disabled="step3Complete" class="select-input">
                    <option disabled value="">Select resume run mode</option>
                    <option v-for="mode in resumeRunModes" :key="mode" :value="mode">{{ mode }}</option>
                  </select>
                </div>
                <div style="display: flex; gap: 10px;">
                  <input v-model="resumeActionComment" :disabled="step3Complete" placeholder="Provide action comment here" class="select-input" style="flex: 1;" />
                </div>
              </div>
              <div style="text-align: right; margin-top: 8px;">
                <button @click="onResumeSubmit" :disabled="!canResumeSubmit || step3Complete" class="step-btn">{{ step3Complete ? 'Completed' : 'Resume' }}</button>
              </div>
            </div>
          </div>
          <div class="instructions-box">
            <p class="instructions-title">Instructions:</p>
            <ul class="instructions-list">
              <li>1. Please choose reporting date, run mode and fill in action comment, then submit to generate the run record.</li>
              <li>2. To resume a failed run, select the configuration file and choose the resume run mode.</li>
              <li>3. To generate reports, click the "Generate Report" button in the Review table for completed records.</li>
            </ul>
            <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 6px; border-left: 4px solid #153D77;">
              <h4 style="margin: 0 0 10px 0; color: #153D77; font-size: 16px;">Run Mode Description:</h4>
              <div style="font-size: 14px; line-height: 1.6; color: #333;">
                <div style="margin-bottom: 10px;">
                  <strong>Individual Run Modes:</strong>
                  <ul style="margin: 5px 0 10px 20px; padding: 0;">
                    <li><strong>0:</strong> Data Merge Only - Converts and merges raw data files</li>
                    <li><strong>1:</strong> Deal Append - Appends new deals to existing data</li>
                    <li><strong>2:</strong> Pre-Run Validation - Validates data before ECL calculation</li>
                    <li><strong>3:</strong> ECL Calculation - Performs core ECL calculations</li>
                    <li><strong>4:</strong> Post-Run Adjustments1 - Applies stage 3 and output adjustments</li>
                    <li><strong>5:</strong> Post-Run Validation2 - Validates calculation results</li>
                    <li><strong>6:</strong> Reporting - Generate reports</li>
                  </ul>
                </div>
                <div>
                  <strong>Combined Run Modes:</strong>
                  <ul style="margin: 5px 0 0 20px; padding: 0;">
                    <li><strong>0-5:</strong> Full pipeline (including data merge) - Steps 0 through 5</li>
                    <li><strong>1-5:</strong> Deal append – Post-run data sanity check - Steps 1 through 5</li>
                    <li><strong>2-5:</strong> Pre-run data sanity check – Post-run data sanity check - Steps 2 through 5</li>
                    <li><strong>3-5:</strong> ECL calculation – Post-run data sanity check - Steps 3 through 5</li>
                    <li><strong>4-5:</strong> Post-run ECL adjustment – Post-run data sanity check - Steps 4 through 5</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
     
      <!-- Review Box -->
      <div>
        <h2 style="font-size: 20px; font-weight: 600; margin-bottom: 8px;">Review</h2>
        
        <!-- Filter Section -->
        <div style="margin-bottom: 15px; display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <label style="font-weight: 500; color: #333;">Reporting Date:</label>
            <select v-model="reviewReportingDateFilter" class="select-input" style="min-width: 150px;">
              <option value="">All Dates</option>
              <option v-for="date in uniqueReviewReportingDates" :key="date" :value="date">{{ date }}</option>
            </select>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <label style="font-weight: 500; color: #333;">Status:</label>
            <select v-model="reviewStatusFilter" class="select-input" style="min-width: 120px;">
              <option value="">All Status</option>
              <option value="Running">Running</option>
              <option value="Completed">Completed</option>
              <option value="Failed">Failed</option>
            </select>
          </div>
          <button @click="clearReviewFilters" class="step-btn" style="background: #6c757d; color: white; padding: 8px 16px; font-size: 14px;">
            Clear Filters
          </button>
        </div>
        
        <div style="max-height: 640px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; background: white; min-width: 1200px;">
          <table style="width: 100%; border-collapse: collapse; background: white;">
            <thead style="background: #f7f7f7; position: sticky; top: 0; z-index: 1;">
              <tr>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Maker</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 150px;">Time</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 18px;">Settings</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 150px;">Action</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Status</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Checker</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 40px;">Download Logs</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 40px;">Download ECL Results</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 120px;">Generate Report</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in filteredReviewList" :key="index" :style="{ backgroundColor: item.approved ? '#e8f5e9' : '#fff' }">
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.maker }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.time }}</td>
                <td style="text-align: left; padding: 16px 18px; border-bottom: 1px solid #e0e0e0; min-width: 260px; font-size: 15px; line-height: 1.7;">
                  <div v-if="item.isResume" class="param-item">
                    <span class="param-label">Resumed version:</span> <span class="param-value">{{ formatResumedVersion(item.resumedVersion) }}</span>
                  </div>
                  <div v-if="item.isResume" class="param-item">
                    <span class="param-label">Run mode:</span> <span class="param-value">{{ item.runMode }}</span>
                  </div>
                  <div v-if="item.isGenerateReport" class="param-item">
                    <span class="param-label">Selected version:</span> <span class="param-value">{{ item.resumedVersion }}</span>
                  </div>
                  <div v-if="item.isGenerateReport" class="param-item">
                    <span class="param-label">Run mode:</span> <span class="param-value">{{ item.runMode }}</span>
                  </div>
                  <div v-if="!item.isResume && !item.isGenerateReport" class="param-item">
                    <span class="param-label">Reporting Date:</span> <span class="param-value">{{ item.reportingDate }}</span>
                  </div>
                  <div v-if="!item.isResume && !item.isGenerateReport" class="param-item">
                    <span class="param-label">Run mode:</span> <span class="param-value">{{ item.runMode }}</span>
                  </div>
                </td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.action }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.status }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.checker }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                  <button @click="downloadRow(index)" style="color: #333; cursor: pointer; font-size: 20px; background: none; border: none;">⬇️</button>
                </td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                  <button @click="downloadEclResults(index)" style="color: #333; cursor: pointer; font-size: 20px; background: none; border: none;">⬇️</button>
                </td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                  <button
                    @click="generateReportFromRecord(index)"
                    :disabled="!canGenerateReport(item)"
                    class="generate-report-btn"
                    style="padding: 6px 12px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;"
                    :style="{
                      background: canGenerateReport(item) ? '#4CAF50' : '#ccc',
                      cursor: canGenerateReport(item) ? 'pointer' : 'not-allowed'
                    }"
                  >
                    Generate Report
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
 
      <!-- Reporting Records Table -->
      <div style="margin-top: 40px;">
        <h2 style="font-size: 20px; font-weight: 600; margin-bottom: 8px;">Reporting Records</h2>
        
        <!-- Filter Section -->
        <div style="margin-bottom: 15px; display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <label style="font-weight: 500; color: #333;">Reporting Date:</label>
            <select v-model="reportingDateFilter" class="select-input" style="min-width: 150px;">
              <option value="">All Dates</option>
              <option v-for="date in uniqueReportingDates" :key="date" :value="date">{{ date }}</option>
            </select>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <label style="font-weight: 500; color: #333;">Status:</label>
            <select v-model="statusFilter" class="select-input" style="min-width: 120px;">
              <option value="">All Status</option>
              <option value="Running">Running</option>
              <option value="Completed">Completed</option>
              <option value="Failed">Failed</option>
              <option value="Confirmed">Confirmed</option>
            </select>
          </div>
          <button @click="clearFilters" class="step-btn" style="background: #6c757d; color: white; padding: 8px 16px; font-size: 14px;">
            Clear Filters
          </button>
        </div>
        
        <div style="max-height: 640px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; background: white; min-width: 1200px;">
          <table style="width: 100%; border-collapse: collapse; background: white;">
            <thead style="background: #f7f7f7; position: sticky; top: 0; z-index: 1;">
              <tr>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 20px;"></th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Maker</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 150px;">Time</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Settings</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 350px;">Action</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 80px;">Status</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Checker</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 40px;">Download Logs</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 40px;">Download Reports</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in filteredReportingRecords" :key="index" :style="{ backgroundColor: item.status === 'Completed' ? '#e8f5e9' : item.status === 'Confirmed' ? '#fff3cd' : '#fff' }">
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                  <input 
                    type="checkbox" 
                    v-model="item.selected" 
                    :disabled="item.status !== 'Completed' && item.status !== 'Confirmed'"
                  />
                </td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.maker }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.time }}</td>
                <td style="text-align: left; padding: 16px 18px; border-bottom: 1px solid #e0e0e0; min-width: 260px; font-size: 15px; line-height: 1.7;">
                  <div class="param-item">
                    <span class="param-label">Reporting Date:</span> <span class="param-value">{{ item.settings.reportingDate || 'N/A' }}</span>
                  </div>
                  <div class="param-item">
                    <span class="param-label">Run Mode:</span> <span class="param-value">{{ item.settings.runMode || 'N/A' }}</span>
                  </div>
                </td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.action }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.status }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.checker }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                  <button @click="downloadReportingLogs(index)" style="color: #333; cursor: pointer; font-size: 20px; background: none; border: none;">⬇️</button>
                </td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                  <button
                    @click="downloadReportingReports(index)"
                    :disabled="item.status !== 'Completed'"
                    style="color: #333; cursor: pointer; font-size: 20px; background: none; border: none;"
                    :style="{
                      color: item.status === 'Completed' ? '#333' : '#ccc',
                      cursor: item.status === 'Completed' ? 'pointer' : 'not-allowed'
                    }"
                  >
                    ▶️
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="margin-top: 3px; text-align: right; display: flex; gap: 10px; justify-content: flex-end;">
          <button 
            class="upload-button" 
            style="background: #FF612C;" 
            @click="confirmSelectedReporting"
            :disabled="!hasSelectedCompletedReporting"
            :title="hasSelectedCompletedReporting ? 'Confirm selected completed records' : 'No completed records selected'"
          >
            Confirm
          </button>
          <button 
            class="upload-button" 
            style="background: #6c757d;" 
            @click="unconfirmSelectedReporting"
            :disabled="!hasSelectedConfirmedReporting"
            :title="hasSelectedConfirmedReporting ? 'Unconfirm selected confirmed records' : 'No confirmed records selected'"
          >
            Unconfirm
          </button>
        </div>
      </div>
 
    </main>
   
    <!-- Process Running Popup -->
    <div v-if="showProcessPopup" class="process-popup">
      <div class="process-popup-content">
        <h3>ECL Engine Running</h3>
        <p>ECL Engine is running. Please wait for results to be generated...</p>
        <div class="spinner"></div>
        <button @click="closeProcessPopup" style="margin-top: 16px; padding: 8px 20px; border-radius: 6px; border: none; background: #eee; cursor: pointer;">Close</button>
      </div>
    </div>

    <!-- Download Processing Popup -->
    <div v-if="showDownloadPopup" class="process-popup">
      <div class="process-popup-content">
        <h3>Preparing Download</h3>
        <p>ECL Results are being compressed into a zip file. Please wait...</p>
        <div class="spinner"></div>
        <button @click="closeDownloadPopup" style="margin-top: 16px; padding: 8px 20px; border-radius: 6px; border: none; background: #eee; cursor: pointer;">Close</button>
      </div>
    </div>
  </div>
</template>
 
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { getUserDisplayName } from '../services/authService'
 
// Define the type for review list items
interface ReviewItem {
  id: number // Added record ID
  maker: string
  time: string
  reportingDate: string
  runMode: string
  action: string
  status: string
  checker: string
  approved: boolean
  downloaded?: boolean // Download status (optional, not used for UI)
  eclResultsDownloaded?: boolean // ECL results download status (optional, not used for UI)
  taskId?: string // Added taskId to the interface
  timestamp?: string // Added timestamp to the interface
  isResume?: boolean // Added isResume flag
  resumedVersion?: string // Added resumedVersion for resume records
  isGenerateReport?: boolean // Added isGenerateReport flag
}
 
// Replace hardcoded options with dynamic lists
const runModes = ['0','1','2','3','0-5','1-5','2-5','3-5','4-5']
 
// Reporting date options
const reportingDateOptions = ['2025-02-24', '2024-12-31', '2024-06-30', '2024-03-31', '2023-12-31', '2023-06-30']
 
const router = useRouter()

const selectedReportingDate = ref('')
const selectedRunMode = ref('')
const actionComment = ref('')
 
// Resume run variables
const selectedResumeConfig = ref('')
const selectedResumeRunMode = ref('')
const resumeActionComment = ref('')
const resumeConfigOptions = ref<string[]>([])
const resumeRunModes = ['1-5','2-5','3-5','4-5']
 
const step1Complete = ref(false)
const step2Complete = ref(false)
const step3Complete = ref(false) // Added step3Complete
 
// Review list with localStorage persistence
const reviewList = ref<ReviewItem[]>([])
 
// Reporting Records list
const reportingRecords = ref<any[]>([])

// Add new refs for process monitoring
const showProcessPopup = ref(false)
const processPopupClosed = ref(false)

// Add new refs for download monitoring
const showDownloadPopup = ref(false)
const downloadPopupClosed = ref(false)

// Add new refs for reporting records filtering and selection
const reportingDateFilter = ref('')
const statusFilter = ref('')

// Add new refs for review filtering
const reviewReportingDateFilter = ref('')
const reviewStatusFilter = ref('')
 
function closeProcessPopup() {
  showProcessPopup.value = false
  processPopupClosed.value = true
}

function closeDownloadPopup() {
  showDownloadPopup.value = false
  downloadPopupClosed.value = true
}

// Computed properties for filtering and selection
const uniqueReportingDates = computed(() => {
  const dates = new Set<string>()
  reportingRecords.value.forEach(record => {
    if (record.settings?.reportingDate) {
      dates.add(record.settings.reportingDate)
    }
  })
  return Array.from(dates).sort()
})

const filteredReportingRecords = computed(() => {
  let filtered = reportingRecords.value
  
  if (reportingDateFilter.value) {
    filtered = filtered.filter(record => 
      record.settings?.reportingDate === reportingDateFilter.value
    )
  }
  
  if (statusFilter.value) {
    filtered = filtered.filter(record => 
      record.status === statusFilter.value
    )
  }
  
  return filtered
})

const hasSelectedCompletedReporting = computed(() => {
  return filteredReportingRecords.value.some(item => item.selected && item.status === 'Completed')
})

const hasSelectedConfirmedReporting = computed(() => {
  return filteredReportingRecords.value.some(item => item.selected && item.status === 'Confirmed')
})

// Computed properties for review filtering
const uniqueReviewReportingDates = computed(() => {
  const dates = new Set<string>()
  reviewList.value.forEach(record => {
    if (record.reportingDate) {
      dates.add(record.reportingDate)
    }
  })
  return Array.from(dates).sort()
})

const filteredReviewList = computed(() => {
  let filtered = reviewList.value
  
  if (reviewReportingDateFilter.value) {
    filtered = filtered.filter(record => 
      record.reportingDate === reviewReportingDateFilter.value
    )
  }
  
  if (reviewStatusFilter.value) {
    filtered = filtered.filter(record => 
      record.status === reviewStatusFilter.value
    )
  }
  
  return filtered
})

// Methods for reporting records
function clearFilters() {
  reportingDateFilter.value = ''
  statusFilter.value = ''
  // Clear all selections
  reportingRecords.value.forEach(item => {
    item.selected = false
  })
}

function clearReviewFilters() {
  reviewReportingDateFilter.value = ''
  reviewStatusFilter.value = ''
}

async function confirmSelectedReporting() {
  const selectedRecords = filteredReportingRecords.value.filter(item => item.selected && item.status === 'Completed')
  
  if (selectedRecords.length === 0) return
  
  // Process the first selected record (since only one can be selected at a time based on UI)
  const selectedRecord = selectedRecords[0]
  const taskId = selectedRecord.task_id
  
  try {
    await axios.post('/api/confirm_reporting_record', {
      task_id: taskId,
      checker: getUserDisplayName()
    })
    
    // Refresh reporting records
    await fetchReportingRecords()
    
    // Clear selection after refresh
    const refreshedRecord = reportingRecords.value.find(item => item.task_id === taskId)
    if (refreshedRecord) {
      refreshedRecord.selected = false
    }
  } catch (error) {
    console.error('Error confirming reporting record:', error)
    alert('Failed to confirm reporting record. Please try again.')
  }
}

async function unconfirmSelectedReporting() {
  const selectedRecords = filteredReportingRecords.value.filter(item => item.selected && item.status === 'Confirmed')
  
  if (selectedRecords.length === 0) return
  
  // Process the first selected record (since only one can be selected at a time based on UI)
  const selectedRecord = selectedRecords[0]
  const taskId = selectedRecord.task_id
  
  try {
    await axios.post('/api/unconfirm_reporting_record', {
      task_id: taskId,
      checker: getUserDisplayName()
    })
    
    // Refresh reporting records
    await fetchReportingRecords()
    
    // Clear selection after refresh
    const refreshedRecord = reportingRecords.value.find(item => item.task_id === taskId)
    if (refreshedRecord) {
      refreshedRecord.selected = false
    }
  } catch (error) {
    console.error('Error unconfirming reporting record:', error)
    alert('Failed to unconfirm reporting record. Please try again.')
  }
}
 
 
 
const canSubmit = computed(() => selectedReportingDate.value !== '' && selectedRunMode.value !== '' && actionComment.value.trim() !== '')
const canResumeSubmit = computed(() => selectedResumeConfig.value !== '' && selectedResumeRunMode.value !== '' && resumeActionComment.value.trim() !== '')
 
// Load data when component mounts
onMounted(() => {
  fetchReviewListFromDB()
  fetchResumeConfigFiles() // Fetch resume config files
  fetchReportingRecords() // Fetch reporting records
})
 
// Clean up event listener
onUnmounted(() => {
  // No longer need to remove event listener since we removed handleBeforeUnload
})
 
async function onSubmit() {
  if (!canSubmit.value) return
 
  const now = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  const timeStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
 
  // Generate UI timestamp in the same format as backend (YYYYMMDDHHMMSS)
  const uiTimestamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
 
  try {
    showProcessPopup.value = true
    processPopupClosed.value = false
 
    // 提交任务，获取 task_id，并传递UI timestamp
    const runResponse = await axios.post('/api/run_ecl_engine', {
      reportingDate: selectedReportingDate.value,
      runMode: selectedRunMode.value,
      action: actionComment.value,
      ui_timestamp: uiTimestamp,
      maker: getUserDisplayName()
    })
 
    const taskId = runResponse.data.task_id
    const backendTimestamp = runResponse.data.timestamp || uiTimestamp
 
    // 立即添加到review列表，初始状态为 Running
    reviewList.value.unshift({
      id: 0, // 临时ID，实际ID会在数据库保存后更新
      maker: getUserDisplayName(),
      time: timeStr,
      reportingDate: selectedReportingDate.value,
      runMode: selectedRunMode.value,
      action: actionComment.value,
      status: 'Running',
      checker: 'Waiting',
      approved: false,
      downloaded: false,
      eclResultsDownloaded: false, // Initialize ECL results download status
      taskId, // 新增字段
      timestamp: backendTimestamp // 保存timestamp用于后续查找
    })
 
    // 轮询任务状态
    const pollStatus = async () => {
      try {
        const statusResponse = await axios.get(`/api/task_status/${taskId}`)
        const status = statusResponse.data.status
        // 找到对应的review item，更新status
        const item = reviewList.value.find(i => i.taskId === taskId)
        if (item) {
          if (status === 'Completed') {
            item.status = 'Completed'
            showProcessPopup.value = false
            if (!processPopupClosed.value) alert('ECL Engine completed successfully!')
            return
          } else if (status === 'Failed') {
            item.status = 'Failed'
            showProcessPopup.value = false
            if (!processPopupClosed.value) alert('ECL Engine failed')
            return
          } else {
            item.status = 'Running'
          }
        }
        setTimeout(pollStatus, 5000)
      } catch (error: any) {
        showProcessPopup.value = false
        if (!processPopupClosed.value) alert(error.message || 'An error occurred while running the ECL engine')
      }
    }
    pollStatus()
 
    // 重置表单
    selectedReportingDate.value = ''
    selectedRunMode.value = ''
    actionComment.value = ''
   
    // 重新获取resume config files列表，包含新生成的config file
    fetchResumeConfigFiles()
   
    // Set step2Complete to true to show 100% progress
    step2Complete.value = true
 
  } catch (error: any) {
    showProcessPopup.value = false
    if (!processPopupClosed.value) alert(error.message || 'An error occurred while running the ECL engine')
  }
}
 
 
 
async function downloadRow(index: number) {
  const item = reviewList.value[index]
 
  if (!item.taskId) {
    alert('No task ID found for this record')
    return
  }
 
  try {
    // Call the backend API to download log files
    const response = await axios.get(`/api/download_log_files/${item.taskId}`, {
      responseType: 'blob'
    })
   
    // Create download link
    const blob = new Blob([response.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ecl_log_files_${item.timestamp || 'unknown'}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
   
    console.log(`Successfully downloaded log files for task: ${item.taskId}`)
   
  } catch (error: any) {
    console.error('Download failed:', error)
    const errorMessage = error.response?.data?.error || 'Download failed. Please try again.'
    alert(`Download failed: ${errorMessage}`)
  }
}
 
async function downloadEclResults(index: number) {
  const item = reviewList.value[index]

  if (!item.taskId) {
    alert('No task ID found for this record')
    return
  }

  try {
    // Show download popup
    showDownloadPopup.value = true
    downloadPopupClosed.value = false

    // Call the backend API to download ECL results
    const response = await axios.get(`/api/download_ecl_results/${item.taskId}`, {
      responseType: 'blob'
    })
   
    // Create download link
    const blob = new Blob([response.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ecl_results_${item.timestamp || 'unknown'}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
   
    console.log(`Successfully downloaded ECL results for task: ${item.taskId}`)
    
    // Close download popup
    showDownloadPopup.value = false
    if (!downloadPopupClosed.value) {
      alert('ECL Results downloaded successfully!')
    }
   
  } catch (error: any) {
    console.error('ECL Results download failed:', error)
    showDownloadPopup.value = false
    const errorMessage = error.response?.data?.error || 'ECL Results download failed. Please try again.'
    if (!downloadPopupClosed.value) {
      alert(`ECL Results download failed: ${errorMessage}`)
    }
  }
}
 
// Check if a record can generate report
function canGenerateReport(item: ReviewItem): boolean {
  if (item.status !== 'Completed') {
    return false
  }
  
  // Check if run mode ends with '5'
  const runMode = item.runMode || ''
  return runMode.endsWith('5')
}

// Generate Report from Record
async function generateReportFromRecord(index: number) {
  const item = reviewList.value[index]
  if (!canGenerateReport(item)) {
    alert('Only completed records with run mode ending in 5 can generate reports')
    return
  }
 
  try {
    showProcessPopup.value = true
    processPopupClosed.value = false
   
    // Generate UI timestamp (consistent with Parameter page)
    const now = new Date()
    const pad = (n: number) => n.toString().padStart(2, '0')
    const uiTimestamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
   
    await axios.post('/api/generate_report_from_record', {
      record_id: item.id,  // 需要从数据库获取record的ID
      maker: getUserDisplayName(),
      ui_timestamp: uiTimestamp  // Send frontend timestamp to backend
    })
    
    // 使用前端生成的时间戳
    const frontendTimestamp = uiTimestamp
    console.log('Generated report timestamp:', frontendTimestamp)
   
    // 刷新reporting records列表
    fetchReportingRecords()
   
    // 关闭popup
    showProcessPopup.value = false
   
  } catch (error: any) {
    showProcessPopup.value = false
    alert('Failed to start report generation: ' + (error.response?.data?.error || error.message))
  }
}
 
// Download reporting logs
async function downloadReportingLogs(index: number) {
  const item = reportingRecords.value[index]
 
  if (!item.task_id) {
    alert('No task ID found for this record')
    return
  }
 
  try {
    // Call the backend API to download log files
    const response = await axios.get(`/api/download_reporting_logs/${item.task_id}`, {
      responseType: 'blob'
    })
   
    // Create download link
    const blob = new Blob([response.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `reporting_logs_${item.original_timestamp || 'unknown'}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
   
    console.log(`Successfully downloaded reporting logs for task: ${item.task_id}`)
   
  } catch (error: any) {
    console.error('Download failed:', error)
    const errorMessage = error.response?.data?.error || 'Download failed. Please try again.'
    alert(`Download failed: ${errorMessage}`)
  }
}
 
// Download reports and redirect to reporting page
async function downloadReportingReports(index: number) {
  const item = reportingRecords.value[index]
 
  if (item.status !== 'Completed') {
    alert('Report is not ready yet')
    return
  }
 
  try {
    // Call the backend API to get redirect information
    const response = await axios.get(`/api/download_reporting_reports/${item.task_id}`)
   
    if (response.data.redirect) {
      // Navigate to reporting page using Vue Router
      router.push(response.data.url)
    } else {
      alert('No redirect information received')
    }
   
  } catch (error: any) {
    console.error('Download reports failed:', error)
    const errorMessage = error.response?.data?.error || 'Download reports failed. Please try again.'
    alert(`Download reports failed: ${errorMessage}`)
  }
}
 
 
const fetchReviewListFromDB = async () => {
  try {
    const res = await axios.get('/api/get_eclengine_records')
    reviewList.value = res.data.records.map((item: any) => {
      let settings: any = {}
      try { settings = JSON.parse(item.settings) } catch {}
      return {
        id: item.id, // 添加record ID
        maker: item.maker,
        time: item.time,
        reportingDate: settings.reportingDate || '',
        runMode: settings.runMode || '',
        action: item.action,
        status: item.status,
        checker: item.checker,
        approved: false,
        downloaded: false,
        eclResultsDownloaded: false, // Initialize ECL results download status
        taskId: settings.task_id || '',
        timestamp: settings.timestamp || '',
        isResume: settings.isResume || false,
        resumedVersion: settings.resumedVersion || '',
        isGenerateReport: settings.isGenerateReport || false // Add this line
      }
    })
  } catch (e) {
    console.error('Error fetching ECL engine records:', e)
  }
}
 
// Fetch reporting records from database
const fetchReportingRecords = async () => {
  try {
    const response = await axios.get('/api/get_reporting_records')
    // Initialize selected property for each record
    reportingRecords.value = response.data.records.map((record: any) => ({
      ...record,
      selected: false
    }))
  } catch (error) {
    console.error('Error fetching reporting records:', error)
  }
}
 
// Function to fetch resume config files
const fetchResumeConfigFiles = async () => {
  try {
    const resumeConfigResponse = await axios.get('/api/get_uploaded_files?type=resume_config')
    resumeConfigOptions.value = resumeConfigResponse.data.files
    console.log('Resume config files updated:', resumeConfigOptions.value)
  } catch (error) {
    console.error('Error fetching resume config files:', error)
  }
}
 
 
async function onResumeSubmit() {
  if (!canResumeSubmit.value) return
 
  const now = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  const timeStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
  const uiTimestamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
 
  try {
    showProcessPopup.value = true
    processPopupClosed.value = false
 
    const resumeResponse = await axios.post('/api/resume_ecl_engine', {
      selectedResumeConfig: selectedResumeConfig.value,
      selectedResumeRunMode: selectedResumeRunMode.value,
      resumeActionComment: resumeActionComment.value,
      ui_timestamp: uiTimestamp,
      maker: getUserDisplayName()
    })
 
    const taskId = resumeResponse.data.task_id
    const backendTimestamp = resumeResponse.data.timestamp || uiTimestamp
 
    reviewList.value.unshift({
      id: 0, // 临时ID，实际ID会在数据库保存后更新
      maker: getUserDisplayName(),
      time: timeStr,
      reportingDate: '', // Resume run doesn't have reporting date
      runMode: selectedResumeRunMode.value,
      action: resumeActionComment.value,
      status: 'Running',
      checker: 'Waiting',
      approved: false,
      downloaded: false,
      eclResultsDownloaded: false, // Initialize ECL results download status
      taskId,
      timestamp: backendTimestamp,
      isResume: true,
      resumedVersion: selectedResumeConfig.value
    })
 
    const pollStatus = async () => {
      try {
        const statusResponse = await axios.get(`/api/task_status/${taskId}`)
        const status = statusResponse.data.status
        const item = reviewList.value.find(i => i.taskId === taskId)
        if (item) {
          if (status === 'Completed') {
            item.status = 'Completed'
            showProcessPopup.value = false
            if (!processPopupClosed.value) alert('ECL Engine resumed successfully!')
            return
          } else if (status === 'Failed') {
            item.status = 'Failed'
            showProcessPopup.value = false
            if (!processPopupClosed.value) alert('ECL Engine failed to resume')
            return
          } else {
            item.status = 'Running'
          }
        }
        setTimeout(pollStatus, 5000)
      } catch (error: any) {
        showProcessPopup.value = false
        if (!processPopupClosed.value) alert(error.message || 'An error occurred while resuming the ECL engine')
      }
    }
    pollStatus()
 
    // Reset resume form
    selectedResumeConfig.value = ''
    selectedResumeRunMode.value = ''
    resumeActionComment.value = ''
    step3Complete.value = true
   
    // 重新获取resume config files列表
    fetchResumeConfigFiles()
   
    // Reset progress bar after a delay
    setTimeout(() => {
      step3Complete.value = false
    }, 2000)
  } catch (error: any) {
    showProcessPopup.value = false
    if (!processPopupClosed.value) alert(error.message || 'An error occurred while resuming the ECL engine')
  }
}
 
 
// New function to get progress width
function getProgressWidth() {
  if (step1Complete.value && step2Complete.value) {
    return '100%'
  } else if (step1Complete.value) {
    return '50%'
  } else {
    return '0%'
  }
}

// Function to format timestamp from config filename to readable format
function formatResumedVersion(configFilename: string | undefined): string {
  if (!configFilename) return ''
  
  // Extract timestamp from filename like "run_config_file_20250904165803.json"
  const match = configFilename.match(/run_config_file_(\d{14})\.json/)
  if (!match) return configFilename
  
  const timestamp = match[1] // e.g., "20250904165803"
  
  // Format: YYYY-MM-DD HH:MM:SS
  const year = timestamp.substring(0, 4)
  const month = timestamp.substring(4, 6)
  const day = timestamp.substring(6, 8)
  const hour = timestamp.substring(8, 10)
  const minute = timestamp.substring(10, 12)
  const second = timestamp.substring(12, 14)
  
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}
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
.progress-bar {
  height: 5px;
  background: #e3e8f0;
  border-radius: 10px 10px 0 0;
  overflow: hidden;
}
.progress-bar-inner {
  height: 100%;
  background: #153D77;
  transition: width 0.4s cubic-bezier(.4,2,.6,1);
}
.config-inner-box {
  padding: 30px 30px 0 30px;
}
.steps-row {
  display: flex;
  justify-content: space-between;
  gap: 30px;
  margin-bottom: 30px;
}
.step-box {
  flex: 1;
  max-width: 48%;
  background: none;
}
.step-box-full-width {
  flex: 1;
  max-width: 100%;
  background: none;
}
.step-box-right {
  max-width: 100%;
}
.step-title {
  display: flex;
  align-items: center;
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 3px;
  color: #153D77;
}
.step-circle {
  width: 22px;
  height: 22px;
  border: 2px solid #bbb;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  margin-right: 10px;
  background: #fff;
  transition: border-color 0.3s;
}
.step-circle.active {
  border-color: #ff4848;
}
.step-circle.done {
  border-color: #4CAF50;
}
.step-status {
  font-size: 16px;
  color: #999;
  margin-bottom: 8px;
}
.select-input {
  flex: 1;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #ddd;
  font-size: 15px;
}
.select-input-full {
  width: 100%;
  min-width: 0;
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
}
.step-btn:disabled {
  background: #eee;
  color: #bbb;
  cursor: not-allowed;
}
.instructions-box {
  margin-top: 30px;
  background: none;
  padding: 0 10px 0 0;
}
.instructions-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 6px;
  color: #153D77;
}
.instructions-list {
  font-size: 16px;
  color: #666;
  line-height: 1.3;
  margin: 0;
  padding-left: 18px;
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
.step-box .select-input {
  min-width: 180px;
}
.step-box .select-input + .select-input {
  margin-left: 0;
}
.step-btn {
  margin-left: 0;
}
 
.fixed-input {
  flex: 1;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #ddd;
  font-size: 15px;
  background-color: #f5f5f5;
  color: #666;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  font-weight: 500;
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
 