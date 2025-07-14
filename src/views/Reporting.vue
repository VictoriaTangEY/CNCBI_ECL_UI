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

          <!-- 下载卡片区域 -->
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px;">
            <div v-for="(report, idx) in reports" :key="idx" style="border: 1px solid #e0e0e0; padding: 24px; border-radius: 10px; background: #fff; box-shadow: 0 2px 8px rgba(21,61,119,0.04);">
              <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">{{ report.title }}</h3>
              <p style="font-size: 15px; color: #888; margin-bottom: 16px;">{{ report.description }}</p>
              <button class="step-btn" style="background: #2563eb; color: #fff; font-size: 15px;" @click="downloadReport(report.title)">Download</button>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'

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

function downloadReport(reportTitle) {
  // Create a dummy file for illustration
  const blob = new Blob(["This is a dummy report file for illustration purposes."], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${reportTitle.toLowerCase().replace(/\s+/g, '_')}.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
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
</style> 