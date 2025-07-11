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
            Download all reporting documents in one package.
          </p>

          <!-- 单一下载卡片区域 -->
          <div style="border: 1px solid #e0e0e0; padding: 24px; border-radius: 10px; background: #fff; box-shadow: 0 2px 8px rgba(21,61,119,0.04); max-width: 600px; margin: 0 auto;">
            <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">Download All Reports</h3>
            <p style="font-size: 15px; color: #888; margin-bottom: 16px;">The download folder will contain the following six reports:</p>
            <ul style="font-size: 15px; color: #333; margin-bottom: 18px; padding-left: 20px;">
              <li>ECL monthly report</li>
              <li>ECL summary by stage, BU and products</li>
              <li>ECL monthly excel report by BUs</li>
              <li>HKMA, Annual/ Interim / Quarter Return, Disclosure reports</li>
              <li>Audit trail report</li>
              <li>GL posting</li>
            </ul>
            <button class="step-btn" style="background: #2563eb; color: #fff; font-size: 15px;" @click="downloadDummyZip">Download All Reports</button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'

function downloadDummyZip() {
  // Create a dummy zip file for illustration
  const blob = new Blob(["This is a dummy report zip file for illustration purposes."], { type: 'application/zip' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'dummy_report.zip'
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
.step-btn:disabled {
  background: #eee;
  color: #bbb;
  cursor: not-allowed;
}
</style> 