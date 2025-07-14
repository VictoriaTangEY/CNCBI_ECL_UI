<template>
  <div style="display: flex; min-height: 100vh; margin-top: 95px;">
    <!-- 左侧导航栏 -->
    <aside style="width: 280px; background-color: #f5f5f5; padding: 30px 20px;">
      <h3 style="font-weight: bold; font-size: 22px; margin-bottom: 24px;">Parameters</h3>
      <ul style="list-style: none; padding-left: 0;">
        <li @click="currentTab = 'parameter'" :style="{ cursor: 'pointer', color: currentTab === 'parameter' ? '#ff612c' : '#333', fontWeight: currentTab === 'parameter' ? '600' : 'normal', marginBottom: '10px', fontSize: '20px' }">▸ Parameter</li>
        <li @click="currentTab = 'adjustment'" :style="{ cursor: 'pointer', color: currentTab === 'adjustment' ? '#ff612c' : '#333', fontWeight: currentTab === 'adjustment' ? '600' : 'normal', fontSize: '20px' }">▸ Adjustment</li>
      </ul>
    </aside>

    <!-- 主体内容 -->
    <main style="flex-grow: 1; padding: 40px;">

      <!-- 面包屑导航 -->
      <nav aria-label="breadcrumb" class="breadcrumb-nav">
        <ol class="breadcrumb-list">
          <li><svg style="width:16px; height:16px; fill:#666; vertical-align:middle;" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg> Home</li>
          <li>Parameter</li>
          <li>{{ currentTab === 'parameter' ? 'Parameter' : 'Adjustment' }}</li>
        </ol>
      </nav>

      <!-- Configuration Box with Progress Bar -->
      <div class="config-outer-box">
        <div class="progress-bar">
          <div class="progress-bar-inner" :style="{ width: uploadTried ? '100%' : '0%' }"></div>
        </div>
        <div class="config-inner-box">
          <h2 class="upload-title">{{ currentTab === 'parameter' ? 'Upload Parameter' : 'Upload Adjustment' }}</h2>
          <div style="display: flex; justify-content: center;">
            <div class="upload-box" :class="{ dragging: isDragging, 'has-file': selectedFile, success: uploadSuccess }" @dragover.prevent="onDragOver" @dragleave.prevent="onDragLeave" @drop.prevent="onDrop" @click="triggerFileInput">
              <input type="file" @change="handleFileChange" class="file-input" ref="fileInput" accept=".xlsx,.xls,.csv,.txt,.json,.docx,.pdf,.zip">
              <div class="upload-icon-text">
                <svg v-if="!selectedFile" width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M32 44V20M32 20L22 30M32 20L42 30" stroke="#B88A7A" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><rect x="12" y="44" width="40" height="8" rx="4" fill="#F8E6E3" stroke="#E9B8A7" stroke-width="2"/></svg>
                <p class="drop-text">{{ selectedFile ? selectedFile.name : 'Drop file or click here to browse' }}</p>
              </div>
              <p v-if="selectedFile" class="file-info">{{ formatFileSize(selectedFile.size) }}</p>
              <button v-if="selectedFile" @click.stop="uploadFile" class="upload-button">Upload File</button>
              <div v-if="message" class="message" :class="messageClass">{{ message }}</div>
            </div>
          </div>
          <!-- 版本名输入框，放在upload box下方 -->
          <div style="margin: 18px auto 0; max-width: 600px; display: flex; gap: 10px; justify-content: center;">
            <!-- Parameter/Data Correction Category Selection -->
            <select
              v-model="selectedCategory"
              class="version-control"
              style="width: 300px; min-width: 300px; height: 35px; padding: 0 15px; font-size: 15px;"
            >
              <option value="" disabled>{{ currentTab === 'parameter' ? 'Select Parameter Category' : 'Select Adjustment Category' }}</option>
              <option v-for="category in currentTab === 'parameter' ? parameterCategories : adjustmentCategories" 
                      :key="category" 
                      :value="category"
                      style="padding: 10px 0;"
              >
                {{ category }}
              </option>
            </select>
            <input
              v-model="versionSuffix"
              :placeholder="currentTab === 'parameter' ? 'Enter parameter version name' : 'Enter adjustment version name'"
              class="version-control"
              style="width: 300px; min-width: 300px; height: 35px; padding: 0 15px; font-size: 15px;"
            />
          </div>
          <!-- Instructions box -->
          <div class="instructions-box no-bg" style="margin-top: 0px;">
            <p class="instructions-title">Instructions:</p>
            <ul class="instructions-list">
              <li>1. Select category from the dropdown list.</li>
              <li>2. Enter the version name (If not entered, will use timestamp as default).</li>
              <li>3. Select and upload your file.</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Review Box -->
      <div style="margin-top: 50px;">
        <h2 style="font-size: 20px; font-weight: 600; margin-bottom: 0;">Review</h2>
        <div style="max-height: 640px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; background: white; min-width: 1200px;">

          <table style="width: 100%; border-collapse: collapse; background: white;">
            <thead style="background: #f7f7f7; position: sticky; top: 0; z-index: 1;">
              <tr>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 40px;"><input type="checkbox" v-model="allSelected"></th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 80px;">Maker</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 160px;">Time</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 80px;">Type</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 80px;">Category</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 80px;">Action</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Status</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 100px;">Checker</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center; min-width: 40px;">Download</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in reviewList" :key="index" :style="{ backgroundColor: item.approved ? '#e8f5e9' : '#fff' }">
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;"><input type="checkbox" v-model="item.selected"></td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.maker }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.time }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.type }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.category || '-' }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">upload: {{ item.type === 'Parameter' ? 'par' : 'adj' }}_{{ item.timestamp }}_{{ item.category }}_{{ item.suffix }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.status }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;">{{ item.checker }}</td>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #e0e0e0;"><button @click="downloadRow(index)" :style="{ color: item.downloaded ? '#4CAF50' : '#333', cursor: 'pointer', fontSize: '20px', background: 'none', border: 'none' }">⬇️</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="margin-top: 3px; text-align: right;">
          <button class="upload-button" style="background: #FF612C;" @click="approveSelected">Approve</button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import axios from 'axios'

const currentTab = ref<'parameter' | 'adjustment'>('parameter')
const selectedFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const message = ref('')
const isDragging = ref(false)
const uploadSuccess = ref(false)
const uploadTried = ref(false)

// Suffix
const versionSuffix = ref('')
// Current timestamp
const currentTimestamp = ref('')

// Unified review list with localStorage persistence
const reviewList = ref<any[]>([])

const messageClass = computed(() => message.value.includes('✅') ? 'success' : message.value.includes('❌') ? 'error' : 'info')

const allSelected = computed({
  get: () => reviewList.value.length > 0 && reviewList.value.every(item => item.selected),
  set: (val: boolean) => {
    reviewList.value.forEach(item => item.selected = val)
  }
})

const selectedCategory = ref('')
const parameterCategories = ['CCF', 'haircut', 'model segment']
const adjustmentCategories = ['CCF', 'haircut', 'model segment']

// Generate current timestamp
const generateTimestamp = () => {
  const now = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

// Watch for tab changes and clear upload box
watch(currentTab, () => {
  selectedFile.value = null
  message.value = ''
  uploadSuccess.value = false
  uploadTried.value = false
  if (fileInput.value) fileInput.value.value = ''
  // 切换tab时清空versionSuffix和selectedCategory
  versionSuffix.value = ''
  selectedCategory.value = ''
  // 更新时间戳
  currentTimestamp.value = generateTimestamp()
})

// Load saved data from localStorage
const loadState = () => {
  // Check if this is a page refresh by looking for a session flag
  const isRefresh = sessionStorage.getItem('isRefresh')
  if (isRefresh) {
    // This is a refresh, clear localStorage and reset
    localStorage.removeItem('parameterReviewList')
    sessionStorage.removeItem('isRefresh')
    reviewList.value = []
  } else {
    // This is navigation, load saved data
    const savedReviewList = localStorage.getItem('parameterReviewList')
    if (savedReviewList) {
      reviewList.value = JSON.parse(savedReviewList)
    }
  }
}

// Save data to localStorage
const saveState = () => {
  localStorage.setItem('parameterReviewList', JSON.stringify(reviewList.value))
}

// Handle page refresh - set session flag
const handleBeforeUnload = () => {
  sessionStorage.setItem('isRefresh', 'true')
}

// Load data when component mounts
onMounted(() => {
  loadState()
  window.addEventListener('beforeunload', handleBeforeUnload)
  // 初始化时间戳
  currentTimestamp.value = generateTimestamp()
})

// Clean up event listener
onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

const triggerFileInput = (e: Event) => {
  if ((e.target as HTMLElement).classList.contains('upload-button')) return
  fileInput.value?.click()
}

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files?.[0]) {
    selectedFile.value = target.files[0]
    message.value = ''
    uploadSuccess.value = false
  }
}

const onDragOver = () => isDragging.value = true
const onDragLeave = () => isDragging.value = false
const onDrop = (e: DragEvent) => {
  isDragging.value = false
  if (e.dataTransfer?.files?.length) {
    selectedFile.value = e.dataTransfer.files[0]
    message.value = ''
    uploadSuccess.value = false
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' bytes'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

const uploadFile = async () => {
  if (!selectedFile.value) return
  if (!selectedCategory.value) {
    message.value = '❌ Please select a category'
    return
  }

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('fileType', currentTab.value)
  formData.append('suffix', versionSuffix.value.trim())
  formData.append('category', selectedCategory.value)

  try {
    message.value = '⏳ Uploading...'
    const response = await axios.post('http://127.0.0.1:5010/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    message.value = '✅ ' + response.data.message
    uploadSuccess.value = true
    fileInput.value!.value = ''
    uploadTried.value = true

    const now = new Date()
    const pad = (n: number) => n.toString().padStart(2, '0')
    const timeStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
    // Use version name or timestamp as default
    const userInput = versionSuffix.value.trim()
    const versionName = userInput ? `${currentTimestamp.value}_${userInput}` : currentTimestamp.value
    const newRecord = {
      maker: 'RMGUser_1',
      time: timeStr,
      type: currentTab.value === 'parameter' ? 'Parameter' : 'Adjustment',
      category: selectedCategory.value,
      timestamp: currentTimestamp.value,
      suffix: versionSuffix.value.trim(),
      action: currentTab.value === 'parameter' ? `Upload Parameters: ${versionName}` : `Upload Adjustments: ${versionName}`,
      status: 'In review',
      checker: 'Waiting',
      approved: false,
      downloaded: false,
      selected: false,
      file: selectedFile.value // Store the file before clearing it
    }

    reviewList.value.unshift(newRecord)
    selectedFile.value = null // Clear after storing in record
    saveState() // Save to localStorage
  } catch (error: any) {
    message.value = '❌ ' + (error.response?.data?.error || 'Upload failed.')
    uploadSuccess.value = false
    uploadTried.value = true
  }
}

const downloadRow = (index: number) => {
  const item = reviewList.value[index]
  if (item.file) {
    // Create a download link
    const url = URL.createObjectURL(item.file)
    const a = document.createElement('a')
    a.href = url
    a.download = item.file.name
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    
    item.downloaded = true
    saveState() // Save to localStorage
  }
}

const approveSelected = () => {
  reviewList.value.forEach(item => {
    if (item.selected) {
      item.approved = true
      item.status = 'Approved'
      item.checker = 'RMGUser_2'
    }
  })
  saveState() // Save to localStorage
}
</script>


<style scoped>
.upload-box {
  width: 400px;
  height: 220px;
  border: 2px dashed #E9B8A7;
  padding: 0 24px;
  text-align: center;
  border-radius: 16px;
  background: #F8E6E3;
  transition: all 0.3s ease;
  cursor: pointer;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}
.upload-icon-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.upload-box.dragging {
  border-color: #ff612c;
  background: #fff1ee;
  transform: scale(1.01);
}
.upload-box.success {
  border-color: #4CAF50;
  background: #e8f5e9;
}
.upload-box.success:hover {
  border-color: #4CAF50;
  background: #e8f5e9;
}
.upload-box:hover {
  border-color: #ff612c;
  background-color: #fff1ee;
}
.file-input { display: none; }
.drop-text {
  font-size: 16px;
  color: #888;
  margin: 0;
  max-width: 90%;
  word-break: break-word;
}
.file-info {
  margin: 5px 0 15px;
  font-size: 14px;
  color: #555;
}
.upload-button {
  padding: 12px 24px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.3s;
  margin-top: 15px;
}
.upload-button:hover {
  background: #45a049;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}
.message {
  margin-top: 20px;
  padding: 15px;
  border-radius: 6px;
  font-size: 14px;
  width: 100%;
  box-sizing: border-box;
}
.message.info { background-color: #e3f2fd; color: #0d47a1; }
.message.success { background-color: #e8f5e9; color: #2e7d32; }
.message.error { background-color: #ffebee; color: #c62828; }
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
  padding: 0 0 16px 0;
  margin-bottom: 30px;
  position: relative;
}
.config-inner-box {
  padding: 20px 30px 0 30px;
}
.upload-title {
  font-size: 20px;
  font-weight: bold;
  color: #153D77;
  margin-bottom: 20px;
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
.version-input-large, .version-input-beauty {
  display: none;
}
.version-control {
  width: 100%;
  max-width: 340px;
  font-size: 15px;
  height: 30px;
  font-weight: 500;
  border: 1.2px solid #e0e0e0;
  border-radius: 10px;
  padding: 10px 16px;
  box-sizing: border-box;
  margin-bottom: 0;
  background: #fff;
  box-shadow: 0 1px 6px rgba(21,61,119,0.05);
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.version-control:focus {
  border-color: #ff612c;
  box-shadow: 0 2px 8px rgba(255,97,44,0.08);
}
.version-control::placeholder {
  color: #bbb;
  font-size: 16px;
  font-weight: 400;
  letter-spacing: 0.5px;
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
.instructions-list li {
  margin-bottom: 3px;
}


</style>