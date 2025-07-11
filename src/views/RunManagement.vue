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
          <div class="progress-bar-inner" :style="{ width: step2Complete ? '100%' : step1Complete ? '50%' : '0%' }"></div>
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
                    <option disabled value="">Select data corrections</option>
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
          <div class="instructions-box">
            <p class="instructions-title">Instructions:</p>
            <ul class="instructions-list">
              <li>1. Please choose parameters and data corrections. If no changes, please choose default and continue.</li>
              <li>2. Please choose run mode and fill in action comment.</li>
              <li>3. Submit to generate the run record.</li>
            </ul>
          </div>
        </div>
      </div>
      
      <!-- Review Box -->
      <div>
        <h2 style="font-size: 20px; font-weight: 600; margin-bottom: 8px;">Review</h2>
        <table style="margin-top: 8px; width: 100%; border-collapse: collapse; background: white; border: 1px solid #e0e0e0;">
          <thead style="background: #f7f7f7;">
            <tr>
              <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 60px;"></th>
              <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Maker</th>
              <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 210px;">Time</th>
              <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 260px;">Settings</th>
              <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 150px;">Action</th>
              <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 120px;">Status</th>
              <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 120px;">Checker</th>
              <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Download</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in reviewList" :key="index" :style="{ backgroundColor: item.approved ? '#e8f5e9' : '#fff' }">
              <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">
                <input type="radio" name="review-select" :checked="selectedReviewIndex === index" @change="selectReview(index)" />
              </td>
              <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.maker }}</td>
              <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.time }}</td>
              <td class="parameters-cell">
                <div class="param-item"><span class="param-label">Parameter:</span> <span class="param-value">{{ item.parameter }}</span></div>
                <div class="param-item"><span class="param-label">Data Correction:</span> <span class="param-value">{{ item.dataCorrection }}</span></div>
                <div class="param-item"><span class="param-label">Reporting Date:</span> <span class="param-value">{{ item.reportingDate }}</span></div>
                <div class="param-item"><span class="param-label">Run mode:</span> <span class="param-value">{{ item.runMode }}</span></div>
                <div class="param-item"><span class="param-label">Country:</span> <span class="param-value">{{ item.country }}</span></div>
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
        <div style="margin-top: 15px; text-align: right;">
          <button class="upload-button" style="background: #FF612C;" @click="approveSelected">Confirm</button>
        </div>
      </div>

    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

// Define the type for review list items
interface ReviewItem {
  maker: string
  time: string
  parameter: string
  dataCorrection: string
  reportingDate: string
  runMode: string
  country: string
  action: string
  status: string
  checker: string
  approved: boolean
  downloaded: boolean
}

const parametersOptions = ['Default Parameters', 'Parameter Set 1', 'Parameter Set 2']
const correctionsOptions = ['No Correction', 'Correction A', 'Correction B']
const runModes = ['Full Run', 'Partial Run', 'Test Run']

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

const step1Complete = ref(false)
const step2Complete = ref(false)

// Review list with localStorage persistence
const reviewList = ref<ReviewItem[]>([])

const canContinue = computed(() => selectedParameters.value !== '' && selectedCorrections.value !== '' && selectedReportingDate.value !== '')
const canSubmit = computed(() => step1Complete.value && selectedRunMode.value !== '' && selectedCountry.value !== '' && actionComment.value.trim() !== '')

// Load saved data from localStorage
const loadState = () => {
  const savedReviewList = localStorage.getItem('runManagementReviewList')
  if (savedReviewList) {
    reviewList.value = JSON.parse(savedReviewList)
  }
}

// Save data to localStorage
const saveState = () => {
  localStorage.setItem('runManagementReviewList', JSON.stringify(reviewList.value))
}

// Handle page refresh - clear localStorage
const handleBeforeUnload = () => {
  localStorage.removeItem('runManagementReviewList')
}

// Load data when component mounts
onMounted(() => {
  loadState()
  window.addEventListener('beforeunload', handleBeforeUnload)
})

// Clean up event listener
onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

function onContinue() {
  if (canContinue.value) {
    step1Complete.value = true
  }
}

function onSubmit() {
  if (!canSubmit.value) return

  const now = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  const timeStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

  reviewList.value.unshift({
    maker: 'RMGUser_1',
    time: timeStr,
    parameter: selectedParameters.value,
    dataCorrection: selectedCorrections.value,
    reportingDate: selectedReportingDate.value,
    runMode: selectedRunMode.value,
    country: selectedCountry.value,
    action: actionComment.value,
    status: 'In review',
    checker: 'Waiting',
    approved: false,
    downloaded: false,
  })
  
  // Reset form for next submission - allow user to select new parameters
  step1Complete.value = false
  step2Complete.value = false
  selectedParameters.value = ''
  selectedCorrections.value = ''
  selectedReportingDate.value = ''
  selectedRunMode.value = ''
  selectedCountry.value = ''
  actionComment.value = ''
  
  saveState() // Save to localStorage
}

const router = useRouter()

// Add a ref to track the selected review index
const selectedReviewIndex = ref<number | null>(null)

function selectReview(index: number) {
  selectedReviewIndex.value = index
}

function downloadRow(index: number) {
  const item = reviewList.value[index]
  const blob = new Blob([], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'dummy_run_ecl_engine.zip'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  item.downloaded = true
  saveState() // Save to localStorage
}

function approveSelected() {
  if (selectedReviewIndex.value === null) return
  const item = reviewList.value[selectedReviewIndex.value]
  if (item) {
    item.approved = true
    item.status = 'Confirmed'
    item.checker = 'RMGUser_2'
    saveState() // Save to localStorage
    // After confirming, navigate to the reporting page
    router.push('/reporting')
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
  background: #f8fafc;
  border-radius: 8px;
  min-width: 260px;
  font-size: 15px;
  line-height: 1.7;
  box-shadow: 0 1px 4px rgba(21,61,119,0.04);
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
</style>
