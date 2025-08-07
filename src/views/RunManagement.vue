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
                <div class="step-circle" :class="{ active: !step1Complete, done: step1Complete }">
                  <svg v-if="!step1Complete" style="width:10px; height:10px; stroke:#ff4848;" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="6" x2="12" y2="12" />
                    <line x1="12" y1="18" x2="12" y2="18" />
                  </svg>
                  <svg v-else style="width:10px; height:10px; stroke:#4CAF50;" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 6L9 17l-5-5"/>
                  </svg>
                </div>
                1. Choose Configuration File
              </div>
              <div class="step-status">{{ step1Complete ? 'Complete' : 'Incomplete' }}</div>
              <div style="display: flex; gap: 10px; margin-bottom: 15px; flex-direction: column;">
                <div style="display: flex; gap: 10px;">
                  <select v-model="selectedParameters" class="select-input">
                    <option disabled value="">Select parameters</option>
                    <option v-for="param in parametersOptions" :key="param" :value="param">{{ param }}</option>
                  </select>
                  <select v-model="selectedCorrections" class="select-input">
                    <option disabled value="">Select adjustments</option>
                    <option v-for="correction in correctionsOptions" :key="correction" :value="correction">{{ correction }}</option>
                  </select>
                </div>
                <div style="display: flex; gap: 10px;">
                  <select v-model="selectedReportingDate" class="select-input">
                    <option disabled value="">Select current reporting date</option>
                    <option v-for="date in reportingDateOptions" :key="date" :value="date">{{ date }}</option>
                  </select>
                </div>
              </div>
              <div style="text-align: right; margin-top: 8px;">
                <button @click="onContinue" :disabled="!canContinue" class="step-btn">Continue</button>
              </div>
            </div>
            <div class="step-box">
              <div class="step-title">
                <div class="step-circle" :class="{ active: step1Complete }">
                  <svg style="width:10px; height:10px; stroke:#4CAF50;" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 6L9 17l-5-5"/>
                  </svg>
                </div>
                2. Initiate Run
              </div>
              <div class="step-status">{{ step1Complete ? 'Ready to submit' : 'Complete Step 1 to enable' }}</div>
              <div style="display: flex; gap: 10px; margin-bottom: 15px; flex-direction: column;">
                <div style="display: flex; gap: 10px;">
                  <select v-model="selectedRunMode" :disabled="!step1Complete" class="select-input">
                    <option disabled value="">Select Run mode</option>
                    <option v-for="mode in runModes" :key="mode" :value="mode">{{ mode }}</option>
                  </select>
                  <select v-model="selectedCountry" :disabled="!step1Complete" class="select-input">
                    <option disabled value="">Select country</option>
                    <option v-for="country in countryOptions" :key="country" :value="country">{{ country }}</option>
                  </select>
                </div>
                <div style="display: flex; gap: 10px;">
                  <input v-model="actionComment" :disabled="!step1Complete" placeholder="Provide action comment here" class="select-input" style="flex: 1;" />
                </div>
              </div>
              <div style="text-align: right; margin-top: 8px;">
                <button @click="onSubmit" :disabled="!canSubmit" class="step-btn">Submit</button>
              </div>
            </div>
          </div>
          <div class="steps-row">
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
                3. Resume Run
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
            <div class="step-box">
              <div class="step-title">
                <div class="step-circle" :class="{ active: !step4Complete, done: step4Complete }">
                  <svg v-if="!step4Complete" style="width:10px; height:10px; stroke:#ff4848;" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="6" x2="12" y2="12" />
                    <line x1="12" y1="18" x2="12" y2="18" />
                  </svg>
                  <svg v-else style="width:10px; height:10px; stroke:#4CAF50;" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 6L9 17l-5-5"/>
                  </svg>
                </div>
                4. Generate Report
              </div>
              <div class="step-status">{{ step4Complete ? 'Complete' : 'Ready to generate report' }}</div>
              <div style="display: flex; gap: 10px; margin-bottom: 15px; flex-direction: column;">
                <div style="display: flex; gap: 10px;">
                  <select v-model="selectedReportConfig" :disabled="step4Complete" class="select-input">
                    <option disabled value="">Select configuration file</option>
                    <option v-for="config in reportConfigOptions" :key="config" :value="config">{{ config }}</option>
                  </select>
                  <div class="fixed-input">Run mode 6</div>
                </div>
                <div style="display: flex; gap: 10px;">
                  <input v-model="reportActionComment" :disabled="step4Complete" placeholder="Provide action comment here" class="select-input" style="flex: 1;" />
                </div>
              </div>
              <div style="text-align: right; margin-top: 8px;">
                <button @click="onGenerateReportSubmit" :disabled="!canGenerateReportSubmit || step4Complete" class="step-btn">{{ step4Complete ? 'Completed' : 'Generate Report' }}</button>
              </div>
            </div>
          </div>
          <div class="instructions-box">
            <p class="instructions-title">Instructions:</p>
            <ul class="instructions-list">
              <li>1. Please choose parameters and adjustments. If no changes, please choose default and continue.</li>
              <li>2. Please choose run mode and fill in action comment.</li>
              <li>3. Submit to generate the run record.</li>
              <li>4. To resume a failed run, select the configuration file and choose the resume run mode.</li>
              <li>5. To generate reports, select the configuration file and run mode will be fixed to 6.</li>
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
        <div style="max-height: 640px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; background: white; min-width: 1200px;">
          <table style="width: 100%; border-collapse: collapse; background: white;">
            <thead style="background: #f7f7f7; position: sticky; top: 0; z-index: 1;">
              <tr>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 40px;"></th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Maker</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 160px;">Time</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 280px;">Settings</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Action</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Status</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Checker</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 40px;">Download Logs</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in reviewList" :key="index" :style="{ backgroundColor: item.approved ? '#e8f5e9' : '#fff' }">
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                  <input v-if="item.isGenerateReport" type="radio" name="review-select" :checked="selectedReviewIndex === index" @change="selectReview(index)" />
                </td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.maker }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.time }}</td>
                <td style="text-align: left; padding: 16px 18px; border-bottom: 1px solid #e0e0e0; min-width: 260px; font-size: 15px; line-height: 1.7;">
                  <div v-if="item.isResume" class="param-item">
                    <span class="param-label">Resumed version:</span> <span class="param-value">{{ item.resumedVersion }}</span>
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
                    <span class="param-label">Parameter:</span> <span class="param-value">{{ item.parameter }}</span>
                  </div>
                  <div v-if="!item.isResume && !item.isGenerateReport" class="param-item">
                    <span class="param-label">Adjustment:</span> <span class="param-value">{{ item.adjustment }}</span>
                  </div>
                  <div v-if="!item.isResume && !item.isGenerateReport" class="param-item">
                    <span class="param-label">Reporting Date:</span> <span class="param-value">{{ item.reportingDate }}</span>
                  </div>
                  <div v-if="!item.isResume && !item.isGenerateReport" class="param-item">
                    <span class="param-label">Run mode:</span> <span class="param-value">{{ item.runMode }}</span>
                  </div>
                  <div v-if="!item.isResume && !item.isGenerateReport" class="param-item">
                    <span class="param-label">Country:</span> <span class="param-value">{{ item.country }}</span>
                  </div>
                </td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.action }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.status }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.checker }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                  <button @click="downloadRow(index)" :style="{ color: item.downloaded ? '#4CAF50' : '#333', cursor: 'pointer', fontSize: '20px', background: 'none', border: 'none' }">⬇️</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="margin-top: 15px; text-align: right;">
          <button class="upload-button" style="background: #FF612C;" @click="approveSelected">Confirm</button>
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
  </div>
</template>
 
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
 
// Define the type for review list items
interface ReviewItem {
  maker: string
  time: string
  parameter: string
  adjustment: string
  reportingDate: string
  runMode: string
  country: string
  action: string
  status: string
  checker: string
  approved: boolean
  downloaded: boolean
  taskId?: string // Added taskId to the interface
  timestamp?: string // Added timestamp to the interface
  isResume?: boolean // Added isResume flag
  resumedVersion?: string // Added resumedVersion for resume records
  isGenerateReport?: boolean // Added isGenerateReport flag
}
 
// Replace hardcoded options with dynamic lists
const parametersOptions = ref<string[]>([])
const correctionsOptions = ref<string[]>([])
const runModes = ['0','1','2','3','0-5','1-5','2-5','3-5','4-5']
 
// Country selection
const countryOptions = ['All', 'Hong Kong', 'Macau', 'Singapore', 'Others']
 
// Reporting date options
const reportingDateOptions = ['2024-12-31', '2024-06-30', '2024-03-31', '2023-12-31', '2023-06-30']
 
const selectedParameters = ref('')
const selectedCorrections = ref('')
const selectedReportingDate = ref('')
const selectedRunMode = ref('')
const selectedCountry = ref('')
const actionComment = ref('')

// Resume run variables
const selectedResumeConfig = ref('')
const selectedResumeRunMode = ref('')
const resumeActionComment = ref('')
const resumeConfigOptions = ref<string[]>([])
const resumeRunModes = ['1-5','2-5','3-5','4-5']

// Generate Report variables
const selectedReportConfig = ref('')
const selectedReportRunMode = ref('6') // Fixed to 6
const reportActionComment = ref('')
const reportConfigOptions = ref<string[]>([])

const step1Complete = ref(false)
const step2Complete = ref(false)
const step3Complete = ref(false) // Added step3Complete
const step4Complete = ref(false) // Added step4Complete
 
// Review list with localStorage persistence
const reviewList = ref<ReviewItem[]>([])
 
// Add new refs for process monitoring
const showProcessPopup = ref(false)
const processPopupClosed = ref(false)
 
function closeProcessPopup() {
  showProcessPopup.value = false
  processPopupClosed.value = true
}
 
function onContinue() {
  if (canContinue.value) {
    step1Complete.value = true
  }
}
 
// Function to fetch uploaded files from backend
const fetchUploadedFiles = async () => {
  try {
    // Fetch parameters
    const paramResponse = await axios.get('https://10.25.108.72/api/get_uploaded_files?type=parameter')
    parametersOptions.value = paramResponse.data.files
   
    // Fetch adjustments
    const corrResponse = await axios.get('https://10.25.108.72/api/get_uploaded_files?type=adjustment')
    correctionsOptions.value = corrResponse.data.files
  } catch (error) {
    console.error('Error fetching uploaded files:', error)
  }
}
 
const canContinue = computed(() => selectedParameters.value !== '' && selectedCorrections.value !== '' && selectedReportingDate.value !== '')
const canSubmit = computed(() => step1Complete.value && selectedRunMode.value !== '' && selectedCountry.value !== '' && actionComment.value.trim() !== '')
const canResumeSubmit = computed(() => selectedResumeConfig.value !== '' && selectedResumeRunMode.value !== '' && resumeActionComment.value.trim() !== '')
const canGenerateReportSubmit = computed(() => selectedReportConfig.value !== '' && reportActionComment.value.trim() !== '')

// Load data when component mounts
onMounted(() => {
  fetchReviewListFromDB()
  fetchUploadedFiles() // Fetch uploaded files when component mounts
  fetchResumeConfigFiles() // Fetch resume config files
  fetchReportConfigFiles() // Fetch report config files
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
    const runResponse = await axios.post('https://10.25.108.72/api/run_ecl_engine', {
      selectedParameters: selectedParameters.value,
      selectedCorrections: selectedCorrections.value,
      reportingDate: selectedReportingDate.value,
      runMode: selectedRunMode.value,
      country: selectedCountry.value,
      action: actionComment.value,
      ui_timestamp: uiTimestamp
    })
 
    const taskId = runResponse.data.task_id
    const backendTimestamp = runResponse.data.timestamp || uiTimestamp
 
    // 立即添加到review列表，初始状态为 Running
    reviewList.value.unshift({
      maker: 'RMGUser_1',
      time: timeStr,
      parameter: selectedParameters.value,
      adjustment: selectedCorrections.value,
      reportingDate: selectedReportingDate.value,
      runMode: selectedRunMode.value,
      country: selectedCountry.value,
      action: actionComment.value,
      status: 'Running',
      checker: 'Waiting',
      approved: false,
      downloaded: false,
      taskId, // 新增字段
      timestamp: backendTimestamp // 保存timestamp用于后续查找
    })

    // 轮询任务状态
    const pollStatus = async () => {
      try {
        const statusResponse = await axios.get(`https://10.25.108.72/api/task_status/${taskId}`)
        const status = statusResponse.data.status
        // 找到对应的review item，更新status
        const item = reviewList.value.find(i => i.taskId === taskId)
        if (item) {
          if (status === 'completed') {
            item.status = 'Completed'
            showProcessPopup.value = false
            if (!processPopupClosed.value) alert('ECL Engine completed successfully!')
            return
          } else if (status === 'failed') {
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
    step1Complete.value = false
    step2Complete.value = false
    selectedParameters.value = ''
    selectedCorrections.value = ''
    selectedReportingDate.value = ''
    selectedRunMode.value = ''
    selectedCountry.value = ''
    actionComment.value = ''
    
    // 重新获取resume config files列表，包含新生成的config file
    fetchResumeConfigFiles()
    fetchReportConfigFiles()
    
    // Set step2Complete to true to show 100% progress
    step2Complete.value = true
 
  } catch (error: any) {
    showProcessPopup.value = false
    if (!processPopupClosed.value) alert(error.message || 'An error occurred while running the ECL engine')
  }
}
 
const router = useRouter()
 
// Add a ref to track the selected review index
const selectedReviewIndex = ref<number | null>(null)
 
function selectReview(index: number) {
  selectedReviewIndex.value = index
}
 
async function downloadRow(index: number) {
  const item = reviewList.value[index]
  
  if (!item.taskId) {
    alert('No task ID found for this record')
    return
  }
  
  try {
    // Show loading state
    item.downloaded = false
    
    // Call the backend API to download log files
    const response = await axios.get(`https://10.25.108.72/api/download_log_files/${item.taskId}`, {
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
    
    // Update download status
  item.downloaded = true
    console.log(`Successfully downloaded log files for task: ${item.taskId}`)
    
  } catch (error: any) {
    console.error('Download failed:', error)
    const errorMessage = error.response?.data?.error || 'Download failed. Please try again.'
    alert(`Download failed: ${errorMessage}`)
    item.downloaded = false
  }
}
 
async function approveSelected() {
  if (selectedReviewIndex.value === null) return
  const item = reviewList.value[selectedReviewIndex.value]
  if (item && item.isGenerateReport) {
    // Get the timestamp from the selected record
    const timestamp = item.timestamp
    if (timestamp) {
      // Check if reports are available for this timestamp before navigating
      checkReportAvailability(timestamp).then(async hasReports => {
        if (hasReports) {
          // Confirm ECL result and log the confirmation
          try {
            await axios.post('https://10.25.108.72/api/confirm_ecl_result', {
              task_id: item.taskId,
              timestamp: timestamp
            })
            
            // Reports are available, navigate to reporting page
            item.approved = true
            item.status = 'Confirmed'
            item.checker = 'RMGUser_2'
            router.push({
              path: '/reporting',
              query: { 
                timestamp: timestamp
              }
            })
          } catch (error) {
            console.error('Error confirming ECL result:', error)
            alert('Error confirming ECL result. Please try again.')
          }
        } else {
          // No reports available, show error message
          alert('No reports available for this record. Please ensure the ECL Engine has completed successfully and generated reports.')
        }
      }).catch(error => {
        console.error('Error checking report availability:', error)
        alert('Error checking report availability. Please try again.')
      })
    } else {
      // No timestamp available
      alert('No output folder found for this record.')
    }
  } else {
    alert('Only Generate Report records can be confirmed for reporting.')
  }
}

// Add function to check report availability
async function checkReportAvailability(timestamp: string): Promise<boolean> {
  try {
    const response = await axios.get(`https://10.25.108.72/api/check_report_availability/${timestamp}`)
    return response.data.has_reports
  } catch (error) {
    console.error('Error checking report availability:', error)
    return false
  }
}

const fetchReviewListFromDB = async () => {
  try {
    const res = await axios.get('https://10.25.108.72/api/get_eclengine_records')
    reviewList.value = res.data.records.map((item: any) => {
      let settings: any = {}
      try { settings = JSON.parse(item.settings) } catch {}
      return {
        maker: item.maker,
        time: item.time,
        parameter: settings.selectedParameters || '',
        adjustment: settings.selectedCorrections || '',
        reportingDate: settings.reportingDate || '',
        runMode: settings.runMode || '',
        country: settings.country || '',
        action: item.action,
        status: item.status,
        checker: item.checker,
        approved: false,
        downloaded: false,
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

// Function to fetch resume config files
const fetchResumeConfigFiles = async () => {
  try {
    const resumeConfigResponse = await axios.get('https://10.25.108.72/api/get_uploaded_files?type=resume_config')
    resumeConfigOptions.value = resumeConfigResponse.data.files
    console.log('Resume config files updated:', resumeConfigOptions.value)
  } catch (error) {
    console.error('Error fetching resume config files:', error)
  }
}

// Function to fetch report config files
const fetchReportConfigFiles = async () => {
  try {
    const reportConfigResponse = await axios.get('https://10.25.108.72/api/get_uploaded_files?type=report_config')
    reportConfigOptions.value = reportConfigResponse.data.files
    console.log('Report config files updated:', reportConfigOptions.value)
  } catch (error) {
    console.error('Error fetching report config files:', error)
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

    const resumeResponse = await axios.post('https://10.25.108.72/api/resume_ecl_engine', {
      selectedResumeConfig: selectedResumeConfig.value,
      selectedResumeRunMode: selectedResumeRunMode.value,
      resumeActionComment: resumeActionComment.value,
      ui_timestamp: uiTimestamp
    })

    const taskId = resumeResponse.data.task_id
    const backendTimestamp = resumeResponse.data.timestamp || uiTimestamp

    reviewList.value.unshift({
      maker: 'RMGUser_1',
      time: timeStr,
      parameter: '', // Resume run doesn't have parameters
      adjustment: '', // Resume run doesn't have adjustments
      reportingDate: '', // Resume run doesn't have reporting date
      runMode: selectedResumeRunMode.value,
      country: '', // Resume run doesn't have country
      action: resumeActionComment.value,
      status: 'Running',
      checker: 'Waiting',
      approved: false,
      downloaded: false,
      taskId,
      timestamp: backendTimestamp,
      isResume: true,
      resumedVersion: selectedResumeConfig.value
    })

    const pollStatus = async () => {
      try {
        const statusResponse = await axios.get(`https://10.25.108.72/api/task_status/${taskId}`)
        const status = statusResponse.data.status
        const item = reviewList.value.find(i => i.taskId === taskId)
        if (item) {
          if (status === 'completed') {
            item.status = 'Completed'
            showProcessPopup.value = false
            if (!processPopupClosed.value) alert('ECL Engine resumed successfully!')
            return
          } else if (status === 'failed') {
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
    fetchReportConfigFiles()
    
    // Reset progress bar after a delay
    setTimeout(() => {
      step3Complete.value = false
    }, 2000)
  } catch (error: any) {
    showProcessPopup.value = false
    if (!processPopupClosed.value) alert(error.message || 'An error occurred while resuming the ECL engine')
  }
}

async function onGenerateReportSubmit() {
  if (!canGenerateReportSubmit.value) return

  const now = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  const timeStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
  const uiTimestamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`

  try {
    showProcessPopup.value = true
    processPopupClosed.value = false

    const reportResponse = await axios.post('https://10.25.108.72/api/generate_report', {
      selectedReportConfig: selectedReportConfig.value,
      selectedReportRunMode: selectedReportRunMode.value,
      reportActionComment: reportActionComment.value,
      ui_timestamp: uiTimestamp
    })

    const taskId = reportResponse.data.task_id
    const backendTimestamp = reportResponse.data.timestamp || uiTimestamp

    reviewList.value.unshift({
      maker: 'RMGUser_1',
      time: timeStr,
      parameter: '', // Report generation doesn't have parameters
      adjustment: '', // Report generation doesn't have adjustments
      reportingDate: '', // Report generation doesn't have reporting date
      runMode: selectedReportRunMode.value,
      country: '', // Report generation doesn't have country
      action: reportActionComment.value,
      status: 'Running',
      checker: 'Waiting',
      approved: false,
      downloaded: false,
      taskId,
      timestamp: backendTimestamp,
      isResume: false, // It's a report generation task
      resumedVersion: selectedReportConfig.value,
      isGenerateReport: true // Set this flag for report generation
    })

    const pollStatus = async () => {
      try {
        const statusResponse = await axios.get(`https://10.25.108.72/api/task_status/${taskId}`)
        const status = statusResponse.data.status
        const item = reviewList.value.find(i => i.taskId === taskId)
        if (item) {
          if (status === 'completed') {
            item.status = 'Completed'
            showProcessPopup.value = false
            if (!processPopupClosed.value) alert('Report generation completed successfully!')
            return
          } else if (status === 'failed') {
            item.status = 'Failed'
            showProcessPopup.value = false
            if (!processPopupClosed.value) alert('Report generation failed')
            return
          } else {
            item.status = 'Running'
          }
        }
        setTimeout(pollStatus, 5000)
      } catch (error: any) {
        showProcessPopup.value = false
        if (!processPopupClosed.value) alert(error.message || 'An error occurred while generating the report')
      }
    }
    pollStatus()

    // Reset report form
    selectedReportConfig.value = ''
    selectedReportRunMode.value = ''
    reportActionComment.value = ''
    step4Complete.value = true
    
    // 重新获取report config files列表
    fetchReportConfigFiles()
    
    // Reset progress bar after a delay
    setTimeout(() => {
      step4Complete.value = false
    }, 2000)
  } catch (error: any) {
    showProcessPopup.value = false
    if (!processPopupClosed.value) alert(error.message || 'An error occurred while generating the report')
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
 