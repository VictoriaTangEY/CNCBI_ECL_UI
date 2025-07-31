<template>
  <div style="display: flex; min-height: 100vh; margin-top: 95px;">
    <!-- 左侧导航栏 -->
    <aside style="width: 280px; background-color: #f5f5f5; padding: 30px 20px;">
      <h3 style="font-weight: bold; font-size: 22px; margin-bottom: 24px;">Reporting</h3>
    </aside>

    <!-- 主体内容 -->
    <main style="flex-grow: 1; padding: 40px;">
      <!-- 面包屑导航 -->
      <nav aria-label="breadcrumb" class="breadcrumb-nav">
        <ol class="breadcrumb-list">
          <li><svg style="width:16px; height:16px; fill:#666; vertical-align:middle;" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg> Home</li>
          <li>Reporting</li>
        </ol>
      </nav>

      <!-- 内容卡片 -->
      <div class="config-outer-box">
        <div class="config-inner-box">
          <h2 class="upload-title">Reporting</h2>
          <p style="color: #888; margin-bottom: 24px;">
            Download ECL reporting documents.
          </p>

          <!-- Loading Message -->
          <div v-if="loading" style="text-align: center; padding: 40px; color: #666;">
            <h3 style="font-size: 20px; margin-bottom: 10px;">Checking Report Availability...</h3>
            <div class="spinner"></div>
          </div>

          <!-- 下载卡片区域 -->
          <div v-if="!loading" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px;">
            <div v-for="(report, idx) in reports" :key="idx" style="border: 1px solid #e0e0e0; padding: 24px; border-radius: 10px; background: #fff; box-shadow: 0 2px 8px rgba(21,61,119,0.04);">
              <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">{{ report.title }}</h3>
              <p style="font-size: 15px; color: #888; margin-bottom: 16px;">{{ report.description }}</p>
              <button class="step-btn" style="background: #2563eb; color: #fff; font-size: 15px;" @click="downloadReport(report.title)">Download</button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- No Timestamp Popup -->
    <div v-if="showNoTimestampPopup" class="popup-overlay">
      <div class="popup-content">
        <h3 style="font-size: 20px; margin-bottom: 15px; color: #333;">No Reports Selected</h3>
        <p style="font-size: 16px; color: #666; margin-bottom: 25px; line-height: 1.5;">
          Please select a record from Run Management and click Confirm to view reports.
        </p>
        <div style="text-align: center;">
          <router-link to="/run-management" class="popup-btn">
            Go to Run Management
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()

// Get timestamp from route query parameters
const timestamp = ref(String(route.query.timestamp || ''))

// Dynamic report base path
const reportBasePath = ref('')

// Add state for report availability
const reportsAvailable = ref(false)
const loading = ref(true)

// Add state for popup visibility
const showNoTimestampPopup = ref(false)

// Compute the dynamic report base path
const computeReportBasePath = () => {
  if (timestamp.value) {
    // Construct the path: /u01/Apps/EY_working/99_data/03_output_folder/timestamp/{data_yymm}_{timestamp_date}/03_result
    // The {data_yymm}_{timestamp_date} folder is automatically created by ECL Engine
    reportBasePath.value = `/u01/Apps/EY_working/99_data/03_output_folder/${timestamp.value}`
  } else {
    // No timestamp available, cannot construct path
    reportBasePath.value = ''
    console.warn('No timestamp available for report path construction')
  }
  console.log('Using report base path:', reportBasePath.value)
}

// Add function to check report availability
async function checkReportAvailability() {
  if (!timestamp.value) {
    reportsAvailable.value = false
    loading.value = false
    showNoTimestampPopup.value = true
    return
  }

  try {
    const response = await axios.get(`https://10.25.108.72/api/check_report_availability/${timestamp.value}`)
    reportsAvailable.value = response.data.has_reports
  } catch (error) {
    console.error('Error checking report availability:', error)
    reportsAvailable.value = false
  } finally {
    loading.value = false
  }
}

const reports = [
  {
    title: 'ECL Monthly Report',
    description: 'Comprehensive monthly ECL calculations and analysis',
    format: 'XLSX'
  },
  {
    title: 'ECL Summary Report',
    description: 'Summary by stage, business unit and products',
    format: 'XLSX'
  },
  {
    title: 'BU Excel Report',
    description: 'Detailed monthly report by business units',
    format: 'XLSX'
  },
  {
    title: 'HKMA Reports',
    description: 'Annual, Interim, Quarter Return and Disclosure reports',
    format: 'XLSX'
  },
  {
    title: 'Audit Trail Report',
    description: 'Complete audit trail of ECL calculations',
    format: 'XLSX'
  },
  {
    title: 'GL Posting Report',
    description: 'General Ledger posting details',
    format: 'XLSX'
  }
]

async function downloadReport(reportTitle) {
  // Check if we have a timestamp
  if (!timestamp.value) {
    showNoTimestampPopup.value = true
    return
  }

  try {
    let endpoint = ''
    let filename = ''
    
    // Map report titles to backend endpoints
    switch (reportTitle) {
      case 'ECL Monthly Report':
        endpoint = '/download_ecl_monthly_report'
        filename = 'reporting_ecl_result_to_rmg.xlsx'
        break
      case 'ECL Summary Report':
        endpoint = '/download_ecl_summary_report'
        filename = 'reporting_ecl_result_summary.xlsx'
        break
      case 'BU Excel Report':
        endpoint = '/download_bu_excel_reports'
        filename = 'BU_Excel_Reports.zip'
        break
      case 'HKMA Reports':
      case 'Audit Trail Report':
      case 'GL Posting Report':
        // These reports are not implemented yet, do nothing
        console.log(`${reportTitle} download not implemented yet`)
        return
      default:
        console.error('Unknown report type:', reportTitle)
        return
    }
    
    // Make API call to backend with dynamic report base path
    const apiUrl = new URL(`https://10.25.108.72/api${endpoint}`)
    apiUrl.searchParams.append('report_base_path', reportBasePath.value)
    
    const response = await fetch(apiUrl.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    // Download the file
    const blob = await response.blob()
    const downloadUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(downloadUrl)
    
    console.log(`Successfully downloaded ${reportTitle} from ${reportBasePath.value}`)
  } catch (error) {
    console.error(`Error downloading ${reportTitle}:`, error)
    // You could add a user notification here if needed
    alert(`Failed to download ${reportTitle}.`)
  }
}

// Initialize when component mounts
onMounted(() => {
  computeReportBasePath()
  checkReportAvailability()
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

/* Popup Styles */
.popup-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.popup-content {
  background-color: #fff;
  padding: 30px;
  border-radius: 10px;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
  text-align: center;
  max-width: 400px;
  width: 90%;
}

.popup-btn {
  padding: 10px 25px;
  background: #FF612C;
  color: #fff;
  border-radius: 20px;
  border: none;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  transition: background-color 0.3s;
}

.popup-btn:hover {
  background: #e05222;
}
</style> 